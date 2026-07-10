from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PracticeMode


class PracticeSession(TimestampMixin, Base):
    __tablename__ = "practice_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[PracticeMode] = mapped_column(Enum(PracticeMode), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 本次会话的题集（word_id 列表）：用于提交时校验 word_id 归属本会话、防刷分。
    # 旧数据为 NULL，提交时跳过校验（向后兼容）。
    question_word_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    records: Mapped[list["PracticeRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="PracticeRecord.id"
    )


class PracticeRecord(TimestampMixin, Base):
    __tablename__ = "practice_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("practice_session.id", ondelete="CASCADE"), nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("word.id", ondelete="CASCADE"), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped["PracticeSession"] = relationship(back_populates="records")
    word: Mapped["Word"] = relationship()  # noqa: F821
