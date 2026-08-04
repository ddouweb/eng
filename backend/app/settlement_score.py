"""每周结算评分纯函数（无 DB 依赖，便于单测）。

三维 0~100 周分：坚持 45 / 新词 25 / 计划 30。
bonus 只来自坚持+计划（与逐题 XP 不重叠），封顶 30/周。
（原「难度」维已移除：它依赖 wrong_count≥2 的卡壳词，反向激励故意答错。）

数据源由 StatsRepo 的周聚合查询提供（见 stats_repo.get_week_*）；
本模块只做算术，不碰 DB。
"""
import math
from datetime import date, timedelta

from app.cash import CASH_WEEKLY_CAP, WEEKLY_CASH_TIERS, CashTier
from app.schemas.plan import parse_learn_weekdays
from app.services.plan_service import _count_learn_days

# bonus 硬上限/周（防通胀）。
BONUS_XP_CAP = 30
# bonus 低于此值不发（杜绝无意义小奖励）。
BONUS_XP_MIN = 5
# 三维满分（合计 100）：坚持 45 / 新词 25 / 计划 30。
# bonus 仅由坚持+计划派生（分母 = LOGIN_FULL + PLAN_FULL = 75）。
LOGIN_FULL = 45
NEW_FULL = 25
PLAN_FULL = 30


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_login(active_days: int, expected_days: int) -> int:
    """坚持分（0~45）：本周真实学习日 / 应学日数。expected_days<=0 按 7 计。"""
    denom = expected_days if expected_days and expected_days > 0 else 7
    return int(round(LOGIN_FULL * _clamp(active_days / denom, 0.0, 1.0)))


def score_new(new_words: int, target: int) -> int:
    """新词分（0~25）：本周首考新词 / 周目标。target<=0 按 1 计。"""
    denom = target if target and target > 0 else 1
    return int(round(NEW_FULL * _clamp(new_words / denom, 0.0, 1.0)))


def score_plan(completed_slots: int, planned_slots: int) -> int:
    """计划分（0~30）：完成槽位 / 计划槽位。分母<=0 → 0。"""
    if planned_slots <= 0:
        return 0
    return int(round(PLAN_FULL * _clamp(completed_slots / planned_slots, 0.0, 1.0)))


def compute_bonus(login_score: int, plan_score: int) -> int:
    """bonus XP = round((坚持+计划)/(45+30)*30)，封顶 30，<5→0。

    仅坚持+计划两维（逐题 XP 已付新词，不重复）。
    """
    bonus = int(round((login_score + plan_score) / (LOGIN_FULL + PLAN_FULL) * BONUS_XP_CAP))
    bonus = int(_clamp(bonus, 0, BONUS_XP_CAP))
    return 0 if bonus < BONUS_XP_MIN else bonus


def compute_weekly_cash(
    stars: int,
    plan_completion: float,
    tiers: list[CashTier] | None = None,
    cap: float = CASH_WEEKLY_CAP,
) -> tuple[float, str | None]:
    """周学习现金（分档制）。返回 (round(amount,2), tier_label)。

    按 tiers 顺序找第一条 (stars>=min_stars AND plan_completion>=min_completion) 命中档；
    都不命中（≤2星）→ (0.0, None)。amount 再 clamp 到 cap（双保险），round(2) 防浮点漂移。

    刻意不与 compute_bonus 共用公式：cash 是阶跃分档、bonus 是线性比例，两套规则独立可调
    （运维改一档不影响 XP 曲线）。tiers 默认取 cash.WEEKLY_CASH_TIERS（settings 驱动），测试可传 override。
    """
    use = tiers if tiers is not None else WEEKLY_CASH_TIERS
    for t in use:
        if stars >= t.min_stars and plan_completion >= t.min_completion:
            return (round(min(t.amount, cap), 2), t.label)
    return (0.0, None)


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
