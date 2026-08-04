from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_overview(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """全局统计概览。

    Example:
        curl http://localhost:8000/api/v1/stats/overview?member_id=1
    """
    svc = StatsService(db)
    return await svc.get_overview(member_id)


@router.get("/units/{unit_id}")
async def get_unit_stats(
    unit_id: int,
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """单个 Unit 的掌握统计。

    Example:
        curl http://localhost:8000/api/v1/stats/units/1?member_id=1
    """
    svc = StatsService(db)
    return await svc.get_unit_stats(member_id, unit_id)


@router.get("/trend")
async def get_trend(
    days: int = Query(30, ge=1, le=365),
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """最近 N 天的每日练习趋势。

    Example:
        curl http://localhost:8000/api/v1/stats/trend?days=7&member_id=1
    """
    svc = StatsService(db)
    return await svc.get_trend(member_id, days)


@router.get("/profile")
async def get_profile(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """坚持机制画像：连续学习/最长/freeze 余额/XP 段位/徽章（首页卡片用）。

    Example:
        curl http://localhost:8000/api/v1/stats/profile?member_id=1
    """
    svc = StatsService(db)
    return await svc.get_profile(member_id)


@router.get("/weekly-settlement")
async def get_weekly_settlement(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """每周奖励结算：周分三维（坚持/新词/计划）+ 星 + bonus + plan_health + 历史。

    打开即懒结算上周（若到期）。单人模式 member_id 恒为 1。

    Example:
        curl http://localhost:8000/api/v1/stats/weekly-settlement?member_id=1
    """
    svc = StatsService(db)
    return await svc.get_weekly_settlement(member_id)


@router.get("/today")
async def get_today(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """今日完成情况（首页「完成情况+建议」卡片用）：今日新词/复习任务进度 + 实时计划体检
    （以今天为基准）+ 今日实际练习量 + 错题待处理数。纯只读聚合，不触发懒结算。

    Example:
        curl http://localhost:8000/api/v1/stats/today?member_id=1
    """
    svc = StatsService(db)
    return await svc.get_today_progress(member_id)


@router.get("/week-progress")
async def get_week_progress(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """本周进度预估（首页「本周进度」卡）：当前进行中本周的三维实时得分（坚持/新词/计划）
    + 星 + 预估 bonus/现金 + 差距量（还差几天全勤、几个新词）。纯只读，不结算、不落表。

    与 /weekly-settlement（只结算已结束的上周）互补：本接口算「本周进行中」实时预估。

    Example:
        curl http://localhost:8000/api/v1/stats/week-progress?member_id=1
    """
    svc = StatsService(db)
    return await svc.get_week_progress(member_id)
