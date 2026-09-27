from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

_INGEST_START_TO_CLOSE_TIMEOUT = timedelta(hours=6)
_INGEST_HEARTBEAT_TIMEOUT = timedelta(minutes=30)
_INGEST_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=0,
)


@workflow.defn(name="ProcessSessionDocumentsWorkflow")
class ProcessSessionDocumentsWorkflow:
    """Workflow that processes session documents for one subdirectory."""

    @workflow.run
    async def run(self, session_id: str, sub_dir: str) -> dict:
        """Execute ingest activity with retries.

        Args:
            session_id: Session UUID string.
            sub_dir: uploads or generated.

        Returns:
            Serialized SessionFilesIngestionOutput from activity.
        """
        workflow.logger.info(
            f"Session ID: {session_id}; workflow start ProcessSessionDocumentsWorkflow sub_dir={sub_dir}"
        )
        result = await workflow.execute_activity(
            "process_session_documents_activity",
            args=[session_id, sub_dir],
            start_to_close_timeout=_INGEST_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=_INGEST_HEARTBEAT_TIMEOUT,
            retry_policy=_INGEST_RETRY_POLICY,
        )
        workflow.logger.info(
            f"Session ID: {session_id}; workflow complete ProcessSessionDocumentsWorkflow"
        )
        return result
