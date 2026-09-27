from __future__ import annotations

import logging
import uuid
from pathlib import Path

import pymupdf
import tiktoken

from backend.config import INGEST_CHUNK_OVERLAP_TOKENS, INGEST_CHUNK_TOKENS
from backend.models.pydantic_models import ProcessedChunk
from backend.tools.doc_search.process_docs.page_metadata import pages_for_chunk

logger = logging.getLogger(__name__)


class PreprocessDocumentPymupdf:
    """Parse and chunk one uploaded file using PyMuPDF + token windows."""

    def __init__(
        self,
        session_id: str | uuid.UUID,
        user_id: str,
        file_id: str,
        file_name: str,
        content_hash: str,
    ) -> None:
        """Bind PDF preprocessing to one stored document.

        Args:
            session_id: Session associated with the document.
            user_id: Owner whose library receives the resulting vectors.
            file_id: Stable identifier stored with every produced chunk.
            file_name: Original filename exposed as citation source metadata.
            content_hash: SHA-256 digest used for content-level deduplication.

        Returns:
            None.
        """
        self.session_id = str(session_id) if isinstance(session_id, uuid.UUID) else session_id
        self.user_id = user_id
        self.file_id = file_id
        self.file_name = file_name
        self.content_hash = content_hash

    def parse_document(self, path: str | Path) -> str:
        """Parse a file with PyMuPDF and return plain text.

        Args:
            path: Document path on disk.

        Returns:
            Extracted document text.

        Raises:
            FileNotFoundError: Not a file.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)

        resolved = str(path.resolve())
        logger.info(
            f"Session ID: {self.session_id}; file_id={self.file_id}; "
            f"file_name={self.file_name}; Parsing document (pymupdf): {resolved}"
        )

        page_texts: list[str] = []
        with pymupdf.open(resolved) as doc:
            for idx, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    page_texts.append(f"[page {idx}]\n{text}")
        return "\n\n".join(page_texts)

    def chunk_document(self, doc: str) -> list[ProcessedChunk]:
        """Chunk parsed text with token-aware windows.

        Args:
            doc: Parsed document text.

        Returns:
            Chunks in order.
        """
        if not doc.strip():
            return []

        try:
            encoding = tiktoken.encoding_for_model("text-embedding-3-large")
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        token_ids = encoding.encode(doc)
        step = max(1, INGEST_CHUNK_TOKENS - INGEST_CHUNK_OVERLAP_TOKENS)

        chunks: list[ProcessedChunk] = []
        current_page: int | None = None
        for start in range(0, len(token_ids), step):
            end = min(start + INGEST_CHUNK_TOKENS, len(token_ids))
            chunk_text = encoding.decode(token_ids[start:end]).strip()
            if not chunk_text:
                continue
            pages, current_page = pages_for_chunk(chunk_text, current_page)
            chunks.append(
                ProcessedChunk(
                    chunk_id=uuid.uuid4().hex[:8],
                    text=chunk_text,
                    source=self.file_name,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    file_id=self.file_id,
                    content_hash=self.content_hash,
                    pages=pages,
                )
            )
            if end >= len(token_ids):
                break

        logger.info(
            f"Session ID: {self.session_id}; file_id={self.file_id}; "
            f"chunk_document (pymupdf) produced count={len(chunks)}"
        )
        return chunks
