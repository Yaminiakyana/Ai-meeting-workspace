from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

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

    speaker_label: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    speaker_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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
        nullable=False,
        index=True,
    )

    language: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )