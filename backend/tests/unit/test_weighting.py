from datetime import date, timedelta

from app.models.enums import MasteryLevel, TagType
from app.utils.weighting import compute_weight, weighted_sample


def test_compute_weight_unlearned():
    assert compute_weight(MasteryLevel.unlearned, None) == 1.5


def test_compute_weight_excluded():
    assert compute_weight(MasteryLevel.learning, [TagType.excluded]) == 0.0


def test_compute_weight_high_freq():
    assert compute_weight(MasteryLevel.learning, [TagType.high_freq]) == 1.3 * 1.5


def test_compute_weight_permanent_low_freq():
    # permanent 不再归零：低频回炉，基础权重 0.3
    assert compute_weight(MasteryLevel.permanent, None) == 0.3


def test_compute_weight_permanent_with_tag_not_zeroed():
    # permanent 不再短路归零：带 high_freq 正常加权（0.3 * 1.5）
    assert compute_weight(MasteryLevel.permanent, [TagType.high_freq]) == 0.3 * 1.5


def test_compute_weight_multiple_tags():
    assert compute_weight(MasteryLevel.familiar, [TagType.favorite, TagType.exam_focus]) == 1.0 * 1.2 * 1.5


# ── SM-2 到期因子 ──
TODAY = date(2026, 7, 24)


def test_due_none_new_word_no_penalty():
    # 新词 / 未排期（next_review_date=None）→ 正常权重，不加 due 因子
    assert compute_weight(MasteryLevel.learning, None, next_review_date=None, today=TODAY) == 1.3


def test_due_overdue_boosted():
    due = TODAY - timedelta(days=7)   # 逾期 7 天 → ×(1 + 7/7) = ×2
    assert abs(compute_weight(MasteryLevel.learning, None, next_review_date=due, today=TODAY) - 1.3 * 2.0) < 1e-6


def test_due_future_suppressed():
    due = TODAY + timedelta(days=1)   # 未到期 → ×0.05
    assert abs(compute_weight(MasteryLevel.learning, None, next_review_date=due, today=TODAY) - 1.3 * 0.05) < 1e-6


def test_due_today_counts_as_due():
    # 今天到期（==today）→ overdue=0 → ×1.0（基础权重不变，视为到期可练）
    assert compute_weight(MasteryLevel.learning, None, next_review_date=TODAY, today=TODAY) == 1.3


def test_due_overdue_capped_at_14_days():
    due = TODAY - timedelta(days=30)  # 逾期 30 天 → 封顶 14 → ×(1 + 14/7) = ×3
    assert abs(compute_weight(MasteryLevel.learning, None, next_review_date=due, today=TODAY) - 1.3 * 3.0) < 1e-6


# ── weighted_sample ──
def test_weighted_sample_basic():
    items = [
        {"id": 1, "weight": 10.0},
        {"id": 2, "weight": 1.0},
        {"id": 3, "weight": 5.0},
    ]
    result = weighted_sample(items, 2)
    assert len(result) == 2
    assert len(set(r["id"] for r in result)) == 2


def test_weighted_sample_excludes_zero_weight():
    items = [{"id": 1, "weight": 0.0}, {"id": 2, "weight": 5.0}]
    result = weighted_sample(items, 1)
    assert result[0]["id"] == 2


def test_weighted_sample_all_excluded():
    assert weighted_sample([{"id": 1, "weight": 0.0}, {"id": 2, "weight": 0.0}], 5) == []


def test_weighted_sample_count_exceeds_candidates():
    items = [{"id": i, "weight": 1.0} for i in range(3)]
    assert len(weighted_sample(items, 10)) == 3
