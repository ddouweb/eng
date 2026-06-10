import random

from app.models.enums import MasteryLevel, TagType

MASTERY_WEIGHT = {
    MasteryLevel.unlearned: 1.5,
    MasteryLevel.learning: 1.3,
    MasteryLevel.familiar: 1.0,
    MasteryLevel.permanent: 0.1,
}

TAG_WEIGHT = {
    TagType.favorite: 1.2,
    TagType.high_freq: 1.5,
    TagType.exam_focus: 1.5,
    TagType.excluded: 0.0,
    TagType.memorized: 0.3,
}


def compute_weight(
    mastery_level: MasteryLevel | None,
    tags: list[TagType] | None,
) -> float:
    """计算单个单词的出题权重。"""
    if tags and TagType.excluded in tags:
        return 0.0

    w = MASTERY_WEIGHT.get(mastery_level or MasteryLevel.unlearned, 1.0)

    if tags:
        for tag in tags:
            w *= TAG_WEIGHT.get(tag, 1.0)

    return w


def weighted_sample(
    items: list[dict],
    count: int,
) -> list[dict]:
    """从候选项中按权重抽取 N 个不重复的题目。

    每个 item 必须包含 "weight" 字段。
    weight <= 0 的项会被排除。
    """
    candidates = [i for i in items if i.get("weight", 0) > 0]
    if not candidates:
        return []

    count = min(count, len(candidates))
    weights = [i["weight"] for i in candidates]

    chosen = []
    remaining = list(candidates)
    remaining_weights = list(weights)

    for _ in range(count):
        picked = random.choices(remaining, weights=remaining_weights, k=1)[0]
        idx = remaining.index(picked)
        chosen.append(picked)
        remaining.pop(idx)
        remaining_weights.pop(idx)

    return chosen
