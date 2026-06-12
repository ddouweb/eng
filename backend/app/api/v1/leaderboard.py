from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.leaderboard_service import LeaderboardService

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    """家庭排行榜 — 所有成员的学习数据对比。

    Example:
        curl http://localhost:8000/api/v1/leaderboard
    """
    svc = LeaderboardService(db)
    return await svc.get_leaderboard()
