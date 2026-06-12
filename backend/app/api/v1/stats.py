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
