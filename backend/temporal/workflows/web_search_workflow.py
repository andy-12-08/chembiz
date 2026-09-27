from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from backend.temporal.activities.web_search_activities import web_search_activity


@workflow.defn
class WebSearchWorkflow:
    """Workflow wrapper for one web search tool execution."""

    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict:
        """Run the web-search activity with a bounded execution time.

        Args:
            payload: Mapping containing session_id and query values.

        Returns:
            Serialized activity output containing normalized web results.
        """
        return await workflow.execute_activity(
            web_search_activity,
            args=[payload["session_id"], payload["query"]],
            start_to_close_timeout=timedelta(seconds=45),
        )
