from datetime import date, datetime, time, timedelta

from sqlalchemy import select
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

    async def get_by_session_word(
        self, session_id: int, word_id: int
    ) -> PracticeRecord | None:
        """查询某会话中某词是否已有作答记录（用于去重，防同一题重复提交刷分）。"""
        stmt = select(PracticeRecord).where(
            PracticeRecord.session_id == session_id,
            PracticeRecord.word_id == word_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_session_word_for_update(
        self, session_id: int, word_id: int
    ) -> PracticeRecord | None:
        """同 get_by_session_word，但加 FOR UPDATE 行锁，供改判端点并发安全使用。
        SQLite 下 with_for_update 为 no-op（单写者串行，测试安全）。
        """
        stmt = (
            select(PracticeRecord)
            .where(
                PracticeRecord.session_id == session_id,
                PracticeRecord.word_id == word_id,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_word_ids_between(
        self, member_id: int, start_date: date, end_date: date,
    ) -> list[int]:
        """返回该 member 在 [start_date, end_date] 区间内 practice_record 出现过的 DISTINCT word_id。

        用于周复习/月复习的题源筛选。用 created_at 区间比较替代 func.DATE()，
        使其命中 created_at 索引（范围 [start_date 00:00, end_date+1 00:00)）。
        """
        start_dt = datetime.combine(start_date, time.min)
        end_excl = datetime.combine(end_date + timedelta(days=1), time.min)
        stmt = (
            select(PracticeRecord.word_id)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .where(
                PracticeSession.member_id == member_id,
                PracticeRecord.created_at >= start_dt,
                PracticeRecord.created_at < end_excl,
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]
