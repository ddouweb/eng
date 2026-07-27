from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Member(TimestampMixin, Base):
    __tablename__ = "member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 累计 XP：答对得 round(新词 5 / 复习 2 × 难度系数)（见 gamification.difficulty_mult），驱动段位。
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    mastery_records: Mapped[list["MasteryRecord"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821
    wrong_word_book: Mapped[list["WrongWordBook"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821
    streak: Mapped["MemberStreak"] = relationship(back_populates="member", uselist=False, cascade="all, delete-orphan")  # noqa: F821
    badges: Mapped[list["MemberBadge"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Member(id={self.id}, name='{self.name}')>"
