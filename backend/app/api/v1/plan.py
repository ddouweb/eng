from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.plan import PlanCreate, TaskUpdateBody
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("")
async def create_plan(body: PlanCreate, db: AsyncSession = Depends(get_db)):
    """创建学习计划，自动生成每日任务。

    Example:
        curl -X POST http://localhost:8000/api/v1/plans \\
             -H 'Content-Type: application/json' \\
             -d '{"name":"三年级上册","daily_goal":15,"unit_ids":[1,2],"deadline":"2026-07-31"}'
    """
    svc = PlanService(db)
    return await svc.create_plan(
        member_id=1, name=body.name, daily_goal=body.daily_goal,
        unit_ids=body.unit_ids, deadline=body.deadline,
    )


@router.get("")
async def list_plans(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """查询学习计划列表。

    Example:
        curl http://localhost:8000/api/v1/plans?status=active
    """
    svc = PlanService(db)
    return await svc.list_plans(member_id=1, status=status)


@router.get("/{plan_id}")
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    """查看计划详情及每日任务。

    Example:
        curl http://localhost:8000/api/v1/plans/1
    """
    svc = PlanService(db)
    return await svc.get_plan(plan_id)


@router.put("/{plan_id}/tasks/{task_id}")
async def update_task(
    plan_id: int, task_id: int, body: TaskUpdateBody, db: AsyncSession = Depends(get_db)
):
    """更新每日任务完成进度。

    Example:
        curl -X PUT http://localhost:8000/api/v1/plans/1/tasks/1 \\
             -H 'Content-Type: application/json' \\
             -d '{"completed_new":10,"completed_review":3}'
    """
    svc = PlanService(db)
    return await svc.update_task(task_id, plan_id, body.completed_new, body.completed_review)


@router.post("/{plan_id}/pause")
async def pause_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    """暂停计划。

    Example:
        curl -X POST http://localhost:8000/api/v1/plans/1/pause
    """
    svc = PlanService(db)
    return await svc.pause_plan(plan_id)


@router.post("/{plan_id}/resume")
async def resume_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    """恢复计划。

    Example:
        curl -X POST http://localhost:8000/api/v1/plans/1/resume
    """
    svc = PlanService(db)
    return await svc.resume_plan(plan_id)
