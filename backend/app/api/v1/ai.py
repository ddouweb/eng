from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.exercise_service import ExerciseService

router = APIRouter(prefix="/ai", tags=["ai"])


class DialogueRequest(BaseModel):
    unit_ids: list[int] = Field(..., min_length=1)
    scenario: str = Field("日常对话", max_length=100)


class ExerciseRequest(BaseModel):
    unit_ids: list[int] = Field(..., min_length=1)
    mode: str = Field("choice", pattern="^(choice|fill)$")


@router.post("/dialogue")
async def generate_dialogue(body: DialogueRequest, db: AsyncSession = Depends(get_db)):
    """生成场景对话。

    Example:
        curl -X POST http://localhost:8000/api/v1/ai/dialogue \\
             -H 'Content-Type: application/json' \\
             -d '{"unit_ids":[1,2],"scenario":"购物"}'
    """
    svc = ExerciseService(db)
    return await svc.generate_dialogue(body.unit_ids, body.scenario)


@router.post("/exercise")
async def generate_exercise(body: ExerciseRequest, db: AsyncSession = Depends(get_db)):
    """生成 AI 练习题。

    Example:
        curl -X POST http://localhost:8000/api/v1/ai/exercise \\
             -H 'Content-Type: application/json' \\
             -d '{"unit_ids":[1],"mode":"choice"}'
    """
    svc = ExerciseService(db)
    return await svc.generate_exercise(body.unit_ids, body.mode)
