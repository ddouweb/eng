"""Create all tables from SQLAlchemy models (SQLite/MySQL compatible)."""
import asyncio
from pathlib import Path

from app.database import engine
from app.models import Base  # noqa: F401 — imports all models


async def main():
    # Ensure data directory exists for SQLite
    if "sqlite" in str(engine.url):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
