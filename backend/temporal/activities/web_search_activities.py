from __future__ import annotations

from temporalio import activity

from backend.tools.web_search.web_search import web_search


@activity.defn
async def web_search_activity(session_id: str, query: str) -> dict:
    """Execute a normalized web search inside a Temporal activity.

    Args:
        session_id: Session identifier used for traceable logging.
        query: Natural-language search query.

    Returns:
        A workflow-serializable mapping containing normalized search results.
    """
    results = await web_search(session_id=session_id, query=query)
    return {"results": results}
