import json
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PlanType


_DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]


class PlanCreate(BaseModel):
    name: str = Field(..., max_length=100)
    daily_goal: int = Field(30, ge=1, le=200)
    unit_ids: list[int] = Field(..., min_length=1)
    deadline: date | None = None
    # 计划生效起始日：默认今天。二/三轮可设未来日期，到期前不产出任务
    start_date: date | None = None
    learn_weekdays: list[int] = Field(
        default_factory=lambda: list(_DEFAULT_WEEKDAYS)
    )
    # None=不开月复习；1-28=每月固定日；31=月末
    monthly_review_day: int | None = Field(None, ge=1, le=31)
    # forward=学新词；review_only=纯复习；wrong_word_drill=错题刷
    plan_type: PlanType = PlanType.forward

    @field_validator("learn_weekdays")
    @classmethod
    def _check_weekdays(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("learn_weekdays must be a non-empty subset of {0..6}")
        if any(d not in range(7) for d in v):
            raise ValueError("learn_weekdays values must be in 0..6 (Mon=0..Sun=6)")
        return sorted(set(v))


class TaskUpdateBody(BaseModel):
    completed_new: int = Field(0, ge=0)
    completed_review: int = Field(0, ge=0)


def parse_learn_weekdays(raw: str | None) -> list[int]:
    """从 LearningPlan.learn_weekdays (JSON 字符串) 解析为 list[int]。"""
    if not raw:
        return list(_DEFAULT_WEEKDAYS)
    try:
        v = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return list(_DEFAULT_WEEKDAYS)
    return sorted({int(x) for x in v if isinstance(x, int) or (isinstance(x, str) and x.isdigit())})


def dump_learn_weekdays(days: list[int] | None) -> str:
    """list[int] → JSON 字符串。"""
    return json.dumps(sorted(set(days)) if days else list(_DEFAULT_WEEKDAYS))
