"""现金激励（Cash Incentive）纯定义：周现金分档 + 里程碑阈值 + 候选生成。

仅含常量与纯函数，无 DB/ORM 依赖（镜像 gamification.py 的分层规则——"仅含常量与纯函数"）。
- settlement_score.compute_weekly_cash 用 WEEKLY_CASH_TIERS + CASH_WEEKLY_CAP；
- StatsService._maybe_grant_milestones 用 build_milestone_candidates 生成候选。

金额默认值由 settings（.env）在模块导入期注入一次（改 .env 需重启）。为保持纯函数可单测，
compute_weekly_cash / build_milestone_candidates 均接受覆盖入参，测试可不依赖 settings。

防通胀：周现金奖「每周质量」、里程碑奖「离散成就」，奖励不同维度、不重复支付。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class CashTier:
    """周现金分档：命中 (stars >= min_stars AND plan_completion >= min_completion) 即发 amount。

    min_completion=0.0 表示不限完成度；1.0 表示要求 ≥100%。
    """
    min_stars: int
    min_completion: float
    amount: float
    label: str


# 档位结构（顺序敏感：更严的档必须放前面，先命中先返回）。amount 由 settings 注入。
# (min_stars, min_completion, setting 属性, label)
_WEEKLY_TIER_SPEC: tuple[tuple[int, float, str, str], ...] = (
    (5, 1.0, "CASH_TIER_5_FULL", "5star_full"),
    (5, 0.0, "CASH_TIER_5", "5star"),
    (4, 1.0, "CASH_TIER_4_FULL", "4star_full"),
    (4, 0.0, "CASH_TIER_4", "4star"),
    (3, 0.0, "CASH_TIER_3", "3star"),
)


def _build_weekly_tiers() -> list[CashTier]:
    return [
        CashTier(ms, mc, float(getattr(settings, attr)), label)
        for ms, mc, attr, label in _WEEKLY_TIER_SPEC
    ]


WEEKLY_CASH_TIERS: list[CashTier] = _build_weekly_tiers()
CASH_WEEKLY_CAP: float = float(settings.CASH_WEEKLY_CAP)


def unit_complete_amount(total_words: int) -> float:
    """背完一个 Unit 的奖金，按词数分档：≥200→100 / 100~199→50 / <100→30。

    大 Unit 花精力更多 → 奖更多；分档而非线性，避免天价。
    """
    if total_words >= 200:
        return float(settings.CASH_MS_UNIT_BIG)
    if total_words >= 100:
        return float(settings.CASH_MS_UNIT_MID)
    return float(settings.CASH_MS_UNIT_SMALL)


# 阈值结构：(setting 属性, 阈值)。金额由 settings 注入。
_WORD_TIER_SPEC = (
    ("CASH_MS_WORDS_100", 100),
    ("CASH_MS_WORDS_500", 500),
    ("CASH_MS_WORDS_1000", 1000),
    ("CASH_MS_WORDS_2000", 2000),
)
_ATTENDANCE_TIER_SPEC = (
    ("CASH_MS_STREAK_4", 4),
    ("CASH_MS_STREAK_8", 8),
    ("CASH_MS_STREAK_12", 12),
)


def _build_threshold_tiers(spec) -> list[tuple[int, float]]:
    return [(thr, float(getattr(settings, attr))) for attr, thr in spec]


CUMULATIVE_WORD_TIERS: list[tuple[int, float]] = _build_threshold_tiers(_WORD_TIER_SPEC)
ATTENDANCE_WEEK_TIERS: list[tuple[int, float]] = _build_threshold_tiers(_ATTENDANCE_TIER_SPEC)


@dataclass(frozen=True)
class MilestoneCandidate:
    """待发放里程碑候选（纯数据）。幂等去重由调用方靠 uq_member_milestone_key 保证。

    threshold：unit_complete 存 unit_id；cumulative_words/attendance_streak 存阈值。
    snapshot：发放时刻证据（落库审计），后续词/周回退不回扣（snapshot 语义）。
    """
    key: str               # "unit_complete:5" / "cumulative_words:500" / "attendance_streak:8"
    type: str              # "unit_complete" / "cumulative_words" / "attendance_streak"
    threshold: int
    amount: float
    snapshot: dict


def build_milestone_candidates(
    units_status: list[dict],
    att_streak: int,
    mastered_total: int,
    *,
    word_tiers: list[tuple[int, float]] | None = None,
    attendance_tiers: list[tuple[int, float]] | None = None,
) -> list[MilestoneCandidate]:
    """根据当下状态生成全部「已达成」里程碑候选（纯函数，便于单测）。

    - units_status: [{unit_id, total_words, mastered}, ...]（mastered 口径 = level∈{familiar,permanent}）
    - att_streak: 连续全勤周数（基于已落表 weekly_settlement 行；懒结算只回算 4 周，超窗会少算）
    - mastered_total: 全局累计掌握词数

    word_tiers / attendance_tiers 默认取模块常量（settings 驱动）；测试可传 override。
    unit_complete 的金额走 unit_complete_amount（按词数分档），故无 override 入参。
    """
    wt = word_tiers if word_tiers is not None else CUMULATIVE_WORD_TIERS
    at = attendance_tiers if attendance_tiers is not None else ATTENDANCE_WEEK_TIERS
    candidates: list[MilestoneCandidate] = []
    # ① unit_complete：每个「全掌握」unit（total>0 且 mastered>=total）
    for u in units_status:
        total = int(u.get("total_words", 0))
        mastered = int(u.get("mastered", 0))
        if total > 0 and mastered >= total:
            uid = int(u["unit_id"])
            candidates.append(MilestoneCandidate(
                key=f"unit_complete:{uid}",
                type="unit_complete",
                threshold=uid,
                amount=unit_complete_amount(total),
                snapshot={"unit_id": uid, "total_words": total, "mastered": mastered},
            ))
    # ② cumulative_words：每个阈值 <= mastered_total
    for threshold, amount in wt:
        if mastered_total >= threshold:
            candidates.append(MilestoneCandidate(
                key=f"cumulative_words:{threshold}",
                type="cumulative_words",
                threshold=threshold,
                amount=amount,
                snapshot={"mastered": mastered_total},
            ))
    # ③ attendance_streak：每个阈值 <= att_streak
    for threshold, amount in at:
        if att_streak >= threshold:
            candidates.append(MilestoneCandidate(
                key=f"attendance_streak:{threshold}",
                type="attendance_streak",
                threshold=threshold,
                amount=amount,
                snapshot={"attendance_streak": att_streak},
            ))
    return candidates


def build_badge_reward_candidates(
    earned_badge_keys: list[str], amount: float,
) -> list[MilestoneCandidate]:
    """对每枚已获徽章生成一次性现金奖励候选（type='badge_reward'）。

    - key 形如 ``badge_reward:{badge_key}``，与现有三类里程碑共用 ``cash_milestone`` 表；
      幂等由调用方靠 ``uq_member_milestone_key`` 保证（已发的被 SELECT 跳过）。
    - 语义「首达」：每枚徽章终身只发一次 amount（默认 ``settings.CASH_BADGE_REWARD``）；
      发放后徽章回收（当前无路径）也不回扣（同 snapshot 语义）。
    """
    return [
        MilestoneCandidate(
            key=f"badge_reward:{k}",
            type="badge_reward",
            threshold=0,
            amount=amount,
            snapshot={"badge_key": k},
        )
        for k in earned_badge_keys
    ]
