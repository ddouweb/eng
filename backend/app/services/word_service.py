from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TagType, WordType
from app.models.word import Word, WordTag
from app.repositories.mastery_repo import MasteryRepo
from app.repositories.word_repo import WordRepo
from app.schemas.common import error, success
from app.schemas.exceptions import AppException


class WordService:
    def __init__(self, session: AsyncSession):
        self.repo = WordRepo(session)
        self.mastery_repo = MasteryRepo(session)
        self.session = session

    async def batch_create(self, unit_id: int, words_data: list[dict]) -> dict:
        words = [Word(unit_id=unit_id, **d) for d in words_data]
        words = await self.repo.batch_create(words)
        await self.session.commit()
        for w in words:
            await self.session.refresh(w)
        return success(data={
            "created_count": len(words),
            "words": [self._to_dict(w) for w in words],
        })

    async def get_by_unit(
        self, unit_id: int, page: int = 1, page_size: int = 50,
        word_type: WordType | None = None
    ) -> dict:
        words, total = await self.repo.get_by_unit(
            unit_id, page=page, page_size=page_size, word_type=word_type
        )
        items = []
        for w in words:
            d = self._to_dict(w)
            d["tags"] = [t.tag.value for t in w.tags]
            d["mastery"] = self._mastery_from_record(w.mastery_records)
            items.append(d)
        return success(data={"items": items, "total": total, "page": page, "page_size": page_size})

    async def update_word(self, word_id: int, data: dict) -> dict:
        word = await self.repo.get_by_id(word_id)
        if not word:
            raise AppException(404, "Word not found")
        word = await self.repo.update(word, data)
        await self.session.commit()
        await self.session.refresh(word)
        return success(data=self._to_dict(word))

    async def delete_word(self, word_id: int) -> dict:
        word = await self.repo.get_by_id(word_id)
        if not word:
            raise AppException(404, "Word not found")
        await self.repo.delete(word)
        await self.session.commit()
        return success(message="Word deleted")

    async def set_tags(self, word_id: int, tags: list[str]) -> dict:
        word = await self.repo.get_by_id(word_id)
        if not word:
            raise AppException(404, "Word not found")
        tag_enums = [TagType(t) for t in tags]
        await self.repo.set_tags(word_id, tag_enums)
        await self.session.commit()
        return success(data={"word_id": word_id, "tags": tags})

    async def remove_tag(self, word_id: int, tag: str) -> dict:
        word = await self.repo.get_by_id(word_id)
        if not word:
            raise AppException(404, "Word not found")
        try:
            tag_enum = TagType(tag)
        except (ValueError, KeyError):
            raise AppException(400, f"Invalid tag: {tag}")
        removed = await self.repo.remove_tag(word_id, tag_enum)
        if not removed:
            raise AppException(404, f"Tag {tag} not found on word {word_id}")
        await self.session.commit()
        return success(message=f"Tag {tag} removed")

    async def get_mastery(self, word_id: int, member_id: int = 1) -> dict:
        word = await self.repo.get_by_id(word_id)
        if not word:
            raise AppException(404, "Word not found")
        record = await self.mastery_repo.get_or_create(member_id, word_id)
        await self.session.commit()
        return success(data={
            "word_id": word_id,
            "member_id": member_id,
            "level": record.level.value,
            "consecutive_correct": record.consecutive_correct,
            "correct_count": record.correct_count,
            "wrong_count": record.wrong_count,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        })

    @staticmethod
    def _mastery_from_record(records: list, member_id: int = 1) -> dict | None:
        for r in records:
            if r.member_id == member_id:
                return {
                    "level": r.level.value,
                    "consecutive_correct": r.consecutive_correct,
                    "correct_count": r.correct_count,
                    "wrong_count": r.wrong_count,
                }
        return None

    def _to_dict(self, word: Word) -> dict:
        return {
            "id": word.id,
            "unit_id": word.unit_id,
            "english": word.english,
            "chinese": word.chinese,
            "type": word.type.value,
            "seq": word.seq,
            "created_at": word.created_at.isoformat() if word.created_at else None,
            "updated_at": word.updated_at.isoformat() if word.updated_at else None,
        }
