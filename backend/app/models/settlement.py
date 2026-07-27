from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WeeklySettlement(TimestampMixin, Base):
    """每周结算快照（一人一周一行，幂等）。

    懒触发：用户打开 profile 时，若「上一完整 ISO 周」未结算则当场聚合、写快照、
    发有封顶的坚持奖励（bonus XP / freeze / 周徽章）。bonus 只来自坚持分+计划分，
    与逐题 XP（已含难度系数）刻意不重叠——防通胀的根本。snapshot 语义：不与并发
    rejudge 强一致（见 StatsService._maybe_settle_week docstring）。
    """

    __tablename__ = "weekly_settlement"
    __table_args__ = (
        UniqueConstraint("member_id", "week_key", name="uq_member_week_settlement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week_key: Mapped[str] = mapped_column(String(10), nullable=False)  # "2026-W30" ISO 周
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    # 四维原始分（落库以便日后调参无需重算）
    login_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    difficulty_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    new_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    plan_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 头部数字（前端直接展示）
    real_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    new_words_learned: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    plan_completion: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    # 奖励发放审计
    bonus_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    freeze_granted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    badges_granted: Mapped[list | None] = mapped_column(JSON, nullable=True)
    plan_health: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<WeeklySettlement(member_id={self.member_id}, week_key={self.week_key}, "
            f"total={self.total_score})>"
        )
