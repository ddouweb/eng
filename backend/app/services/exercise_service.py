from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.models.word import Word
from app.schemas.common import success
from app.schemas.exceptions import AppException

logger = logging.getLogger(__name__)


class ExerciseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_dialogue(self, unit_ids: list[int], scenario: str) -> dict:
        words = await self._get_words(unit_ids)
        if not words:
            raise AppException(400, "没有可用的单词")

        p = get_ai_provider()
        try:
            result = await p.generate_dialogue(words, scenario)
        except Exception as e:  # noqa: BLE001 - AI 限流/不可用 → 友好报错而非裸 500
            logger.warning("AI generate_dialogue failed: %s", e)
            raise AppException(503, "AI 服务暂不可用（可能限流或额度不足），请稍后重试")

        return success(data={
            "scenario": result.scenario,
            "lines": [
                {"role": line.role, "english": line.english, "chinese": line.chinese}
                for line in result.lines
            ],
        })

    async def generate_exercise(self, unit_ids: list[int], mode: str) -> dict:
        words = await self._get_words(unit_ids)
        if not words:
            raise AppException(400, "没有可用的单词")

        p = get_ai_provider()
        try:
            result = await p.generate_exercise(words, mode)
        except Exception as e:  # noqa: BLE001 - AI 限流/不可用 → 友好报错而非裸 500
            logger.warning("AI generate_exercise failed: %s", e)
            raise AppException(503, "AI 服务暂不可用（可能限流或额度不足），请稍后重试")

        return success(data={
            "mode": result.mode,
            "items": [
                {
                    "question": item.question,
                    "options": item.options,
                    "answer": item.answer,
                    "explanation": item.explanation,
                }
                for item in result.items
            ],
        })

    async def _get_words(self, unit_ids: list[int]) -> list[str]:
        stmt = select(Word.english).where(Word.unit_id.in_(unit_ids))
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]
