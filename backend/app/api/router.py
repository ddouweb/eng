from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.member import router as member_router
from app.api.v1.plan import router as plan_router
from app.api.v1.practice import router as practice_router
from app.api.v1.stats import router as stats_router
from app.api.v1.tts import router as tts_router
from app.api.v1.unit import router as unit_router
from app.api.v1.word import router as word_router

api_router = APIRouter(prefix="/api/v1")

# 不需要认证的路由
api_router.include_router(auth_router)
api_router.include_router(health_router)

# 需要 JWT 认证的路由
_auth = Depends(get_current_user)
for r in [
    member_router, unit_router, word_router,
    practice_router, plan_router, stats_router, leaderboard_router,
    ai_router, tts_router,
]:
    api_router.include_router(r, dependencies=[_auth])
