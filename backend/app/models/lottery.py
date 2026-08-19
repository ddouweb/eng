from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LotteryGrant(TimestampMixin, Base):
    """抽卡次数发放台账（一人一来源粒度一行，幂等）。

    8 类学习行为 + init 补偿各映射为一笔 grant（uq_member_lottery_grant 防重发）：
      - init:boot            系统上线补偿 5 次（draws=5）
      - daily:{date}         每日免费 1 次（打卡式：当天不开抽卡页则该天不发）
      - practice:{n}         终身累计每 5 场 ended 练习 = 1 次
      - unit:{unit_id}       每个全掌握单元 = 1 次
      - learn_task:{date}    完成今日学习任务 = 1 次/天
      - review_task:{date}   完成今日到期复习任务 = 1 次/天
      - star:{n}             段位每加一星 = 1 次
      - badge:{badge_key}    每枚徽章 = 1 次
      - weekstars:{week}:{i} 周结算每星 = 1 次
    snapshot 语义：XP 回退致星数跌再涨不重发不回收（同 cash_milestone）。
    懒触发：打开 /lottery/state 时 LotteryService._sync_grants 重建候选差集补发。

    可用次数 = SUM(lottery_grant.draws) - COUNT(lottery_ticket)（两台账对账，member 不存次数）。
    """

    __tablename__ = "lottery_grant"
    __table_args__ = (
        UniqueConstraint("member_id", "grant_key", name="uq_member_lottery_grant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # init/daily/practice/unit/learn_task/review_task/star/badge/weekstars
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # 全局粒度标识，如 "unit:5" / "weekstars:2026-W30:3"（绝不解析已存 key，只做差集）
    grant_key: Mapped[str] = mapped_column(String(80), nullable=False)
    draws: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # 人读备注，如 "2026-W30 结算 4 星"
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)

    member: Mapped["Member"] = relationship(back_populates="lottery_grants")  # noqa: F821

    def __repr__(self) -> str:
        return f"<LotteryGrant(member_id={self.member_id}, key={self.grant_key}, draws={self.draws})>"


class LotteryTicket(TimestampMixin, Base):
    """出票记录 = 抽卡次数消耗记录（每张票即消耗 1 次，settle 时才入彩金账）。

    开奖在后端（app/lottery.build_ticket 先抽结果再反演票面），前端只渲染刮卡；
    ticket 存全量票面 JSON（前后端契约：{prize, win_numbers, cells, wins}）。
    settled_at NULL = 未结算（已消耗次数但彩金未入账，刮开确认后 settle）。

    批次玩法：同批 N 张共享 batch_id（uuid4().hex），无独立批次表——战报/续挂
    走聚合查询；单张模式 batch_id 为 NULL。
    """

    __tablename__ = "lottery_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # 中奖金额（元）；独立列便于批次聚合战报，与 ticket JSON 内 prize 冗余一致
    prize: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ticket: Mapped[dict] = mapped_column(JSON, nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    member: Mapped["Member"] = relationship(back_populates="lottery_tickets")  # noqa: F821

    def __repr__(self) -> str:
        return f"<LotteryTicket(id={self.id}, prize={self.prize}, batch_id={self.batch_id})>"
