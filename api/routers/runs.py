import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.deepsearch.run_deepsearch_agent import run_deepsearch_agent
from backend.models.pydantic_models import (
    AgentOutputResponse,
    GetRunResponse,
    StartRunRequest,
    StartRunResponse,
)
from database.db import get_session_db
from database.models import AgentOutputRecord, RunRecord, RunStatus, SessionRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post(
    "/",
    response_model=StartRunResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="start_run",
)
async def start_run(
    background_tasks: BackgroundTasks,
    body: StartRunRequest,
    session_db: AsyncSession = Depends(get_session_db),
) -> StartRunResponse:
    """Create a run for an existing session and enqueue DeepSearch execution.

    Args:
        background_tasks: FastAPI background task queue.
        body: Session id and user id (must match session owner; used for retrieval filtering).
        session_db: Request-scoped async database session.

    Returns:
        Created run id and initial status.
    """
    try:
        session_uuid = uuid.UUID(body.session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid session_id") from None

    session_row = (
        await session_db.execute(
            select(SessionRecord).where(SessionRecord.session_id == session_uuid)
        )
    ).scalar_one_or_none()
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if body.user_id != session_row.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id does not match session owner",
        )

    run = RunRecord(
        session_id=session_row.session_id,
        status=RunStatus.queued,
        query_snapshot=session_row.user_query,
    )
    session_db.add(run)
    await session_db.flush()
    run_id = run.run_id
    logger.info(f"Run queued run_id={run_id} session_id={body.session_id}")
    await session_db.commit()

    background_tasks.add_task(run_deepsearch_agent, str(run_id))
    return StartRunResponse(run_id=str(run_id), status=run.status.value)


@router.get(
    "/{run_id}",
    response_model=GetRunResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_run",
)
async def get_run(
    run_id: str,
    session_db: AsyncSession = Depends(get_session_db),
) -> GetRunResponse:
    """Fetch one run status and current result fields.

    Args:
        run_id: Run id path parameter.
        session_db: Request-scoped async database session.

    Returns:
        Run status payload including final answer and error fields.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid run_id") from None

    try:
        run = await session_db.get(RunRecord, run_uuid)
    except SQLAlchemyError as e:
        logger.exception(f"get_run database error run_id={run_id}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable") from e

    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    logger.info(f"Run fetched run_id={run_id} session_id={run.session_id}")

    return GetRunResponse(
        run_id=str(run.run_id),
        session_id=str(run.session_id),
        status=run.status.value,
        query_snapshot=run.query_snapshot,
        final_answer=run.final_answer,
        error_message=run.error_message,
    )


@router.get(
    "/{run_id}/output",
    response_model=AgentOutputResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_run_output",
)
async def get_run_output(
    run_id: str,
    session_db: AsyncSession = Depends(get_session_db),
) -> AgentOutputResponse:
    """Fetch latest structured handoff artifact for a run.

    Args:
        run_id: Run id path parameter.
        session_db: Request-scoped async database session.

    Returns:
        Latest structured agent output row for the run.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid run_id") from None

    output = (
        await session_db.execute(
            select(AgentOutputRecord)
            .where(AgentOutputRecord.run_id == run_uuid)
            .order_by(AgentOutputRecord.created_at.desc())
        )
    ).scalars().first()
    if output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run output not found")
    logger.info(f"Run output fetched run_id={run_id} session_id={output.session_id}")

    return AgentOutputResponse(
        output_id=str(output.output_id),
        session_id=str(output.session_id),
        run_id=str(output.run_id),
        agent_name=output.agent_name,
        output_type=output.output_type,
        payload=output.payload,
    )
