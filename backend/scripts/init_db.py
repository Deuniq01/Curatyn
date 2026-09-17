"""
Creates the pgvector extension and all tables. Run once against a fresh
database: `python scripts/init_db.py`
Prefer Alembic migrations for anything beyond local dev / this smoke test.
"""
import asyncio

from sqlalchemy import text

from app.db import Base, engine
from app import models  # noqa: F401 — registers models on Base.metadata


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("Schema created.")


if __name__ == "__main__":
    asyncio.run(main())
