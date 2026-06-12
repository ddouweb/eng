from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import MasteryRecord
from app.models.practice import PracticeSession


class LeaderboardRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_total_word_count(self) -> int:
        from app.models.word import Word
        result = await self.session.execute(select(func.count(Word.id)))
        return result.scalar() or 0

    async def get_mastery_by_member(self) -> dict[int, dict[str, int]]:
        """每个 member 的 mastery 分布: {member_id: {level: count}}."""
        levels = ["unlearned", "learning", "familiar", "permanent"]
        result = await self.session.execute(
            select(MasteryRecord.member_id, MasteryRecord.level, func.count(MasteryRecord.id))
            .group_by(MasteryRecord.member_id, MasteryRecord.level)
        )
        data: dict[int, dict[str, int]] = {}
        for member_id, level, count in result.all():
            data.setdefault(member_id, {lv: 0 for lv in levels})
            data[member_id][level] = count
        return data

    async def get_practice_by_member(self) -> dict[int, dict]:
        """每个 member 的练习统计."""
        result = await self.session.execute(
            select(
                PracticeSession.member_id,
                func.count(PracticeSession.id),
                func.coalesce(func.sum(PracticeSession.total_count), 0),
                func.coalesce(func.sum(PracticeSession.correct_count), 0),
            )
            .where(PracticeSession.ended_at.isnot(None))
            .group_by(PracticeSession.member_id)
        )
        data: dict[int, dict] = {}
        for member_id, sessions, total_q, total_c in result.all():
            data[member_id] = {
                "session_count": sessions,
                "total_questions": int(total_q),
                "total_correct": int(total_c),
            }
        return data

    async def get_streak_by_member(self) -> dict[int, int]:
        """每个 member 的连续学习天数 (兼容 MySQL 和 SQLite)."""
        # Use DATE() which works on both MySQL and SQLite for datetime columns
        result = await self.session.execute(
            select(
                PracticeSession.member_id,
                func.date(PracticeSession.started_at).label("d"),
            )
            .where(PracticeSession.started_at >= date.today() - timedelta(days=400))
            .group_by(PracticeSession.member_id, func.date(PracticeSession.started_at))
            .order_by(PracticeSession.member_id)
        )
        member_dates: dict[int, set[date]] = {}
        for member_id, d in result.all():
            # func.date() returns date on MySQL, str on SQLite — normalize
            if isinstance(d, str):
                d = date.fromisoformat(d)
            member_dates.setdefault(member_id, set()).add(d)

        streaks: dict[int, int] = {}
        for member_id, dates in member_dates.items():
            streak = 0
            check = date.today()
            if check not in dates:
                check -= timedelta(days=1)
            while check in dates:
                streak += 1
                check -= timedelta(days=1)
            streaks[member_id] = streak
        return streaks
