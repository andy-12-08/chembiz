import json

from langchain_core.messages import AIMessage, ToolMessage

from backend.agents.deepsearch.handoff_payload import (
    _citations_from_claims,
    _document_chunks_from_tool_results,
    _grounded_answer_from_claims,
    _sanitize_claims,
    _sanitize_citations,
    _web_sources_from_temporal_tool_results,
    evidence_inventory_from_result,
)
from backend.prompts.deepsearch_agent_prompt import DEEPSEARCH_SYSTEM_PROMPT
from backend.tools.doc_search.process_docs.page_metadata import pages_for_chunk


def _agent_result() -> dict:
    """Build representative document and web tool messages for citation tests.

    Returns:
        Agent-result mapping containing one document result and one web result.
    """
    documents = [
        {
            "chunk_id": "abc12345",
            "text": "Canonical retrieved evidence.",
            "source": "source.pdf",
            "file_id": "file-123",
            "source_session_id": "source-session-123",
            "pages": [4, 5],
            "score": 0.91,
        }
    ]
    web = {
        "results": [
            {
                "url": "https://example.org/evidence?tracking=1",
                "title": "Canonical Web Title",
                "content": "Web evidence",
            }
        ]
    }
    return {
        "messages": [
            ToolMessage(
                content=json.dumps(documents),
                tool_call_id="doc-call",
                name="document_search_tool",
            ),
            ToolMessage(
                content=json.dumps(web),
                tool_call_id="web-call",
                name="web_search_temporal_tool",
            ),
        ]
    }


def test_collects_canonical_tool_evidence() -> None:
    """Verify canonical document and web metadata are collected from tool output.

    Returns:
        None.
    """
    result = _agent_result()

    chunks = _document_chunks_from_tool_results(result)
    web = _web_sources_from_temporal_tool_results(result)
    inventory = evidence_inventory_from_result(result)

    assert chunks["abc12345"]["source"] == "source.pdf"
    assert chunks["abc12345"]["file_id"] == "file-123"
    assert chunks["abc12345"]["source_session_id"] == "source-session-123"
    assert chunks["abc12345"]["pages"] == [4, 5]
    assert web["https://example.org/evidence"]["title"] == "Canonical Web Title"
    assert web["https://example.org/evidence"]["content"] == "Web evidence"
    assert "chunk_id=abc12345" in inventory
    assert 'url="https://example.org/evidence?tracking=1"' in inventory
    assert 'excerpt="Web evidence"' in inventory


def test_web_inventory_includes_content_needed_to_verify_claim_support() -> None:
    """Verify web provenance includes bounded text for semantic verification.

    Returns:
        None.
    """
    result = _agent_result()
    inventory = evidence_inventory_from_result(result)

    assert "WEB " in inventory
    assert "Web evidence" in inventory


def test_web_inventory_centers_long_content_on_search_query() -> None:
    """Verify long web pages retain the requested row and trailing limitations.

    Returns:
        None.
    """
    target = "Potassium hydroxide solution below 70 percent: 8 hr Butyl."
    disclaimer = "Suggested barriers should be confirmed with the vendor; check additional information and use limitations."
    content = (
        ("unrelated table row " * 1000)
        + target
        + ("later row " * 1000)
        + disclaimer
        + ("appendix text " * 1000)
    )
    result = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "web-long",
                        "name": "web_search_temporal_tool",
                        "args": {"query": "potassium hydroxide protective clothing barriers"},
                    }
                ],
            ),
            ToolMessage(
                content=json.dumps(
                    {
                        "results": [
                            {
                                "url": "https://example.org/long-table",
                                "title": "Long table",
                                "content": content,
                            }
                        ]
                    }
                ),
                tool_call_id="web-long",
                name="web_search_temporal_tool",
            ),
        ]
    }

    inventory = evidence_inventory_from_result(result)

    assert target in inventory
    assert disclaimer in inventory


