from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_meeting
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.meeting import Meeting
from app.models.meeting_participant import MeetingParticipant
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    MeetingUpdate,
)
from app.services.meeting_summary import extract_live_insights


class LiveInsightsRequest(BaseModel):
    text: str
    meeting_title: str | None = None


class LiveTranscriptItem(BaseModel):
    text: str
    speaker_label: str | None = "Speaker"
    speaker_name: str | None = None
    start_time: float
    end_time: float
    sequence_number: int | None = 0


class LiveTranscriptRequest(BaseModel):
    segments: list[LiveTranscriptItem]


router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
)


@router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_meeting(
    request: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = Meeting(
        owner_id=current_user.id,
        title=request.title,
        description=request.description,
        meeting_date=request.meeting_date,
    )

    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return meeting

@router.get(
    "",
    response_model=list[MeetingResponse],
)
def list_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all accessible meetings for current_user:
    - Meetings launched/created by current_user (owner)
    - Meetings current_user joined as an attendee/participant
    """
    user_participated_meeting_ids = select(MeetingParticipant.meeting_id).where(
        MeetingParticipant.user_id == current_user.id
    )

    meetings = db.scalars(
        select(Meeting)
        .where(
            or_(
                Meeting.owner_id == current_user.id,
                Meeting.id.in_(user_participated_meeting_ids),
            )
        )
        .order_by(Meeting.created_at.desc())
    ).all()

    return meetings

@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
)
def get_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_accessible_meeting(db, meeting_id, current_user.id)

@router.post(
    "/{meeting_id}/join",
    response_model=MeetingResponse,
)
def join_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register the current user as an attendee/participant of the meeting and return the meeting.
    """
    meeting = db.scalar(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # If current user is not the owner, ensure they are registered in meeting_participants
    if meeting.owner_id != current_user.id:
        participant = db.scalar(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.user_id == current_user.id,
            )
        )
        display_name = current_user.full_name or current_user.email.split("@")[0]
        if participant is None:
            participant = MeetingParticipant(
                meeting_id=meeting.id,
                user_id=current_user.id,
                display_name=display_name,
                email=current_user.email,
                joined_at=datetime.utcnow(),
            )
            db.add(participant)
            db.commit()
        else:
            participant.joined_at = datetime.utcnow()
            db.commit()

    return meeting

@router.patch(
    "/{meeting_id}",
    response_model=MeetingResponse,
)
def update_meeting(
    meeting_id: int,
    request: MeetingUpdate,
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
            detail="Meeting not found",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(meeting, field, value)

    db.commit()
    db.refresh(meeting)

    return meeting

@router.delete(
    "/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_meeting(
    meeting_id: int,
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
            detail="Meeting not found",
        )

    db.delete(meeting)
    db.commit()

    return None


@router.post(
    "/{meeting_id}/live-insights",
    response_model=dict[str, Any],
)
def generate_live_insights(
    meeting_id: int,
    request: LiveInsightsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Extract real-time action items and decisions from live meeting speech.
    """
    meeting = get_accessible_meeting(db, meeting_id, current_user.id)

    title = request.meeting_title or meeting.title
    insights = extract_live_insights(
        text=request.text,
        meeting_title=title,
    )
    return insights


@router.post(
    "/{meeting_id}/live-transcript",
    status_code=status.HTTP_201_CREATED,
)
def save_live_transcript_batch(
    meeting_id: int,
    request: LiveTranscriptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save streaming/live transcript segments generated during a live meeting session.
    """
    meeting = get_accessible_meeting(db, meeting_id, current_user.id)

    # Sort incoming segments strictly chronologically by start_time
    sorted_segments = sorted(request.segments, key=lambda s: float(s.start_time or 0.0))

    # Remove any unattached prior live transcripts for this meeting to avoid duplicates
    db.query(Transcript).filter(
        Transcript.meeting_id == meeting.id,
        Transcript.recording_id.is_(None),
    ).delete(synchronize_session=False)

    saved_count = 0
    for idx, seg in enumerate(sorted_segments):
        text = seg.text.strip()
        if not text:
            continue
        transcript = Transcript(
            meeting_id=meeting.id,
            recording_id=None,
            speaker_label=seg.speaker_label or "Speaker",
            speaker_name=seg.speaker_name or seg.speaker_label,
            text=text,
            start_time=float(seg.start_time or 0.0),
            end_time=float(seg.end_time or (seg.start_time or 0.0) + 2.0),
            sequence_number=idx + 1,
        )
        db.add(transcript)
        saved_count += 1

    db.commit()
    return {"saved_segments": saved_count}
