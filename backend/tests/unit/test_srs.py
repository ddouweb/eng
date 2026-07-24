"""SM-2 间隔重复算法测试（纯函数，不连 DB）。

update_srs 原地改 record 的 interval/ease/next_review_date/level；
interval_to_level 按 interval 派生四级。用简单 stub 对象模拟 MasteryRecord。
"""
from datetime import date, timedelta

from app.models.enums import MasteryLevel
from app.srs import EF_DEFAULT, interval_to_level, update_srs


def _record(cc=0, interval=0, ease=EF_DEFAULT):
    """构造类 MasteryRecord 的 stub（avoid ORM/DB）。"""
    class _R:
        pass
    r = _R()
    r.consecutive_correct = cc
    r.interval_days = interval
    r.ease_factor = ease
    r.next_review_date = None
    r.level = MasteryLevel.unlearned
    return r


TODAY = date(2026, 7, 24)


# ── interval_to_level 边界 ──
def test_interval_to_level_boundaries():
    assert interval_to_level(0) == MasteryLevel.unlearned
    assert interval_to_level(1) == MasteryLevel.learning
    assert interval_to_level(6) == MasteryLevel.learning
    assert interval_to_level(7) == MasteryLevel.familiar
    assert interval_to_level(20) == MasteryLevel.familiar
    assert interval_to_level(21) == MasteryLevel.permanent
    assert interval_to_level(100) == MasteryLevel.permanent


# ── update_srs：答对 ──
def test_correct_first_sets_interval_1():
    r = _record(cc=1)                      # n=1
    update_srs(r, True, TODAY)
    assert r.interval_days == 1
    assert r.next_review_date == TODAY + timedelta(days=1)
    assert r.level == MasteryLevel.learning


def test_correct_second_sets_interval_6():
    r = _record(cc=2)                      # n=2
    update_srs(r, True, TODAY)
    assert r.interval_days == 6
    assert r.next_review_date == TODAY + timedelta(days=6)


def test_correct_third_multiplies_by_ease():
    r = _record(cc=3, interval=6, ease=2.5)   # n=3, prev=6, ease→2.6
    update_srs(r, True, TODAY)
    assert r.interval_days == round(6 * 2.6)
    assert abs(r.ease_factor - 2.6) < 1e-6


def test_correct_ease_capped_at_3():
    r = _record(cc=5, interval=10, ease=2.95)  # +0.1 → 3.05 封顶 3.0
    update_srs(r, True, TODAY)
    assert r.ease_factor == 3.0


def test_correct_reaches_permanent():
    r = _record(cc=3, interval=10, ease=2.5)   # round(10 * 2.6) = 26 ≥ 21
    update_srs(r, True, TODAY)
    assert r.interval_days == 26
    assert r.level == MasteryLevel.permanent


# ── update_srs：答错 ──
def test_wrong_resets_interval_and_cc():
    r = _record(cc=5, interval=20, ease=2.5)
    update_srs(r, False, TODAY)
    assert r.consecutive_correct == 0
    assert r.interval_days == 1
    assert r.next_review_date == TODAY + timedelta(days=1)
    assert r.level == MasteryLevel.learning   # interval=1 → learning
    assert abs(r.ease_factor - (2.5 - 0.32)) < 1e-6


def test_wrong_ease_floored_at_1_3():
    r = _record(ease=1.4)                    # -0.32 → 1.08 下限 1.3
    update_srs(r, False, TODAY)
    assert r.ease_factor == 1.3


def test_wrong_from_permanent_downgrades():
    # permanent 词答错 → interval=1 → level 降回 learning（不再「永久锁死」）
    r = _record(cc=0, interval=30, ease=2.5)
    update_srs(r, False, TODAY)
    assert r.interval_days == 1
    assert r.level == MasteryLevel.learning
