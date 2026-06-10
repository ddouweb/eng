from sqlalchemy import select
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
        record = await self.get_by_member_word(member_id, word_id)
        if record is None:
            record = MasteryRecord(member_id=member_id, word_id=word_id)
            self.session.add(record)
            await self.session.flush()
        return record
