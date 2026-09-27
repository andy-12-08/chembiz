from __future__ import annotations

import logging
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from backend.config import (
    INGEST_SCHEMA_VERSION,
    QDRANT_SCROLL_BATCH,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_UPSERT_BATCH_SIZE,
)
from backend.models.pydantic_models import EmbeddedChunk

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Upsert embedded chunks into a Qdrant collection."""

    def __init__(self, session_id: str) -> None:
        """Configure a Qdrant client for one traced ingestion session.

        Args:
            session_id: Session identifier included in operational log messages.

        Returns:
            None.
        """
        url = os.environ["QDRANT_URL"]
        collection_name = os.environ["QDRANT_COLLECTION"]
        api_key = os.environ.get("QDRANT_API_KEY") or None

        self._session_id = session_id
        self._client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=QDRANT_TIMEOUT_SECONDS,
        )
        self._collection = collection_name

        logger.info(
            f"Session ID: {self._session_id}; QdrantVectorStore init "
            f"url={url} collection={collection_name} "
            f"timeout_s={QDRANT_TIMEOUT_SECONDS} upsert_batch={QDRANT_UPSERT_BATCH_SIZE}"
        )

    def ensure_collection(self, vector_size: int) -> None:
        """Create the collection if it does not exist (cosine distance).

        Args:
            vector_size: Embedding dimension (e.g. 3072 for text-embedding-3-large).
        """
        names = {c.name for c in self._client.get_collections().collections}
        if self._collection in names:
            logger.info(
                f"Session ID: {self._session_id}; "
                f"Qdrant collection exists name={self._collection}"
            )
            return
        try:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        except UnexpectedResponse as e:
            if e.status_code == 409:
                logger.info(
                    f"Session ID: {self._session_id}; Qdrant collection already exists "
                    f"(concurrent create) name={self._collection}"
                )
                return
            raise
        logger.info(
            f"Session ID: {self._session_id}; Qdrant collection created "
            f"name={self._collection} vector_size={vector_size}"
        )

    def upsert_embedded(self, items: list[EmbeddedChunk]) -> None:
        """Upsert points in batches; point id is deterministic per session, file, and chunk.

        Args:
            items: Embedded chunks to store.

        Returns:
            None
        """
        if not items:
            logger.warning(
                f"Session ID: {self._session_id}; upsert_embedded called with empty list"
            )
            return

        dim = len(items[0].embedding)
        self.ensure_collection(dim)

        points: list[PointStruct] = []
        for item in items:
            c = item.chunk
            point_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{c.session_id}:{c.file_id}:{c.chunk_id}",
            )
            payload = {
                "chunk_id": c.chunk_id,
                "session_id": c.session_id,
                "user_id": c.user_id,
                "file_id": c.file_id,
                "content_hash": c.content_hash,
                "ingest_schema_version": INGEST_SCHEMA_VERSION,
                "pages": c.pages,
                "text": c.text,
                "source": c.source,
            }
            points.append(
                PointStruct(
                    id=point_id,
                    vector=item.embedding,
                    payload=payload,
                )
            )

        total = len(points)
        for start in range(0, total, QDRANT_UPSERT_BATCH_SIZE):
            batch = points[start : start + QDRANT_UPSERT_BATCH_SIZE]
            self._client.upsert(collection_name=self._collection, points=batch)
            logger.info(
                f"Session ID: {self._session_id}; Qdrant upsert batch ok "
                f"collection={self._collection} size={len(batch)} "
                f"start={start} end={start + len(batch)} total={total}"
            )

    def find_existing_content_hashes(
        self,
        user_id: str,
        content_hashes: list[str],
    ) -> set[str]:
        """Return content hashes that already have vectors for this user.

        This powers user-level file dedupe for the current ingestion schema: if a
        new session uploads the same file bytes, ingestion can skip parse/embed
        and rely on the user's existing current-schema Qdrant chunks.

        Args:
            user_id: Owning user id to dedupe within.
            content_hashes: SHA-256 file content hashes to look up.

        Returns:
            Subset of content_hashes already present in the collection for user_id.
        """
        if not content_hashes:
            return set()

        collection_names = {c.name for c in self._client.get_collections().collections}
        if self._collection not in collection_names:
            return set()

        requested_hashes = set(content_hashes)
        existing_hashes: set[str] = set()

        scroll_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                ),
                FieldCondition(
                    key="content_hash",
                    match=MatchAny(any=content_hashes),
                ),
                FieldCondition(
                    key="ingest_schema_version",
                    match=MatchValue(value=INGEST_SCHEMA_VERSION),
                ),
            ]
        )

        next_offset = None
        while True:
            points, next_offset = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=scroll_filter,
                limit=QDRANT_SCROLL_BATCH,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                existing_hashes.add(str(payload["content_hash"]))

            if next_offset is None or requested_hashes <= existing_hashes:
                break

        return existing_hashes
