from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.enums import WordType
from app.schemas.word import TagOperation, WordBatchCreate, WordUpdate
from app.services.word_service import WordService

router = APIRouter(prefix="/words", tags=["words"])


@router.post("/units/{unit_id}/words")
async def batch_create_words(
    unit_id: int, body: WordBatchCreate, db: AsyncSession = Depends(get_db)
):
    """批量添加单词到指定 Unit。

    Example:
        curl -X POST http://localhost:8000/api/v1/words/units/1/words \\
             -H 'Content-Type: application/json' \\
             -d '{"words":[{"english":"hello","chinese":"你好","type":"word"}]}'
    """
    svc = WordService(db)
    return await svc.batch_create(unit_id, [w.model_dump() for w in body.words])


@router.get("/units/{unit_id}/words")
async def list_words_by_unit(
    unit_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: WordType | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """单元内单词列表。

    Example:
        curl http://localhost:8000/api/v1/words/units/1/words?page=1&page_size=50
    """
    svc = WordService(db)
    return await svc.get_by_unit(unit_id, page=page, page_size=page_size, word_type=type)


@router.put("/{word_id}")
async def update_word(
    word_id: int, body: WordUpdate, db: AsyncSession = Depends(get_db)
):
    """更新单词。

    Example:
        curl -X PUT http://localhost:8000/api/v1/words/1 \\
             -H 'Content-Type: application/json' \\
             -d '{"english":"hi","chinese":"嗨"}'
    """
    svc = WordService(db)
    return await svc.update_word(word_id, body.model_dump(exclude_unset=True))


@router.delete("/{word_id}")
async def delete_word(word_id: int, db: AsyncSession = Depends(get_db)):
    """删除单词。

    Example:
        curl -X DELETE http://localhost:8000/api/v1/words/1
    """
    svc = WordService(db)
    return await svc.delete_word(word_id)


@router.post("/{word_id}/tags")
async def set_tags(
    word_id: int, body: TagOperation, db: AsyncSession = Depends(get_db)
):
    """设置单词标签（覆盖式）。

    Example:
        curl -X POST http://localhost:8000/api/v1/words/1/tags \\
             -H 'Content-Type: application/json' \\
             -d '{"tags":["favorite","high_freq"]}'
    """
    svc = WordService(db)
    return await svc.set_tags(word_id, [t.value for t in body.tags])


@router.delete("/{word_id}/tags/{tag}")
async def remove_tag(word_id: int, tag: str, db: AsyncSession = Depends(get_db)):
    """移除单个标签。

    Example:
        curl -X DELETE http://localhost:8000/api/v1/words/1/tags/favorite
    """
    svc = WordService(db)
    return await svc.remove_tag(word_id, tag)


@router.get("/{word_id}/mastery")
async def get_mastery(
    word_id: int,
    member_id: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """查询掌握状态。

    Example:
        curl http://localhost:8000/api/v1/words/1/mastery?member_id=1
    """
    svc = WordService(db)
    return await svc.get_mastery(word_id, member_id=member_id)
