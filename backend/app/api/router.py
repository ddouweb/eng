from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.checkin import router as checkin_router
from app.api.v1.health import router as health_router
from app.api.v1.lottery import router as lottery_router
from app.api.v1.plan import router as plan_router
from app.api.v1.practice import router as practice_router
from app.api.v1.review import router as review_router
from app.api.v1.stats import router as stats_router
from app.api.v1.tts import router as tts_router
from app.api.v1.unit import router as unit_router
from app.api.v1.word import router as word_router
from app.api.v1.wrong_book import router as wrong_book_router

api_router = APIRouter(prefix="/api/v1")

# 不需要认证的路由
api_router.include_router(auth_router)
api_router.include_router(health_router)
# TTS 免登录：st.audio 加载音频时不带 Authorization 头，且音频内容无敏感性
api_router.include_router(tts_router)

# 需要 JWT 认证的路由
_auth = Depends(get_current_user)
for r in [
    unit_router, word_router,
    practice_router, review_router, plan_router, stats_router,
    ai_router, checkin_router, wrong_book_router, lottery_router,
]:
    api_router.include_router(r, dependencies=[_auth])
