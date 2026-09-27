from __future__ import annotations

from backend.tools.web_search.search_client.travily_client import TravilyWebSearchClient


async def web_search(session_id: str, query: str) -> list[dict]:
    """Run web search for a session.

    Args:
        session_id: Session id for logs and traceability.
        query: Natural language web query.

    Returns:
        List of normalized web search result dicts.
    """
    client = TravilyWebSearchClient()
    results = await client.search(session_id, query)
    return [result.model_dump() for result in results]
