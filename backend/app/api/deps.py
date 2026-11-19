from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.meeting_participant import MeetingParticipant


def get_accessible_meeting(
    db: Session,
    meeting_id: int,
    user_id: int,
) -> Meeting:
    """
    Retrieve a meeting if the user is either the host/creator (owner)
    or has joined/attended as a participant.
    Raises 404 if not found, 403 if user has not attended and is not the host.
    """
    meeting = db.scalar(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.owner_id != user_id:
        is_participant = db.scalar(
            select(MeetingParticipant.id).where(
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.user_id == user_id,
            )
        )
        if is_participant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this meeting.",
            )

    return meeting
