"""每周结算评分纯函数（无 DB 依赖，便于单测）。

四维 0~100 周分：坚持 25 / 难度 25 / 新词 20 / 计划 30。
bonus 只来自坚持+计划（与逐题难度 XP 不重叠），封顶 30/周。

数据源由 StatsRepo 的周聚合查询提供（见 stats_repo.get_week_*）；
本模块只做算术，不碰 DB。
"""
import math
from datetime import date, timedelta

from app.schemas.plan import parse_learn_weekdays
from app.services.plan_service import _count_learn_days

# bonus 硬上限/周（防通胀）。
BONUS_XP_CAP = 30
# bonus 低于此值不发（杜绝无意义小奖励）。
BONUS_XP_MIN = 5
# 坚持分满分 / 计划分满分（bonus 仅由这两维派生）。
LOGIN_FULL = 25
PLAN_FULL = 30
# 难度维基线：难词占答对词比例达此值即满分。
HARD_SHARE_BASELINE = 0.6


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_login(active_days: int, expected_days: int) -> int:
    """坚持分（0~25）：本周真实学习日 / 应学日数。expected_days<=0 按 7 计。"""
    denom = expected_days if expected_days and expected_days > 0 else 7
    return int(round(LOGIN_FULL * _clamp(active_days / denom, 0.0, 1.0)))


def score_difficulty(hard_words: int, correct_words: int) -> int:
    """难度分（0~25）：难词占答对词比例 / 0.6 基线。

    难词由 stats_repo 判定（wrong_count≥2 AND ease_factor<2.3，高置信"卡壳词"）。
    correct_words<=0 → 0。
    """
    if correct_words <= 0:
        return 0
    share = hard_words / correct_words
    return int(round(25 * _clamp(share / HARD_SHARE_BASELINE, 0.0, 1.0)))


def score_new(new_words: int, target: int) -> int:
    """新词分（0~20）：本周首考新词 / 周目标。target<=0 按 1 计。"""
    denom = target if target and target > 0 else 1
    return int(round(20 * _clamp(new_words / denom, 0.0, 1.0)))


def score_plan(completed_slots: int, planned_slots: int) -> int:
    """计划分（0~30）：完成槽位 / 计划槽位。分母<=0 → 0。"""
    if planned_slots <= 0:
        return 0
    return int(round(PLAN_FULL * _clamp(completed_slots / planned_slots, 0.0, 1.0)))


def compute_bonus(login_score: int, plan_score: int) -> int:
    """bonus XP = round((坚持+计划)/(25+30)*30)，封顶 30，<5→0。

    仅坚持+计划两维（实时 XP 已付难度/新词，不重复）。
    """
    bonus = int(round((login_score + plan_score) / (LOGIN_FULL + PLAN_FULL) * BONUS_XP_CAP))
    bonus = int(_clamp(bonus, 0, BONUS_XP_CAP))
    return 0 if bonus < BONUS_XP_MIN else bonus


def compute_stars(total_score: int) -> int:
    """0~5 星 = round(总分/20)，clamp[0,5]。"""
    return int(_clamp(round(total_score / 20.0), 0, 5))


def expected_learn_days(weekdays_raw: str | None, ws: date, we: date) -> int:
    """本周 [ws,we] 内落 learn_weekdays 的学习日数。"""
    weekdays = parse_learn_weekdays(weekdays_raw)
    return _count_learn_days(ws, we, weekdays)


def plan_health(
    total_words: int,
    mastered: int,
    deadline: date | None,
    daily_goal: int,
    weekdays_raw: str | None,
    today: date,
) -> dict:
    """只读计划体检：剩余词 / 剩余学习日 / 预计完成日 / on_track / 建议日新词。

    无 deadline → 仅返回 remaining_unmastered，其余 None。
    """
    remaining_unmastered = max(total_words - mastered, 0)
    base = {"remaining_unmastered": remaining_unmastered}
    if deadline is None:
        return {**base, "remaining_learn_days": None, "projected_finish": None,
                "on_track": None, "suggested_daily_goal": None}
    weekdays = parse_learn_weekdays(weekdays_raw)
    remaining_learn_days = _count_learn_days(today + timedelta(days=1), deadline, weekdays)
    suggested = (
        math.ceil(remaining_unmastered / remaining_learn_days)
        if remaining_learn_days > 0 else None
    )
    pace = max(daily_goal, 1)
    projected_finish = (
        today + timedelta(days=math.ceil(remaining_unmastered / pace))
        if remaining_unmastered > 0 else today
    )
    return {
        **base,
        "remaining_learn_days": remaining_learn_days,
        "projected_finish": projected_finish.isoformat(),
        "on_track": projected_finish <= deadline,
        "suggested_daily_goal": suggested,
    }
