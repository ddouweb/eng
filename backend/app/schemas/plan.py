from datetime import date
from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    name: str = Field(..., max_length=100)
    daily_goal: int = Field(30, ge=1, le=200)
    unit_ids: list[int] = Field(..., min_length=1)
    deadline: date | None = None


class TaskUpdateBody(BaseModel):
    completed_new: int = Field(0, ge=0)
    completed_review: int = Field(0, ge=0)
