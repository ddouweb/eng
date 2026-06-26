from datetime import date

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

    async def get_word_ids_between(
        self, member_id: int, start_date: date, end_date: date,
    ) -> list[int]:
        """返回该 member 在 [start_date, end_date] 区间内 practice_record 出现过的 DISTINCT word_id。

        用于周复习/月复习的题源筛选。
        """
        stmt = (
            select(PracticeRecord.word_id)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .where(
                PracticeSession.member_id == member_id,
                func.DATE(PracticeRecord.created_at) >= start_date,
                func.DATE(PracticeRecord.created_at) <= end_date,
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]
