from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CashMilestone(TimestampMixin, Base):
    """现金里程碑发放台账（一人一里程碑一行，幂等）。

    达标即发、终身一次（uq_member_milestone_key 防重发）；发放时刻的证据落 snapshot，
    之后词/周回退不回扣（snapshot 语义，同 bonus_xp）。三类里程碑：
      - unit_complete:{unit_id}      该 unit 所有词 level∈{familiar,permanent}
      - cumulative_words:{threshold} 全局累计掌握词数 ≥ 阈值
      - attendance_streak:{threshold} 连续全勤周数 ≥ 阈值（基于已落表 weekly_settlement 行）

    懒触发：打开 /weekly-settlement 时，StatsService._maybe_grant_milestones 检测并发放。
    """

    __tablename__ = "cash_milestone"
    __table_args__ = (
        UniqueConstraint("member_id", "milestone_key", name="uq_member_milestone_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_key: Mapped[str] = mapped_column(String(80), nullable=False)
    milestone_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # unit_complete 存 unit_id；cumulative_words/attendance_streak 存阈值。
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    # 发放时刻证据（审计）：如 {"unit_id":5,"total_words":120,"mastered":120}。
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="cash_milestones")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<CashMilestone(member_id={self.member_id}, key={self.milestone_key}, "
            f"amount={self.amount})>"
        )
