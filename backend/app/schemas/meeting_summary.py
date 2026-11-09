from datetime import datetime
from pydantic import BaseModel, ConfigDict


# ============================================================
# Meeting Summary
# ============================================================

class MeetingSummaryResponse(BaseModel):
    id: int
    meeting_id: int
    summary: str
    model_name: str
    generated_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateSummaryRequest(BaseModel):
    force_regenerate: bool = False


# ============================================================
# Action Items
# ============================================================

class ActionItemBase(BaseModel):
    description: str
    due_date: datetime | None = None
    priority: str = "medium"
    status: str = "pending"
    source_start_time: float | None = None
    source_end_time: float | None = None


class ActionItemCreate(ActionItemBase):
    meeting_id: int
    owner_id: int | None = None
    assignee_name: str | None = None


class ActionItemUpdate(BaseModel):
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    owner_id: int | None = None


class ActionItemResponse(ActionItemBase):
    id: int
    meeting_id: int
    owner_id: int | None
    assignee_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# Decisions
# ============================================================

class DecisionBase(BaseModel):
    description: str
    decision_type: str | None = "strategic"
    source_start_time: float | None = None
    source_end_time: float | None = None


class DecisionCreate(DecisionBase):
    meeting_id: int


class DecisionResponse(DecisionBase):
    id: int
    meeting_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# Aggregated Insights
# ============================================================

class MeetingInsightsResponse(BaseModel):
    summary: MeetingSummaryResponse | None = None
    action_items: list[ActionItemResponse] = []
    decisions: list[DecisionResponse] = []


# ============================================================
# Follow-up Email
# ============================================================

class FollowupEmailRequest(BaseModel):
    custom_instructions: str | None = None
    recipient_names: list[str] | None = None


class FollowupEmailResponse(BaseModel):
    subject: str
    body: str
    recipients: list[str] = []
