from __future__ import annotations

import logging
import os
import uuid

from langchain_core.tools import tool

from backend.temporal.client import get_temporal_client
from backend.temporal.workflows.web_search_workflow import WebSearchWorkflow
from backend.tools.doc_search.document_search import document_search
from backend.tools.doc_search.page_ocr import read_document_page_ocr
from backend.tools.web_search.web_search import web_search

logger = logging.getLogger(__name__)


@tool
async def document_search_tool(
    session_id: str,
    query: str,
) -> list[dict]:
    """Search session documents and return relevant chunks with source metadata.

    Args:
        session_id: Session UUID string.
        query: Natural language search query.

    Returns:
        List of retrieved chunk dicts with chunk_id, text, source, file_id,
        source_session_id, pages, and score.
    """
    logger.info(f"Document search tool start session_id={session_id}")
    results = await document_search(session_id, query)
    logger.info(f"Document search tool done session_id={session_id} chunks={len(results)}")
    return results


@tool
async def document_page_ocr_tool(
    session_id: str,
    source_session_id: str,
    file_id: str,
    chunk_id: str,
    page_number: int,
) -> dict:
    """OCR one retrieved PDF page to verify exact text hidden by a damaged text layer.

    Use this only after document_search_tool returns an OCR-corrupted passage. Copy
    source_session_id, file_id, chunk_id, and a one-based page_number from that result.

    Args:
        session_id: Active question session used for ownership authorization.
        source_session_id: Session where the retrieved file was originally uploaded.
        file_id: Retrieved source file identifier.
        chunk_id: Retrieved chunk being verified; retained for citation provenance.
        page_number: One-based PDF page to render and OCR.

    Returns:
        Native and fresh OCR text plus canonical source metadata and chunk id.
    """
    try:
        return await read_document_page_ocr(
            session_id=session_id,
            source_session_id=source_session_id,
            file_id=file_id,
            chunk_id=chunk_id,
            page_number=page_number,
        )
    except (FileNotFoundError, LookupError, PermissionError, ValueError) as exc:
        logger.warning(
            "Document page OCR rejected session_id=%s chunk_id=%s page_number=%s error=%s",
            session_id,
            chunk_id,
            page_number,
            exc,
        )
        return {
            "error": str(exc),
            "chunk_id": chunk_id,
            "source_session_id": source_session_id,
            "file_id": file_id,
            "page_number": page_number,
        }


@tool
async def web_search_tool(session_id: str, query: str) -> list[dict]:
    """Search the public web and return normalized source-grounded results.

    Args:
        session_id: Session id for logs and traceability.
        query: Natural language web query.

    Returns:
        List of normalized web search result dicts.
    """
    logger.info(f"Web search tool start session_id={session_id}")
    results = await web_search(session_id, query)
    logger.info(f"Web search tool done session_id={session_id} results={len(results)}")
    return results


@tool
async def web_search_temporal_tool(session_id: str, query: str) -> dict:
    """Run web search through a Temporal workflow and return normalized results.

    Args:
        session_id: Session id for traceability.
        query: Natural language web query.

    Returns:
        Temporal workflow result payload containing web search results.
    """
    client = await get_temporal_client()
    workflow_id = f"web-search:{session_id}:{uuid.uuid4()}"
    logger.info(f"Web search temporal tool start session_id={session_id} workflow_id={workflow_id}")
    handle = await client.start_workflow(
        WebSearchWorkflow.run,
        {"session_id": session_id, "query": query},
        id=workflow_id,
        task_queue=os.environ["TEMPORAL_TASK_QUEUE"],
    )
    result = await handle.result()
    logger.info(f"Web search temporal tool done session_id={session_id} workflow_id={workflow_id}")
    return result
