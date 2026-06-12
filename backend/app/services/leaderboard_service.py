from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.leaderboard_repo import LeaderboardRepo
from app.repositories.member_repo import MemberRepo
from app.schemas.common import success


class LeaderboardService:
    def __init__(self, session: AsyncSession):
        self.member_repo = MemberRepo(session)
        self.repo = LeaderboardRepo(session)

    async def get_leaderboard(self) -> dict:
        members = await self.member_repo.get_all()
        total_words = await self.repo.get_total_word_count()
        mastery_map = await self.repo.get_mastery_by_member()
        practice_map = await self.repo.get_practice_by_member()
        streak_map = await self.repo.get_streak_by_member()

        levels = ["unlearned", "learning", "familiar", "permanent"]
        rows = []
        for m in members:
            dist = mastery_map.get(m.id, {lv: 0 for lv in levels})
            mastered = dist.get("familiar", 0) + dist.get("permanent", 0)
            # Cap mastered at total_words to avoid >100% from orphan mastery records
            mastered = min(mastered, total_words)
            practice = practice_map.get(m.id, {"session_count": 0, "total_questions": 0, "total_correct": 0})
            total_q = practice["total_questions"]
            total_c = practice["total_correct"]

            rows.append({
                "member_id": m.id,
                "name": m.name,
                "avatar": m.avatar,
                "total_words": total_words,
                "mastered_count": mastered,
                "mastery_rate": round(mastered / total_words * 100, 1) if total_words > 0 else 0.0,
                "session_count": practice["session_count"],
                "total_questions": total_q,
                "total_correct": total_c,
                "accuracy": round(total_c / total_q * 100, 1) if total_q > 0 else 0.0,
                "streak_days": streak_map.get(m.id, 0),
                "mastery_distribution": dist,
            })

        rows.sort(key=lambda r: (r["mastered_count"], r["accuracy"], r["streak_days"]), reverse=True)
        return success(data={"members": rows})
