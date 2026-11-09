from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MeetingCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    meeting_date: datetime | None = None


class MeetingUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    meeting_date: datetime | None = None

    status: str | None = Field(
        default=None,
        max_length=50,
    )


class MeetingResponse(BaseModel):
    id: int
    owner_id: int
    title: str
    description: str | None
    meeting_date: datetime | None
    status: str

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )