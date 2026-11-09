from pydantic import BaseModel, ConfigDict


class TranscriptResponse(BaseModel):
    id: int
    meeting_id: int
    recording_id: int | None = None

    speaker_label: str | None = None
    speaker_name: str | None = None

    text: str

    start_time: float
    end_time: float

    sequence_number: int
    language: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )