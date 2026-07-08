from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.wrong_book_service import WrongBookService

router = APIRouter(prefix="/wrong-book", tags=["wrong-book"])


@router.get("")
async def list_wrong_book(
    member_id: int = Query(1, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """错题本列表（含单词 + Unit 标题 + 掌握度）。

    Example:
        curl 'http://localhost:8000/api/v1/wrong-book?member_id=1&page=1&page_size=50'
    """
    svc = WrongBookService(db)
    return await svc.list(member_id, page, page_size)


@router.get("/count")
async def count_wrong_book(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """错题总数（用于练习页 badge）。

    Example:
        curl 'http://localhost:8000/api/v1/wrong-book/count?member_id=1'
    """
    svc = WrongBookService(db)
    return await svc.count(member_id)


@router.delete("")
async def clear_wrong_book(
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """清空错题本。

    Example:
        curl -X DELETE 'http://localhost:8000/api/v1/wrong-book?member_id=1'
    """
    svc = WrongBookService(db)
    return await svc.clear(member_id)


@router.post("/{word_id}")
async def add_word(
    word_id: int,
    member_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    """手动加入错题本。

    Example:
        curl -X POST 'http://localhost:8000/api/v1/wrong-book/5?member_id=1'
    """
    svc = WrongBookService(db)
    return await svc.add_manual(member_id, word_id)


@router.delete("/{word_id}")
async def remove_word(
    word_id: int,
    member_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    """移除单个错题。

    Example:
        curl -X DELETE 'http://localhost:8000/api/v1/wrong-book/5?member_id=1'
    """
    svc = WrongBookService(db)
    return await svc.remove(member_id, word_id)
