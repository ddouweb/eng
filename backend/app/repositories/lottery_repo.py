"""彩票抽卡数据访问层：条件事实查询 + grant/ticket 台账 CRUD + 批次聚合。"""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lottery import GrantCandidate
from app.models.enums import PlanStatus, TaskStatus
from app.models.lottery import LotteryGrant, LotteryTicket
from app.models.plan import DailyTask, LearningPlan
from app.models.practice import PracticeSession
from app.models.settlement import WeeklySettlement
from app.models.streak import MemberBadge


class LotteryRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ─────────────────────────────────────────────────────
    # 条件事实查询（供 build_grant_candidates，service 查好传入）
    # ─────────────────────────────────────────────────────

    async def count_ended_sessions(self, member_id: int) -> int:
        """终身累计已结束练习场数（ended_at 非空，口径同 StatsRepo.get_practice_summary）。"""
        stmt = (
            select(func.count())
            .select_from(PracticeSession)
            .where(
                PracticeSession.member_id == member_id,
                PracticeSession.ended_at.isnot(None),
            )
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def get_today_task_flags(self, member_id: int, today: date) -> dict:
        """今日学习/复习完成标记（各 EXISTS 一次，命中即 true）。

        按槽位判定而非任务类型：learn 型任务内嵌 review_count 槽（plan_service
        生成时 review = new×0.3），按类型会把 learn 任务里的复习部分漏掉。
        new_count/review_count=0 的空槽守卫必加——update_task 对 0 槽任务直接置
        completed，不守卫会空发（见 plan_service.update_task L92）。
        """
        base = (
            select(func.count())
            .select_from(DailyTask)
            .join(LearningPlan, LearningPlan.id == DailyTask.plan_id)
            .where(
                LearningPlan.member_id == member_id,
                LearningPlan.status == PlanStatus.active,
                DailyTask.task_date == today,
                DailyTask.status == TaskStatus.completed,
            )
        )
        learn = int((await self.session.execute(
            base.where(DailyTask.new_count > 0)
        )).scalar_one() or 0)
        review = int((await self.session.execute(
            base.where(DailyTask.review_count > 0)
        )).scalar_one() or 0)
        return {"learn": learn > 0, "review": review > 0}

    async def get_badge_keys(self, member_id: int) -> list[str]:
        """已获全部徽章 key（历史全量，供补发）。"""
        stmt = select(MemberBadge.badge_key).where(MemberBadge.member_id == member_id)
        return [r[0] for r in (await self.session.execute(stmt)).all()]

    async def get_week_stars(self, member_id: int) -> list[tuple[str, int]]:
        """已落表周结算的 (week_key, stars)，stars>0。

        仅基于已落表行：懒结算只回算最近 SETTLE_BACKFILL_WEEKS 周，超窗历史周
        不计入（同 attendance_streak 的已知盲区口径）。
        """
        stmt = (
            select(WeeklySettlement.week_key, WeeklySettlement.stars)
            .where(WeeklySettlement.member_id == member_id, WeeklySettlement.stars > 0)
            .order_by(WeeklySettlement.week_start)
        )
        return [(r[0], int(r[1])) for r in (await self.session.execute(stmt)).all()]

    # ─────────────────────────────────────────────────────
    # grant 台账（次数发放）
    # ─────────────────────────────────────────────────────

    async def get_granted_keys(self, member_id: int) -> set[str]:
        """已发 grant_key 全集（一次查询，供差集预过滤）。"""
        stmt = select(LotteryGrant.grant_key).where(LotteryGrant.member_id == member_id)
        return {r[0] for r in (await self.session.execute(stmt)).all()}

    async def sum_grant_draws(self, member_id: int) -> int:
        stmt = (
            select(func.coalesce(func.sum(LotteryGrant.draws), 0))
            .where(LotteryGrant.member_id == member_id)
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def add_grant(self, member_id: int, cand: GrantCandidate) -> None:
        """插入一笔发放（调用方包 savepoint，IntegrityError 由调用方自愈）。"""
        self.session.add(LotteryGrant(
            member_id=member_id,
            source=cand.source,
            grant_key=cand.key,
            draws=cand.draws,
            remark=cand.remark,
        ))

    async def list_grants(self, member_id: int) -> list[dict]:
        """发放流水（前端任务清单对账用，按时间正序）。"""
        stmt = (
            select(LotteryGrant)
            .where(LotteryGrant.member_id == member_id)
            .order_by(LotteryGrant.id)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [
            {
                "source": g.source,
                "grant_key": g.grant_key,
                "draws": g.draws,
                "remark": g.remark,
                "created_at": g.created_at,
            }
            for g in rows
        ]

    # ─────────────────────────────────────────────────────
    # ticket 台账（出票 = 消耗）
    # ─────────────────────────────────────────────────────

    async def count_tickets(self, member_id: int) -> int:
        stmt = select(func.count()).select_from(LotteryTicket).where(
            LotteryTicket.member_id == member_id
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def get_won_stats(self, member_id: int) -> dict:
        """已结算票的中奖合计与中奖张数（/state 战绩展示用）。"""
        stmt = select(
            func.coalesce(func.sum(LotteryTicket.prize), 0),
            func.count(),
        ).where(
            LotteryTicket.member_id == member_id,
            LotteryTicket.settled_at.isnot(None),
            LotteryTicket.prize > 0,
        )
        row = (await self.session.execute(stmt)).one()
        return {"total_won": int(row[0] or 0), "hit_count": int(row[1] or 0)}

    async def add_ticket(
        self, member_id: int, prize: int, ticket: dict, batch_id: str | None
    ) -> LotteryTicket:
        row = LotteryTicket(
            member_id=member_id, prize=prize, ticket=ticket, batch_id=batch_id
        )
        self.session.add(row)
        await self.session.flush()  # 拿自增 id
        return row

    async def get_ticket(self, member_id: int, ticket_id: int) -> LotteryTicket | None:
        stmt = select(LotteryTicket).where(
            LotteryTicket.id == ticket_id, LotteryTicket.member_id == member_id
        )
        return (await self.session.scalars(stmt)).first()

    async def recent_tickets(self, member_id: int, limit: int = 10) -> list[dict]:
        stmt = (
            select(LotteryTicket)
            .where(LotteryTicket.member_id == member_id)
            .order_by(LotteryTicket.id.desc())
            .limit(limit)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self.ticket_brief(r) for r in rows]

    @staticmethod
    def ticket_brief(r: LotteryTicket) -> dict:
        return {
            "id": r.id,
            "prize": r.prize,
            "batch_id": r.batch_id,
            "created_at": r.created_at,
            "settled_at": r.settled_at,
        }

    # ─────────────────────────────────────────────────────
    # 批次聚合（batch_id 维度，无独立批次表）
    # ─────────────────────────────────────────────────────

    async def get_batch_tickets(self, member_id: int, batch_id: str) -> list[LotteryTicket]:
        stmt = (
            select(LotteryTicket)
            .where(
                LotteryTicket.member_id == member_id, LotteryTicket.batch_id == batch_id
            )
            .order_by(LotteryTicket.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def find_active_batch(self, member_id: int) -> dict | None:
        """最新一个仍有未结算票的批次（刷新续挂用）；无则 None。"""
        stmt = (
            select(LotteryTicket.batch_id)
            .where(
                LotteryTicket.member_id == member_id,
                LotteryTicket.batch_id.isnot(None),
                LotteryTicket.settled_at.is_(None),
            )
            .order_by(LotteryTicket.id.desc())
            .limit(1)
        )
        batch_id = (await self.session.execute(stmt)).scalar_one_or_none()
        if batch_id is None:
            return None
        rows = await self.get_batch_tickets(member_id, batch_id)
        return self.batch_summary(rows, batch_id)

    async def find_pending_single(self, member_id: int) -> dict | None:
        """最新一张未结算的单张票（batch_id 为空，续刮用）；无则 None。"""
        stmt = (
            select(LotteryTicket)
            .where(
                LotteryTicket.member_id == member_id,
                LotteryTicket.batch_id.is_(None),
                LotteryTicket.settled_at.is_(None),
            )
            .order_by(LotteryTicket.id.desc())
            .limit(1)
        )
        row = (await self.session.scalars(stmt)).first()
        return self.ticket_brief(row) if row else None

    @staticmethod
    def batch_summary(rows: list[LotteryTicket], batch_id: str) -> dict:
        """批次聚合：size/settled/remaining/total_prize/hit_count/best_prize + 票列表。"""
        settled_rows = [r for r in rows if r.settled_at is not None]
        prizes = [r.prize for r in settled_rows if r.prize > 0]
        return {
            "batch_id": batch_id,
            "size": len(rows),
            "settled": len(settled_rows),
            "remaining": len(rows) - len(settled_rows),
            "total_prize": sum(prizes),
            "hit_count": len(prizes),
            "best_prize": max(prizes) if prizes else 0,
            "tickets": [
                {
                    "id": r.id,
                    "index": i + 1,
                    "prize": r.prize,
                    "settled": r.settled_at is not None,
                    "settled_at": r.settled_at,
                    "created_at": r.created_at,
                }
                for i, r in enumerate(rows)
            ],
        }
