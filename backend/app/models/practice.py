from datetime import datetime

from sqlalchemy import BIGINT, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PracticeMode


class PracticeSession(TimestampMixin, Base):
    __tablename__ = "practice_session"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[PracticeMode] = mapped_column(Enum(PracticeMode), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    records: Mapped[list["PracticeRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="PracticeRecord.id"
    )


class PracticeRecord(TimestampMixin, Base):
    __tablename__ = "practice_record"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("practice_session.id", ondelete="CASCADE"), nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("word.id", ondelete="CASCADE"), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped["PracticeSession"] = relationship(back_populates="records")
    word: Mapped["Word"] = relationship()  # noqa: F821
