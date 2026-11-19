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

    if live_ones and rec_ones:
        return sorted(live_ones, key=lambda t: (t.start_time or 0.0, t.sequence_number or 0, t.id or 0))
    elif live_ones:
        return sorted(live_ones, key=lambda t: (t.start_time or 0.0, t.sequence_number or 0, t.id or 0))
    else:
        return sorted(rec_ones, key=lambda t: (t.start_time or 0.0, t.sequence_number or 0, t.id or 0))