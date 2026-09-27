"""FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session_db
from database.session_dao import SessionDAO


async def get_session_dao(session_db: AsyncSession = Depends(get_session_db)) -> SessionDAO:
    """Inject SessionDAO bound to the request AsyncSession.

    Args:
        session_db: Request-scoped async database session.

    Returns:
        SessionDAO instance.
    """
    return SessionDAO(session_db)
