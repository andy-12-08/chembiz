from __future__ import annotations

import logging
import os
from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

_checkpointer: AsyncPostgresSaver | None = None
_checkpointer_cm: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None


def _checkpointer_database_url() -> str:
    """Return DATABASE_URL normalized for psycopg consumers.

    LangGraph checkpointers use psycopg directly, so SQLAlchemy dialect URLs
    like postgresql+psycopg://... are not accepted.

    Returns:
        A PostgreSQL URL accepted by psycopg.

    Raises:
        ValueError: DATABASE_URL is missing or uses an unsupported scheme.
    """
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        raise ValueError("DATABASE_URL is not set")
    if raw.startswith("postgresql+psycopg://"):
        return "postgresql://" + raw.removeprefix("postgresql+psycopg://")
    if raw.startswith("postgresql+psycopg_async://"):
        return "postgresql://" + raw.removeprefix("postgresql+psycopg_async://")
    if raw.startswith("postgresql://"):
        return raw
    raise ValueError(
        "DATABASE_URL must start with postgresql://, "
        "postgresql+psycopg://, or postgresql+psycopg_async://"
    )


async def init_deepsearch_checkpointer() -> None:
    """Initialize Postgres-backed LangGraph checkpointer for DeepSearch.

    Args:
        None

    Returns:
        None
    """
    global _checkpointer, _checkpointer_cm
    if _checkpointer is not None:
        return

    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(_checkpointer_database_url())
    try:
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
    except Exception:
        if _checkpointer_cm is not None:
            await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
        _checkpointer = None
        raise
    logger.info("DeepSearch checkpointer initialized")


def get_deepsearch_checkpointer() -> AsyncPostgresSaver:
    """Return initialized DeepSearch checkpointer instance.

    Args:
        None

    Returns:
        Initialized AsyncPostgresSaver instance.
    """
    if _checkpointer is None:
        raise RuntimeError("DeepSearch checkpointer not initialized")
    return _checkpointer


async def close_deepsearch_checkpointer() -> None:
    """Close DeepSearch checkpointer resources.

    Args:
        None

    Returns:
        None
    """
    global _checkpointer, _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
    _checkpointer_cm = None
    _checkpointer = None
    logger.info("DeepSearch checkpointer closed")
