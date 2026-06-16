"""Initialize database: create tables from models and load seed data.

Idempotent — safe to re-run. Tables are created with checkfirst=True
(skip existing); seed data uses TRUNCATE then INSERT inside init_data.sql,
so every run resets to the factory dataset.

Usage:
    python init_db.py
"""
import asyncio
import sys
from pathlib import Path

import aiomysql
from pymysql.constants import CLIENT
from sqlalchemy.engine import make_url

from app.config import settings
from app.database import engine
from app.models import Base  # noqa: F401 — imports all models for create_all

SEED_SQL_PATH = Path(__file__).parent / "init_data.sql"


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("[1/2] Tables created (skipped any that already exist).")


async def load_seed_data() -> None:
    if not SEED_SQL_PATH.exists():
        print(f"[skip] Seed file not found: {SEED_SQL_PATH}")
        return

    url = make_url(settings.DATABASE_URL)
    sql_text = SEED_SQL_PATH.read_text(encoding="utf-8")

    conn = await aiomysql.connect(
        host=url.host or "localhost",
        port=url.port or 3306,
        user=url.username or "root",
        password=url.password or "",
        db=url.database or "english_coach",
        charset="utf8mb4",
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(sql_text)
            await cur.execute("SELECT COUNT(*) FROM member")
            members = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(*) FROM unit")
            units = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(*) FROM word")
            words = (await cur.fetchone())[0]
        print(f"[2/2] Seed data loaded: members={members}, units={units}, words={words}")
    finally:
        conn.close()


async def main() -> None:
    print(f"Target DB: {settings.DATABASE_URL}")
    try:
        await create_tables()
        await load_seed_data()
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
