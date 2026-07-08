from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import PracticeMode, TaskType


class PracticeStart(BaseModel):
    member_id: int = Field(1, ge=1)
    mode: PracticeMode
    # source="units" 时为选中的 Unit 列表；
    # source="wrong_book" 时可为空（按 member 的错题本选题）
    unit_ids: list[int] = Field(default_factory=list)
    count: int = Field(10, ge=1, le=2000)
    # None / "learn" → 学习日默认选题（按 unit_id 抽取）
    # "weekly_review" / "monthly_review" → 按本周/本月练习记录的 word_id 选题
    task_type: TaskType | None = None
    # 题目来源：units（默认）或 wrong_book（错题本训练）
    source: Literal["units", "wrong_book"] = "units"


class SubmitAnswer(BaseModel):
    word_id: int = Field(..., ge=1)
    is_correct: bool
    user_answer: str | None = None
