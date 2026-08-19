"""build_grant_candidates 纯函数测试（无 DB）：8 类来源逐源覆盖 + key 全局唯一。

输入事实全部显式构造（service 层负责真实查询），today 用注入日期避免跨日跑挂。
"""
from datetime import date

from app.lottery import INIT_GRANT_DRAWS, build_grant_candidates

_TODAY = date(2026, 8, 19)


def _build(**overrides):
    kwargs = dict(
        today=_TODAY,
        ended_practice_count=0,
        units_status=[],
        learn_task_done=False,
        review_task_done=False,
        stars=0,
        badge_keys=[],
        week_stars=[],
    )
    kwargs.update(overrides)
    return build_grant_candidates(**kwargs)


def _keys(cands):
    return [c.key for c in cands]


def _by_source(cands, source):
    return [c for c in cands if c.source == source]


# ── init / daily ──


def test_init_and_daily_always_present():
    cands = _build()
    init = _by_source(cands, "init")
    assert len(init) == 1
    assert init[0].key == "init:boot"
    assert init[0].draws == INIT_GRANT_DRAWS == 5
    daily = _by_source(cands, "daily")
    assert daily[0].key == f"daily:{_TODAY:%Y-%m-%d}" and daily[0].draws == 1


# ── practice：终身累计每 5 场 = 1 次 ──


def test_practice_thresholds():
    assert _keys(_by_source(_build(ended_practice_count=4), "practice")) == []
    assert _keys(_by_source(_build(ended_practice_count=5), "practice")) == ["practice:1"]
    assert _keys(_by_source(_build(ended_practice_count=9), "practice")) == ["practice:1"]
    assert _keys(_by_source(_build(ended_practice_count=10), "practice")) == ["practice:1", "practice:2"]
    assert _keys(_by_source(_build(ended_practice_count=53), "practice")) == [
        "practice:1", "practice:2", "practice:3", "practice:4", "practice:5", "practice:6",
        "practice:7", "practice:8", "practice:9", "practice:10",
    ]


# ── unit：全掌握单元 ──


def test_unit_complete_only_when_fully_mastered():
    units = [
        {"unit_id": 1, "total_words": 100, "mastered": 100},   # 通关
        {"unit_id": 2, "total_words": 120, "mastered": 119},   # 差 1 词
        {"unit_id": 3, "total_words": 0, "mastered": 0},       # 空 unit
        {"unit_id": 4, "total_words": 50, "mastered": 60},     # 超额（口径 >=）
    ]
    keys = _keys(_by_source(_build(units_status=units), "unit"))
    assert keys == ["unit:1", "unit:4"]


# ── learn_task / review_task 每日标记 ──


def test_daily_task_flags():
    base = _build(learn_task_done=True, review_task_done=True)
    assert f"learn_task:{_TODAY:%Y-%m-%d}" in _keys(base)
    assert f"review_task:{_TODAY:%Y-%m-%d}" in _keys(base)
    off = _build()
    assert not any(k.startswith("learn_task:") for k in _keys(off))
    assert not any(k.startswith("review_task:") for k in _keys(off))


# ── star：每加一星 1 次 ──


def test_star_milestones():
    assert _keys(_by_source(_build(stars=0), "star")) == []
    assert _keys(_by_source(_build(stars=3), "star")) == ["star:1", "star:2", "star:3"]
    # 负数防御（理论不会出现）
    assert _keys(_by_source(_build(stars=-2), "star")) == []


# ── badge：每枚 1 次 ──


def test_badge_keys():
    cands = _build(badge_keys=["streak_7", "xp_1000"])
    keys = _keys(_by_source(cands, "badge"))
    assert keys == ["badge:streak_7", "badge:xp_1000"]
    # remark 用 BADGES 元数据的中文名
    assert all("徽章" in c.remark for c in _by_source(cands, "badge"))


# ── weekstars：每星 1 次 ──


def test_weekstars_expansion():
    assert _keys(_by_source(_build(week_stars=[("2026-W30", 0)]), "weekstars")) == []
    keys = _keys(_by_source(_build(week_stars=[("2026-W30", 4)]), "weekstars"))
    assert keys == [f"weekstars:2026-W30:{i}" for i in range(1, 5)]
    both = _build(week_stars=[("2026-W29", 2), ("2026-W30", 3)])
    assert _keys(_by_source(both, "weekstars")) == [
        "weekstars:2026-W29:1", "weekstars:2026-W29:2",
        "weekstars:2026-W30:1", "weekstars:2026-W30:2", "weekstars:2026-W30:3",
    ]


# ── 全源混合：key 全局唯一 ──


def test_all_sources_mixed_keys_unique():
    cands = _build(
        ended_practice_count=12,
        units_status=[{"unit_id": 7, "total_words": 80, "mastered": 80}],
        learn_task_done=True,
        review_task_done=True,
        stars=2,
        badge_keys=["streak_3", "wrongbook_clear"],
        week_stars=[("2026-W30", 5)],
    )
    keys = _keys(cands)
    assert len(keys) == len(set(keys))  # 无重复
    # 各源条数：init1+daily1+practice2+unit1+learn1+review1+star2+badge2+weekstars5 = 16
    assert len(cands) == 16
    sources = {c.source for c in cands}
    assert sources == {
        "init", "daily", "practice", "unit", "learn_task", "review_task",
        "star", "badge", "weekstars",
    }
