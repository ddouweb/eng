"""每日签到服务。

- generate_encouragement：取当前学习状态 → AI 生成鼓励/劝学寄语（只读，不落库、不推进 streak）。
- checkin：标记今日活跃（推进 streak + 月度 freeze，**不加 XP**），同日幂等。

设计：把"签到"作为练习之外的另一条"今日活跃"入口——即使当天没做完一整轮练习，
点一下签到也能保住连续记录、避免 🛡️ freeze 白白消耗。寄语与签到两步解耦：寄语是预览，
checkin 接口独立可用（AI 不可用时前端退静态寄语、仍可签到）。
"""
import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.gamification import xp_to_level
from app.models.member import Member
from app.models.streak import MemberStreak
from app.schemas.common import success
from app.services.practice_service import PracticeService
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)


class CheckinService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_encouragement(self, member_id: int) -> dict:
        """生成签到励学寄语（只读，不落库）。

        AI best-effort：成功返回 AI 个性化寄语；失败（限流/不可用）则用**真实学习数据**
        拼出概况兜底——绝不返回空或通用文案，用户始终能看到当前学习情况。
        """
        state = await self.session.get(MemberStreak, member_id)
        member = await self.session.get(Member, member_id)
        # get_overview 不触发周结算（区别于 get_profile），适合只读摘要
        overview = (await StatsService(self.session).get_overview(member_id))["data"]
        dist = overview["mastery_distribution"]

        today = date.today()
        last = state.last_active_date if state else None
        gap = (today - last).days if last else None
        xp = member.total_xp if member else 0
        level = xp_to_level(xp)

        status = "今日已活跃" if gap == 0 else ("首次签到" if gap is None else f"距上次练习 {gap} 天")
        summary = (
            f"连续学习：{state.current_streak if state else 0} 天"
            f"（最长 {state.longest_streak if state else 0}）；"
            f"段位：{level['level_icon']} {level['level_name']}（累计 XP {xp}）；"
            f"掌握度：未学 {dist.get('unlearned', 0)} / 学习中 {dist.get('learning', 0)}"
            f" / 熟悉 {dist.get('familiar', 0)} / 已掌握 {dist.get('permanent', 0)}"
            f"（共 {overview['total_words']} 词，掌握率 {overview['mastery_rate']}%）；"
            f"答题正确率：{overview['accuracy']}%（共 {overview['total_questions']} 题）；"
            f"🛡️ 断签冻结余额：{state.freeze_balance if state else 2} 个；今日状态：{status}。"
        )

        title, message, ai_used = "今日学习情况", "", False
        try:
            result = await get_ai_provider().generate_checkin_encouragement(summary)
            if result.message:
                title, message, ai_used = result.title or "今日寄语", result.message, True
        except Exception as e:  # noqa: BLE001 - 限流/不可用 → 真实数据兜底（不抛错、不阻断）
            logger.warning("checkin encouragement AI failed, use stats fallback: %s", e)
        if not ai_used:
            message = self._stats_fallback(state, member, overview, dist, gap, level)

        return success(data={"title": title, "message": message, "ai_used": ai_used})

    @staticmethod
    def _stats_fallback(state, member, overview, dist, gap, level) -> str:
        """AI 不可用时，用真实学习数据拼一段概况（用户始终能看到当前情况）。"""
        streak = state.current_streak if state else 0
        longest = state.longest_streak if state else 0
        xp = member.total_xp if member else 0
        parts = [
            f"已连续 {streak} 天（最长 {longest}），段位 {level['level_icon']} {level['level_name']}（累计 XP {xp}）。",
            f"掌握度：未学 {dist.get('unlearned', 0)} / 学习中 {dist.get('learning', 0)}"
            f" / 熟悉 {dist.get('familiar', 0)} / 已掌握 {dist.get('permanent', 0)}"
            f"（共 {overview['total_words']} 词，掌握率 {overview['mastery_rate']}%）。",
            f"答题正确率 {overview['accuracy']}%（共 {overview['total_questions']} 题）。",
        ]
        if gap is None:
            parts.append("首次签到，开启你的学习记录吧！")
        elif gap == 0:
            parts.append("今天已活跃，继续保持～")
        else:
            parts.append(f"距上次练习已 {gap} 天，点「确认签到」可保住连续记录、不消耗 🛡️ 冻结！")
        return "".join(parts)

    async def checkin(self, member_id: int) -> dict:
        """确认签到：标记今日活跃（推进 streak + 月度 freeze，不加 XP），同日幂等。

        复用 PracticeService 的 streak 推进纯逻辑（staticmethod，已由 test_gamification 覆盖）：
        先 _maybe_grant_monthly_freeze 再 _advance_streak（顺序与 _apply_gamification 一致，
        保证 freeze 补给先生效、再被断签缺口消耗）。徽章不在签到发（留待下次练习，幂等无碍）。
        """
        state = await self.session.get(MemberStreak, member_id)
        if state is None:
            state = MemberStreak(member_id=member_id)
            self.session.add(state)
            await self.session.flush()
        today = date.today()
        already_active = state.last_active_date == today

        PracticeService._maybe_grant_monthly_freeze(state, today)
        PracticeService._advance_streak(state, today)
        await self.session.commit()

        return success(data={
            "current_streak": state.current_streak,
            "longest_streak": state.longest_streak,
            "freeze_balance": state.freeze_balance,
            "last_active_date": (
                state.last_active_date.isoformat() if state.last_active_date else None
            ),
            # 本次是否为"今日首次活跃"（False=同日重复签到，streak 不变）
            "first_active_today": not already_active,
        })
