from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecordingResponse(BaseModel):
    id: int
    meeting_id: int
    file_name: str
    storage_key: str
    content_type: str | None
    file_size: int | None
    duration_seconds: float | None
    processing_status: str
    processing_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)