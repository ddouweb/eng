"""settlement_score 纯函数测试（无 DB）：四维评分 + bonus + stars + plan_health。"""
from datetime import date

from app.settlement_score import (
    compute_bonus,
    compute_stars,
    expected_learn_days,
    plan_health,
    score_difficulty,
    score_login,
    score_new,
    score_plan,
)


# ── score_login（0~25）──
def test_score_login_full():
    assert score_login(7, 5) == 25      # 超额封顶
    assert score_login(5, 5) == 25


def test_score_login_partial():
    assert score_login(3, 5) == 15      # 25 * 0.6


def test_score_login_expected_zero_uses_seven():
    assert score_login(7, 0) == 25      # expected<=0 按 7 计 → 7/7=1.0
    assert score_login(0, 0) == 0


# ── score_difficulty（0~25，hard_share/0.6 基线）──
def test_score_difficulty_no_correct():
    assert score_difficulty(0, 0) == 0


def test_score_difficulty_at_baseline():
    # hard/correct = 0.6 → 满分 25
    assert score_difficulty(6, 10) == 25


def test_score_difficulty_below_baseline():
    # 3/10 = 0.3 → 0.3/0.6=0.5 → 25*0.5=12.5 → round(12.5)=12（银行家舍入）
    assert score_difficulty(3, 10) == 12


def test_score_difficulty_saturated():
    assert score_difficulty(10, 10) == 25   # 1.0/0.6 封顶


# ── score_new（0~20）──
def test_score_new_full():
    assert score_new(150, 150) == 20


def test_score_new_target_zero_uses_one():
    assert score_new(5, 0) == 20      # target<=0 按 1 计 → 5/1 封顶 20


def test_score_new_partial():
    assert score_new(75, 150) == 10   # 20 * 0.5


# ── score_plan（0~30，分母为零→0）──
def test_score_plan_full():
    assert score_plan(20, 20) == 30


def test_score_plan_zero_denominator():
    assert score_plan(0, 0) == 0
    assert score_plan(5, 0) == 0      # 无任务 → 0（不除零）


def test_score_plan_half():
    assert score_plan(10, 20) == 15


# ── compute_bonus（仅坚持+计划，封顶 30，<5→0）──
def test_bonus_max():
    assert compute_bonus(25, 30) == 30   # 满分坚持+计划


def test_bonus_only_login():
    # round(25/55*30)=round(13.636)=14
    assert compute_bonus(25, 0) == 14


def test_bonus_below_threshold_zero():
    # round(4/55*30)=round(2.18)=2 → <5 → 0
    assert compute_bonus(2, 2) == 0


def test_bonus_just_at_threshold():
    # round(10/55*30)=round(5.45)=5 → >=5 → 5
    assert compute_bonus(5, 5) == 5


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
