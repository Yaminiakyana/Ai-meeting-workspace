from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

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

    transcripts = db.scalars(
        select(Transcript)
        .where(
            Transcript.meeting_id == meeting_id
        )
        .order_by(
            Transcript.sequence_number.asc()
        )
    ).all()

    return transcripts