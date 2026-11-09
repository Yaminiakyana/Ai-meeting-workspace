from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    recording_id: Mapped[int | None] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    speaker_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    start_time: Mapped[float] = mapped_column(
        nullable=False,
        index=True,
    )

    end_time: Mapped[float] = mapped_column(
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Serialized JSON array of float embeddings
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
