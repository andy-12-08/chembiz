"""Session document search: retrieve chunks from existing indexed session docs."""

from __future__ import annotations

from backend.config import DEFAULT_RETRIEVAL_SCORE_THRESHOLD, DEFAULT_RETRIEVAL_TOP_K
from backend.tools.doc_search.retriever.document_retriever import DocumentRetriever
from database.db import get_async_session_maker
from database.session_dao import SessionDAO


async def document_search(
    session_id: str,
    query: str,
) -> list[dict]:
    """Run dense retrieval over already indexed session documents.

    Args:
        session_id: Session UUID string.
        query: Natural language search query.
    Returns:
        List of dicts, one per retrieved chunk (chunk_id, text, source, file_id,
        source_session_id, pages, and score).

    Retrieval breadth uses DEFAULT_RETRIEVAL_TOP_K in backend.config.
    """
    maker = get_async_session_maker()
    async with maker() as session_db:
        session_dao = SessionDAO(session_db)
        user_id = await session_dao.get_user_id(session_id)
        retriever = DocumentRetriever(session_id)
        chunks = await retriever.search(
            query,
            top_k=DEFAULT_RETRIEVAL_TOP_K,
            user_id=user_id,
            score_threshold=DEFAULT_RETRIEVAL_SCORE_THRESHOLD,
        )
        await session_db.commit()

    return [chunk.model_dump() for chunk in chunks]
