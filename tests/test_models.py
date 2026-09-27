"""Deterministic tests for public API and handoff data models."""

from backend.models.pydantic_models import (
    DeepSearchCitation,
    DeepSearchClaim,
    FileIngestionOutput,
    SessionFilesIngestionOutput,
)


def test_citation_normalizes_nullable_llm_fields() -> None:
    """LLM nulls must not leak into string and list fields."""
    citation = DeepSearchCitation(
        type=None,  # type: ignore[arg-type]
        source=None,  # type: ignore[arg-type]
        chunk_id=123,  # type: ignore[arg-type]
        pages=None,  # type: ignore[arg-type]
        url=None,  # type: ignore[arg-type]
        title=None,  # type: ignore[arg-type]
    )

    assert citation.type == "unknown"
    assert citation.source == ""
    assert citation.chunk_id == "123"
    assert citation.pages == []
    assert citation.url == ""
    assert citation.title == ""


def test_claim_normalizes_empty_llm_collections() -> None:
    """Claim normalization keeps a stable schema for sanitization."""
    claim = DeepSearchClaim(
        statement="  Supported statement.  ",
        chunk_ids=None,  # type: ignore[arg-type]
        urls=None,  # type: ignore[arg-type]
    )

    assert claim.statement == "Supported statement."
    assert claim.chunk_ids == []
    assert claim.urls == []


def test_ingestion_all_ok_requires_nonempty_successful_batch() -> None:
    """An empty or partially failed batch must not report success."""
    assert not SessionFilesIngestionOutput(session_id="empty").all_ok

    successful = FileIngestionOutput(
        filename="source.pdf",
        file_id="file-1",
        ok=True,
        chunk_count=2,
    )
    failed = FileIngestionOutput(
        filename="broken.pdf",
        file_id="file-2",
        ok=False,
        error="parse failed",
    )

    assert SessionFilesIngestionOutput(session_id="ok", files=[successful]).all_ok
    assert not SessionFilesIngestionOutput(
        session_id="mixed", files=[successful, failed]
    ).all_ok
