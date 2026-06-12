from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.schemas.common import success
from app.schemas.exceptions import AppException


class NLParseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def parse_words(self, text: str, provider: "AIProvider | None" = None) -> dict:
        p = provider or get_ai_provider()
        try:
            result = await p.parse_natural_language(text)
        except Exception as e:
            raise AppException(500, f"AI 解析失败: {e}") from e

        draft_words = [
            {"english": w.english, "chinese": w.chinese, "type": w.word_type}
            for w in result.words
        ]
        return success(data={"draft_words": draft_words, "parsed_count": len(draft_words)})
