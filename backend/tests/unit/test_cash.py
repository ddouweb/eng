"""cash.py 纯函数测试（无 DB）：Unit 金额分档 + 里程碑候选生成。

显式传 word_tiers/attendance_tiers 以脱离 settings；少量用例验证默认常量与 settings 一致。
"""
from app.cash import (
    MilestoneCandidate,
    build_milestone_candidates,
    unit_complete_amount,
)

# ── unit_complete_amount（按词数分档：≥200→100 / 100~199→50 / <100→30）──


def test_unit_amount_big():
    assert unit_complete_amount(200) == 100.0
    assert unit_complete_amount(500) == 100.0


def test_unit_amount_mid():
    assert unit_complete_amount(100) == 50.0
    assert unit_complete_amount(199) == 50.0


def test_unit_amount_small():
    assert unit_complete_amount(99) == 30.0
    assert unit_complete_amount(1) == 30.0


# ── build_milestone_candidates ──
_WT = [(100, 10.0), (500, 20.0), (1000, 50.0)]
_AT = [(4, 20.0), (8, 50.0)]


def test_unit_complete_candidate():
    units = [{"unit_id": 5, "total_words": 120, "mastered": 120}]
    cands = build_milestone_candidates(
        units, att_streak=0, mastered_total=0, word_tiers=_WT, attendance_tiers=_AT
    )
    u = next(c for c in cands if c.type == "unit_complete")
    assert u.key == "unit_complete:5"
    assert u.amount == 50.0  # 120 词 → mid
    assert u.threshold == 5
    assert u.snapshot == {"unit_id": 5, "total_words": 120, "mastered": 120}


def test_unit_not_complete_no_candidate():
    # 差 1 词未全掌握 → 不发
    units = [{"unit_id": 5, "total_words": 120, "mastered": 119}]
    cands = build_milestone_candidates(units, 0, 0, word_tiers=_WT, attendance_tiers=_AT)
    assert not any(c.type == "unit_complete" for c in cands)


def test_unit_total_zero_ignored():
    # 空词 unit（total=0）不计 unit_complete（避免空 unit 误发）
    units = [{"unit_id": 9, "total_words": 0, "mastered": 0}]
    cands = build_milestone_candidates(units, 0, 0, word_tiers=_WT, attendance_tiers=_AT)
    assert not any(c.type == "unit_complete" for c in cands)


def test_cumulative_words_thresholds():
    # mastered=600 → 命中 100、500；未达 1000
    cands = build_milestone_candidates([], 0, 600, word_tiers=_WT, attendance_tiers=_AT)
    amounts = {c.threshold: c.amount for c in cands if c.type == "cumulative_words"}
    assert amounts == {100: 10.0, 500: 20.0}


def test_attendance_streak_thresholds():
    cands = build_milestone_candidates([], 8, 0, word_tiers=_WT, attendance_tiers=_AT)
    amounts = {c.threshold: c.amount for c in cands if c.type == "attendance_streak"}
    assert amounts == {4: 20.0, 8: 50.0}


def test_all_three_kinds_combined():
    units = [{"unit_id": 1, "total_words": 250, "mastered": 250}]
    cands = build_milestone_candidates(
        units, att_streak=4, mastered_total=100, word_tiers=_WT, attendance_tiers=_AT
    )
    types = {c.type for c in cands}
    assert types == {"unit_complete", "cumulative_words", "attendance_streak"}


def test_no_candidates_when_nothing_achieved():
    cands = build_milestone_candidates(
        [{"unit_id": 1, "total_words": 50, "mastered": 0}], 0, 50,
        word_tiers=_WT, attendance_tiers=_AT,
    )
    assert cands == []


def test_candidate_is_frozen_dataclass():
    cands = build_milestone_candidates([], 4, 100)  # 默认 tiers
    assert all(isinstance(c, MilestoneCandidate) for c in cands)
    keys = {c.key for c in cands}
    assert "cumulative_words:100" in keys
    assert "attendance_streak:4" in keys
