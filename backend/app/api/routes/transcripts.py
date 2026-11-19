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