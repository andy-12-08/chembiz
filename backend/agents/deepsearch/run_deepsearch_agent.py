"""Run one DeepSearch job: load run row, invoke agent, persist handoff output."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import select

from backend.agents.deepsearch.graph import get_deepsearch_agent
from backend.agents.deepsearch.handoff_payload import (
    build_handoff_payload,
    final_answer_from_result,
)
from backend.config import (
    DEEPSEARCH_AGENT_TIMEOUT_SECONDS,
    DEEPSEARCH_HANDOFF_TIMEOUT_SECONDS,
    DEEPSEARCH_RECURSION_LIMIT,
)
from backend.prompts.deepsearch_agent_prompt import (
    DEEPSEARCH_SYSTEM_PROMPT,
    build_deepsearch_user_prompt,
)
from database.db import get_async_session_maker
from database.models import AgentOutputRecord, RunRecord, RunStatus

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


def _consume_detached_task(task: asyncio.Future) -> None:
    """Consume a detached task result so late cancellation cannot log warnings.

    Args:
        task: Timed-out task that was cancelled without awaiting completion.

    Returns:
        None.
    """
    try:
        task.result()
    except BaseException:
        pass


async def _await_with_deadline(
    awaitable: Awaitable[_T],
    *,
    timeout_seconds: int,
    stage_name: str,
) -> _T:
    """Await work until a hard status deadline without waiting for cancellation.

    Args:
        awaitable: Agent or handoff operation to execute.
        timeout_seconds: Maximum seconds before returning a terminal timeout.
        stage_name: Human-readable stage used in the error message.

    Returns:
        Completed awaitable result.

    Raises:
        TimeoutError: The operation is not complete at the deadline.
    """
    task = asyncio.ensure_future(awaitable)
    done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
    if task not in done:
        task.cancel()
        task.add_done_callback(_consume_detached_task)
        raise TimeoutError(f"{stage_name} exceeded {timeout_seconds} seconds")
    return await task


async def run_deepsearch_agent(run_id: str) -> None:
    """Load a queued run, execute DeepSearch, write status and handoff artifact.

    Args:
        run_id: UUID string of the run row.

    Returns:
        None. Updates the run row in place; logs and returns early if the run is missing.
    """
    run_uuid = uuid.UUID(run_id)
    session_maker = get_async_session_maker()

    async with session_maker() as session_db:
        run = (
            await session_db.execute(select(RunRecord).where(RunRecord.run_id == run_uuid))
        ).scalar_one_or_none()
        if run is None:
            logger.error("Run not found run_id=%s", run_id)
            return

        session_id = str(run.session_id)
        run.status = RunStatus.running
        run.started_at = datetime.now(timezone.utc)
        await session_db.commit()
        logger.info("DeepSearch run started run_id=%s session_id=%s", run_id, session_id)

        try:
            agent = get_deepsearch_agent()
            invoke_payload = {
                "messages": [
                    {"role": "system", "content": DEEPSEARCH_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_deepsearch_user_prompt(
                            session_id=str(run.session_id),
                            query=run.query_snapshot,
                        ),
                    },
                ]
            }
            agent_result = await _await_with_deadline(
                agent.ainvoke(
                    invoke_payload,
                    config={
                        "configurable": {"thread_id": str(run.run_id)},
                        "recursion_limit": DEEPSEARCH_RECURSION_LIMIT,
                    },
                ),
                timeout_seconds=DEEPSEARCH_AGENT_TIMEOUT_SECONDS,
                stage_name="DeepSearch research stage",
            )

            draft_answer = final_answer_from_result(agent_result)
            handoff = await _await_with_deadline(
                build_handoff_payload(run, agent_result),
                timeout_seconds=DEEPSEARCH_HANDOFF_TIMEOUT_SECONDS,
                stage_name="DeepSearch handoff stage",
            )

            run.final_answer = handoff["answer"]
            run.status = RunStatus.succeeded
            run.finished_at = datetime.now(timezone.utc)
            session_db.add(
                AgentOutputRecord(
                    session_id=run.session_id,
                    run_id=run.run_id,
                    agent_name="deepsearch",
                    output_type="handoff",
                    payload=handoff,
                )
            )
            await session_db.commit()
            logger.info(
                "DeepSearch run completed run_id=%s session_id=%s draft_chars=%s grounded_claims=%s",
                run_id,
                session_id,
                len(draft_answer),
                len(handoff.get("claims") or []),
            )
        except Exception as e:
            run.status = RunStatus.failed
            run.error_message = str(e)
            run.finished_at = datetime.now(timezone.utc)
            await session_db.commit()
            logger.exception("DeepSearch run failed run_id=%s session_id=%s", run_id, session_id)
