import random

from app.models.enums import MasteryLevel, TagType

# permanent 不再归零：低频回炉（到期时以低权重出现，而非永不出现）。
# 原先 permanent=0.0 会把「永久掌握」的词彻底踢出练习池，与遗忘曲线冲突。
MASTERY_WEIGHT = {
    MasteryLevel.unlearned: 1.5,
    MasteryLevel.learning: 1.3,
    MasteryLevel.familiar: 1.0,
    MasteryLevel.permanent: 0.3,
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
    next_review_date=None,
    today=None,
) -> float:
    """计算单个单词的出题权重（含 SM-2 到期因子）。

    - excluded 标签 → 0（永不出现）。
    - permanent 不再短路归零：走 MASTERY_WEIGHT=0.3（低频回炉）。
    - 到期因子（仅当 next_review_date 与 today 都提供时叠加）：
      · None（新词 / 未排期）→ 正常权重（可学）；
      · 未到期（>today）→ ×0.05（几乎不出，允许微量预热）；
      · 到期 / 逾期（<=today）→ ×(1 + min(overdue,14)/7)（逾期越久权重越高，封顶约 ×3）。
    """
    if tags and TagType.excluded in tags:
        return 0.0

    w = MASTERY_WEIGHT.get(mastery_level or MasteryLevel.unlearned, 1.0)

    if tags:
        for tag in tags:
            w *= TAG_WEIGHT.get(tag, 1.0)

    if next_review_date is not None and today is not None:
        if next_review_date > today:
            w *= 0.05                                   # 未到期：几乎不出
        else:
            overdue = (today - next_review_date).days
            w *= 1.0 + min(max(overdue, 0), 14) / 7.0    # 到期/逾期：封顶 ~3x

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
