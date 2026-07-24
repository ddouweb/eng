"""SM-2（SuperMemo-2）间隔重复算法 —— 纯函数，无 DB 依赖。

update_srs(record, is_correct, today) 原地更新 MasteryRecord 的 SM-2 字段
（interval_days / ease_factor / next_review_date / level）并返回 record。
level 由 interval_days 派生（interval_to_level），不再用离散阈值跃迁。

复用 MasteryRecord.consecutive_correct 作为 SM-2 的连续答对次数 n；
correct_count / wrong_count 由调用方累加，不参与间隔计算。
"""
from datetime import date, timedelta

from app.models.enums import MasteryLevel

EF_MIN = 1.3
EF_MAX = 3.0
EF_DEFAULT = 2.5
FAMILIAR_MIN = 7       # interval_days >= 7 → familiar
PERMANENT_MIN = 21     # interval_days >= 21 → permanent


def _clamp_ef(ef: float) -> float:
    return max(EF_MIN, min(EF_MAX, ef))


def interval_to_level(interval_days: int) -> MasteryLevel:
    """按 SM-2 间隔派生掌握度等级（对齐现有四级枚举）。"""
    if interval_days >= PERMANENT_MIN:
        return MasteryLevel.permanent
    if interval_days >= FAMILIAR_MIN:
        return MasteryLevel.familiar
    if interval_days >= 1:
        return MasteryLevel.learning
    return MasteryLevel.unlearned


def update_srs(record, is_correct: bool, today: date):
    """SM-2 更新：原地改 record 的 interval/ease/next_review_date/level，返回 record。

    - 答对（q=5）：n=consecutive_correct（调用前已 +1）；n<=1→1、n==2→6、else round(prev*ease)；
      ease +0.1 封顶 3.0；next_review_date = today + interval。
    - 答错（q=2）：consecutive_correct 归 0；interval=1；ease -0.32 下限 1.3；next_review_date = today+1。
    - level 由 interval 派生写回。

    二值 is_correct 映射：答对 q=5、答错 q=2（视为「部分遗忘可重学」而非完全不会）。
    """
    ef = _clamp_ef(float(record.ease_factor) if record.ease_factor is not None else EF_DEFAULT)

    if is_correct:
        # q=5 → EF delta = 0.1 - (5-5)*(...) = +0.1
        ef = _clamp_ef(ef + 0.1)
        n = int(record.consecutive_correct or 0)   # 调用前已 +1
        prev = int(record.interval_days or 0)
        if n <= 1:
            interval = 1
        elif n == 2:
            interval = 6
        else:
            interval = max(1, round(prev * ef))
    else:
        # q=2 → EF delta = 0.1 - 3*(0.08 + 3*0.02) = 0.1 - 0.42 = -0.32
        ef = _clamp_ef(ef - 0.32)
        record.consecutive_correct = 0
        interval = 1

    record.ease_factor = ef
    record.interval_days = interval
    record.next_review_date = today + timedelta(days=interval)
    record.level = interval_to_level(interval)
    return record
