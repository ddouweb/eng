from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit import Unit
from app.models.word import Word
from app.repositories.base import BaseRepo


class UnitRepo(BaseRepo[Unit]):
    def __init__(self, session: AsyncSession):
        super().__init__(Unit, session)

    async def get_with_word_counts(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[tuple[Unit, int]], int]:
        base_stmt = select(Unit).order_by(Unit.sequence)
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(Unit, func.count(Word.id).label("word_count"))
            .outerjoin(Word, Word.unit_id == Unit.id)
            .group_by(Unit.id)
            .order_by(Unit.sequence)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [(row[0], row[1]) for row in rows], total

    async def get_by_sequence(self, sequence: int) -> Unit | None:
        stmt = select(Unit).where(Unit.sequence == sequence)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
