from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import TagType, WordType
from app.models.word import Word, WordTag
from app.repositories.base import BaseRepo


class WordRepo(BaseRepo[Word]):
    def __init__(self, session: AsyncSession):
        super().__init__(Word, session)

    async def get_by_unit(
        self, unit_id: int, *, page: int = 1, page_size: int = 50,
        word_type: WordType | None = None
    ):
        stmt = (
            select(Word)
            .where(Word.unit_id == unit_id)
            .options(selectinload(Word.tags), selectinload(Word.mastery_records))
            .order_by(Word.seq.is_(None), Word.seq, Word.id)
        )
        if word_type:
            stmt = stmt.where(Word.type == word_type)
        return await self.get_paginated(stmt, page=page, page_size=page_size)

    async def batch_create(self, words: list[Word]) -> list[Word]:
        self.session.add_all(words)
        await self.session.flush()
        return words

    async def set_tags(self, word_id: int, tags: list[TagType]) -> list[WordTag]:
        await self.session.execute(
            WordTag.__table__.delete().where(WordTag.word_id == word_id)
        )
        new_tags = [WordTag(word_id=word_id, tag=t) for t in tags]
        self.session.add_all(new_tags)
        await self.session.flush()
        return new_tags

    async def remove_tag(self, word_id: int, tag: TagType) -> bool:
        stmt = select(WordTag).where(WordTag.word_id == word_id, WordTag.tag == tag)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await self.session.delete(existing)
            await self.session.flush()
            return True
        return False

    async def get_tags(self, word_id: int) -> list[TagType]:
        stmt = select(WordTag.tag).where(WordTag.word_id == word_id)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]
