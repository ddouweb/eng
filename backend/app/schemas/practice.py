from pydantic import BaseModel, Field

from app.models.enums import PracticeMode, TaskType


class PracticeStart(BaseModel):
    member_id: int = Field(1, ge=1)
    mode: PracticeMode
    # 选中的 Unit 列表，可含虚拟错题本单元 ID（0）与真实 Unit 多选混合
    unit_ids: list[int] = Field(..., min_length=1)
    count: int = Field(10, ge=1, le=2000)
    # None / "learn" → 学习日默认选题（按 unit_id 抽取）
    # "weekly_review" / "monthly_review" → 按本周/本月练习记录的 word_id 选题
    task_type: TaskType | None = None
    # True → 「全部」主动复习：兜底选词池允许未到期的 permanent 词进入（仅自由练习全量模式）
    include_mastered: bool = False


class SubmitAnswer(BaseModel):
    word_id: int = Field(..., ge=1)
    is_correct: bool
    user_answer: str | None = None


class Rejudge(BaseModel):
    """结束页改判某题正误（人工覆盖，绕过客观题服务端复判与 submit 的幂等去重）。"""
    word_id: int = Field(..., ge=1)
    is_correct: bool
