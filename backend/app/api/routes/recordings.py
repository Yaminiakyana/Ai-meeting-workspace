from pathlib import Path
import re
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_meeting
from app.core.security import decode_access_token, get_current_user
from app.db.database import get_db
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.user import User
from app.schemas.recording import RecordingResponse
from app.worker.tasks import process_recording, resolve_recording_path

router = APIRouter(
    prefix="/meetings",
    tags=["Recordings"],
)


BASE_STORAGE_DIR = (
    Path(__file__).resolve().parents[3]
    / "storage"
    / "recordings"
)


ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "audio/webm",
    "video/mp4",
    "video/webm",
    "video/quicktime",
}


@router.post(
    "/{meeting_id}/recordings",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_recording(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = get_accessible_meeting(db, meeting_id, current_user.id)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required",
        )

    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()

    if raw_content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported recording format ({file.content_type}). "
                "Supported formats include MP3, WAV, M4A, "
                "MP4, WebM, and MOV."
            ),
        )

    original_name = Path(file.filename).name
    extension = Path(original_name).suffix.lower()

    storage_filename = f"{uuid4().hex}{extension}"

    meeting_directory = (
        BASE_STORAGE_DIR / str(meeting_id)
    )

    meeting_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    storage_path = (
        meeting_directory / storage_filename
    )

    file_size = 0

    try:
        with storage_path.open("wb") as output_file:
            while chunk := await file.read(1024 * 1024):
                output_file.write(chunk)
                file_size += len(chunk)

    except Exception:
        if storage_path.exists():
            storage_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store recording",
        )

    finally:
        await file.close()

    storage_key = str(
        storage_path.relative_to(BASE_STORAGE_DIR)
    )

    recording = Recording(
        meeting_id=meeting_id,
        file_name=original_name,
        storage_key=storage_key,
        content_type=file.content_type,
        file_size=file_size,
        processing_status="uploaded",
    )

    db.add(recording)

    meeting.status = "recording_uploaded"

    db.commit()
    db.refresh(recording)

    try:
        process_recording.delay(recording.id)
    except Exception as exc:
        print(f"Celery dispatch failed ({exc}); running fallback in background...")
        if background_tasks:
            background_tasks.add_task(process_recording, recording.id)

    return recording


@router.get(
    "/{meeting_id}/recordings",
    response_model=list[RecordingResponse],
)
def list_recordings(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = get_accessible_meeting(db, meeting_id, current_user.id)

    recordings = db.scalars(
        select(Recording)
        .where(Recording.meeting_id == meeting_id)
        .order_by(Recording.created_at.desc())
    ).all()

    return recordings


@router.get(
    "/{meeting_id}/recordings/{recording_id}/stream",
)
def stream_recording(
    meeting_id: int,
    recording_id: int,
    request: Request,
    token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Stream recording audio with HTTP 206 Range support for synchronized playback.
    Supports either Authorization header or query param token.
    """
    # Authenticate via Header or Query param
    auth_header = request.headers.get("authorization")
    user_id = None

    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header.split(" ", 1)[1]
        try:
            user_id = decode_access_token(raw_token)
        except Exception:
            pass

    if user_id is None and token:
        try:
            user_id = decode_access_token(token)
        except Exception:
            pass

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to stream recording",
        )

    meeting = get_accessible_meeting(db, meeting_id, user_id)

    recording = db.scalar(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.meeting_id == meeting_id,
        )
    )
    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found",
        )

    try:
        audio_path = resolve_recording_path(recording.storage_key)
        file_size = audio_path.stat().st_size
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording audio file not found on disk",
        )

    import mimetypes
    guessed_type, _ = mimetypes.guess_type(str(audio_path))
    content_type = guessed_type or recording.content_type or "audio/mpeg"

    range_header = request.headers.get("range")
    if not range_header:
        def full_file_iterator():
            with open(audio_path, "rb") as f:
                while chunk := f.read(1024 * 64):
                    yield chunk

        return StreamingResponse(
            full_file_iterator(),
            status_code=200,
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Type": content_type,
            },
        )

    # Range request handling (HTTP 206 Partial Content)
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        raise HTTPException(status_code=416, detail="Invalid range request")

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    content_length = (end - start) + 1

    def range_file_iterator():
        with open(audio_path, "rb") as f:
            f.seek(start)
            bytes_remaining = content_length
            while bytes_remaining > 0:
                chunk_size = min(1024 * 64, bytes_remaining)
                data = f.read(chunk_size)
                if not data:
                    break
                bytes_remaining -= len(data)
                yield data

    return StreamingResponse(
        range_file_iterator(),
        status_code=206,
        media_type=content_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": content_type,
        },
    )


@router.delete(
    "/{meeting_id}/recordings/{recording_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_recording(
    meeting_id: int,
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.owner_id == current_user.id,
        )
    )
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or you are not the meeting host.",
        )

    recording = db.scalar(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.meeting_id == meeting_id,
        )
    )
    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found",
        )

    # Clean up storage file if it exists
    try:
        audio_path = resolve_recording_path(recording.storage_key)
        if audio_path.exists():
            audio_path.unlink()
    except Exception:
        pass

    db.delete(recording)
    db.commit()
    return None

