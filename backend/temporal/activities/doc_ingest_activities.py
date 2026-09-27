from __future__ import annotations

import asyncio
import logging

from temporalio import activity

import database.db as db
from backend.tools.doc_search.process_docs.process_docs_unstructured import (
    ProcessDocumentsUnstructured,
)
from database.session_dao import SessionDAO

logger = logging.getLogger(__name__)


async def _heartbeat_loop(session_id: str, sub_dir: str) -> None:
    """Emit periodic Temporal heartbeats while document ingestion runs.

    Args:
        session_id: Session whose documents are being ingested.
        sub_dir: Session data subdirectory being processed.

    Returns:
        None. The coroutine runs until its task is cancelled.
    """
    while True:
        activity.heartbeat(f"session_id={session_id} sub_dir={sub_dir} status=running")
        await asyncio.sleep(30)


@activity.defn(name="process_session_documents_activity")
async def process_session_documents_activity(session_id: str, sub_dir: str) -> dict:
    """Run document ingest for one session and subdirectory.

    Args:
        session_id: Session UUID string.
        sub_dir: uploads or generated.

    Returns:
        Serialized SessionFilesIngestionOutput.
    """
    logger.info(f"Session ID: {session_id}; temporal activity start sub_dir={sub_dir}")
    await db.engine_init()
    session_maker = db.get_async_session_maker()
    heartbeat_task = asyncio.create_task(_heartbeat_loop(session_id, sub_dir))
    try:
        async with session_maker() as session_db:
            session_dao = SessionDAO(session_db)
            result = await ProcessDocumentsUnstructured(session_id).process_session_documents(
                session_dao,
                sub_dir=sub_dir,
            )
            await session_db.commit()
            logger.info(
                f"Session ID: {session_id}; temporal activity complete "
                f"all_ok={result.all_ok} files={len(result.files)}"
            )
            return result.model_dump()
    except Exception:
        logger.exception(f"Session ID: {session_id}; temporal activity failed sub_dir={sub_dir}")
        raise
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        await db.engine_dispose()
