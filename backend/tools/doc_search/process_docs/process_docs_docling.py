"""Session-level ingest: preprocess, embed, and upsert to Qdrant with per-file concurrency."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.config import (
    MAX_CONCURRENT_INGEST_FILES,
    SESSION_GENERATED_SUBDIR,
    SESSION_UPLOADS_SUBDIR,
)
from backend.tools.doc_search.process_docs.embed_docs import EmbedDocument
from backend.tools.doc_search.process_docs.preprocess_docs_docling import PreprocessDocumentDocling
from backend.tools.doc_search.vectorstore.qdrant import QdrantVectorStore
from backend.models.pydantic_models import (
    FileInfo,
    FileIngestionOutput,
    ProcessedChunk,
    SessionFilesIngestionOutput,
)
from database.session_dao import SessionDAO

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).resolve().parents[4] / "data"


class ProcessDocumentsDocling:
    """Orchestrate ingest for all files recorded on a session (Docling preprocessor)."""

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
        """Parse and chunk one file on disk using PreprocessDocumentDocling.

        Args:
            path: Absolute or resolved file path.
            session_id: Session UUID string.
            user_id: Owning user id for the session.
            file_id: Stored file id for this upload.
            filename: Original filename (metadata and chunk source).
            content_hash: SHA-256 hash of the original file content.

        Returns:
            Chunks in order.

        Raises:
            FileNotFoundError: Path is not a file.
        """
        processor = PreprocessDocumentDocling(
            session_id=session_id,
            user_id=user_id,
            file_id=file_id,
            file_name=filename,
            content_hash=content_hash,
        )
        doc = processor.parse_document(path)
        return processor.chunk_document(doc)

    def _failed_step(self, filename: str, file_id: str, error: str) -> FileIngestionOutput:
        """Build a failed ingestion result for one file.

        Args:
            filename: Original filename.
            file_id: Stored file id.
            error: Human-readable failure reason.

        Returns:
            FileIngestionOutput with ok set to False.
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
        """Run parse, chunk, embed, and upsert for a single file path.

        Args:
            path: Document path under data/<session_id>/uploads/.
            user_id: Owning user id for the session.
            file_id: Stored file id.
            filename: Original filename.
            content_hash: SHA-256 hash of the original file content.
            embedder: Embedder client for this ingest run.
            vector_store: Qdrant store for this session.
            sem: Semaphore limiting concurrent files per session.

        Returns:
            FileIngestionOutput with ok True on success, or ok False and error set.
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
            vector_store: Store bound to this instance session_id.
            file_infos: Candidate rows from the database.
            user_id: Owning user id for the session.

        Returns:
            Same entries as file_infos minus any already stored in Qdrant.
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
        """Ingest files for this session from under data/<session_id>/<sub_dir>/.

        When sub_dir is SESSION_UPLOADS_SUBDIR, loads metadata from uploaded_files
        and reads paths under uploads/. When sub_dir is SESSION_GENERATED_SUBDIR,
        loads from generated_files and reads under generated/. Files already
        vectorized for this user by content hash are omitted so they are not
        parsed or embedded again. Remaining files run concurrently up to
        MAX_CONCURRENT_INGEST_FILES in backend.config. Parse and chunk run in a thread pool;
        embedding and upsert share that concurrency limit.

        Args:
            session_dao: DAO used to load user id and file list for this session.
            sub_dir: Subdirectory name under data/<session_id>/; must be
                SESSION_UPLOADS_SUBDIR or SESSION_GENERATED_SUBDIR.

        Returns:
            SessionFilesIngestionOutput with one FileIngestionOutput per file
            ingested in this run only.

        Raises:
            LookupError: No session row for this instance session_id.
            ValueError: sub_dir is not a supported value.
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
