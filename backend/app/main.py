import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.schemas.exceptions import AppException, app_exception_handler

UPLOAD_DIR = Path("uploads")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    UPLOAD_DIR.mkdir(exist_ok=True)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.include_router(api_router)