def test_deepsearch_prompt_requires_generic_engineering_qualification_retrieval() -> None:
    """Verify engineering extraction retrieves source-wide qualifications.

    Returns:
        None.
    """
    assert "chemical-engineering research assistant" in DEEPSEARCH_SYSTEM_PROMPT
    assert "applicable headings, definitions, footnotes" in DEEPSEARCH_SYSTEM_PROMPT
    assert "Do not fabricate missing values" in DEEPSEARCH_SYSTEM_PROMPT
    assert "laboratory observations distinct from plant-scale performance" in DEEPSEARCH_SYSTEM_PROMPT
    assert "protective-clothing" not in DEEPSEARCH_SYSTEM_PROMPT


def test_evidence_inventory_keeps_decisive_text_beyond_old_preview_limit() -> None:
    """Verify handoff evidence includes relevant text occurring after 300 characters.

    Returns:
        None.
    """
    decisive_text = "The decisive compatibility categories are listed here."
    documents = [
        {
            "chunk_id": "late1234",
            "text": ("introductory OCR text " * 30) + decisive_text,
            "source": "source.pdf",
            "file_id": "file-123",
            "source_session_id": "source-session-123",
            "pages": [130, 131],
            "score": 0.95,
        }
    ]
    result = {
        "messages": [
            ToolMessage(
                content=json.dumps(documents),
                tool_call_id="doc-call",
                name="document_search_tool",
            )
        ]
    }

    inventory = evidence_inventory_from_result(result)

    assert decisive_text in inventory
    assert "score=0.950000" in inventory


def test_fresh_page_ocr_augments_only_an_existing_retrieved_chunk() -> None:
    """Verify fresh OCR can clarify retrieved evidence without inventing provenance.

    Returns:
        None.
    """
    result = _agent_result()
    result["messages"].extend(
        [
            ToolMessage(
                content=json.dumps(
                    {
                        "chunk_id": "abc12345",
                        "page_number": 5,
                        "ocr_text": "Clean alloy identifier 17-7PH H900.",
                    }
                ),
                tool_call_id="ocr-valid",
                name="document_page_ocr_tool",
            ),
            ToolMessage(
                content=json.dumps(
                    {
                        "chunk_id": "invented",
                        "page_number": 5,
                        "ocr_text": "This must not become evidence.",
                    }
                ),
                tool_call_id="ocr-invalid",
                name="document_page_ocr_tool",
            ),
        ]
    )

    chunks = _document_chunks_from_tool_results(result)
    inventory = evidence_inventory_from_result(result)

    assert "Clean alloy identifier 17-7PH H900." in chunks["abc12345"]["text"]
    assert chunks["abc12345"]["text"].startswith("[fresh OCR verification")
    assert "Clean alloy identifier 17-7PH H900." in inventory
    assert "invented" not in chunks


def test_fresh_page_ocr_rejects_page_outside_retrieved_chunk() -> None:
    """Verify OCR text from an unrelated page cannot augment a retrieved chunk.

    Returns:
        None.
    """
    result = _agent_result()
    result["messages"].append(
        ToolMessage(
            content=json.dumps(
                {
                    "chunk_id": "abc12345",
                    "page_number": 131,
                    "ocr_text": "Unrelated page text.",
                }
            ),
            tool_call_id="ocr-wrong-page",
            name="document_page_ocr_tool",
        )
    )

    chunks = _document_chunks_from_tool_results(result)

    assert "Unrelated page text." not in chunks["abc12345"]["text"]


def test_valid_document_citation_uses_canonical_metadata() -> None:
    """Verify model-provided metadata is replaced with canonical chunk metadata.

    Returns:
        None.
    """
    payload = {
        "citations": [
            {
                "type": "document",
                "source": "invented.pdf",
                "chunk_id": "abc12345",
                "file_id": "invented-file",
                "title": "Invented title",
            }
        ],
        "confidence": "high",
    }

    _sanitize_citations(payload, _agent_result())

    assert payload["citations"] == [
        {
            "type": "document",
            "source": "source.pdf",
            "chunk_id": "abc12345",
            "file_id": "file-123",
            "pages": [4, 5],
            "url": "",
            "title": "source.pdf",
        }
    ]
    assert payload["confidence"] == "high"


def test_missing_and_invented_document_chunk_ids_are_dropped() -> None:
    """Verify missing and non-tool-backed document identifiers are rejected.

    Returns:
        None.
    """
    payload = {
        "citations": [
            {"type": "document", "source": "source.pdf", "chunk_id": ""},
            {"type": "document", "source": "source.pdf", "chunk_id": "invented"},
        ],
        "confidence": "high",
    }

    _sanitize_citations(payload, _agent_result())

    assert payload["citations"] == []
    assert payload["confidence"] == "low"


