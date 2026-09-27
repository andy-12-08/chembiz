from __future__ import annotations

import asyncio
import logging
import os

from temporalio.worker import Worker

from backend.logging_setup import configure_logging
from backend.temporal.activities.doc_ingest_activities import process_session_documents_activity
from backend.temporal.activities.web_search_activities import web_search_activity
from backend.temporal.client import get_temporal_client
from backend.temporal.workflows.doc_ingest_workflow import ProcessSessionDocumentsWorkflow
from backend.temporal.workflows.web_search_workflow import WebSearchWorkflow

configure_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run Temporal worker for workflows.

    Args:
        None

    Returns:
        None. This coroutine blocks while the worker polls for tasks.
    """
    client = await get_temporal_client()
    task_queue = os.environ["TEMPORAL_TASK_QUEUE"]
    logger.info(f"Temporal worker start task_queue={task_queue}")
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ProcessSessionDocumentsWorkflow, WebSearchWorkflow],
        activities=[process_session_documents_activity, web_search_activity],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
