from pydantic import BaseModel, Field

from app.models.enums import PracticeMode


class PracticeStart(BaseModel):
    member_id: int = Field(1, ge=1)
    mode: PracticeMode
    unit_ids: list[int] = Field(..., min_length=1)
    count: int = Field(10, ge=1, le=2000)


class SubmitAnswer(BaseModel):
    word_id: int = Field(..., ge=1)
    is_correct: bool
    user_answer: str | None = None
