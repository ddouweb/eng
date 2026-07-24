from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MemberStreak(TimestampMixin, Base):
    """成员的连续学习状态（坚持机制：streak + freeze）。

    streak 不再每次从 PracticeSession 聚合计算，而是持久化维护——这样才能支持
    freeze（用配额把断签的那天「补」上）、最长记录、月度 freeze 发放等「有状态」能力。
    每次 submit_answer 且为「今天首次该成员练习」时推进一次（见 PracticeService）。
    """

    __tablename__ = "member_streak"

    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), primary_key=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 可用冻结数：新成员 2 个；每月补充 1 个（上限 5）。断签时优先消耗它把缺失天补上。
    freeze_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 上次发放月度 freeze 的月份 "YYYY-MM"：用于每月首次访问时补 1 个。
    freeze_grant_month: Mapped[str | None] = mapped_column(String(7), nullable=True)

    member: Mapped["Member"] = relationship(back_populates="streak")  # noqa: F821


class MemberBadge(Base):
    """成员已获得的徽章发放记录（每个 member × badge_key 唯一，幂等防重复发放）。"""

    __tablename__ = "member_badges"
    __table_args__ = (
        UniqueConstraint("member_id", "badge_key", name="uq_member_badge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    badge_key: Mapped[str] = mapped_column(String(50), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="badges")  # noqa: F821
