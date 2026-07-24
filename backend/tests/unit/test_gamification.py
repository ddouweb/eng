"""坚持机制（游戏化）的纯逻辑测试：streak / freeze 推进 + XP 段位 + 月度发放。

_advance_streak / _maybe_grant_monthly_freeze 是 staticmethod，xp_to_level 是纯函数，
三者都不连 DB，直接用 MemberStreak 实例验证关键路径：
首次、连续、同日幂等、断 1 天靠 freeze 补、断多天补不满重置、月度发放与上限。
"""
from datetime import date

from app.gamification import xp_to_level
from app.models.streak import MemberStreak
from app.services.practice_service import PracticeService


def _state(last=None, current=0, longest=0, freeze=2, grant_month=None):
    s = MemberStreak(member_id=1)
    s.current_streak = current
    s.longest_streak = longest
    s.freeze_balance = freeze
    s.last_active_date = last
    s.freeze_grant_month = grant_month
    return s


# ── xp_to_level（段位边界 + 进度）──
def test_xp_to_level_boundary_and_progress():
    assert xp_to_level(0)["level_name"] == "青铜"
    assert xp_to_level(99)["level_name"] == "青铜"
    lv100 = xp_to_level(100)
    assert lv100["level_name"] == "白银"
    assert lv100["level_min_xp"] == 100
    # 白银(100)→黄金(300)：150 XP 进度 = 0.25
    assert abs(xp_to_level(150)["progress"] - 0.25) < 1e-6
    top = xp_to_level(5000)
    assert top["level_name"] == "大师"
    assert top["next_level_min_xp"] is None and top["progress"] == 1.0


# ── _advance_streak ──
def test_advance_streak_first_ever():
    s = _state(last=None)
    PracticeService._advance_streak(s, date(2026, 7, 23))
    assert s.current_streak == 1
    assert s.longest_streak == 1
    assert s.last_active_date == date(2026, 7, 23)


def test_advance_streak_consecutive_day():
    s = _state(last=date(2026, 7, 22), current=3, longest=3)
    PracticeService._advance_streak(s, date(2026, 7, 23))
    assert s.current_streak == 4
    assert s.longest_streak == 4
    assert s.freeze_balance == 2   # 连续无需消耗 freeze


def test_advance_streak_same_day_idempotent():
    s = _state(last=date(2026, 7, 23), current=5, longest=7)
    PracticeService._advance_streak(s, date(2026, 7, 23))
    assert s.current_streak == 5   # 同一天再练不变
    assert s.longest_streak == 7


def test_advance_streak_gap_one_day_uses_freeze():
    # last=7/21, today=7/23：中间缺 7/22 一天(gap=1)，1 个 freeze 补上 → 接续
    s = _state(last=date(2026, 7, 21), current=5, longest=5, freeze=2)
    PracticeService._advance_streak(s, date(2026, 7, 23))
    assert s.current_streak == 6
    assert s.freeze_balance == 1


def test_advance_streak_gap_too_large_resets():
    # last=7/18, today=7/23：缺 7/19~7/22 共 4 天，freeze 只有 2 → 补不满 → 重置为 1
    s = _state(last=date(2026, 7, 18), current=5, longest=5, freeze=2)
    PracticeService._advance_streak(s, date(2026, 7, 23))
    assert s.current_streak == 1
    assert s.freeze_balance == 0   # 2 个全用光仍补不满
    assert s.longest_streak == 5   # 最长记录不被拉低


# ── _maybe_grant_monthly_freeze ──
def test_monthly_freeze_first_month_no_grant():
    s = _state(freeze=2, grant_month=None)
    PracticeService._maybe_grant_monthly_freeze(s, date(2026, 7, 23))
    assert s.freeze_balance == 2          # 首月只登记不补
    assert s.freeze_grant_month == "2026-07"


def test_monthly_freeze_new_month_grants_one():
    s = _state(freeze=2, grant_month="2026-06")
    PracticeService._maybe_grant_monthly_freeze(s, date(2026, 7, 1))
    assert s.freeze_balance == 3
    assert s.freeze_grant_month == "2026-07"


def test_monthly_freeze_capped_and_idempotent():
    s = _state(freeze=5, grant_month="2026-06")   # 已达上限
    PracticeService._maybe_grant_monthly_freeze(s, date(2026, 7, 1))
    assert s.freeze_balance == 5                  # 上限 5
    PracticeService._maybe_grant_monthly_freeze(s, date(2026, 7, 15))
    assert s.freeze_balance == 5                  # 同月不重复发
