"""Session-level ingest with PyMuPDF preprocessing, embed, and Qdrant upsert."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.config import (
    MAX_CONCURRENT_INGEST_FILES,
    SESSION_GENERATED_SUBDIR,
    SESSION_UPLOADS_SUBDIR,
)
from backend.models.pydantic_models import (
    FileInfo,
    FileIngestionOutput,
    ProcessedChunk,
    SessionFilesIngestionOutput,
)
from backend.tools.doc_search.process_docs.embed_docs import EmbedDocument
from backend.tools.doc_search.process_docs.preprocess_docs_pymupdf import (
    PreprocessDocumentPymupdf,
)
from backend.tools.doc_search.vectorstore.qdrant import QdrantVectorStore
from database.session_dao import SessionDAO

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).resolve().parents[4] / "data"


class ProcessDocumentsPymupdf:
    """Orchestrate ingest for all files recorded on a session using PyMuPDF."""

    def __init__(self, session_id: str) -> None:
        """Bind ingest to one session.

        Args:
            session_id: Session UUID string for this ingest run.

        File-level parallelism uses MAX_CONCURRENT_INGEST_FILES in backend.config.
        """
        self._session_id = session_id
        self._max_concurrent_files = MAX_CONCURRENT_INGEST_FILES

    def _parse_and_chunk(
        self,
        path: Path,
        session_id: str,
        user_id: str,
        file_id: str,
        filename: str,
        content_hash: str,
    ) -> list[ProcessedChunk]:
        """Parse and chunk one PDF with the PyMuPDF pipeline.

        Args:
            path: Stored PDF path.
            session_id: Session associated with the document.
            user_id: Owner of the document library.
            file_id: Stored file identifier.
            filename: Original source filename.
            content_hash: SHA-256 digest of the stored bytes.

        Returns:
            Ordered processed chunks ready for embedding.
        """
        processor = PreprocessDocumentPymupdf(
            session_id=session_id,
            user_id=user_id,
            file_id=file_id,
            file_name=filename,
            content_hash=content_hash,
        )
        doc = processor.parse_document(path)
        return processor.chunk_document(doc)

    def _failed_step(self, filename: str, file_id: str, error: str) -> FileIngestionOutput:
        """Build a standardized failed-ingestion result.

        Args:
            filename: Source filename associated with the failure.
            file_id: Stored file identifier.
            error: Human-readable failure detail.

        Returns:
            A failed FileIngestionOutput with no produced chunks.
        """
        return FileIngestionOutput(filename=filename, file_id=file_id, ok=False, error=error)

    async def _ingest_one_file(
        self,
        *,
        path: Path,
        user_id: str,
        file_id: str,
        filename: str,
        content_hash: str,
        embedder: EmbedDocument,
        vector_store: QdrantVectorStore,
        sem: asyncio.Semaphore,
    ) -> FileIngestionOutput:
        """Parse, chunk, embed, and index one file under a concurrency guard.

        Args:
            path: Stored PDF path.
            user_id: Owner of the document library.
            file_id: Stored file identifier.
            filename: Original source filename.
            content_hash: SHA-256 digest used for deduplication.
            embedder: Shared embedding adapter for the ingestion batch.
            vector_store: Destination Qdrant adapter.
            sem: Semaphore limiting concurrent file ingestion.

        Returns:
            Per-file success details or a captured failure result.
        """
        session_id = self._session_id
        async with sem:
            if not path.is_file():
                msg = f"File not found on disk: {path}"
                logger.error(f"Session ID: {session_id}; file_id={file_id}; {msg}")
                return self._failed_step(filename, file_id, msg)

            try:
                chunks = await asyncio.to_thread(
                    self._parse_and_chunk,
                    path,
                    session_id,
                    user_id,
                    file_id,
                    filename,
                    content_hash,
                )
            except Exception as e:
                logger.error(
                    f"Session ID: {session_id}; file_id={file_id}; parse/chunk failed: {e}"
                )
                return self._failed_step(filename, file_id, str(e))

            if not chunks:
                msg = "No chunks produced"
                logger.error(
                    f"Session ID: {session_id}; file_id={file_id}; filename={filename}; {msg}"
                )
                return self._failed_step(filename, file_id, msg)

            try:
                embedded = await embedder.embed_chunks(chunks, session_id=session_id)
            except Exception as e:
                logger.error(
                    f"Session ID: {session_id}; file_id={file_id}; embed failed: {e}"
                )
                return self._failed_step(filename, file_id, str(e))

            try:
                await asyncio.to_thread(vector_store.upsert_embedded, embedded)
            except Exception as e:
                logger.error(
                    f"Session ID: {session_id}; file_id={file_id}; upsert failed: {e}"
                )
                return self._failed_step(filename, file_id, str(e))

            n = len(embedded)
            logger.info(
                f"Session ID: {session_id}; file_id={file_id}; filename={filename}; "
                f"ingest ok chunks={n}"
            )
            return FileIngestionOutput(
                filename=filename,
                file_id=file_id,
                ok=True,
                chunk_count=n,
            )

    async def _get_unique_files(
        self,
        vector_store: QdrantVectorStore,
        file_infos: list[FileInfo],
        user_id: str,
    ) -> list[FileInfo]:
        """Return file_infos that still need vectors in Qdrant.

        Files are skipped when this user already has vectors for the same content hash.

        Args:
            vector_store: Qdrant adapter used to query existing content hashes.
            file_infos: Candidate file metadata from the session record.
            user_id: Owner used to scope content-level deduplication.

        Returns:
            Candidate files whose current-schema vectors do not already exist.
        """
        if not file_infos:
            return []
        existing_hashes = await asyncio.to_thread(
            vector_store.find_existing_content_hashes,
            user_id,
            [f.content_hash for f in file_infos],
        )
        return [f for f in file_infos if f.content_hash not in existing_hashes]

    async def process_session_documents(
        self,
        session_dao: SessionDAO,
        *,
        sub_dir: str,
    ) -> SessionFilesIngestionOutput:
        """Ingest recorded session files from an uploads or generated directory.

        Args:
            session_dao: Data-access object used to load session and file metadata.
            sub_dir: Either the configured uploads or generated-files subdirectory.

        Returns:
            Aggregate per-file ingestion outcomes for the session.

        Raises:
            ValueError: sub_dir is not a supported session data directory.
        """
        session_id = self._session_id
        user_id = await session_dao.get_user_id(session_id)

        if sub_dir == SESSION_UPLOADS_SUBDIR:
            data_dir = _DATA_ROOT / session_id / SESSION_UPLOADS_SUBDIR
            file_entries = await session_dao.get_session_uploads(session_id)
        elif sub_dir == SESSION_GENERATED_SUBDIR:
            data_dir = _DATA_ROOT / session_id / SESSION_GENERATED_SUBDIR
            file_entries = await session_dao.get_session_generated_files(session_id)
        else:
            raise ValueError(
                f"sub_dir must be {SESSION_UPLOADS_SUBDIR} or {SESSION_GENERATED_SUBDIR}, "
                f"got {sub_dir}"
            )

        if not file_entries:
            logger.info(
                f"Session ID: {session_id}; process_session_documents: no files to ingest "
                f"(sub_dir={sub_dir})"
            )
            return SessionFilesIngestionOutput(session_id=session_id, files=[])

        vector_store = QdrantVectorStore(session_id=session_id)
        files_to_ingest = await self._get_unique_files(vector_store, file_entries, user_id)
        n_skip = len(file_entries) - len(files_to_ingest)
        if n_skip:
            logger.info(
                f"Session ID: {session_id}; process_session_documents: "
                f"omit {n_skip} file(s) already vectorized for this user/session"
            )
        if not files_to_ingest:
            logger.info(
                f"Session ID: {session_id}; process_session_documents: "
                f"nothing left to ingest (sub_dir={sub_dir})"
            )
            return SessionFilesIngestionOutput(session_id=session_id, files=[])

        sem = asyncio.Semaphore(max(1, self._max_concurrent_files))
        embedder = EmbedDocument()

        tasks = [
            self._ingest_one_file(
                path=data_dir / file_info.filename,
                user_id=user_id,
                file_id=file_info.file_id,
                filename=file_info.filename,
                content_hash=file_info.content_hash,
                embedder=embedder,
                vector_store=vector_store,
                sem=sem,
            )
            for file_info in files_to_ingest
        ]

        files = await asyncio.gather(*tasks)
        return SessionFilesIngestionOutput(session_id=session_id, files=files)
