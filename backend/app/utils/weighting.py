import random

from app.models.enums import MasteryLevel, TagType

MASTERY_WEIGHT = {
    MasteryLevel.unlearned: 1.5,
    MasteryLevel.learning: 1.3,
    MasteryLevel.familiar: 1.0,
    MasteryLevel.permanent: 0.0,  # 永久掌握默认不进入主动练习（CLAUDE.md 展示策略）
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
    # 永久掌握的词默认不进入主动练习（与 excluded 同等短路归零）。
    # 显式短路而非仅靠权重表，避免后续 tag 乘子把它"救回"非零。
    if mastery_level == MasteryLevel.permanent:
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
        # 直接抽下标，便于 O(1) swap-pop 删除（避免 list.index + 两次 pop 的 O(n)）。
        # "全部"模式可能传 count=2000，原 O(n×k) 会退化到数百 ms。
        idx = random.choices(range(len(remaining)), weights=remaining_weights, k=1)[0]
        chosen.append(remaining[idx])
        last = len(remaining) - 1
        if idx != last:
            remaining[idx] = remaining[last]
            remaining_weights[idx] = remaining_weights[last]
        remaining.pop()
        remaining_weights.pop()

    return chosen
