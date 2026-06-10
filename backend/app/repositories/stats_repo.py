from datetime import date, timedelta

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, TaskStatus
from app.models.mastery import MasteryRecord
from app.models.plan import DailyTask, LearningPlan
from app.models.practice import PracticeSession
from app.models.word import Word


class StatsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_mastery_distribution(self, member_id: int) -> dict[str, int]:
        stmt = (
            select(MasteryRecord.level, func.count())
            .where(MasteryRecord.member_id == member_id)
            .group_by(MasteryRecord.level)
        )
        result = await self.session.execute(stmt)
        counts = {row[0].value: row[1] for row in result.all()}
        for level in ("unlearned", "learning", "familiar", "permanent"):
            counts.setdefault(level, 0)
        return counts

    async def get_mastery_by_unit(self, member_id: int, unit_id: int) -> dict[str, int]:
        stmt = (
            select(MasteryRecord.level, func.count())
            .join(Word, Word.id == MasteryRecord.word_id)
            .where(MasteryRecord.member_id == member_id, Word.unit_id == unit_id)
            .group_by(MasteryRecord.level)
        )
        result = await self.session.execute(stmt)
        counts = {row[0].value: row[1] for row in result.all()}
        for level in ("unlearned", "learning", "familiar", "permanent"):
            counts.setdefault(level, 0)
        return counts

    async def get_total_word_count(self, unit_id: int | None = None) -> int:
        stmt = select(func.count()).select_from(Word)
        if unit_id is not None:
            stmt = stmt.where(Word.unit_id == unit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_practice_summary(self, member_id: int) -> dict:
        stmt = select(
            func.count(PracticeSession.id),
            func.coalesce(func.sum(PracticeSession.total_count), 0),
            func.coalesce(func.sum(PracticeSession.correct_count), 0),
        ).where(PracticeSession.member_id == member_id, PracticeSession.ended_at.isnot(None))
        result = await self.session.execute(stmt)
        row = result.one()
        return {"session_count": row[0], "total_questions": row[1], "total_correct": row[2]}

    async def get_recent_practice_daily(self, member_id: int, days: int = 30) -> list[dict]:
        since = date.today() - timedelta(days=days)
        stmt = (
            select(
                func.date(PracticeSession.started_at).label("day"),
                func.sum(PracticeSession.total_count).label("total"),
                func.sum(PracticeSession.correct_count).label("correct"),
            )
            .where(
                PracticeSession.member_id == member_id,
                func.date(PracticeSession.started_at) >= since,
            )
            .group_by("day")
            .order_by("day")
        )
        result = await self.session.execute(stmt)
        return [
            {"date": str(row[0]), "total": int(row[1]), "correct": int(row[2])}
            for row in result.all()
        ]

    async def get_streak(self, member_id: int) -> int:
        stmt = (
            select(func.date(PracticeSession.started_at).label("day"))
            .where(PracticeSession.member_id == member_id)
            .group_by("day")
            .order_by("day")
        )
        result = await self.session.execute(stmt)
        days = [row[0] for row in result.all()]
        if not days:
            return 0

        streak = 0
        today = date.today()
        check = today
        if check not in days:
            check = today - timedelta(days=1)
        while check in days:
            streak += 1
            check -= timedelta(days=1)
        return streak
