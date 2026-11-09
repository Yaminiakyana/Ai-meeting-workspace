from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.action_item import ActionItem
from app.models.decision import Decision
from app.models.meeting import Meeting
from app.models.meeting_summary import MeetingSummary
from app.models.user import User
from app.schemas.meeting_summary import (
    ActionItemResponse,
    ActionItemUpdate,
    DecisionResponse,
    FollowupEmailRequest,
    FollowupEmailResponse,
    GenerateSummaryRequest,
    MeetingInsightsResponse,
    MeetingSummaryResponse,
)
from app.services.meeting_summary import (
    generate_followup_email,
    generate_meeting_insights,
)
from app.services.rag_service import index_meeting_chunks

router = APIRouter(
    tags=["Summaries & Insights"],
)


@router.post(
    "/meetings/{meeting_id}/summary/generate",
    response_model=MeetingInsightsResponse,
    status_code=status.HTTP_200_OK,
)
def generate_summary_endpoint(
    meeting_id: int,
    request: GenerateSummaryRequest = GenerateSummaryRequest(),
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

    try:
        insights = generate_meeting_insights(
            db=db,
            meeting_id=meeting_id,
            force_regenerate=request.force_regenerate,
        )

        # Also trigger indexing for RAG
        try:
            index_meeting_chunks(db, meeting_id)
        except Exception:
            pass

        return {
            "summary": insights["summary"],
            "action_items": insights["action_items"],
            "decisions": insights["decisions"],
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/meetings/{meeting_id}/insights",
    response_model=MeetingInsightsResponse,
)
def get_meeting_insights(
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

    summary = db.scalar(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
    )
    actions = db.scalars(
        select(ActionItem)
        .where(ActionItem.meeting_id == meeting_id)
        .order_by(ActionItem.created_at.asc())
    ).all()
    decisions = db.scalars(
        select(Decision)
        .where(Decision.meeting_id == meeting_id)
        .order_by(Decision.created_at.asc())
    ).all()

    return {
        "summary": summary,
        "action_items": actions,
        "decisions": decisions,
    }


@router.get(
    "/meetings/{meeting_id}/summary",
    response_model=MeetingSummaryResponse,
)
def get_summary(
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

    summary = db.scalar(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
    )
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary has not been generated for this meeting yet.",
        )

    return summary


@router.get(
    "/meetings/{meeting_id}/action-items",
    response_model=list[ActionItemResponse],
)
def get_action_items(
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

    return db.scalars(
        select(ActionItem)
        .where(ActionItem.meeting_id == meeting_id)
        .order_by(ActionItem.created_at.asc())
    ).all()


@router.patch(
    "/meetings/{meeting_id}/action-items/{action_item_id}",
    response_model=ActionItemResponse,
)
def update_action_item(
    meeting_id: int,
    action_item_id: int,
    request: ActionItemUpdate,
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

    item = db.scalar(
        select(ActionItem).where(
            ActionItem.id == action_item_id,
            ActionItem.meeting_id == meeting_id,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found",
        )

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/meetings/{meeting_id}/decisions",
    response_model=list[DecisionResponse],
)
def get_decisions(
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

    return db.scalars(
        select(Decision)
        .where(Decision.meeting_id == meeting_id)
        .order_by(Decision.created_at.asc())
    ).all()


@router.post(
    "/meetings/{meeting_id}/followup-email",
    response_model=FollowupEmailResponse,
)
def generate_email_endpoint(
    meeting_id: int,
    request: FollowupEmailRequest = FollowupEmailRequest(),
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

    summary = db.scalar(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
    )
    summary_text = summary.summary if summary else "No summary available."

    actions = db.scalars(
        select(ActionItem).where(ActionItem.meeting_id == meeting_id)
    ).all()
    decisions = db.scalars(
        select(Decision).where(Decision.meeting_id == meeting_id)
    ).all()

    email_data = generate_followup_email(
        meeting_title=meeting.title,
        summary_text=summary_text,
        action_items=list(actions),
        decisions=list(decisions),
        custom_instructions=request.custom_instructions,
    )

    return {
        "subject": email_data["subject"],
        "body": email_data["body"],
        "recipients": request.recipient_names or [],
    }


@router.get(
    "/action-items",
    response_model=list[ActionItemResponse],
)
def list_all_action_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Centralized repository of action items across all user meetings.
    """
    return db.scalars(
        select(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .where(Meeting.owner_id == current_user.id)
        .order_by(ActionItem.created_at.desc())
    ).all()
