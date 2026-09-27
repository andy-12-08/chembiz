"""Session-scoped dense retrieval: embed query, search Qdrant with payload filters."""

from __future__ import annotations

import logging
import os
import re
from math import sqrt

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from backend.config import (
    DEFAULT_RETRIEVAL_SCORE_THRESHOLD,
    DEFAULT_RETRIEVAL_TOP_K,
    INGEST_SCHEMA_VERSION,
    RETRIEVAL_LEXICAL_CANDIDATE_LIMIT,
    RETRIEVAL_LEXICAL_RESERVED_SLOTS,
    RETRIEVAL_TOP_K_MAX,
)
from backend.tools.doc_search.process_docs.embed_docs import EmbedDocument
from backend.models.pydantic_models import RetrievedChunk

logger = logging.getLogger(__name__)

_LEXICAL_STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "how",
    "into",
    "material",
    "materials",
    "say",
    "the",
    "their",
    "this",
    "what",
    "which",
    "with",
}


def _lexical_terms(text: str) -> set[str]:
    """Extract normalized content terms for lightweight lexical retrieval.

    Args:
        text: Query or document text.

    Returns:
        Unique lowercase alphanumeric terms excluding common question words.
    """
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if len(token) >= 3 and token not in _LEXICAL_STOP_WORDS
    }


def _lexical_score(query_terms: set[str], text: str) -> float:
    """Score a chunk by query-term coverage with a small length normalization.

    Args:
        query_terms: Normalized terms from the user query.
        text: Candidate chunk text.

    Returns:
        Nonnegative lexical relevance score; zero means no term overlap.
    """
    if not query_terms:
        return 0.0
    document_terms = _lexical_terms(text)
    overlap = len(query_terms & document_terms)
    if not overlap:
        return 0.0
    coverage = overlap / len(query_terms)
    length_penalty = sqrt(max(1.0, len(document_terms) / 200.0))
    return coverage / length_penalty


class DocumentRetriever:
    """Retrieve relevant chunks for one session (same embedding model and collection as ingest)."""

    def __init__(self, session_id: str) -> None:
        """Configure retrieval for a session and its owning user's document library.

        Args:
            session_id: Active session used for filtering, embedding logs, and tracing.

        Returns:
            None.
        """
        self._session_id = session_id
        self._collection = os.environ["QDRANT_COLLECTION"]
        url = os.environ["QDRANT_URL"]
        api_key = os.environ.get("QDRANT_API_KEY") or None
        self._client = QdrantClient(url=url, api_key=api_key)
        self._embedder = EmbedDocument()

    def _collection_exists(self) -> bool:
        """Check whether the configured Qdrant collection is available.

        Returns:
            True when Qdrant reports the configured collection name.
        """
        names = {c.name for c in self._client.get_collections().collections}
        return self._collection in names

    def _lexical_points(
        self,
        query: str,
        query_filter: Filter,
        limit: int,
    ) -> list[tuple[object, float]]:
        """Return top payload-bearing points from a filtered lexical scan.

        Args:
            query: Original user search text.
            query_filter: Same ownership and schema filter used for dense search.
            limit: Maximum lexical results to return.

        Returns:
            Qdrant points paired with local lexical scores, ordered by relevance.
        """
        query_terms = _lexical_terms(query)
        if not query_terms or limit <= 0:
            return []
        points, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=query_filter,
            limit=RETRIEVAL_LEXICAL_CANDIDATE_LIMIT,
            with_payload=True,
            with_vectors=False,
        )
        scored = []
        for point in points:
            payload = point.payload or {}
            score = _lexical_score(query_terms, str(payload.get("text") or ""))
            if score > 0:
                scored.append((score, point))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [(point, score) for score, point in scored[:limit]]

    async def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_RETRIEVAL_TOP_K,
        user_id: str | None = None,
        score_threshold: float | None = DEFAULT_RETRIEVAL_SCORE_THRESHOLD,
    ) -> list[RetrievedChunk]:
        """Dense search over chunks indexed for this session_id.

        Args:
            query: Natural language query.
            top_k: Number of chunks to return (capped at RETRIEVAL_TOP_K_MAX). Defaults to
                DEFAULT_RETRIEVAL_TOP_K from config.
            user_id: If set, points match when payload session_id or user_id equals the
                given values (Qdrant should). If None, only session_id is required.
            score_threshold: Drop hits with score strictly below this (cosine similarity).
                Defaults to DEFAULT_RETRIEVAL_SCORE_THRESHOLD; None means no cutoff.

        Returns:
            Ranked retrieved chunks, highest score first. Empty if query is blank or there
            are no matches.

        Raises:
            RuntimeError: Qdrant collection from QDRANT_COLLECTION env is not present, or a
                point has no payload.
            KeyError: A point payload is missing chunk_id, text, source, or file_id.
        """
        if not query.strip():
            return []

        if not self._collection_exists():
            raise RuntimeError(
                f"Qdrant collection does not exist: {self._collection} "
                f"(session_id={self._session_id})"
            )

        k = min(top_k, RETRIEVAL_TOP_K_MAX)

        query_vector = await self._embedder.embed_query(
            query.strip(),
            session_id=self._session_id,
        )

        if user_id is not None:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="ingest_schema_version",
                        match=MatchValue(value=INGEST_SCHEMA_VERSION),
                    ),
                ],
                should=[
                    FieldCondition(
                        key="session_id",
                        match=MatchValue(value=self._session_id),
                    ),
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id),
                    ),
                ]
            )
        else:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="ingest_schema_version",
                        match=MatchValue(value=INGEST_SCHEMA_VERSION),
                    ),
                    FieldCondition(
                        key="session_id",
                        match=MatchValue(value=self._session_id),
                    ),
                ]
            )

        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=query_filter,
            limit=k,
            with_payload=True,
        )
        dense_points = response.points
        lexical_slots = min(RETRIEVAL_LEXICAL_RESERVED_SLOTS, k)
        lexical_results = self._lexical_points(query.strip(), query_filter, lexical_slots)
        lexical_scores = {str(point.id): score for point, score in lexical_results}
        dense_limit = max(0, k - lexical_slots)
        scored_points = [point for point, _ in lexical_results]
        seen_point_ids = {str(point.id) for point in scored_points}
        for point in dense_points[:dense_limit]:
            if str(point.id) not in seen_point_ids:
                scored_points.append(point)
                seen_point_ids.add(str(point.id))
        for point in dense_points[dense_limit:]:
            if len(scored_points) >= k:
                break
            if str(point.id) not in seen_point_ids:
                scored_points.append(point)
                seen_point_ids.add(str(point.id))

        retrieved_chunks: list[RetrievedChunk] = []
        for point in scored_points:
            score = max(
                float(getattr(point, "score", 0.0) or 0.0),
                lexical_scores.get(str(point.id), 0.0),
            )
            if score_threshold is not None and score < score_threshold:
                continue
            payload = point.payload
            if payload is None:
                raise RuntimeError(
                    f"Qdrant point has no payload (point_id={getattr(point, 'id', None)})"
                )
            retrieved_chunks.append(
                RetrievedChunk(
                    chunk_id=str(payload["chunk_id"]),
                    text=str(payload["text"]),
                    source=str(payload["source"]),
                    file_id=str(payload["file_id"]),
                    source_session_id=str(payload["session_id"]),
                    pages=[int(page) for page in payload.get("pages") or []],
                    score=score,
                )
            )

        logger.info(
            f"Session ID: {self._session_id}; DocumentRetriever search "
            f"retrieved_chunks={len(retrieved_chunks)} top_k={k}"
        )
        return retrieved_chunks
