from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gamification import xp_to_level
from app.models.member import Member
from app.models.streak import MemberBadge, MemberStreak
from app.repositories.stats_repo import StatsRepo
from app.schemas.common import success


class StatsService:
    def __init__(self, session: AsyncSession):
        self.repo = StatsRepo(session)
        self.session = session

    async def get_overview(self, member_id: int) -> dict:
        dist = await self.repo.get_mastery_distribution(member_id)
        total_words = await self.repo.get_total_word_count()
        practice = await self.repo.get_practice_summary(member_id)
        streak = await self.repo.get_streak(member_id)

        mastered = min(dist["familiar"] + dist["permanent"], total_words)
        total_answered = practice["total_questions"]
        total_correct = practice["total_correct"]
        accuracy = round(total_correct / total_answered * 100, 1) if total_answered > 0 else 0.0

        return success(data={
            "total_words": total_words,
            "mastery_distribution": dist,
            "mastered_count": mastered,
            "mastery_rate": round(mastered / total_words * 100, 1) if total_words > 0 else 0.0,
            "practice_session_count": practice["session_count"],
            "total_questions": total_answered,
            "total_correct": total_correct,
            "accuracy": accuracy,
            "streak_days": streak,
        })

    async def get_unit_stats(self, member_id: int, unit_id: int) -> dict:
        dist = await self.repo.get_mastery_by_unit(member_id, unit_id)
        total = await self.repo.get_total_word_count(unit_id)
        mastered = dist["familiar"] + dist["permanent"]
        return success(data={
            "unit_id": unit_id,
            "total_words": total,
            "mastery_distribution": dist,
            "mastered_count": mastered,
            "mastery_rate": round(mastered / total * 100, 1) if total > 0 else 0.0,
        })

    async def get_trend(self, member_id: int, days: int = 30) -> dict:
        daily = await self.repo.get_recent_practice_daily(member_id, days)
        return success(data={
            "days": days,
            "daily": daily,
        })

    async def get_profile(self, member_id: int) -> dict:
        """首页坚持机制卡片：streak / freeze / XP 段位 / 徽章。"""
        state = await self.session.get(MemberStreak, member_id)
        member = await self.session.get(Member, member_id)
        xp = member.total_xp if member else 0
        stmt = select(MemberBadge.badge_key).where(MemberBadge.member_id == member_id)
        badges = [r[0] for r in (await self.session.execute(stmt)).all()]
        return success(data={
            "current_streak": state.current_streak if state else 0,
            "longest_streak": state.longest_streak if state else 0,
            "freeze_balance": state.freeze_balance if state else 2,
            "last_active_date": (
                state.last_active_date.isoformat() if state and state.last_active_date else None
            ),
            "total_xp": xp,
            "level": xp_to_level(xp),
            "badges": badges,
        })
