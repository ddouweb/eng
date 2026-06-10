from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.practice import PracticeRecord, PracticeSession
from app.repositories.base import BaseRepo


class PracticeSessionRepo(BaseRepo[PracticeSession]):
    def __init__(self, session: AsyncSession):
        super().__init__(PracticeSession, session)


class PracticeRecordRepo(BaseRepo[PracticeRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(PracticeRecord, session)

    async def get_by_session(self, session_id: int) -> list[PracticeRecord]:
        stmt = (
            select(PracticeRecord)
            .where(PracticeRecord.session_id == session_id)
            .order_by(PracticeRecord.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
