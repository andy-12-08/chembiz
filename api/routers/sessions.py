import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.deps import get_session_dao
from backend.models.pydantic_models import CreateSessionRequest, CreateSessionResponse
from database.session_dao import SessionDAO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "/",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_session",
)
async def create_session(
    request_body: CreateSessionRequest,
    session_dao: SessionDAO = Depends(get_session_dao),
) -> CreateSessionResponse:
    """Create a session and return a new session id.

    Args:
        request_body: Client user id and query.
        session_dao: Session data access.

    Returns:
        New session identifier (UUID string).

    Raises:
        HTTPException: 409 if duplicate session id; 503 on database errors.
    """
    session_id = str(uuid.uuid4())
    try:
        await session_dao.insert_session(
            session_id,
            request_body.user_id,
            request_body.user_query,
        )
    except IntegrityError as e:
        logger.exception(f"create_session integrity error session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session already exists",
        ) from e
    except SQLAlchemyError as e:
        logger.exception(f"create_session database error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from e

    logger.info(f"Session created session_id={session_id}")
    return CreateSessionResponse(session_id=session_id)
