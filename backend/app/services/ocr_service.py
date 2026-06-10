import os
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import OCRResult
from app.ai.factory import get_ai_provider
from app.schemas.common import error, success
from app.services.word_service import WordService

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

_drafts: dict[int, list[dict]] = {}


class OCRService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.word_service = WordService(session)

    async def upload_and_parse(
        self, unit_id: int, image_bytes: bytes, filename: str
    ) -> dict:
        from app.repositories.unit_repo import UnitRepo
        unit_repo = UnitRepo(self.session)
        unit = await unit_repo.get_by_id(unit_id)
        if not unit:
            return error(code=404, message="Unit not found")

        saved_name = f"unit_{unit_id}_{uuid.uuid4().hex[:8]}_{filename}"
        saved_path = UPLOAD_DIR / saved_name
        saved_path.write_bytes(image_bytes)

        image_url = f"/uploads/{saved_name}"

        try:
            provider = get_ai_provider()
            ocr_result: OCRResult = await provider.parse_image(image_bytes, filename)
        except Exception as e:
            return error(code=500, message=f"OCR failed: {e}")

        draft_words = [
            {"english": w.english, "chinese": w.chinese, "type": w.word_type}
            for w in ocr_result.words
        ]
        _drafts[unit_id] = draft_words

        await unit_repo.update(unit, {"image_url": image_url})
        await self.session.commit()

        return success(data={
            "unit_id": unit_id,
            "image_url": image_url,
            "draft_words": draft_words,
            "parsed_count": len(draft_words),
        })

    async def get_ocr_result(self, unit_id: int) -> dict:
        draft = _drafts.get(unit_id, [])
        return success(data={
            "unit_id": unit_id,
            "draft_words": draft,
            "parsed_count": len(draft),
            "confirmed": unit_id not in _drafts,
        })

    async def confirm_ocr(self, unit_id: int, words: list[dict]) -> dict:
        from app.repositories.unit_repo import UnitRepo
        unit_repo = UnitRepo(self.session)
        unit = await unit_repo.get_by_id(unit_id)
        if not unit:
            return error(code=404, message="Unit not found")

        result = await self.word_service.batch_create(unit_id, words)
        _drafts.pop(unit_id, None)
        return result
