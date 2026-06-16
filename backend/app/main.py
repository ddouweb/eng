import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.middleware.sensitive import SensitiveDataMiddleware
from app.schemas.exceptions import AppException, app_exception_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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

app.add_exception_handler(AppException, app_exception_handler)

app.add_middleware(SensitiveDataMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
