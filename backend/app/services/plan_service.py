from datetime import date, datetime, timedelta
import calendar
import logging
import math

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, PlanStatus, PlanType, TaskStatus, TaskType
from app.models.mastery import MasteryRecord
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.word import Word
from app.repositories.plan_repo import DailyTaskRepo, PlanRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException
from app.schemas.plan import dump_learn_weekdays, parse_learn_weekdays

logger = logging.getLogger(__name__)


class PlanService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plan_repo = PlanRepo(session)
        self.task_repo = DailyTaskRepo(session)

    async def create_plan(
        self, member_id: int, name: str, daily_goal: int,
        unit_ids: list[int], deadline: date | None = None,
        learn_weekdays: list[int] | None = None,
        monthly_review_day: int | None = None,
        start_date: date | None = None,
        plan_type: PlanType = PlanType.forward,
    ) -> dict:
        plan = LearningPlan(
            member_id=member_id, name=name,
            daily_goal=daily_goal, deadline=deadline,
            learn_weekdays=dump_learn_weekdays(learn_weekdays),
            monthly_review_day=monthly_review_day,
            start_date=start_date or date.today(),
            plan_type=plan_type,
        )
        plan = await self.plan_repo.create(plan)
        for uid in unit_ids:
            self.session.add(PlanUnit(plan_id=plan.id, unit_id=uid))
        await self.session.flush()
        await self._generate_tasks(plan)
        await self.session.commit()
        await self.session.refresh(plan)
        return success(data=self._plan_to_dict(plan))

    async def list_plans(self, member_id: int, status: str | None = None) -> dict:
        if status:
            try:
                status_enum = PlanStatus(status)
            except ValueError:
                raise AppException(400, f"Invalid status: {status}")
            stmt = select(LearningPlan).where(
                LearningPlan.member_id == member_id,
                LearningPlan.status == status_enum,
            )
        else:
            stmt = select(LearningPlan).where(LearningPlan.member_id == member_id)
        stmt = stmt.order_by(LearningPlan.created_at.desc())
        result = await self.session.execute(stmt)
        plans = list(result.scalars().all())
        return success(data=[self._plan_to_dict(p) for p in plans])

    async def get_plan(self, plan_id: int) -> dict:
        plan = await self.plan_repo.get_with_units(plan_id)
        if not plan:
            raise AppException(404, "Plan not found")
        unit_ids_stmt = select(PlanUnit.unit_id).where(PlanUnit.plan_id == plan.id)
        unit_ids = [r[0] for r in (await self.session.execute(unit_ids_stmt)).all()]
        tasks = await self.task_repo.get_by_plan_range(
            plan.id, date.today(), plan.deadline or date.today() + timedelta(days=30)
        )
        d = self._plan_to_dict(plan)
        d["unit_ids"] = unit_ids
        d["tasks"] = [self._task_to_dict(t) for t in tasks]
        return success(data=d)

    async def update_task(self, task_id: int, plan_id: int, completed_new: int, completed_review: int) -> dict:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise AppException(404, "Task not found")
        if task.plan_id != plan_id:
            raise AppException(400, "Task does not belong to this plan")
        task.completed_new = completed_new
        task.completed_review = completed_review
        if completed_new >= task.new_count and completed_review >= task.review_count:
            task.status = TaskStatus.completed
        elif completed_new > 0 or completed_review > 0:
            task.status = TaskStatus.in_progress
        await self.session.commit()
        return success(data=self._task_to_dict(task))

    async def pause_plan(self, plan_id: int) -> dict:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise AppException(404, "Plan not found")
        plan.status = PlanStatus.paused
        await self.session.commit()
        return success(message="Plan paused")

    async def resume_plan(self, plan_id: int) -> dict:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise AppException(404, "Plan not found")
        plan.status = PlanStatus.active
        await self.session.commit()
        return success(message="Plan resumed")

    async def rebalance_plan(self, plan_id: int) -> dict:
        """手动重新平衡计划：把剩余未掌握词重新摊到 deadline 前的未来学习日。

        只对 active forward 计划生效（review_only/wrong_word_drill/paused 无新词可重排）。
        单日新词硬上限 cap = round(daily_goal×1.5)（Python round 为银行家舍入：奇数 daily_goal
        如 3→4、15→22；过载护栏，偏保守）。
        全部短路（feasible=False 且不动任何任务，均在写操作之前判定）：
        - reason=not_rebalanceable：非 forward / 非 active；
        - reason=no_deadline：无 deadline；
        - reason=nothing_to_rebalance：已无未掌握词；
        - reason=deadline_passed：deadline 已过或其前无学习日；
        - reason=no_free_learn_days：未来学习日全被手动占用（in_progress/completed/skipped）。
        重建路径：reason=infeasible 时即便 cap 也救不回（仍按 cap 重建，不越界，只告警）；
        reason=conflict 为并发 rebalance 撞唯一约束（已回滚，可重试）。

        needed 基于「有效学习日」= 未来学习日 − 已被手动占用的学习日，故 feasible 不会因
        occupied 占用而虚高（否则词会被静默丢弃却报 feasible=True）。删除未来 pending learn
        任务（保护今天/历史/手动进度/复习任务），按有效学习日重建新词槽，剩余词用尽即停
        （与 _generate_tasks 同口径）。写 last_rebalanced_at。
        """
        plan = await self.plan_repo.get_by_id(plan_id)
        if plan is None:
            raise AppException(404, "Plan not found")

        cap = round(plan.daily_goal * 1.5)

        # 短路：非 forward / 非 active 无新词进度可重排
        if plan.plan_type != PlanType.forward or plan.status != PlanStatus.active:
            return success(data=self._rebalance_noop(plan, cap, "not_rebalanceable"))

        today = date.today()
        deadline = plan.deadline

        # 无 deadline 无法定义"剩余学习日"，重平衡无意义
        if deadline is None:
            return success(data=self._rebalance_noop(plan, cap, "no_deadline"))

        remaining_unmastered = await self._remaining_unmastered(plan)

        # 已无未掌握词 → 无可重排，不动任何任务
        if remaining_unmastered == 0:
            return success(data=self._rebalance_noop(
                plan, cap, "nothing_to_rebalance", remaining_unmastered=0))

        weekdays = parse_learn_weekdays(plan.learn_weekdays)
        remaining_learn_days = _count_learn_days(today + timedelta(days=1), deadline, weekdays)

        # deadline 已过或其前无学习日 → 救不回，不重建
        if remaining_learn_days <= 0:
            return success(data=self._rebalance_noop(
                plan, cap, "deadline_passed", remaining_unmastered=remaining_unmastered))

        # 先（只读）收集未来已被手动占用（非 pending）的 learn 任务日期——这些日子不可重排。
        # 有效学习日 = 全部未来学习日 − 被占用日；据此算 needed/feasible，避免「feasible=True
        # 实则词被静默丢弃」的误导。
        occupied = {
            r[0] for r in (
                await self.session.execute(
                    select(DailyTask.task_date).where(
                        DailyTask.plan_id == plan.id,
                        DailyTask.task_type == TaskType.learn,
                        DailyTask.task_date > today,
                        DailyTask.status != TaskStatus.pending,
                    )
                )
            ).all()
        }
        occupied_in_window = {
            d for d in occupied if today < d <= deadline and d.weekday() in weekdays
        }
        effective_learn_days = max(remaining_learn_days - len(occupied_in_window), 0)

        # 所有未来学习日都已被手动占用 → 无可重排日，不动任务
        if effective_learn_days <= 0:
            return success(data=self._rebalance_noop(
                plan, cap, "no_free_learn_days", remaining_unmastered=remaining_unmastered))

        needed = math.ceil(remaining_unmastered / effective_learn_days)
        new_per_day = min(cap, needed)
        feasible = needed <= cap
        reason = None if feasible else "infeasible"

        # 删未来 pending learn 任务 + 按有效学习日重建（跳过 occupied，既不撞 uk_plan_date_type
        # 唯一约束，也不覆盖手动进度）。整体 try：并发 rebalance 撞唯一约束则回滚、返回 conflict。
        try:
            await self.task_repo.delete_future_pending_learn(plan.id, today)
            remaining = remaining_unmastered
            d = today + timedelta(days=1)
            while d <= deadline and remaining > 0:
                if d.weekday() in weekdays and d not in occupied:
                    new_words = min(new_per_day, remaining)
                    review_words = int(new_words * 0.3) if new_words > 0 else 0
                    self.session.add(DailyTask(
                        plan_id=plan.id, task_date=d, task_type=TaskType.learn,
                        new_count=new_words, review_count=review_words,
                    ))
                    remaining -= new_words
                d += timedelta(days=1)
            plan.last_rebalanced_at = datetime.now()
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.info("rebalance race: plan=%s concurrently rebalanced, skipping", plan.id)
            return success(data=self._rebalance_noop(plan, cap, "conflict"))

        return success(data={
            "plan_id": plan.id,
            "feasible": feasible,
            "reason": reason,
            "remaining_unmastered": remaining_unmastered,
            "remaining_learn_days": remaining_learn_days,
            "effective_learn_days": effective_learn_days,
            "new_per_day": new_per_day,
            "daily_goal": plan.daily_goal,
            "cap": cap,
            "deadline": str(deadline),
            "last_rebalanced_at": plan.last_rebalanced_at.isoformat(),
        })

    async def _remaining_unmastered(self, plan: LearningPlan) -> int:
        """与 _generate_tasks 同口径：plan_units 总词数 − 已掌握(level∈{familiar,permanent})。"""
        unit_ids_stmt = select(PlanUnit.unit_id).where(PlanUnit.plan_id == plan.id)
        unit_ids = [r[0] for r in (await self.session.execute(unit_ids_stmt)).all()]
        if not unit_ids:
            return 0
        total = int((await self.session.execute(
            select(func.count()).where(Word.unit_id.in_(unit_ids))
        )).scalar_one())
        mastered = int((await self.session.execute(
            select(func.count())
            .select_from(MasteryRecord)
            .join(Word, Word.id == MasteryRecord.word_id)
            .where(
                Word.unit_id.in_(unit_ids),
                MasteryRecord.member_id == plan.member_id,
                MasteryRecord.level.in_([MasteryLevel.familiar, MasteryLevel.permanent]),
            )
        )).scalar_one())
        return max(total - mastered, 0)

    @staticmethod
    def _rebalance_noop(
        plan: LearningPlan, cap: int, reason: str, remaining_unmastered: int | None = None,
    ) -> dict:
        """重平衡短路时的统一响应（feasible=False，不动任何任务）。"""
        return {
            "plan_id": plan.id,
            "feasible": False,
            "reason": reason,
            "remaining_unmastered": remaining_unmastered,
            "remaining_learn_days": None,
            "effective_learn_days": None,
            "new_per_day": None,
            "daily_goal": plan.daily_goal,
            "cap": cap,
            "deadline": str(plan.deadline) if plan.deadline else None,
            "last_rebalanced_at": (
                plan.last_rebalanced_at.isoformat() if plan.last_rebalanced_at else None
            ),
        }

    async def _generate_tasks(self, plan: LearningPlan) -> None:
        """按日轮询 [start_date, deadline] 生成 daily_task。

        每天根据 plan_type 和规则生成**最多一条** task：

        - **forward**（首轮，含新词）：
          - 月复习日 → monthly_review，new=0, review=min(daily_goal*22*0.4, 150)
          - 学习日（weekday ∈ learn_weekdays） → learn，new=min(daily_goal, remaining), review=int(new*0.3)
          - 其余 → weekly_review，new=0, review=min(daily_goal*5*0.6, 200)

        - **review_only**（二轮，无新词）：
          - 月复习日 → monthly_review（同上）
          - 学习日 → learn 任务但 new=0, review=daily_goal（纯复习槽）
          - 其余 → weekly_review（同 forward 公式）

        - **wrong_word_drill**（三轮，错题刷）：
          - 所有日子 → wrong_word_drill，new=0, review=daily_goal
          - 忽略 learn_weekdays / monthly_review_day
        """
        stmt = select(PlanUnit.unit_id).where(PlanUnit.plan_id == plan.id)
        result = await self.session.execute(stmt)
        unit_ids = [r[0] for r in result.all()]

        total_words_stmt = select(func.count()).where(Word.unit_id.in_(unit_ids))
        total_words = (await self.session.execute(total_words_stmt)).scalar_one()

        mastered_stmt = (
            select(func.count())
            .select_from(MasteryRecord)
            .join(Word, Word.id == MasteryRecord.word_id)
            .where(
                Word.unit_id.in_(unit_ids),
                MasteryRecord.member_id == plan.member_id,
                MasteryRecord.level.in_([MasteryLevel.familiar, MasteryLevel.permanent]),
            )
        )
        mastered = (await self.session.execute(mastered_stmt)).scalar_one()
        remaining = max(total_words - mastered, 0)

        start = plan.start_date or date.today()
        weekdays = parse_learn_weekdays(plan.learn_weekdays)
        mrd = plan.monthly_review_day

        if plan.deadline:
            end = plan.deadline
            # 有 deadline：按区间内实际学习日数均摊新词
            learn_days = _count_learn_days(start, end, weekdays)
            new_per_day = (
                min(plan.daily_goal, math.ceil(remaining / learn_days))
                if learn_days > 0 else min(plan.daily_goal, remaining)
            )
        else:
            # 无 deadline：按"学完 remaining 需要多少个学习日"反推结束日，
            # 保证所有新词都能落到学习日任务上（修复原先仅按日历天数估算、
            # 未考虑 learn_weekdays 导致 20-30% 新词漏排的问题）。
            needed = math.ceil(remaining / max(plan.daily_goal, 1)) if remaining > 0 else 0
            end = _end_for_learn_days(start, needed, weekdays)
            new_per_day = (
                min(plan.daily_goal, math.ceil(remaining / needed))
                if needed > 0 else remaining
            )

        total_days = max((end - start).days + 1, 1)

        existing = await self.task_repo.get_by_plan_range(plan.id, start, end)
        existing_keys = {(t.task_date, t.task_type) for t in existing}

        for i in range(total_days):
            d = start + timedelta(days=i)
            is_month_review = _hits_monthly_review(d, mrd)
            is_learn_day = d.weekday() in weekdays

            # ─── 三轮：错题刷，所有日子同一类型 ───
            if plan.plan_type == PlanType.wrong_word_drill:
                ttype = TaskType.wrong_word_drill
                new_words = 0
                review_words = plan.daily_goal
            # ─── 二轮：纯复习模式 ───
            elif plan.plan_type == PlanType.review_only:
                if is_month_review:
                    ttype = TaskType.monthly_review
                    new_words = 0
                    review_words = min(int(plan.daily_goal * 22 * 0.4), 150)
                elif is_learn_day:
                    ttype = TaskType.learn
                    new_words = 0
                    review_words = plan.daily_goal
                else:
                    ttype = TaskType.weekly_review
                    new_words = 0
                    review_words = min(int(plan.daily_goal * 5 * 0.6), 200)
            # ─── 一轮：forward 默认 ───
            else:
                if is_month_review:
                    ttype = TaskType.monthly_review
                    new_words = 0
                    # 当月已过学习日 ≤ 22，按 40% 复习率，硬上限 150
                    review_words = min(int(plan.daily_goal * 22 * 0.4), 150)
                elif is_learn_day:
                    ttype = TaskType.learn
                    new_words = min(new_per_day, remaining)
                    remaining -= new_words
                    review_words = int(new_words * 0.3) if new_words > 0 else 0
                else:
                    ttype = TaskType.weekly_review
                    new_words = 0
                    # 一周 5 学习日 × daily_goal × 0.6，硬上限 200
                    review_words = min(int(plan.daily_goal * 5 * 0.6), 200)

            if (d, ttype) in existing_keys:
                continue
            if new_words == 0 and review_words == 0:
                continue
            self.session.add(DailyTask(
                plan_id=plan.id, task_date=d, task_type=ttype,
                new_count=new_words, review_count=review_words,
            ))

    def _plan_to_dict(self, plan: LearningPlan) -> dict:
        from app.schemas.plan import parse_learn_weekdays
        return {
            "id": plan.id,
            "member_id": plan.member_id,
            "name": plan.name,
            "daily_goal": plan.daily_goal,
            "deadline": str(plan.deadline) if plan.deadline else None,
            "status": plan.status.value,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "learn_weekdays": parse_learn_weekdays(plan.learn_weekdays),
            "monthly_review_day": plan.monthly_review_day,
            "start_date": str(plan.start_date) if plan.start_date else None,
            "plan_type": plan.plan_type.value,
        }

    @staticmethod
    def _task_to_dict(task: DailyTask) -> dict:
        return {
            "id": task.id,
            "plan_id": task.plan_id,
            "task_date": str(task.task_date),
            "new_count": task.new_count,
            "review_count": task.review_count,
            "completed_new": task.completed_new,
            "completed_review": task.completed_review,
            "status": task.status.value,
            "task_type": task.task_type.value,
        }


