import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cash import build_milestone_candidates
from app.gamification import MAX_FREEZE_BALANCE, xp_to_level
from app.models.cash_milestone import CashMilestone
from app.models.member import Member
from app.models.settlement import WeeklySettlement
from app.models.streak import MemberBadge, MemberStreak
from app.repositories.stats_repo import StatsRepo
from app.schemas.common import success
from app.settlement_score import (
    compute_bonus,
    compute_stars,
    compute_weekly_cash,
    expected_learn_days,
    plan_health,
    score_difficulty,
    score_login,
    score_new,
    score_plan,
)

logger = logging.getLogger(__name__)

# 回算最多 N 个历史周（防首启爆量；用户不打开=没学=不结算，零浪费）。
SETTLE_BACKFILL_WEEKS = 4


class StatsService:
    def __init__(self, session: AsyncSession):
        self.repo = StatsRepo(session)
        self.session = session

    async def get_overview(self, member_id: int) -> dict:
        dist = await self.repo.get_mastery_distribution(member_id)
        total_words = await self.repo.get_total_word_count()
        practice = await self.repo.get_practice_summary(member_id)
        streak = await self.repo.get_streak(member_id)

        mastered = min(dist["familiar"] + dist["permanent"], total_words)
        total_answered = practice["total_questions"]
        total_correct = practice["total_correct"]
        accuracy = round(total_correct / total_answered * 100, 1) if total_answered > 0 else 0.0

        return success(data={
            "total_words": total_words,
            "mastery_distribution": dist,
            "mastered_count": mastered,
            "mastery_rate": round(mastered / total_words * 100, 1) if total_words > 0 else 0.0,
            "practice_session_count": practice["session_count"],
            "total_questions": total_answered,
            "total_correct": total_correct,
            "accuracy": accuracy,
            "streak_days": streak,
        })

    async def get_unit_stats(self, member_id: int, unit_id: int) -> dict:
        dist = await self.repo.get_mastery_by_unit(member_id, unit_id)
        total = await self.repo.get_total_word_count(unit_id)
        mastered = dist["familiar"] + dist["permanent"]
        return success(data={
            "unit_id": unit_id,
            "total_words": total,
            "mastery_distribution": dist,
            "mastered_count": mastered,
            "mastery_rate": round(mastered / total * 100, 1) if total > 0 else 0.0,
        })

    async def get_trend(self, member_id: int, days: int = 30) -> dict:
        daily = await self.repo.get_recent_practice_daily(member_id, days)
        return success(data={
            "days": days,
            "daily": daily,
        })

    async def get_profile(self, member_id: int) -> dict:
        """首页坚持机制卡片：streak / freeze / XP 段位 / 徽章。

        入口先懒结算上周（若到期），故 bonus 入账后 XP/段位/徽章即时反映。
        """
        await self._maybe_settle_week(member_id)
        state = await self.session.get(MemberStreak, member_id)
        member = await self.session.get(Member, member_id)
        xp = member.total_xp if member else 0
        stmt = select(MemberBadge.badge_key).where(MemberBadge.member_id == member_id)
        badges = [r[0] for r in (await self.session.execute(stmt)).all()]
        return success(data={
            "current_streak": state.current_streak if state else 0,
            "longest_streak": state.longest_streak if state else 0,
            "freeze_balance": state.freeze_balance if state else 2,
            "last_active_date": (
                state.last_active_date.isoformat() if state and state.last_active_date else None
            ),
            "total_xp": xp,
            "level": xp_to_level(xp),
            "badges": badges,
        })

    async def get_weekly_settlement(self, member_id: int) -> dict:
        """每周结算：周分四维 + 星 + bonus + cash + plan_health + 历史快照（近 20 周）。

        打开即懒结算上周，随后（CASH_ENABLED 时）懒发放里程碑奖金。snapshot 语义：不保证与
        并发 rejudge 强一致；首启回算最多 4 周可能延迟 1~2 秒。响应另含 cash_balance /
        cash_enabled / milestones 供前端现金卡展示。
        """
        await self._maybe_settle_week(member_id)
        if settings.CASH_ENABLED:
            await self._maybe_grant_milestones(member_id)
        rows = (
            await self.session.execute(
                select(WeeklySettlement)
                .where(WeeklySettlement.member_id == member_id)
                .order_by(WeeklySettlement.week_key.desc())
                .limit(20)
            )
        ).scalars().all()
        history = [self._settlement_to_dict(r) for r in rows]

        member = await self.session.get(Member, member_id)
        milestones = (
            await self.session.execute(
                select(CashMilestone)
                .where(CashMilestone.member_id == member_id)
                .order_by(CashMilestone.granted_at.desc())
                .limit(50)
            )
        ).scalars().all()
        return success(data={
            "history": history,
            "latest": history[0] if history else None,
            "cash_balance": round((member.cash_balance if member else 0.0) or 0.0, 2),
            "cash_enabled": bool(settings.CASH_ENABLED),
            "milestones": [self._milestone_to_dict(m) for m in milestones],
        })

    @staticmethod
    def _milestone_to_dict(m: CashMilestone) -> dict:
        return {
            "milestone_key": m.milestone_key,
            "milestone_type": m.milestone_type,
            "threshold": m.threshold,
            "amount": round(m.amount or 0.0, 2),
            "snapshot": m.snapshot,
            "granted_at": m.granted_at.isoformat() if m.granted_at else None,
        }

    # ─────────────────────────────────────────────────────
    # 每周懒结算
    # ─────────────────────────────────────────────────────
    async def _maybe_settle_week(self, member_id: int) -> None:
        """懒结算：把所有「已完整结束且未结算」的近 SETTLE_BACKFILL_WEEKS 个 ISO 周结算落表。

        - 周以 ISO 周号（%G-%V，跨年正确）标识；ws/we 用 Gregorian 周一~周日。
        - 回算按 week_key 升序处理：freeze 对顺序敏感（较早的全勤周先拿 freeze），
          bonus/徽章幂等不敏感。
        - 幂等：每周先 SELECT，未命中才聚合；INSERT 用 savepoint 包裹（含 bonus/freeze/徽章
          同事务），命中 uq_member_week_settlement 则 savepoint 回滚全部、安全跳过。
        """
        today = date.today()
        this_monday = today - timedelta(days=today.weekday())  # 本周周一（未结束，不结算）
        weeks: list[tuple[str, date, date]] = []
        for i in range(1, SETTLE_BACKFILL_WEEKS + 1):
            ws = this_monday - timedelta(days=7 * i)
            we = ws + timedelta(days=6)
            iso = ws.isocalendar()
            weeks.append((f"{iso.year}-W{iso.week:02d}", ws, we))
        weeks.reverse()  # 升序：最老的最先结算
        settled_any = False
        for week_key, ws, we in weeks:
            if await self._settle_one_week(member_id, week_key, ws, we):
                settled_any = True
        if settled_any:
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                raise

    async def _settle_one_week(
        self, member_id: int, week_key: str, ws: date, we: date,
    ) -> bool:
        """结算单个周。返回 True 表示新结算落表；False=已结算/无练习/竞态跳过。

        plan_health 快照以 we（该周周日）为基准日，反映周末态、确定性强；回算多周时
        每周快照各自独立，不共享打开当天的 today（否则所有回算周会显示同一份 plan_health）。
        """
        existing = await self.session.scalar(
            select(WeeklySettlement).where(
                WeeklySettlement.member_id == member_id,
                WeeklySettlement.week_key == week_key,
            )
        )
        if existing is not None:
            return False

        active_days = await self.repo.get_week_active_days(member_id, ws, we)
        if active_days == 0:
            return False  # 本周完全没练习 → 不造 0 分垃圾行

        breakdown = await self.repo.get_week_correct_breakdown(member_id, ws, we)
        new_words = await self.repo.get_week_new_word_count(member_id, ws, we)
        task_stats = await self.repo.get_week_task_stats(member_id, ws, we)
        plan_inputs = await self.repo.get_active_forward_plan_with_remaining(member_id)

        if plan_inputs is not None:
            exp_days = expected_learn_days(plan_inputs["learn_weekdays_raw"], ws, we)
            daily_goal = plan_inputs["daily_goal"]
        else:
            exp_days = 5
            daily_goal = 30
        weekly_new_target = daily_goal * max(exp_days, 1)

        login_score = score_login(active_days, exp_days)
        difficulty_score = score_difficulty(breakdown["hard_words"], breakdown["correct_words"])
        new_score = score_new(new_words, weekly_new_target)
        plan_score = score_plan(task_stats["completed_slots"], task_stats["planned_slots"])
        total = login_score + difficulty_score + new_score + plan_score
        stars = compute_stars(total)
        bonus = compute_bonus(login_score, plan_score)

        # 奖励：freeze（全勤且未达上限）+ 周徽章（幂等，先 SELECT 过滤已得的）
        state = await self.session.get(MemberStreak, member_id)
        freeze_balance = (state.freeze_balance if state else 0) or 0
        freeze_granted = 1 if (
            state is not None and active_days >= 7 and freeze_balance < MAX_FREEZE_BALANCE
        ) else 0
        candidate_badges: list[str] = []
        if total >= 100:
            candidate_badges.append("week_full_score")
        if active_days >= 7:
            candidate_badges.append("week_login_7")
        new_badges: list[str] = []
        for key in candidate_badges:
            got = await self.session.scalar(
                select(MemberBadge.member_id).where(
                    MemberBadge.member_id == member_id, MemberBadge.badge_key == key,
                )
            )
            if not got:
                new_badges.append(key)

        # plan_health（只读快照）：以该周周日 we 为基准日，回算多周时每周快照各自独立、确定。
        health = None
        if plan_inputs is not None:
            health = plan_health(
                plan_inputs["total_words"], plan_inputs["mastered"], plan_inputs["deadline"],
                plan_inputs["daily_goal"], plan_inputs["learn_weekdays_raw"], we,
            )

        plan_completion = (
            round(task_stats["completed_slots"] / task_stats["planned_slots"], 3)
            if task_stats["planned_slots"] > 0 else 0.0
        )
        # 周学习现金：CASH_ENABLED 关闭时为 (0.0, None)（行照写，不累加钱包）。
        # 与 bonus_xp 独立的阶跃分档（见 settlement_score.compute_weekly_cash），不回收 bonus。
        cash_reward, cash_tier = (
            compute_weekly_cash(stars, plan_completion)
            if settings.CASH_ENABLED else (0.0, None)
        )
        row = WeeklySettlement(
            member_id=member_id, week_key=week_key, week_start=ws, week_end=we,
            login_score=login_score, difficulty_score=difficulty_score,
            new_score=new_score, plan_score=plan_score, total_score=total, stars=stars,
            real_days=active_days, new_words_learned=new_words, plan_completion=plan_completion,
            bonus_xp=bonus, freeze_granted=freeze_granted,
            badges_granted=new_badges or None, plan_health=health,
            cash_reward=cash_reward, cash_tier_label=cash_tier,
        )

        # 一个原子提交：row + bonus + cash + freeze + 徽章 同 savepoint。
        # 命中周唯一约束 OR 徽章唯一约束都会整体回滚——后者极罕见（首获徽章的并发竞态），
        # 且自愈：下次打开时该周仍未结算、徽章已被 pre-filter 跳过，干净补结。
        # ⚠️ 条件须含 cash_reward：只发现金不发 XP 时也要加载 member 累加 cash_balance。
        try:
            async with self.session.begin_nested():
                if bonus > 0 or cash_reward > 0:
                    member = await self.session.get(Member, member_id)
                    if member is not None:
                        if bonus > 0:
                            member.total_xp = (member.total_xp or 0) + bonus
                        if cash_reward > 0:
                            member.cash_balance = round(
                                (member.cash_balance or 0.0) + cash_reward, 2
                            )
                if freeze_granted and state is not None:
                    state.freeze_balance = min(freeze_balance + 1, MAX_FREEZE_BALANCE)
                for key in new_badges:
                    self.session.add(MemberBadge(member_id=member_id, badge_key=key))
                self.session.add(row)
        except IntegrityError:
            logger.info(
                "weekly settlement race: member=%s week=%s already owned, skipping",
                member_id, week_key,
            )
            return False
        logger.info(
            "settled member=%s week=%s total=%s bonus=%s cash=%s freeze=%s",
            member_id, week_key, total, bonus, cash_reward, freeze_granted,
        )
        return True

    # ─────────────────────────────────────────────────────
    # 现金里程碑懒发放
    # ─────────────────────────────────────────────────────
    async def _maybe_grant_milestones(self, member_id: int) -> None:
        """检测三类里程碑并幂等发放（unit_complete / cumulative_words / attendance_streak）。

        每条独立 savepoint（单条竞态不影响其他条）；幂等预过滤先 SELECT，未命中才 INSERT。
        snapshot 语义：发放后词/周回退不回扣（同 bonus_xp）。里程碑=「首达」非「持续」，
        故 CASH_ENABLED 首次开启后，打开页面会一次性补发所有当下已达成的历史里程碑。
        """
        units_status = await self.repo.get_all_units_mastery_status(member_id)
        mastered_total = sum(u["mastered"] for u in units_status)
        att_streak = await self.repo.get_full_attendance_week_streak(member_id)
        candidates = build_milestone_candidates(units_status, att_streak, mastered_total)

        granted_any = False
        for cand in candidates:
            existing = await self.session.scalar(
                select(CashMilestone).where(
                    CashMilestone.member_id == member_id,
                    CashMilestone.milestone_key == cand.key,
                )
            )
            if existing is not None:
                continue
            try:
                async with self.session.begin_nested():
                    member = await self.session.get(Member, member_id)
                    if member is not None:
                        member.cash_balance = round(
                            (member.cash_balance or 0.0) + cand.amount, 2
                        )
                    self.session.add(CashMilestone(
                        member_id=member_id,
                        milestone_key=cand.key,
                        milestone_type=cand.type,
                        threshold=cand.threshold,
                        amount=cand.amount,
                        snapshot=cand.snapshot,
                    ))
                granted_any = True
            except IntegrityError:
                # 极罕见：SELECT 与 INSERT 之间另一次并发刚插了同一 key。
                # savepoint 已回滚该次 cash_balance 累加 → 自愈：下次打开被 SELECT 跳过。
                logger.info("milestone race: member=%s key=%s", member_id, cand.key)
                continue
        if granted_any:
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                raise

    @staticmethod
    def _settlement_to_dict(r: WeeklySettlement) -> dict:
        return {
            "week_key": r.week_key,
            "week_start": r.week_start.isoformat(),
            "week_end": r.week_end.isoformat(),
            "login_score": r.login_score,
            "difficulty_score": r.difficulty_score,
            "new_score": r.new_score,
            "plan_score": r.plan_score,
            "total_score": r.total_score,
            "stars": r.stars,
            "real_days": r.real_days,
            "new_words_learned": r.new_words_learned,
            "plan_completion": r.plan_completion,
            "bonus_xp": r.bonus_xp,
            "freeze_granted": r.freeze_granted,
            "cash_reward": round(r.cash_reward or 0.0, 2),
            "cash_tier_label": r.cash_tier_label,
            "badges_granted": r.badges_granted or [],
            "plan_health": r.plan_health,
            "settled_at": r.settled_at.isoformat() if r.settled_at else None,
        }
