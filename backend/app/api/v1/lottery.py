"""彩票抽卡奖励机制（点石成金刮刮乐）。

开奖在后端（先抽结果再反演票面），前端只渲染刮卡；懒触发单咽喉点：
GET /lottery/state 打开时同步补发 8 类学习行为对应的抽卡次数。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.lottery_service import MAX_BATCH_SIZE, LotteryService

router = APIRouter(prefix="/lottery", tags=["lottery"])


@router.get("/state")
async def get_lottery_state(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """抽卡页总览：懒同步补发次数（init 5 + 8 类条件）+ 可用次数/彩金/任务清单/续挂票。

    Example:
        curl 'http://localhost:8000/api/v1/lottery/state?member_id=1' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.get_state(member_id)


@router.post("/draw")
async def draw_ticket(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """单张出票（消耗 1 次），返回全量票面（含 win_numbers/cells/wins）。

    Example:
        curl -X POST 'http://localhost:8000/api/v1/lottery/draw?member_id=1' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.draw(member_id)


@router.post("/draw-batch")
async def draw_batch(
    member_id: int = Query(1, ge=1),
    count: int = Query(..., ge=1, le=MAX_BATCH_SIZE),
    db: AsyncSession = Depends(get_db),
):
    """开一批（开批即定局）：N 张共享 batch_id，只回 ticket_ids 不回 prize（悬念）。

    Example:
        curl -X POST 'http://localhost:8000/api/v1/lottery/draw-batch?member_id=1&count=10' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.draw_batch(member_id, count)


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """取票全量票面（批次挂卡 / 刷新续刮）。

    Example:
        curl 'http://localhost:8000/api/v1/lottery/tickets/7?member_id=1' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.get_ticket(member_id, ticket_id)


@router.post("/tickets/{ticket_id}/settle")
async def settle_ticket(
    ticket_id: int,
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """结算入账（幂等）：刮完后领取，彩金累加进 lottery_wealth；批次票附带批次摘要。

    Example:
        curl -X POST 'http://localhost:8000/api/v1/lottery/tickets/7/settle?member_id=1' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.settle(member_id, ticket_id)


@router.get("/batch/{batch_id}")
async def get_batch_summary(
    batch_id: str,
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """批次战报：size / 已核对 / 中奖合计 / best_prize + 逐张票状态。

    Example:
        curl 'http://localhost:8000/api/v1/lottery/batch/abc123?member_id=1' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.batch_summary(member_id, batch_id)


@router.get("/history")
async def get_history(
    member_id: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """历史战绩：总张数 / 中奖合计 / 中奖张数 + 最近票列表。

    Example:
        curl 'http://localhost:8000/api/v1/lottery/history?member_id=1&limit=20' -H 'Authorization: Bearer <token>'
    """
    svc = LotteryService(db)
    return await svc.history(member_id, limit)
