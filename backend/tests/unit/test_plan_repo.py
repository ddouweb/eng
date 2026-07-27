"""DailyTaskRepo.delete_future_pending_learn 谓词的真实 SQL 测试（sqlite in-memory）。

这是 Phase C「手动重平衡计划」的关键不变量：只删未来、pending、learn 类型的任务，
绝不碰今天/历史/手动 in_progress·completed·skipped 进度、以及复习类任务。
项目其余 repo 信任 + 审查（SQL 不单测）；此谓词因涉及「不可删用户进度」的安全语义，
特用真实库验证。自包含、不依赖 async fixture（避开 strict-mode）。
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.enums import PlanStatus, PlanType, TaskStatus, TaskType
from app.models.plan import DailyTask, LearningPlan
from app.repositories.plan_repo import DailyTaskRepo


@pytest.mark.asyncio
async def test_delete_predicate_protects_manual_progress():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        today = date(2026, 7, 24)

        async with Session() as session:
            session.add(LearningPlan(
                id=1, member_id=1, name="t", daily_goal=10,
                status=PlanStatus.active, plan_type=PlanType.forward,
            ))
            # (相对 today, 类型, 状态, 是否应被删)
            cases = [
                (today + timedelta(days=2), TaskType.learn, TaskStatus.pending, True),       # 未来待学 → 删
                (today + timedelta(days=3), TaskType.weekly_review, TaskStatus.pending, False),  # 复习类 → 留
                (today + timedelta(days=4), TaskType.learn, TaskStatus.in_progress, False),  # 手动进行中 → 留
                (today + timedelta(days=5), TaskType.learn, TaskStatus.completed, False),    # 已完成 → 留
                (today + timedelta(days=6), TaskType.learn, TaskStatus.skipped, False),      # 已跳过 → 留
                (today, TaskType.learn, TaskStatus.pending, False),                          # 今天 → 留
                (today - timedelta(days=1), TaskType.learn, TaskStatus.pending, False),      # 历史 → 留
            ]
            for d, ttype, status, _ in cases:
                session.add(DailyTask(
                    plan_id=1, task_date=d, task_type=ttype,
                    new_count=10, review_count=3, status=status,
                ))
            await session.commit()

            repo = DailyTaskRepo(session)
            deleted = await repo.delete_future_pending_learn(1, today)
            await session.commit()
            assert deleted == 1  # 仅第一行命中

            rows = (await session.execute(
                select(DailyTask).where(DailyTask.plan_id == 1).order_by(DailyTask.task_date)
            )).scalars().all()
            kept = {(r.task_date, r.task_type) for r in rows}
            assert len(kept) == 6  # 7 行删 1 行
            # 被删的 (today+2, learn) 不在留存集合中
            assert (today + timedelta(days=2), TaskType.learn) not in kept
            # 手动 in_progress / completed / skipped 的 learn 任务都在
            assert (today + timedelta(days=4), TaskType.learn) in kept
            assert (today + timedelta(days=5), TaskType.learn) in kept
            assert (today + timedelta(days=6), TaskType.learn) in kept
    finally:
        await engine.dispose()
