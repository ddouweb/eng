from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanStatus, TaskStatus, TaskType
from app.models.plan import DailyTask, LearningPlan
from app.repositories.base import BaseRepo


class PlanRepo(BaseRepo[LearningPlan]):
    def __init__(self, session: AsyncSession):
        super().__init__(LearningPlan, session)

    async def get_active_by_member(self, member_id: int) -> list[LearningPlan]:
        stmt = (
            select(LearningPlan)
            .where(LearningPlan.member_id == member_id, LearningPlan.status == PlanStatus.active)
            .order_by(LearningPlan.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_units(self, plan_id: int) -> LearningPlan | None:
        stmt = select(LearningPlan).where(LearningPlan.id == plan_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class DailyTaskRepo(BaseRepo[DailyTask]):
    def __init__(self, session: AsyncSession):
        super().__init__(DailyTask, session)

    async def get_by_plan_date(self, plan_id: int, task_date) -> DailyTask | None:
        stmt = select(DailyTask).where(
            DailyTask.plan_id == plan_id, DailyTask.task_date == task_date
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_plan_range(self, plan_id: int, start_date, end_date):
        stmt = (
            select(DailyTask)
            .where(
                DailyTask.plan_id == plan_id,
                DailyTask.task_date >= start_date,
                DailyTask.task_date <= end_date,
            )
            .order_by(DailyTask.task_date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_future_pending_learn(self, plan_id: int, today: date) -> int:
        """删除某计划「未来、pending、learn 类型」的每日任务，返回删除行数。

        谓词三重保护（手动重平衡计划的关键不变量）：
        - task_date > today：不动今天及历史任务（保留进度与记录）；
        - status == pending：保护用户手动置为 in_progress / completed / skipped 的任务；
        - task_type == learn：只重排新词槽，weekly/monthly_review 复习任务原样保留。
        """
        stmt = delete(DailyTask).where(
            DailyTask.plan_id == plan_id,
            DailyTask.task_date > today,
            DailyTask.status == TaskStatus.pending,
            DailyTask.task_type == TaskType.learn,
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)
