from datetime import date, datetime, time, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel
from app.models.mastery import MasteryRecord
from app.models.practice import PracticeSession
from app.models.word import Word


class StatsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_mastery_distribution(self, member_id: int) -> dict[str, int]:
        # LEFT JOIN Word → MasteryRecord：从未练过的词无记录，COALESCE 计为 unlearned，
        # 使分布的 unlearned 桶如实反映"未学"词数（原先几乎恒为 0，与 mastery_rate 口径矛盾）。
        level_expr = func.coalesce(MasteryRecord.level, MasteryLevel.unlearned).label("level")
        stmt = (
            select(level_expr, func.count())
            .select_from(Word)
            .outerjoin(
                MasteryRecord,
                (MasteryRecord.word_id == Word.id) & (MasteryRecord.member_id == member_id),
            )
            .group_by(level_expr)
        )
        result = await self.session.execute(stmt)
        counts: dict[str, int] = {}
        for row in result.all():
            lvl = row[0]
            key = lvl.value if hasattr(lvl, "value") else str(lvl)
            counts[key] = row[1]
        for level in ("unlearned", "learning", "familiar", "permanent"):
            counts.setdefault(level, 0)
        return counts

    async def get_mastery_by_unit(self, member_id: int, unit_id: int) -> dict[str, int]:
        # 同上：按 unit 范围 LEFT JOIN，未练过的词计 unlearned
        level_expr = func.coalesce(MasteryRecord.level, MasteryLevel.unlearned).label("level")
        stmt = (
            select(level_expr, func.count())
            .select_from(Word)
            .outerjoin(
                MasteryRecord,
                (MasteryRecord.word_id == Word.id) & (MasteryRecord.member_id == member_id),
            )
            .where(Word.unit_id == unit_id)
            .group_by(level_expr)
        )
        result = await self.session.execute(stmt)
        counts: dict[str, int] = {}
        for row in result.all():
            lvl = row[0]
            key = lvl.value if hasattr(lvl, "value") else str(lvl)
            counts[key] = row[1]
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
        since_dt = datetime.combine(date.today() - timedelta(days=days), time.min)
        day_col = func.date(PracticeSession.started_at).label("day")
        stmt = (
            select(
                day_col,
                func.sum(PracticeSession.total_count).label("total"),
                func.sum(PracticeSession.correct_count).label("correct"),
            )
            .where(
                PracticeSession.member_id == member_id,
                PracticeSession.started_at >= since_dt,
            )
            .group_by(func.date(PracticeSession.started_at))
            .order_by(func.date(PracticeSession.started_at))
        )
        result = await self.session.execute(stmt)
        rows = []
        for row in result.all():
            d = row[0]
            if isinstance(d, str):
                d = date.fromisoformat(d)
            rows.append({"date": str(d), "total": int(row[1]), "correct": int(row[2])})
        return rows

    async def get_streak(self, member_id: int) -> int:
        stmt = (
            select(func.date(PracticeSession.started_at).label("day"))
            .where(PracticeSession.member_id == member_id)
            .group_by(func.date(PracticeSession.started_at))
            .order_by(func.date(PracticeSession.started_at).desc())
            .limit(400)
        )
        result = await self.session.execute(stmt)
        days = set()
        for row in result.all():
            d = row[0]
            if isinstance(d, str):
                d = date.fromisoformat(d)
            days.add(d)
        if not days:
            return 0

        streak = 0
        check = date.today()
        if check not in days:
            check -= timedelta(days=1)
        while check in days:
            streak += 1
            check -= timedelta(days=1)
        return streak
