from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.models.word import Word
from app.schemas.common import success
from app.schemas.exceptions import AppException


class ExerciseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_dialogue(self, unit_ids: list[int], scenario: str) -> dict:
        words = await self._get_words(unit_ids)
        if not words:
            raise AppException(400, "没有可用的单词")

        p = get_ai_provider()
        result = await p.generate_dialogue(words, scenario)

        return success(data={
            "scenario": result.scenario,
            "lines": [
                {"role": l.role, "english": l.english, "chinese": l.chinese}
                for l in result.lines
            ],
        })

    async def generate_exercise(self, unit_ids: list[int], mode: str) -> dict:
        words = await self._get_words(unit_ids)
        if not words:
            raise AppException(400, "没有可用的单词")

        p = get_ai_provider()
        result = await p.generate_exercise(words, mode)

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
