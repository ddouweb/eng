"""现金里程碑两个新 repo 查询的真实 SQL 测试（sqlite in-memory）。

自包含、不依赖 async fixture（避开 strict-mode）。照 test_plan_repo.py 范式。
重点验证 get_full_attendance_week_streak 的 week_start 连续性（缺失周不跳过——防虚高 streak 多付钱）。
"""
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.enums import MasteryLevel
from app.models.mastery import MasteryRecord
from app.models.member import Member
from app.models.settlement import WeeklySettlement
from app.models.unit import Unit
from app.models.word import Word
from app.repositories.stats_repo import StatsRepo


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


def _week(member_id: int, start: date, real_days: int) -> WeeklySettlement:
    """构造一张 weekly_settlement 行（week_start=start，周一）。"""
    iso = start.isocalendar()
    return WeeklySettlement(
        member_id=member_id,
        week_key=f"{iso.year}-W{iso.week:02d}",
        week_start=start,
        week_end=start + timedelta(days=6),
        real_days=real_days,
    )


# ── get_full_attendance_week_streak：连续性是关键 ──
@pytest.mark.asyncio
async def test_streak_consecutive_full_weeks():
    """连续 3 个全勤周（相邻 7 天）→ streak=3。"""
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            base = date(2026, 7, 13)  # 周一
            for i in range(3):
                s.add(_week(1, base + timedelta(days=7 * i), 7))
            await s.commit()
            assert await StatsRepo(s).get_full_attendance_week_streak(1) == 3
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_streak_stops_at_missing_week_gap():
    """缺失周（无 settlement 行）打断连续——这是连续性修复防的 bug（旧逻辑会跳过缺失周虚高）。"""
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            # W0(7/13,7), W2(7/27,7) —— 缺 W1(7/20)
            s.add(_week(1, date(2026, 7, 13), 7))
            s.add(_week(1, date(2026, 7, 27), 7))
            await s.commit()
            # 从最近(7/27)往回：7/27 满→1，期望 7/20；下一行 7/13 ≠ 7/20 → 停。streak=1（非 2）
            assert await StatsRepo(s).get_full_attendance_week_streak(1) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_streak_stops_at_non_full_week():
    """中间一周非全勤(real_days<7) → 当前连续段在该周结束。"""
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            s.add(_week(1, date(2026, 7, 13), 7))
            s.add(_week(1, date(2026, 7, 20), 3))   # 非全勤
            s.add(_week(1, date(2026, 7, 27), 7))   # 最近，满
            await s.commit()
            # 7/27 满→1，期望 7/20；7/20 满足相邻但 real_days=3<7 → 停。streak=1
            assert await StatsRepo(s).get_full_attendance_week_streak(1) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_streak_zero_when_most_recent_not_full():
    """最近一周非全勤 → 当前 streak=0（即便更早有全勤周）。"""
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            s.add(_week(1, date(2026, 7, 13), 7))
            s.add(_week(1, date(2026, 7, 20), 2))   # 最近，非全勤
            await s.commit()
            assert await StatsRepo(s).get_full_attendance_week_streak(1) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_streak_zero_when_no_settlement():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            await s.commit()
            assert await StatsRepo(s).get_full_attendance_week_streak(1) == 0
    finally:
        await engine.dispose()


# ── get_all_units_mastery_status：mastered 口径 = level∈{familiar,permanent} ──
@pytest.mark.asyncio
async def test_units_mastery_status_mastered_counts():
    engine, Session = await _setup()
    try:
        async with Session() as s:
            s.add(Member(id=1, name="t"))
            # Unit1：2 词全掌握
            u1 = Unit(id=1, title="u1", sequence=1)
            # Unit2：2 词，1 掌握 1 未练
            u2 = Unit(id=2, title="u2", sequence=2)
            # Unit3：2 词，全未练（无 mastery 记录）
            u3 = Unit(id=3, title="u3", sequence=3)
            s.add_all([u1, u2, u3])
            for uid in (1, 2, 3):
                for k in (0, 1):
                    s.add(Word(unit_id=uid, english=f"u{uid}w{k}", chinese="中", seq=k))
            await s.commit()
            # 掌握记录
            s.add(MasteryRecord(member_id=1, word_id=1, level=MasteryLevel.familiar))
            s.add(MasteryRecord(member_id=1, word_id=2, level=MasteryLevel.permanent))
            s.add(MasteryRecord(member_id=1, word_id=3, level=MasteryLevel.familiar))  # u2w0 掌握
            # word_id=4(u2w1) 不加 → 未练；u3 全无记录
            await s.commit()

            rows = await StatsRepo(s).get_all_units_mastery_status(1)
            by_id = {r["unit_id"]: r for r in rows}
            assert by_id[1] == {"unit_id": 1, "total_words": 2, "mastered": 2}
            assert by_id[2] == {"unit_id": 2, "total_words": 2, "mastered": 1}
            assert by_id[3] == {"unit_id": 3, "total_words": 2, "mastered": 0}
    finally:
        await engine.dispose()
