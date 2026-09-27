"""Authorized, on-demand OCR for a page from an already retrieved PDF."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pymupdf
import pytesseract
from PIL import Image, ImageOps
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from backend.config import (
    INGEST_SCHEMA_VERSION,
    SESSION_GENERATED_SUBDIR,
    SESSION_UPLOADS_SUBDIR,
)
from database.db import get_async_session_maker
from database.session_dao import SessionDAO

_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def _verified_chunk_pages(
    source_session_id: str,
    file_id: str,
    chunk_id: str,
) -> list[int]:
    """Load authoritative page metadata for one indexed chunk from Qdrant.

    Args:
        source_session_id: Session stored on the vector payload.
        file_id: File identifier stored on the vector payload.
        chunk_id: Retrieved chunk identifier.

    Returns:
        One-based page numbers recorded for the matching chunk.

    Raises:
        LookupError: No current-schema vector matches all identifiers.
    """
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )
    points, _ = client.scroll(
        collection_name=os.environ["QDRANT_COLLECTION"],
        scroll_filter=Filter(
            must=[
                FieldCondition(key="session_id", match=MatchValue(value=source_session_id)),
                FieldCondition(key="file_id", match=MatchValue(value=file_id)),
                FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id)),
                FieldCondition(
                    key="ingest_schema_version",
                    match=MatchValue(value=INGEST_SCHEMA_VERSION),
                ),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not points or points[0].payload is None:
        raise LookupError("Chunk metadata does not match the requested source file")
    return [int(page) for page in points[0].payload.get("pages") or []]


def _safe_file_path(source_session_id: str, subdir: str, filename: str) -> Path:
    """Resolve a recorded session filename while preventing directory traversal.

    Args:
        source_session_id: Session that owns the stored file.
        subdir: Recorded uploads or generated directory name.
        filename: Filename from persisted FileInfo metadata.

    Returns:
        Resolved file path contained by the expected session directory.

    Raises:
        ValueError: The filename escapes the expected session directory.
    """
    base = (_DATA_ROOT / source_session_id / subdir).resolve()
    path = (base / filename).resolve()
    if path.parent != base:
        raise ValueError("Recorded filename resolves outside its session directory")
    return path


def _extract_page(path: Path, page_number: int) -> tuple[str, str, int]:
    """Read native text and fresh Tesseract OCR from one PDF page.

    Args:
        path: Authorized PDF path.
        page_number: One-based page number.

    Returns:
        Native text, OCR text, and total page count.

    Raises:
        ValueError: The file is not a PDF or page number is out of range.
    """
    if path.suffix.casefold() != ".pdf":
        raise ValueError("Page OCR is supported only for PDF files")
    with pymupdf.open(path) as document:
        page_count = document.page_count
        if page_number < 1 or page_number > page_count:
            raise ValueError(
                f"page_number must be between 1 and {page_count}, got {page_number}"
            )
        page = document[page_number - 1]
        native_text = page.get_text("text").strip()
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(4, 4), alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        normalized = ImageOps.autocontrast(ImageOps.grayscale(image))
        variants: list[tuple[int, str]] = []
        for page_segmentation_mode in (3, 6):
            text = pytesseract.image_to_string(
                normalized,
                lang="eng",
                config=f"--oem 3 --psm {page_segmentation_mode}",
            ).strip()
            if text and text not in {value for _, value in variants}:
                variants.append((page_segmentation_mode, text))
        ocr_text = "\n\n".join(
            f"[Tesseract psm {mode}]\n{text}"
            for mode, text in variants
        )
    return native_text, ocr_text, page_count


async def read_document_page_ocr(
    *,
    session_id: str,
    source_session_id: str,
    file_id: str,
    chunk_id: str,
    page_number: int,
) -> dict[str, Any]:
    """Authorize and OCR one page from a file in the active user's document library.

    Args:
        session_id: Active question session.
        source_session_id: Session where the source file was recorded.
        file_id: File identifier returned by document retrieval.
        chunk_id: Retrieved chunk whose text is being verified.
        page_number: One-based PDF page number.

    Returns:
        Canonical file metadata, native text, fresh OCR text, and page count.

    Raises:
        PermissionError: The active and source sessions have different owners.
        LookupError: The file id is not recorded on the source session.
        FileNotFoundError: The recorded file is absent from disk.
    """
    session_maker = get_async_session_maker()
    async with session_maker() as session_db:
        dao = SessionDAO(session_db)
        active_user = await dao.get_user_id(session_id)
        source_user = await dao.get_user_id(source_session_id)
        if active_user != source_user:
            raise PermissionError("Source file does not belong to the active user")

        candidates = [
            (SESSION_UPLOADS_SUBDIR, await dao.get_session_uploads(source_session_id)),
            (
                SESSION_GENERATED_SUBDIR,
                await dao.get_session_generated_files(source_session_id),
            ),
        ]

    match = next(
        (
            (subdir, file_info)
            for subdir, files in candidates
            for file_info in files
            if file_info.file_id == file_id
        ),
        None,
    )
    if match is None:
        raise LookupError(f"File id is not recorded on source session: {file_id}")
    subdir, file_info = match
    path = _safe_file_path(source_session_id, subdir, file_info.filename)
    if not path.is_file():
        raise FileNotFoundError(path)

    chunk_pages = await asyncio.to_thread(
        _verified_chunk_pages,
        source_session_id,
        file_id,
        chunk_id,
    )
    if page_number not in chunk_pages:
        raise ValueError(
            f"page_number {page_number} is not represented by chunk {chunk_id}; "
            f"allowed pages: {chunk_pages}"
        )

    native_text, ocr_text, page_count = await asyncio.to_thread(
        _extract_page,
        path,
        page_number,
    )
    return {
        "chunk_id": chunk_id,
        "source_session_id": source_session_id,
        "file_id": file_id,
        "source": file_info.filename,
        "page_number": page_number,
        "page_count": page_count,
        "native_text": native_text,
        "ocr_text": ocr_text,
    }
