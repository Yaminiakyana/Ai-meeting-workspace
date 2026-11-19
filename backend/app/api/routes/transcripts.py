from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_meeting
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.transcript import TranscriptResponse


router = APIRouter(
    prefix="/meetings",
    tags=["Transcripts"],
)


@router.get(
    "/{meeting_id}/transcript",
    response_model=list[TranscriptResponse],
)
def get_transcript(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = get_accessible_meeting(db, meeting_id, current_user.id)

    all_transcripts = list(
        db.scalars(
            select(Transcript)
            .where(
                Transcript.meeting_id == meeting_id
            )
            .order_by(
                Transcript.start_time.asc(),
                Transcript.sequence_number.asc(),
                Transcript.id.asc(),
            )
        ).all()
    )

    # If both live transcripts (recording_id is None) and Whisper transcripts (recording_id is not None) exist,
    # prioritize live transcripts that have real participant speaker names.
    live_ones = [t for t in all_transcripts if t.recording_id is None]
    rec_ones = [t for t in all_transcripts if t.recording_id is not None]

    selected = live_ones if live_ones else rec_ones
    sorted_res = sorted(selected, key=lambda t: (t.start_time or 0.0, t.sequence_number or 0, t.id or 0))

    # Guard: Ensure transcripts always start cleanly from 0.0s (e.g. if recorded with an offset or timezone skew)
    if sorted_res and (sorted_res[0].start_time or 0.0) > 10.0:
        offset = float(sorted_res[0].start_time or 0.0)
        for t in sorted_res:
            raw_start = float(t.start_time or 0.0)
            raw_end = float(t.end_time or (raw_start + 2.0))
            t.start_time = max(0.0, round(raw_start - offset, 2))
            t.end_time = max(t.start_time + 1.0, round(raw_end - offset, 2))

    return sorted_res