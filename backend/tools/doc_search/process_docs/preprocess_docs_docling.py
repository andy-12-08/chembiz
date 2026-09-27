from __future__ import annotations

import logging
import uuid
from pathlib import Path

import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling_core.types import DoclingDocument
from backend.models.pydantic_models import ProcessedChunk

logger = logging.getLogger(__name__)


class PreprocessDocumentDocling:
    """Parse and chunk one uploaded file with Docling; identity fixed at init."""

    def __init__(
        self,
        session_id: str | uuid.UUID,
        user_id: str,
        file_id: str,
        file_name: str,
        content_hash: str,
    ) -> None:
        """Bind Docling preprocessing to one stored document.

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

    def parse_document(self, path: str | Path) -> DoclingDocument:
        """Parse a file with Docling.

        Args:
            path: Document path on disk.

        Returns:
            Parsed document.

        Raises:
            FileNotFoundError: Not a file.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)

        resolved = str(path.resolve())
        logger.info(
            f"Session ID: {self.session_id}; file_id={self.file_id}; "
            f"file_name={self.file_name}; Parsing document: {resolved}"
        )
        converter = DocumentConverter()
        result = converter.convert(resolved)
        return result.document

    def chunk_document(
        self,
        doc: DoclingDocument,
        *,
        merge_peers: bool = True,
    ) -> list[ProcessedChunk]:
        """Chunk a parsed document.

        Args:
            doc: Parsed document.
            merge_peers: HybridChunker option.

        Returns:
            Chunks in order.
        """
        try:
            encoding = tiktoken.encoding_for_model("text-embedding-3-large")
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        tokenizer = OpenAITokenizer(tokenizer=encoding, max_tokens=8191)
        chunker = HybridChunker(tokenizer=tokenizer, merge_peers=merge_peers)
        raw_chunks = list(chunker.chunk(dl_doc=doc))

        chunks: list[ProcessedChunk] = []
        for chunk in raw_chunks:
            chunks.append(
                ProcessedChunk(
                    chunk_id=uuid.uuid4().hex[:8],
                    text=chunk.text,
                    source=self.file_name,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    file_id=self.file_id,
                    content_hash=self.content_hash,
                )
            )

        logger.info(
            f"Session ID: {self.session_id}; file_id={self.file_id}; "
            f"chunk_document produced count={len(chunks)}"
        )
        return chunks
