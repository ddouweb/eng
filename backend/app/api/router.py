from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.health import router as health_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.member import router as member_router
from app.api.v1.ocr import router as ocr_router
from app.api.v1.plan import router as plan_router
from app.api.v1.practice import router as practice_router
from app.api.v1.stats import router as stats_router
from app.api.v1.tts import router as tts_router
from app.api.v1.unit import router as unit_router
from app.api.v1.word import router as word_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(member_router)
api_router.include_router(unit_router)
api_router.include_router(word_router)
api_router.include_router(ocr_router)
api_router.include_router(practice_router)
api_router.include_router(plan_router)
api_router.include_router(stats_router)
api_router.include_router(leaderboard_router)
api_router.include_router(ai_router)
api_router.include_router(tts_router)
