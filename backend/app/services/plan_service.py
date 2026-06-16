from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, PlanStatus, TaskStatus
from app.models.mastery import MasteryRecord
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.word import Word
from app.repositories.plan_repo import DailyTaskRepo, PlanRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException


class PlanService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plan_repo = PlanRepo(session)
        self.task_repo = DailyTaskRepo(session)

    async def create_plan(
        self, member_id: int, name: str, daily_goal: int,
        unit_ids: list[int], deadline: date | None = None,
    ) -> dict:
        plan = LearningPlan(
            member_id=member_id, name=name,
            daily_goal=daily_goal, deadline=deadline,
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

    async def _generate_tasks(self, plan: LearningPlan) -> None:
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

        start = date.today()
        end = plan.deadline or start + timedelta(days=max(remaining // max(plan.daily_goal, 1), 1))
        total_days = max((end - start).days, 1)

        new_per_day = min(plan.daily_goal, remaining) if total_days > 0 else remaining
        review_ratio = 0.3

        existing = await self.task_repo.get_by_plan_range(plan.id, start, end)
        existing_dates = {t.task_date for t in existing}

        for i in range(total_days):
            d = start + timedelta(days=i)
            if d in existing_dates:
                continue
            new_words = min(new_per_day, remaining)
            remaining -= new_words
            review_words = int(new_words * review_ratio) if new_words > 0 else 0
            self.session.add(DailyTask(
                plan_id=plan.id, task_date=d,
                new_count=new_words, review_count=review_words,
            ))

    def _plan_to_dict(self, plan: LearningPlan) -> dict:
        return {
            "id": plan.id,
            "member_id": plan.member_id,
            "name": plan.name,
            "daily_goal": plan.daily_goal,
            "deadline": str(plan.deadline) if plan.deadline else None,
            "status": plan.status.value,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
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
        }
