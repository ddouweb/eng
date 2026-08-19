"""彩票抽卡业务层：懒同步补发次数 + 出票/结算 + 批次 + 总览。

懒触发单咽喉点：GET /lottery/state 打开时 _sync_grants 补发 8 类条件对应的
抽卡次数；绝不往 practice/stats/badge service 里加 lottery 钩子（与周结算/
里程碑懒发放同一哲学：用户不打开 = 没学 = 不发，零浪费）。

开奖在后端（app.lottery 先抽结果再反演票面），前端只渲染刮卡；
彩金入 Member.lottery_wealth，与现金激励 cash_balance 完全分开。
"""
import logging
import random
import uuid
from datetime import date, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.gamification import xp_to_level
from app.lottery import PRACTICE_PER_DRAW, build_grant_candidates, build_ticket, draw_outcome
from app.models.lottery import LotteryTicket
from app.models.member import Member
from app.repositories.lottery_repo import LotteryRepo
from app.repositories.stats_repo import StatsRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 500  # 开一批上限（500 张 × ~2KB JSON ≈ 1MB 入库，可接受）

# 任务清单元数据（/state 展示；done/note 由 facts 动态算）
TASK_META = [
    {"key": "daily", "title": "每日免费", "icon": "🎟️", "rule": "每天打开抽卡页 +1 次"},
    {"key": "practice", "title": "练习奖励", "icon": "📝", "rule": f"每累计 {PRACTICE_PER_DRAW} 场练习 +1 次"},
    {"key": "unit", "title": "单元通关", "icon": "📚", "rule": "每学完一个单元全部单词 +1 次"},
    {"key": "learn_task", "title": "今日学习", "icon": "📖", "rule": "完成今日学习 +1 次/天"},
    {"key": "review_task", "title": "今日复习", "icon": "🔁", "rule": "完成今日到期复习 +1 次/天"},
    {"key": "star", "title": "段位星辰", "icon": "⭐", "rule": "段位每加一星 +1 次"},
    {"key": "badge", "title": "徽章收藏", "icon": "🏅", "rule": "每获得一枚徽章 +1 次"},
    {"key": "weekstars", "title": "周结算星", "icon": "🌟", "rule": "每周结算每颗星 +1 次"},
]


class LotteryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LotteryRepo(session)
        self.stats_repo = StatsRepo(session)
        self.rng = random.Random()

    # ─────────────────────────────────────────────────────
    # 懒同步：8 类条件 → 抽卡次数补发（唯一写入点）
    # ─────────────────────────────────────────────────────

    async def _collect_facts(self, member_id: int, today: date) -> dict:
        """查齐 build_grant_candidates 所需的全部事实（纯查询，不做写入）。"""
        member = await self.session.get(Member, member_id)
        if member is None:
            raise AppException(404, "成员不存在")
        task_flags = await self.repo.get_today_task_flags(member_id, today)
        return {
            "member": member,
            "today": today,
            "ended_practice_count": await self.repo.count_ended_sessions(member_id),
            "units_status": await self.stats_repo.get_all_units_mastery_status(member_id),
            "learn_task_done": task_flags["learn"],
            "review_task_done": task_flags["review"],
            "stars": xp_to_level(member.total_xp)["stars"],
            "badge_keys": await self.repo.get_badge_keys(member_id),
            "week_stars": await self.repo.get_week_stars(member_id),
        }

    async def _sync_grants(self, member_id: int, facts: dict) -> int:
        """重建候选集、与已发 key 做差、逐条独立 savepoint 补发（幂等黄金模式，
        逐行照抄 stats_service._maybe_grant_milestones）。返回本次新发条数。

        XP 可被 rejudge 回退 → 段位星跌再涨不重发不回收（key 已在，snapshot 语义）。
        """
        candidates = build_grant_candidates(**{
            k: v for k, v in facts.items() if k != "member"
        })
        granted = await self.repo.get_granted_keys(member_id)
        granted_any = 0
        for cand in candidates:
            if cand.key in granted:
                continue
            try:
                async with self.session.begin_nested():
                    await self.repo.add_grant(member_id, cand)
                granted_any += 1
            except IntegrityError:
                # 极罕见：SELECT 与 INSERT 之间并发刚插了同一 key → savepoint 已回滚，自愈。
                logger.info("lottery grant race: member=%s key=%s", member_id, cand.key)
                continue
        if granted_any:
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                raise
        return granted_any

    async def _available(self, member_id: int) -> int:
        """可用次数 = Σgrant.draws − 票数（两台账对账，member 不存次数）。"""
        total_granted = await self.repo.sum_grant_draws(member_id)
        total_drawn = await self.repo.count_tickets(member_id)
        return total_granted - total_drawn

    # ─────────────────────────────────────────────────────
    # GET /lottery/state：懒同步 + 总览
    # ─────────────────────────────────────────────────────

    async def get_state(self, member_id: int) -> dict:
        today = date.today()
        facts = await self._collect_facts(member_id, today)
        new_grants = await self._sync_grants(member_id, facts)
        if new_grants:
            # sync 已 commit，facts 里的查询结果不受影响（都是只读快照）
            logger.info("lottery sync: member=%s granted %s draws", member_id, new_grants)

        member: Member = facts["member"]
        won = await self.repo.get_won_stats(member_id)
        active_batch = await self.repo.find_active_batch(member_id)
        pending_single = await self.repo.find_pending_single(member_id)
        return success(data={
            "draw_count": await self._available(member_id),
            "wealth": member.lottery_wealth or 0.0,
            "total_granted": await self.repo.sum_grant_draws(member_id),
            "total_drawn": await self.repo.count_tickets(member_id),
            "total_won": won["total_won"],
            "hit_count": won["hit_count"],
            "tasks": self._tasks_payload(facts),
            "active_batch": active_batch,
            "pending_single": pending_single,
            "recent_tickets": await self.repo.recent_tickets(member_id, limit=10),
        })

    @staticmethod
    def _tasks_payload(facts: dict) -> list[dict]:
        """8 项任务清单：done/note 由当下事实动态算（sync 后已发数 == 成就数）。"""
        completed_units = sum(
            1 for u in facts["units_status"]
            if u["total_words"] > 0 and u["mastered"] >= u["total_words"]
        )
        practice_batches = facts["ended_practice_count"] // PRACTICE_PER_DRAW
        week_star_total = sum(s for _wk, s in facts["week_stars"])
        notes = {
            "daily": "今天已领",  # daily 同步即领（打开 /state 的那一刻就发了）
            "practice": f"累计 {facts['ended_practice_count']} 场 · 已领 {practice_batches} 次",
            "unit": f"{completed_units} 个单元通关",
            "learn_task": "今日已完成" if facts["learn_task_done"] else "今日未完成",
            "review_task": "今日已完成" if facts["review_task_done"] else "今日未完成",
            "star": f"当前 {facts['stars']}⭐" if facts["stars"] else "大师段位后每 1000XP 一星",
            "badge": f"已获 {len(facts['badge_keys'])} 枚",
            "weekstars": f"历史 {week_star_total} 星" if week_star_total else "暂无结算周",
        }
        done = {
            "daily": True,
            "practice": practice_batches >= 1,
            "unit": completed_units >= 1,
            "learn_task": facts["learn_task_done"],
            "review_task": facts["review_task_done"],
            "star": facts["stars"] >= 1,
            "badge": len(facts["badge_keys"]) >= 1,
            "weekstars": week_star_total >= 1,
        }
        draws = {
            "daily": 1,
            "practice": practice_batches,
            "unit": completed_units,
            "learn_task": 1,
            "review_task": 1,
            "star": facts["stars"],
            "badge": len(facts["badge_keys"]),
            "weekstars": week_star_total,
        }
        return [
            {**meta, "done": done[meta["key"]], "draws": draws[meta["key"]], "note": notes[meta["key"]]}
            for meta in TASK_META
        ]

    # ─────────────────────────────────────────────────────
    # 出票 / 取票 / 结算
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _ticket_payload(row: LotteryTicket) -> dict:
        return {
            "id": row.id,
            "batch_id": row.batch_id,
            "prize": row.prize,
            "ticket": row.ticket,
            "created_at": row.created_at,
            "settled_at": row.settled_at,
        }

    async def draw(self, member_id: int) -> dict:
        """单张出票（消耗 1 次）。先抽结果再反演票面，全量票面（含 wins）直接下发。"""
        available = await self._available(member_id)
        if available < 1:
            raise AppException(400, "抽卡次数不足，完成学习任务赚取更多次数")
        prize = draw_outcome(self.rng)
        ticket = build_ticket(prize, self.rng)
        row = await self.repo.add_ticket(member_id, prize, ticket, batch_id=None)
        await self.session.commit()
        return success(data={**self._ticket_payload(row), "draw_count_left": available - 1})

    async def draw_batch(self, member_id: int, count: int) -> dict:
        """开一批（开批即定局）：一事务内 N 张共享 batch_id，只回 id 不回 prize（悬念）。"""
        if not 1 <= count <= MAX_BATCH_SIZE:
            raise AppException(400, f"一批数量须在 1~{MAX_BATCH_SIZE} 之间")
        available = await self._available(member_id)
        if count > available:
            raise AppException(400, f"抽卡次数不足（可用 {available} 次）")
        batch_id = uuid.uuid4().hex
        ticket_ids: list[int] = []
        for _ in range(count):
            prize = draw_outcome(self.rng)
            ticket = build_ticket(prize, self.rng)
            row = await self.repo.add_ticket(member_id, prize, ticket, batch_id=batch_id)
            ticket_ids.append(row.id)
        await self.session.commit()
        return success(data={
            "batch_id": batch_id,
            "count": count,
            "ticket_ids": ticket_ids,
            "draw_count_left": available - count,
        })

    async def get_ticket(self, member_id: int, ticket_id: int) -> dict:
        row = await self.repo.get_ticket(member_id, ticket_id)
        if row is None:
            raise AppException(404, "票据不存在")
        return success(data=self._ticket_payload(row))

    async def settle(self, member_id: int, ticket_id: int) -> dict:
        """结算入账（幂等）：条件 UPDATE settled_at 抢占 → 抢到才累加彩金，天然防双击/竞态。"""
        row = await self.repo.get_ticket(member_id, ticket_id)
        if row is None:
            raise AppException(404, "票据不存在")
        member = await self.session.get(Member, member_id)
        already_settled = row.settled_at is not None
        if not already_settled:
            # 单语句原子抢占：并发第二次 settle rowcount=0，不重复入账
            result = await self.session.execute(
                update(LotteryTicket)
                .where(LotteryTicket.id == ticket_id, LotteryTicket.settled_at.is_(None))
                .values(settled_at=datetime.now())
            )
            if result.rowcount == 1:
                member.lottery_wealth = round(
                    (member.lottery_wealth or 0.0) + row.prize, 2
                )
                row.settled_at = datetime.now()
                await self.session.commit()
            else:
                # 并发已被结算：rollback 会过期 ORM 对象，重新取一份再组装响应
                already_settled = True
                await self.session.rollback()
                row = await self.repo.get_ticket(member_id, ticket_id)
                member = await self.session.get(Member, member_id)
        data = {
            "id": row.id,
            "prize": row.prize,
            "wealth": member.lottery_wealth or 0.0,
            "already_settled": already_settled,
        }
        if row.batch_id:
            rows = await self.repo.get_batch_tickets(member_id, row.batch_id)
            summary = self.repo.batch_summary(rows, row.batch_id)
            data["batch"] = {
                k: summary[k] for k in
                ("batch_id", "size", "settled", "remaining", "total_prize", "hit_count", "best_prize")
            }
        return success(data=data)

    # ─────────────────────────────────────────────────────
    # 批次战报 / 历史
    # ─────────────────────────────────────────────────────

    async def batch_summary(self, member_id: int, batch_id: str) -> dict:
        rows = await self.repo.get_batch_tickets(member_id, batch_id)
        if not rows:
            raise AppException(404, "批次不存在")
        return success(data=self.repo.batch_summary(rows, batch_id))

    async def history(self, member_id: int, limit: int = 20) -> dict:
        won = await self.repo.get_won_stats(member_id)
        return success(data={
            "total": await self.repo.count_tickets(member_id),
            "total_won": won["total_won"],
            "hit_count": won["hit_count"],
            "items": await self.repo.recent_tickets(member_id, limit=min(limit, 100)),
        })
