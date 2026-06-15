from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_postgres() -> None:
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    from rootcause.db.models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("postgres_ready")


async def close_postgres() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        log.info("postgres_closed")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("PostgreSQL not initialized")
    async with _session_factory() as session:
        async with session.begin():
            yield session
