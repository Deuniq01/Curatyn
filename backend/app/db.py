"""
Async SQLAlchemy engine.

DATABASE_URL is normalized here so you can paste a Supabase connection
string almost verbatim:
  * the scheme is coerced to `postgresql+asyncpg://`
  * libpq-only query params asyncpg rejects (`sslmode`, `channel_binding`)
    are stripped and translated into asyncpg `connect_args`
  * for Supabase hosts we force SSL and disable the prepared-statement
    cache, which is required when connecting through the pgbouncer pooler.
"""
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import ssl

from app.config import settings


def _build_engine():
    url = make_url(settings.database_url)

    # Coerce plain postgres schemes to the async driver.
    if url.drivername in ("postgresql", "postgres", "postgresql+psycopg2"):
        url = url.set(drivername="postgresql+asyncpg")

    connect_args: dict = {}

    # asyncpg does not understand libpq's sslmode/channel_binding query args.
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    url = url.set(query=query)

    host = url.host or ""
    is_supabase = "supabase.co" in host or "supabase.com" in host

    if is_supabase or (sslmode and sslmode != "disable"):
        connect_args["ssl"] = (
            ssl.create_default_context()
            if settings.database_ssl_verify
            else ssl._create_unverified_context()
        )
    if is_supabase:
        # Required behind Supabase's pgbouncer transaction pooler.
        connect_args["statement_cache_size"] = 0

    return create_async_engine(url, echo=False, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = _build_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
