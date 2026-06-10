from app.models.enums import MasteryLevel, TagType
from app.utils.weighting import compute_weight, weighted_sample


def test_compute_weight_unlearned():
    w = compute_weight(MasteryLevel.unlearned, None)
    assert w == 1.5


def test_compute_weight_excluded():
    w = compute_weight(MasteryLevel.learning, [TagType.excluded])
    assert w == 0.0


def test_compute_weight_high_freq():
    w = compute_weight(MasteryLevel.learning, [TagType.high_freq])
    assert w == 1.3 * 1.5


def test_compute_weight_permanent_no_tags():
    w = compute_weight(MasteryLevel.permanent, None)
    assert w == 0.1


def test_compute_weight_multiple_tags():
    w = compute_weight(MasteryLevel.familiar, [TagType.favorite, TagType.exam_focus])
    assert w == 1.0 * 1.2 * 1.5


def test_weighted_sample_basic():
    items = [
        {"id": 1, "weight": 10.0},
        {"id": 2, "weight": 1.0},
        {"id": 3, "weight": 5.0},
    ]
    result = weighted_sample(items, 2)
    assert len(result) == 2
    ids = [r["id"] for r in result]
    assert len(set(ids)) == 2


def test_weighted_sample_excludes_zero_weight():
    items = [
        {"id": 1, "weight": 0.0},
        {"id": 2, "weight": 5.0},
    ]
    result = weighted_sample(items, 1)
    assert len(result) == 1
    assert result[0]["id"] == 2


def test_weighted_sample_all_excluded():
    items = [
        {"id": 1, "weight": 0.0},
        {"id": 2, "weight": 0.0},
    ]
    result = weighted_sample(items, 5)
    assert result == []


def test_weighted_sample_count_exceeds_candidates():
    items = [{"id": i, "weight": 1.0} for i in range(3)]
    result = weighted_sample(items, 10)
    assert len(result) == 3
