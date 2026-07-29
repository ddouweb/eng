import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.config import prepare_security, settings
from app.middleware.sensitive import SensitiveDataMiddleware
from app.schemas.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 启动期安全自检：生产环境若仍是弱口令/占位 JWT 密钥则直接拒绝启动；
    # 开发环境兜底为可用配置并打印告警。必须在服务对外提供前完成。
    prepare_security(settings)
    yield
    from app.ai.factory import close_ai_provider
    await close_ai_provider()
    from app.utils.cache import close_redis
    await close_redis()
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="Family English Coach",
    version="0.1.0",
    lifespan=lifespan,
)

# 统一错误信封：业务异常 + HTTPException(401/404/...) + 请求校验(422) 全部走 {code,message,data}
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(SensitiveDataMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