def _last_day_of_month(d: date) -> int:
    """返回 d 所在月份的最后一天（1-31）。"""
    return calendar.monthrange(d.year, d.month)[1]


def _count_learn_days(start: date, end: date, weekdays: list[int]) -> int:
    """统计 [start, end] 闭区间内、weekday ∈ weekdays 的学习日数。"""
    if end < start:
        return 0
    wd = set(weekdays)
    n = 0
    d = start
    while d <= end:
        if d.weekday() in wd:
            n += 1
        d += timedelta(days=1)
    return n


def _end_for_learn_days(start: date, needed_learn_days: int, weekdays: list[int]) -> date:
    """从 start 起逐日推进，返回恰好覆盖 needed_learn_days 个学习日的结束日。

    用于无 deadline 计划反推结束日：保证区间内学习日数 ≥ needed_learn_days，
    从而所有新词都能排进学习日任务（月复习日占用日历日但不计入学习日，自动顺延）。
    """
    if needed_learn_days <= 0:
        return start
    wd = set(weekdays)
    count = 0
    d = start
    while count < needed_learn_days:
        if d.weekday() in wd:
            count += 1
        d += timedelta(days=1)
    return d - timedelta(days=1)


def _hits_monthly_review(d: date, mrd: int | None) -> bool:
    """d 是否命中月复习日。

    - mrd is None → False
    - mrd == 31   → d.day == 当月最后一天（2 月自动适配 28/29）
    - 1 ≤ mrd ≤ 28 → d.day == mrd
    """
    if mrd is None:
        return False
    if mrd == 31:
        return d.day == _last_day_of_month(d)
    if 1 <= mrd <= 28:
        return d.day == mrd
    return False
