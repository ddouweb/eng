from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import MasteryLevel


class MasteryRecord(TimestampMixin, Base):
    __tablename__ = "mastery_record"
    # 同一 (member, word) 只允许一条掌握记录：并发 get_or_create 不会产生重复行，
    # 也保证下游 stats 计数 / mastery_map 取值正确。
    __table_args__ = (
        UniqueConstraint("member_id", "word_id", name="uk_member_word_mastery"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("word.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[MasteryLevel] = mapped_column(
        Enum(MasteryLevel), nullable=False, default=MasteryLevel.unlearned
    )
    consecutive_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # SM-2 间隔重复字段（由 srs.py update_srs 维护）。default + server_default 同时覆盖
    # 两个创建入口：_update_mastery(submit) 与 word_service.get_mastery(GET 懒建)。
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5, server_default="2.5")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    member: Mapped["Member"] = relationship(back_populates="mastery_records")  # noqa: F821
    word: Mapped["Word"] = relationship(back_populates="mastery_records")  # noqa: F821

    def __repr__(self) -> str:
        return f"<MasteryRecord(word_id={self.word_id}, level={self.level})>"
