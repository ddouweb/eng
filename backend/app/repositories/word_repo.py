from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import MasteryLevel, TagType, WordType
from app.models.mastery import MasteryRecord
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

    async def search(
        self, *,
        q: str | None = None,
        member_id: int = 1,
        tag: TagType | None = None,
        level: MasteryLevel | None = None,
        unit_id: int | None = None,
        word_type: WordType | None = None,
        page: int = 1,
        page_size: int = 50,
    ):
        """跨 Unit 全局搜索单词。

        - q：对 english/chinese 做 icontains（自动转义 % _ 、可移植，免依赖默认排序规则）。
        - tag：相关 EXISTS（标签非 member 级，仅按 word_id 关联）。
        - level：member 级掌握度，依赖 ``uk_member_word_mastery`` 唯一约束 —— 每个 (member,word)
          至多一条记录，故 "level == unlearned" 等价于 "不存在非 unlearned 的记录"
          （含"无记录"与"记录为 unlearned"两种情况）。
        """
        stmt = (
            select(Word)
            .options(
                selectinload(Word.unit),
                selectinload(Word.tags),
                selectinload(Word.mastery_records),
            )
            .order_by(Word.english, Word.id)
        )
        q = (q or "").strip()
        if q:
            # autoescape=True：把用户输入里的 % 和 _ 当字面量而非 LIKE 通配符。
            stmt = stmt.where(or_(
                Word.english.icontains(q, autoescape=True),
                Word.chinese.icontains(q, autoescape=True),
            ))
        if tag is not None:
            stmt = stmt.where(
                exists(select(WordTag.word_id).where(
                    WordTag.word_id == Word.id, WordTag.tag == tag,
                ))
            )
        if level is not None:
            if level == MasteryLevel.unlearned:
                stmt = stmt.where(
                    ~exists(select(MasteryRecord.id).where(
                        MasteryRecord.member_id == member_id,
                        MasteryRecord.word_id == Word.id,
                        MasteryRecord.level != MasteryLevel.unlearned,
                    ))
                )
            else:
                stmt = stmt.where(
                    exists(select(MasteryRecord.id).where(
                        MasteryRecord.member_id == member_id,
                        MasteryRecord.word_id == Word.id,
                        MasteryRecord.level == level,
                    ))
                )
        if unit_id is not None:
            stmt = stmt.where(Word.unit_id == unit_id)
        if word_type is not None:
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
