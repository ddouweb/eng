from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Member(TimestampMixin, Base):
    __tablename__ = "member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 累计 XP：答对得 round(新词 5 / 复习 2 × 难度系数)（见 gamification.difficulty_mult），驱动段位。
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 现金激励虚拟钱包：周学习现金 + 里程碑奖金累加进此（CASH_ENABLED 开启时）。
    # 线下兑现，系统只记账；写入端 round(2) 防浮点漂移。详见 docs/Settlement.md。
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")

    mastery_records: Mapped[list["MasteryRecord"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821
    wrong_word_book: Mapped[list["WrongWordBook"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821
    streak: Mapped["MemberStreak"] = relationship(back_populates="member", uselist=False, cascade="all, delete-orphan")  # noqa: F821
    badges: Mapped[list["MemberBadge"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821
    cash_milestones: Mapped[list["CashMilestone"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Member(id={self.id}, name='{self.name}')>"
