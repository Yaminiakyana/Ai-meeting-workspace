from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.meeting import Meeting
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
    meetings = db.scalars(
        select(Meeting)
        .where(Meeting.owner_id == current_user.id)
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
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

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
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

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
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    saved_count = 0
    for idx, seg in enumerate(request.segments):
        text = seg.text.strip()
        if not text:
            continue
        transcript = Transcript(
            meeting_id=meeting.id,
            recording_id=None,
            speaker_label=seg.speaker_label or "Speaker",
            speaker_name=seg.speaker_name,
            text=text,
            start_time=seg.start_time,
            end_time=seg.end_time,
            sequence_number=seg.sequence_number or (idx + 1),
        )
        db.add(transcript)
        saved_count += 1

    db.commit()
    return {"saved_segments": saved_count}
