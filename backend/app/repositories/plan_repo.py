from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanStatus, TaskStatus
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.word import Word
from app.repositories.base import BaseRepo
from app.schemas.exceptions import AppException


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
