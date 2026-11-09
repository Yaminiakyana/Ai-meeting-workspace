from pydantic import BaseModel, ConfigDict


class TranscriptResponse(BaseModel):
    id: int
    meeting_id: int
    recording_id: int

    speaker_label: str | None
    speaker_name: str | None

    text: str

    start_time: float
    end_time: float

    sequence_number: int
    language: str | None

    model_config = ConfigDict(
        from_attributes=True,
    )