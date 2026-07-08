from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WrongWordBook(Base):
    """错题本：member 维度的全局错题集合，跨所有 Unit。

    答错自动 upsert：联合唯一保证同一 (member, word) 只有一条记录，
    wrong_count 字段在已有记录上 +1，added_at 保留首次加入时间。
    答对时刻意不动 —— 仅由用户在错题本页手动移除。
    """

    __tablename__ = "wrong_word_book"
    __table_args__ = (
        UniqueConstraint("member_id", "word_id", name="uk_member_word_wrongbook"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("word.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    member: Mapped["Member"] = relationship(  # noqa: F821
        back_populates="wrong_word_book"
    )
    word: Mapped["Word"] = relationship(  # noqa: F821
        back_populates="wrong_word_book"
    )

    def __repr__(self) -> str:
        return f"<WrongWordBook(member_id={self.member_id}, word_id={self.word_id})>"
