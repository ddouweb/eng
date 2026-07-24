from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.review_service import ReviewService

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/due")
async def get_due(
    member_id: int = Query(1, ge=1),
    unit_ids: str | None = Query(None, description="逗号分隔的 unit_id，不传=全部"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """今日到期复习画像（首页 / 练习页「今日复习」入口用）。

    Example:
        curl 'http://localhost:8000/api/v1/review/due?member_id=1'
        curl 'http://localhost:8000/api/v1/review/due?member_id=1&unit_ids=1,2&limit=20'
    """
    ids: list[int] | None = None
    if unit_ids:
        ids = [int(x) for x in unit_ids.split(",") if x.strip().isdigit()]
        if not ids:
            ids = None
    svc = ReviewService(db)
    return await svc.get_due(member_id, unit_ids=ids, limit=limit)
