"""settlement_score 纯函数测试（无 DB）：三维评分 + bonus + stars + plan_health + 周现金。"""
from datetime import date

from app.cash import CashTier
from app.settlement_score import (
    compute_bonus,
    compute_stars,
    compute_weekly_cash,
    expected_learn_days,
    plan_health,
    score_login,
    score_new,
    score_plan,
)


# ── score_login（0~45）──
def test_score_login_full():
    assert score_login(7, 5) == 45      # 超额封顶
    assert score_login(5, 5) == 45


def test_score_login_partial():
    assert score_login(3, 5) == 27      # 45 * 0.6


def test_score_login_expected_zero_uses_seven():
    assert score_login(7, 0) == 45      # expected<=0 按 7 计 → 7/7=1.0
    assert score_login(0, 0) == 0


# ── score_new（0~25）──
def test_score_new_full():
    assert score_new(150, 150) == 25


def test_score_new_target_zero_uses_one():
    assert score_new(5, 0) == 25      # target<=0 按 1 计 → 5/1 封顶 25


def test_score_new_partial():
    # 75/150=0.5 → 25*0.5=12.5 → round(12.5)=12（银行家舍入）
    assert score_new(75, 150) == 12


# ── score_plan（0~30，分母为零→0）──
def test_score_plan_full():
    assert score_plan(20, 20) == 30


def test_score_plan_zero_denominator():
    assert score_plan(0, 0) == 0
    assert score_plan(5, 0) == 0      # 无任务 → 0（不除零）


def test_score_plan_half():
    assert score_plan(10, 20) == 15


# ── compute_bonus（仅坚持+计划，封顶 30，<5→0；分母=45+30=75）──
def test_bonus_max():
    assert compute_bonus(45, 30) == 30   # 满分坚持+计划


def test_bonus_only_login():
    # round(45/75*30)=round(18.0)=18
    assert compute_bonus(45, 0) == 18


def test_bonus_below_threshold_zero():
    # round(4/75*30)=round(1.6)=2 → <5 → 0
    assert compute_bonus(2, 2) == 0


def test_bonus_just_at_threshold():
    # round(12/75*30)=round(4.8)=5 → >=5 → 5
    assert compute_bonus(6, 6) == 5


# ── compute_stars（0~5，round(总分/20)，银行家舍入）──
def test_stars_boundaries():
    assert compute_stars(0) == 0
    assert compute_stars(100) == 5


def test_stars_bankers_rounding():
    # 50/20=2.5 → round(2.5)=2（round-half-to-even，非 3）
    assert compute_stars(50) == 2


# ── expected_learn_days ──
def test_expected_learn_days_weekday_range():
    # 2026-07-13(周一)~2026-07-19(周日)， weekdays=[0,1,2,3,4] → 5 个学习日
    assert expected_learn_days("[0,1,2,3,4]", date(2026, 7, 13), date(2026, 7, 19)) == 5


def test_expected_learn_days_all_week():
    # weekdays 全周 → 7
    assert expected_learn_days("[0,1,2,3,4,5,6]", date(2026, 7, 13), date(2026, 7, 19)) == 7


# ── plan_health ──
def test_plan_health_no_deadline():
    h = plan_health(100, 40, None, 30, "[0,1,2,3,4]", date(2026, 7, 24))
    assert h["remaining_unmastered"] == 60
    assert h["remaining_learn_days"] is None
    assert h["on_track"] is None
    assert h["suggested_daily_goal"] is None


def test_plan_health_with_deadline_fields():
    h = plan_health(100, 40, date(2026, 12, 31), 30, "[0,1,2,3,4]", date(2026, 7, 24))
    assert h["remaining_unmastered"] == 60
    assert h["remaining_learn_days"] > 0
    assert isinstance(h["projected_finish"], str)
    assert isinstance(h["on_track"], bool)
    assert h["suggested_daily_goal"] is not None and h["suggested_daily_goal"] > 0


# ── compute_weekly_cash（分档制；显式 tiers 不依赖 settings）──
_TIERS = [
    CashTier(5, 1.0, 50.0, "5star_full"),
    CashTier(5, 0.0, 40.0, "5star"),
    CashTier(4, 1.0, 30.0, "4star_full"),
    CashTier(4, 0.0, 20.0, "4star"),
    CashTier(3, 0.0, 10.0, "3star"),
]


def test_cash_5star_full_completion():
    assert compute_weekly_cash(5, 1.0, _TIERS) == (50.0, "5star_full")


def test_cash_5star_below_full():
    # 0.99 < 1.0 → 落普通 5 星档（plan_completion 是浮点，边界敏感）
    assert compute_weekly_cash(5, 0.99, _TIERS) == (40.0, "5star")


def test_cash_4star_full():
    assert compute_weekly_cash(4, 1.0, _TIERS) == (30.0, "4star_full")


def test_cash_4star_plain():
    assert compute_weekly_cash(4, 0.5, _TIERS) == (20.0, "4star")


def test_cash_3star():
    assert compute_weekly_cash(3, 0.0, _TIERS) == (10.0, "3star")


def test_cash_below_3star_zero():
    assert compute_weekly_cash(2, 1.0, _TIERS) == (0.0, None)
    assert compute_weekly_cash(0, 0.0, _TIERS) == (0.0, None)


def test_cash_cap_clamp():
    # 档金额超过 cap → 截断到 cap（双保险）
    big = [CashTier(5, 1.0, 999.0, "x")]
    assert compute_weekly_cash(5, 1.0, big, cap=50.0) == (50.0, "x")


def test_cash_default_tiers_match_settings_defaults():
    # 不传 tiers → 用 cash.WEEKLY_CASH_TIERS（settings 默认 50/40/30/20/10）
    assert compute_weekly_cash(5, 1.0) == (50.0, "5star_full")
    assert compute_weekly_cash(3, 0.0) == (10.0, "3star")
