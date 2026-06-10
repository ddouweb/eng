from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.ocr import router as ocr_router
from app.api.v1.plan import router as plan_router
from app.api.v1.practice import router as practice_router
from app.api.v1.unit import router as unit_router
from app.api.v1.word import router as word_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(unit_router)
api_router.include_router(word_router)
api_router.include_router(ocr_router)
api_router.include_router(practice_router)
api_router.include_router(plan_router)
