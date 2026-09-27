import asyncio

import pytest

from backend.agents.deepsearch.run_deepsearch_agent import _await_with_deadline
from backend.tools import tools as tool_module


def test_await_with_deadline_returns_completed_result() -> None:
    """Verify the hard-deadline helper preserves successful results.

    Returns:
        None.
    """

    async def completed() -> str:
        return "done"

    result = asyncio.run(
        _await_with_deadline(completed(), timeout_seconds=1, stage_name="test stage")
    )

    assert result == "done"


def test_await_with_deadline_raises_named_timeout() -> None:
    """Verify incomplete work produces a clear terminal timeout.

    Returns:
        None.
    """

    async def delayed() -> None:
        await asyncio.sleep(1)

    with pytest.raises(TimeoutError, match="test stage exceeded 0 seconds"):
        asyncio.run(
            _await_with_deadline(delayed(), timeout_seconds=0, stage_name="test stage")
        )


def test_ocr_tool_returns_recoverable_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an invalid OCR request does not fail the complete research run.

    Args:
        monkeypatch: Pytest fixture used to replace the OCR implementation.

    Returns:
        None.
    """

    async def rejected_ocr(**_: object) -> dict:
        raise ValueError("requested page is outside the retrieved chunk")

    monkeypatch.setattr(tool_module, "read_document_page_ocr", rejected_ocr)
    result = asyncio.run(
        tool_module.document_page_ocr_tool.ainvoke(
            {
                "session_id": "active-session",
                "source_session_id": "source-session",
                "file_id": "file-id",
                "chunk_id": "chunk-id",
                "page_number": 2,
            }
        )
    )

    assert result["error"] == "requested page is outside the retrieved chunk"
    assert result["chunk_id"] == "chunk-id"
    assert result["page_number"] == 2
