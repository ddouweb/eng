from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.checkin_service import CheckinService

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.post("/encouragement")
async def encouragement(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """生成签到励学寄语（AI 结合当前学习情况，只读不落库）。

    用户点「签到」时调；确认后再调 POST /checkin 落库。

    Example:
        curl -X POST 'http://localhost:8000/api/v1/checkin/encouragement?member_id=1'
    """
    return await CheckinService(db).generate_encouragement(member_id)


@router.post("")
async def checkin(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """确认签到：标记今日活跃（推进 streak，不加 XP），返回最新连续记录。同日重复签到幂等。

    Example:
        curl -X POST 'http://localhost:8000/api/v1/checkin?member_id=1'
    """
    return await CheckinService(db).checkin(member_id)
