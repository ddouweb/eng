from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import MasteryLevel


class MasteryRecord(TimestampMixin, Base):
    __tablename__ = "mastery_record"

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

    member: Mapped["Member"] = relationship(back_populates="mastery_records")  # noqa: F821
    word: Mapped["Word"] = relationship(back_populates="mastery_records")  # noqa: F821

    def __repr__(self) -> str:
        return f"<MasteryRecord(word_id={self.word_id}, level={self.level})>"
