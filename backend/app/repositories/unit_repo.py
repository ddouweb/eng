from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit import Unit
from app.repositories.base import BaseRepo


class UnitRepo(BaseRepo[Unit]):
    def __init__(self, session: AsyncSession):
        super().__init__(Unit, session)

    async def get_word_count(self, unit_id: int) -> int:
        from app.models.word import Word

        stmt = select(func.count()).where(Word.unit_id == unit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_sequence(self, sequence: int) -> Unit | None:
        stmt = select(Unit).where(Unit.sequence == sequence)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
