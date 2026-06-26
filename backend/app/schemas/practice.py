from pydantic import BaseModel, Field

from app.models.enums import PracticeMode, TaskType


class PracticeStart(BaseModel):
    member_id: int = Field(1, ge=1)
    mode: PracticeMode
    unit_ids: list[int] = Field(..., min_length=1)
    count: int = Field(10, ge=1, le=2000)
    # None / "learn" → 学习日默认选题（按 unit_id 抽取）
    # "weekly_review" / "monthly_review" → 按本周/本月练习记录的 word_id 选题
    task_type: TaskType | None = None


class SubmitAnswer(BaseModel):
    word_id: int = Field(..., ge=1)
    is_correct: bool
    user_answer: str | None = None
