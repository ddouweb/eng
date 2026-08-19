"""lottery_repo 真实 SQL 测试（sqlite in-memory，自包含，照 test_stats_repo_cash.py 范式）。

重点：
- uq_member_lottery_grant 唯一约束真实生效；
- count_ended_sessions 只计 ended 会话；
- get_today_task_flags 的空槽守卫（new_count=0/review_count=0 的 completed 任务不点亮）；
- 批次聚合 / find_active_batch / find_pending_single。
"""
from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.lottery import GrantCandidate
from app.models.base import Base
from app.models.enums import PlanStatus, PracticeMode, TaskStatus, TaskType
from app.models.lottery import LotteryTicket
from app.models.member import Member
from app.models.plan import DailyTask, LearningPlan
from app.models.practice import PracticeSession
from app.models.settlement import WeeklySettlement
from app.models.streak import MemberBadge
from app.repositories.lottery_repo import LotteryRepo


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


def _session(member_id: int, ended: bool) -> PracticeSession:
    return PracticeSession(
        member_id=member_id,
        mode=PracticeMode.flashcard,
        total_count=10,
        correct_count=8,
        ended_at=datetime(2026, 8, 19, 10, 0, 0) if ended else None,
    )


def _ticket(member_id: int, prize: int, batch_id: str | None, settled: bool) -> LotteryTicket:
    return LotteryTicket(
        member_id=member_id,
        prize=prize,
        ticket={"prize": prize, "win_numbers": [], "cells": [], "wins": []},
        batch_id=batch_id,
        settled_at=datetime(2026, 8, 19, 12, 0, 0) if settled else None,
    )


# ── uq_member_lottery_grant：唯一约束 ──


@pytest.mark.asyncio
async def test_grant_unique_constraint_raises():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            await s.commit()
            repo = LotteryRepo(s)
            await repo.add_grant(1, GrantCandidate("daily:2026-08-19", "daily"))
            await s.commit()
            await repo.add_grant(1, GrantCandidate("daily:2026-08-19", "daily"))
            with pytest.raises(Exception):
                await s.commit()
    finally:
        await engine.dispose()


# ── count_ended_sessions ──


@pytest.mark.asyncio
async def test_count_ended_sessions_only_counts_ended():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            await s.commit()
            s.add_all([
                _session(1, ended=True), _session(1, ended=True),
                _session(1, ended=False), _session(1, ended=False),
            ])
            await s.commit()
            assert await LotteryRepo(s).count_ended_sessions(1) == 2
    finally:
        await engine.dispose()


# ── get_today_task_flags：空槽守卫 ──


async def _flags_case(tasks: list[DailyTask]) -> dict:
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            s.add(LearningPlan(id=10, member_id=1, name="p", status=PlanStatus.active))
            await s.commit()
            for t in tasks:
                t.plan_id = 10
                s.add(t)
            await s.commit()
            return await LotteryRepo(s).get_today_task_flags(1, date(2026, 8, 19))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_flags_learn_task_done():
    flags = await _flags_case([DailyTask(
        task_date=date(2026, 8, 19), task_type=TaskType.learn,
        new_count=10, review_count=3, status=TaskStatus.completed,
    )])
    # learn 任务内嵌复习槽 → 两个标记都点亮
    assert flags == {"learn": True, "review": True}


@pytest.mark.asyncio
async def test_flags_empty_slot_guard():
    """new_count=0 且 review_count=0 的 completed 任务（update_task 会直接置 completed）不点亮。"""
    flags = await _flags_case([DailyTask(
        task_date=date(2026, 8, 19), task_type=TaskType.learn,
        new_count=0, review_count=0, status=TaskStatus.completed,
    )])
    assert flags == {"learn": False, "review": False}


@pytest.mark.asyncio
async def test_flags_review_only_task():
    flags = await _flags_case([DailyTask(
        task_date=date(2026, 8, 19), task_type=TaskType.weekly_review,
        new_count=0, review_count=20, status=TaskStatus.completed,
    )])
    assert flags == {"learn": False, "review": True}


@pytest.mark.asyncio
async def test_flags_in_progress_not_done():
    flags = await _flags_case([DailyTask(
        task_date=date(2026, 8, 19), task_type=TaskType.learn,
        new_count=10, review_count=3, status=TaskStatus.in_progress,
    )])
    assert flags == {"learn": False, "review": False}


@pytest.mark.asyncio
async def test_flags_other_date_ignored():
    flags = await _flags_case([DailyTask(
        task_date=date(2026, 8, 18), task_type=TaskType.learn,
        new_count=10, review_count=3, status=TaskStatus.completed,
    )])
    assert flags == {"learn": False, "review": False}


# ── 徽章 / 周结算星 ──


@pytest.mark.asyncio
async def test_badge_keys_and_week_stars():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            await s.commit()
            s.add_all([
                MemberBadge(member_id=1, badge_key="streak_3"),
                MemberBadge(member_id=1, badge_key="xp_1000"),
            ])
            s.add(WeeklySettlement(
                member_id=1, week_key="2026-W30", week_start=date(2026, 7, 20),
                week_end=date(2026, 7, 26), stars=4,
            ))
            s.add(WeeklySettlement(
                member_id=1, week_key="2026-W31", week_start=date(2026, 7, 27),
                week_end=date(2026, 8, 2), stars=0,  # 0 星不计
            ))
            await s.commit()
            repo = LotteryRepo(s)
            assert await repo.get_badge_keys(1) == ["streak_3", "xp_1000"]
            assert await repo.get_week_stars(1) == [("2026-W30", 4)]
    finally:
        await engine.dispose()


# ── 批次聚合 / 续挂查询 ──


@pytest.mark.asyncio
async def test_batch_summary_and_active_batch():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            await s.commit()
            s.add_all([
                _ticket(1, 500, "batchA", settled=True),
                _ticket(1, 0, "batchA", settled=True),
                _ticket(1, 100, "batchA", settled=False),
                _ticket(1, 200, "batchA", settled=False),
                _ticket(1, 40, None, settled=True),   # 单张已结算
                _ticket(1, 0, None, settled=False),   # 单张未结算
            ])
            await s.commit()
            repo = LotteryRepo(s)
            # active batch：最新含未结算票的批次 = batchA
            active = await repo.find_active_batch(1)
            assert active["batch_id"] == "batchA"
            assert active["size"] == 4
            assert active["settled"] == 2
            assert active["remaining"] == 2
            assert active["total_prize"] == 500  # 只算已结算
            assert active["hit_count"] == 1
            assert active["best_prize"] == 500
            assert [t["index"] for t in active["tickets"]] == [1, 2, 3, 4]
            # pending single：最新未结算单张
            pending = await repo.find_pending_single(1)
            assert pending is not None and pending["batch_id"] is None
            # 中奖统计：已结算且 prize>0 的票 = 500(batchA) + 40(单张)
            won = await repo.get_won_stats(1)
            assert won == {"total_won": 540, "hit_count": 2}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_active_batch_returns_none():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            await s.commit()
            s.add(_ticket(1, 100, "batchA", settled=True))
            await s.commit()
            repo = LotteryRepo(s)
            assert await repo.find_active_batch(1) is None
            assert await repo.find_pending_single(1) is None
    finally:
        await engine.dispose()
