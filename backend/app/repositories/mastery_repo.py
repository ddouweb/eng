from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import MasteryRecord
from app.repositories.base import BaseRepo


class MasteryRepo(BaseRepo[MasteryRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(MasteryRecord, session)

    async def get_by_member_word(
        self, member_id: int, word_id: int
    ) -> MasteryRecord | None:
        stmt = select(MasteryRecord).where(
            MasteryRecord.member_id == member_id,
            MasteryRecord.word_id == word_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, member_id: int, word_id: int) -> MasteryRecord:
        """获取或创建某 (member, word) 的掌握记录。

        用 SAVEPOINT（嵌套事务）包裹插入：并发下若另一事务已先插入同一
        (member, word)（命中唯一约束 uk_member_word_mastery），仅回滚该
        savepoint、回读已有记录，不影响外层事务（如同会话内已 flush 的
        PracticeRecord / correct_count 等改动）。避免 race 导致重复行。
        """
        record = await self.get_by_member_word(member_id, word_id)
        if record is not None:
            return record

        record = MasteryRecord(member_id=member_id, word_id=word_id)
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                # 退出 begin_nested 时自动 flush，触发 INSERT；命中唯一约束则抛
                # IntegrityError 并自动回滚 savepoint。
        except IntegrityError:
            existing = await self.get_by_member_word(member_id, word_id)
            if existing is not None:
                return existing
            raise
        return record