def test_misclassified_web_citation_is_canonicalized_when_url_is_valid() -> None:
    """Verify a mislabeled but tool-backed web URL becomes a canonical web citation.

    Returns:
        None.
    """
    payload = {
        "citations": [
            {
                "type": "document",
                "source": "Incorrect source",
                "url": "https://example.org/evidence?tracking=1#section",
                "title": "Invented title",
            }
        ],
        "confidence": "high",
    }

    _sanitize_citations(payload, _agent_result())

    assert payload["citations"] == [
        {
            "type": "web",
            "source": "",
            "chunk_id": "",
            "file_id": "",
            "pages": [],
            "url": "https://example.org/evidence?tracking=1",
            "title": "Canonical Web Title",
        }
    ]


def test_source_only_and_unseen_web_citations_are_dropped() -> None:
    """Verify unverifiable source-only and unseen web citations are rejected.

    Returns:
        None.
    """
    payload = {
        "citations": [
            {"type": "web", "source": "Example", "title": "No URL"},
            {"type": "web", "url": "https://unseen.example/evidence"},
        ],
        "confidence": "medium",
    }

    _sanitize_citations(payload, _agent_result())

    assert payload["citations"] == []
    assert payload["confidence"] == "low"


def test_open_evidence_gap_caps_high_confidence_at_medium() -> None:
    """Verify unresolved evidence gaps prevent a high-confidence designation.

    Returns:
        None.
    """
    payload = {
        "citations": [{"type": "document", "chunk_id": "abc12345"}],
        "open_questions": ["A material evidence gap remains."],
        "confidence": "high",
    }

    _sanitize_citations(payload, _agent_result())

    assert payload["confidence"] == "medium"


def test_page_markers_are_carried_across_overlapping_windows() -> None:
    """Verify page context survives token windows that omit repeated page markers.

    Returns:
        None.
    """
    pages, latest = pages_for_chunk("[page 7]\nEvidence", None)
    assert pages == [7]
    assert latest == 7

    pages, latest = pages_for_chunk("Continuation without marker", latest)
    assert pages == [7]
    assert latest == 7

    pages, latest = pages_for_chunk("end of page\n[page 8]\nnext", latest)
    assert pages == [7, 8]
    assert latest == 8


def test_claims_without_tool_backed_evidence_are_dropped() -> None:
    """Verify only claims with exact retrieved identifiers survive validation.

    Returns:
        None.
    """
    payload = {
        "claims": [
            {"statement": "Supported claim.", "chunk_ids": ["abc12345"], "urls": []},
            {"statement": "Invented claim.", "chunk_ids": ["not-retrieved"], "urls": []},
            {"statement": "Uncited claim.", "chunk_ids": [], "urls": []},
        ],
        "facts": ["Untrusted extractor fact."],
    }

    _sanitize_claims(payload, _agent_result())

    assert payload["claims"] == [
        {"statement": "Supported claim.", "chunk_ids": ["abc12345"], "urls": []}
    ]
    assert payload["facts"] == ["Supported claim."]


def test_grounded_answer_is_built_only_from_validated_claims() -> None:
    """Verify rendered answers contain canonical evidence beside every claim.

    Returns:
        None.
    """
    claims = [
        {"statement": "Supported claim.", "chunk_ids": ["abc12345"], "urls": []}
    ]
    payload = {"claims": claims, "citations": _citations_from_claims(claims)}
    _sanitize_citations(payload, _agent_result())

    answer = _grounded_answer_from_claims(claims, payload["citations"])

    assert "Supported claim." in answer
    assert "source.pdf, pp. 4-5, chunk abc12345" in answer
    assert "Invented claim" not in answer


def test_no_validated_claims_returns_evidence_insufficiency() -> None:
    """Verify an empty validated claim set cannot reuse an ungrounded draft answer.

    Returns:
        None.
    """
    answer = _grounded_answer_from_claims([], [])

    assert "could not produce a claim-level grounded answer" in answer
