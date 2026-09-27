from __future__ import annotations

import logging
import uuid

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.pydantic_models import FileInfo
from database.models import SessionRecord

logger = logging.getLogger(__name__)

_files_adapter = TypeAdapter(list[FileInfo])


class SessionDAO:
    """Read and write session rows (user id, query, uploaded/generated file metadata JSONB)."""

    def __init__(self, session_db: AsyncSession) -> None:
        """Bind session persistence operations to an async database session.

        Args:
            session_db: Request- or activity-scoped SQLAlchemy session.

        Returns:
            None.
        """
        self._session_db = session_db

    async def _get_session_row(self, session_id: str) -> SessionRecord:
        """Load the SessionRecord for a session id (shared by getters and appends).

        Args:
            session_id: Session UUID string.

        Returns:
            The matching SessionRecord row.

        Raises:
            LookupError: No session row for that session_id.
        """
        row = (
            await self._session_db.execute(
                select(SessionRecord).where(
                    SessionRecord.session_id == uuid.UUID(session_id)
                )
            )
        ).scalar_one_or_none()
        if row is None:
            logger.error(f"Session ID: {session_id}; No row found")
            raise LookupError(session_id)
        return row

    async def get_user_id(self, session_id: str) -> str:
        """Load the owning user id for a session.

        Args:
            session_id: Session UUID string.

        Returns:
            Stored user_id for that session.

        Raises:
            LookupError: No session row for that session_id.
        """
        return (await self._get_session_row(session_id)).user_id

    async def get_session_uploads(self, session_id: str) -> list[FileInfo]:
        """Load uploaded file metadata (JSONB) for a session.

        Args:
            session_id: Session UUID string.

        Returns:
            Parsed FileInfo list (possibly empty).

        Raises:
            LookupError: No session row for that session_id.
        """
        row = await self._get_session_row(session_id)
        return _files_adapter.validate_python(row.uploaded_files or [])

    async def get_session_generated_files(self, session_id: str) -> list[FileInfo]:
        """Load generated file metadata (JSONB) for a session.

        Args:
            session_id: Session UUID string.

        Returns:
            Parsed FileInfo list (possibly empty).

        Raises:
            LookupError: No session row for that session_id.
        """
        row = await self._get_session_row(session_id)
        return _files_adapter.validate_python(row.generated_files or [])

    async def insert_session(self, session_id: str, user_id: str, user_query: str) -> None:
        """Insert a new sessions row with empty uploaded_files and generated_files JSONB.

        Args:
            session_id: UUID string for the primary key.
            user_id: Owning user identifier.
            user_query: User query text stored with the session.

        Returns:
            None
        """
        self._session_db.add(
            SessionRecord(
                session_id=uuid.UUID(session_id),
                user_id=user_id,
                user_query=user_query,
                uploaded_files=[],
                generated_files=[],
            )
        )
        await self._session_db.flush()
        logger.info(f"Session ID: {session_id}; insert_session ok")

    def _merge_jsonb_file_list(
        self,
        existing_raw: list | None,
        additions: list[FileInfo],
    ) -> list[dict]:
        """Merge stored JSON list with new FileInfo rows for persistence on SessionRecord.

        Args:
            existing_raw: Raw JSONB list from the ORM, or None when empty.
            additions: New FileInfo instances to append after existing entries.

        Returns:
            List of dicts in JSON-compatible form for assigning to a JSONB column.
        """
        merged = _files_adapter.validate_python(existing_raw or []) + additions
        return [f.model_dump(mode="json") for f in merged]

    async def append_uploaded_files(self, session_id: str, files: list[FileInfo]) -> None:
        """Merge new file metadata into sessions.uploaded_files JSONB.

        Args:
            session_id: Session UUID string.
            files: New FileInfo entries to append to stored JSON.

        Returns:
            None
        """
        row = await self._get_session_row(session_id)
        merged = self._merge_jsonb_file_list(row.uploaded_files, files)
        n = len(merged)
        row.uploaded_files = merged
        await self._session_db.flush()
        logger.info(
            f"Session ID: {session_id}; append_uploaded_files ok "
            f"added={len(files)} total={n}"
        )

    async def append_generated_files(self, session_id: str, files: list[FileInfo]) -> None:
        """Merge new file metadata into sessions.generated_files JSONB.

        Args:
            session_id: Session UUID string.
            files: New FileInfo entries to append to stored JSON.

        Returns:
            None
        """
        row = await self._get_session_row(session_id)
        merged = self._merge_jsonb_file_list(row.generated_files, files)
        n = len(merged)
        row.generated_files = merged
        await self._session_db.flush()
        logger.info(
            f"Session ID: {session_id}; append_generated_files ok "
            f"added={len(files)} total={n}"
        )
