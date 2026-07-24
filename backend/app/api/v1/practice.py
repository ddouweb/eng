from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.practice import PracticeStart, Rejudge, SubmitAnswer
from app.services.practice_service import PracticeService

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/start")
async def start_practice(body: PracticeStart, db: AsyncSession = Depends(get_db)):
    """开始练习会话，返回按权重抽选的题目列表。

    Example:
        curl -X POST http://localhost:8000/api/v1/practice/start \\
             -H 'Content-Type: application/json' \\
             -d '{"member_id":1,"mode":"flashcard","unit_ids":[1],"count":10}'
    """
    svc = PracticeService(db)
    return await svc.start_practice(
        member_id=body.member_id,
        mode=body.mode,
        unit_ids=body.unit_ids,
        count=body.count,
        task_type=body.task_type,
    )


@router.post("/{session_id}/submit")
async def submit_answer(
    session_id: int, body: SubmitAnswer, db: AsyncSession = Depends(get_db)
):
    """提交单题答案，自动更新掌握状态。

    Example:
        curl -X POST http://localhost:8000/api/v1/practice/1/submit \\
             -H 'Content-Type: application/json' \\
             -d '{"word_id":5,"is_correct":true,"user_answer":"hello"}'
    """
    svc = PracticeService(db)
    return await svc.submit_answer(
        session_id=session_id,
        word_id=body.word_id,
        is_correct=body.is_correct,
        user_answer=body.user_answer,
    )


@router.post("/{session_id}/finish")
async def finish_practice(session_id: int, db: AsyncSession = Depends(get_db)):
    """结束练习会话，返回汇总统计。

    Example:
        curl -X POST http://localhost:8000/api/v1/practice/1/finish
    """
    svc = PracticeService(db)
    return await svc.finish_practice(session_id)


@router.post("/{session_id}/rejudge")
async def rejudge_answer(
    session_id: int, body: Rejudge, db: AsyncSession = Depends(get_db)
):
    """改判某题正误（结束页「改判为对/错」用）。允许在会话结束后调用；
    绕过 submit 的幂等去重与客观题服务端复判，按人工判定覆盖更新
    PracticeRecord / mastery / SRS / 错题本 / XP / 每日任务。

    Example:
        curl -X POST http://localhost:8000/api/v1/practice/1/rejudge \\
             -H 'Content-Type: application/json' \\
             -d '{"word_id":5,"is_correct":true}'
    """
    svc = PracticeService(db)
    return await svc.rejudge_answer(
        session_id=session_id,
        word_id=body.word_id,
        is_correct=body.is_correct,
    )


@router.get("/{session_id}")
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """查询练习会话详情。

    Example:
        curl http://localhost:8000/api/v1/practice/1
    """
    svc = PracticeService(db)
    return await svc.get_session(session_id)
