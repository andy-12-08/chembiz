"""Async SQLAlchemy engine and FastAPI session dependency."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def database_url_async(raw: str | None) -> str:
    """Normalize DATABASE_URL for the async SQLAlchemy driver.

    Args:
        raw: DATABASE_URL string, usually postgresql://user:pass@host:port/dbname

    Returns:
        URL using the postgresql+psycopg_async driver.
    """
    if not raw or not raw.strip():
        raise ValueError("DATABASE_URL is not set")
    url = raw.strip()
    if url.startswith("postgresql+psycopg_async://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg_async://" + url.removeprefix("postgresql://")
    raise ValueError("DATABASE_URL must start with postgresql:// or postgresql+psycopg_async://")


def database_url_sync(raw: str | None) -> str:
    """Normalize DATABASE_URL for Alembic (sync psycopg3).

    Args:
        raw: Same value as the DATABASE_URL environment variable.

    Returns:
        URL using the postgresql+psycopg driver for migrations.
    """
    async_url = database_url_async(raw)
    return "postgresql+psycopg://" + async_url.removeprefix("postgresql+psycopg_async://")


async def engine_init() -> None:
    """Create the global async engine and session factory once (safe to call twice).

    Returns:
        None
    """
    global _engine, _async_session_maker
    if _engine is not None:
        return
    url = database_url_async(os.environ.get("DATABASE_URL"))
    _engine = create_async_engine(url, pool_pre_ping=True)
    _async_session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info(f"Database engine initialized")


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the global async session factory (after engine_init).

    Returns:
        Session factory for async with maker() as session (commit/rollback as needed).

    Raises:
        RuntimeError: If engine_init has not been called.
    """
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized; call engine_init() during startup")
    return _async_session_maker


async def engine_dispose() -> None:
    """Shut down the global async engine and clear factory state.

    Returns:
        None
    """
    global _engine, _async_session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info(f"Database engine disposed")


async def get_session_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one database session per HTTP request.

    Yields:
        An async SQLAlchemy session that commits after a successful request,
        rolls back after an exception, and always closes.

    Raises:
        RuntimeError: The database engine has not been initialized.
    """
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized; call engine_init() during startup")
    session_db = _async_session_maker()
    try:
        yield session_db
        await session_db.commit()
    except Exception:
        await session_db.rollback()
        raise
    finally:
        await session_db.close()
