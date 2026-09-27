from __future__ import annotations

import logging

from openai import AsyncOpenAI

from backend.config import embedding
from backend.models.pydantic_models import EmbeddedChunk, ProcessedChunk

logger = logging.getLogger(__name__)


class EmbedDocument:
    """Embed chunk texts using the OpenAI embeddings API."""

    def __init__(self, *, model: str | None = None) -> None:
        """Create an embedding adapter using the configured OpenAI model.

        Args:
            model: Optional model override; defaults to the shared embedding configuration.

        Returns:
            None.
        """
        self._model = model if model is not None else embedding.model
        self._client = AsyncOpenAI()

    async def embed_chunks(
        self,
        chunks: list[ProcessedChunk],
        *,
        session_id: str | None = None,
    ) -> list[EmbeddedChunk]:
        """Return one EmbeddedChunk per input, preserving order.

        Args:
            chunks: Chunks from PreprocessDocument.chunk_document.
            session_id: Optional explicit session id for tracing/logging.

        Returns:
            Same length as chunks; each item pairs the chunk with its vector.
        """
        if not chunks:
            logger.warning(f"Session ID: {session_id}; embed_chunks called with empty list")
            return []

        batch_size = embedding.batch_size
        embedded_chunks: list[EmbeddedChunk] = []
        session_id = session_id or chunks[0].session_id
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.text for c in batch]
            logger.info(
                f"Session ID: {session_id}; Embedding batch start_index={i} "
                f"size={len(batch)} model={self._model}"
            )
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            for chunk, data in zip(batch, response.data, strict=True):
                embedded_chunks.append(
                    EmbeddedChunk(chunk=chunk, embedding=list(data.embedding)),
                )

        logger.info(
            f"Session ID: {session_id}; embed_chunks complete "
            f"total={len(embedded_chunks)} model={self._model}"
        )
        return embedded_chunks

    async def embed_query(self, text: str, *, session_id: str | None = None) -> list[float]:
        """Embed a single search query with the same model as chunk ingest.

        Args:
            text: Query string (non-empty).
            session_id: Optional id for log lines.

        Returns:
            One embedding vector (same dimension as document chunks).

        Raises:
            ValueError: Empty or whitespace-only text.
        """
        if not text.strip():
            raise ValueError("embed_query requires non-empty text")
        logger.info(
            f"Session ID: {session_id}; embed_query model={self._model} "
            f"chars={len(text)}"
        )
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return list(response.data[0].embedding)
