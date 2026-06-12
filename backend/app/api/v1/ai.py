from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import create_ai_provider, safe_close_provider
from app.database import get_db
from app.services.exercise_service import ExerciseService

router = APIRouter(prefix="/ai", tags=["ai"])


class AIBodyBase(BaseModel):
    ai_provider: str | None = Field(None, pattern="^(claude|deepseek|glm)$")
    ai_api_key: str | None = None


class DialogueRequest(AIBodyBase):
    unit_ids: list[int] = Field(..., min_length=1)
    scenario: str = Field("日常对话", max_length=100)


class ExerciseRequest(AIBodyBase):
    unit_ids: list[int] = Field(..., min_length=1)
    mode: str = Field("choice", pattern="^(choice|fill)$")


class ParseWordsRequest(AIBodyBase):
    text: str = Field(..., min_length=1, max_length=10000)


def _build_provider(body: "AIBodyBase"):
    if body.ai_provider and body.ai_api_key:
        return create_ai_provider(body.ai_provider, body.ai_api_key)
    return None


@router.post("/dialogue")
async def generate_dialogue(body: DialogueRequest, db: AsyncSession = Depends(get_db)):
    """生成场景对话。

    Example:
        curl -X POST http://localhost:8000/api/v1/ai/dialogue \\
             -H 'Content-Type: application/json' \\
             -d '{"unit_ids":[1,2],"scenario":"购物"}'
    """
    svc = ExerciseService(db)
    provider = _build_provider(body)
    try:
        return await svc.generate_dialogue(body.unit_ids, body.scenario, provider)
    finally:
        if provider:
            await safe_close_provider(provider)


@router.post("/exercise")
async def generate_exercise(body: ExerciseRequest, db: AsyncSession = Depends(get_db)):
    """生成 AI 练习题。

    Example:
        curl -X POST http://localhost:8000/api/v1/ai/exercise \\
             -H 'Content-Type: application/json' \\
             -d '{"unit_ids":[1],"mode":"choice"}'
    """
    svc = ExerciseService(db)
    provider = _build_provider(body)
    try:
        return await svc.generate_exercise(body.unit_ids, body.mode, provider)
    finally:
        if provider:
            await safe_close_provider(provider)


@router.post("/parse-words")
async def parse_words(body: ParseWordsRequest, db: AsyncSession = Depends(get_db)):
    """自然语言解析为单词列表。

    Example:
        curl -X POST http://localhost:8000/api/v1/ai/parse-words \\
             -H 'Content-Type: application/json' \\
             -d '{"text":"apple 苹果，banana 香蕉，How are you 你好吗"}'
    """
    from app.services.nl_parse_service import NLParseService
    svc = NLParseService(db)
    provider = _build_provider(body)
    try:
        return await svc.parse_words(body.text, provider)
    finally:
        if provider:
            await safe_close_provider(provider)
