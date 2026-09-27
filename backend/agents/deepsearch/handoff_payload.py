"""Post-run handoff: transcript to stored JSON, citation fixes, and tool trace.

Research is done only by the LangGraph ReAct agent in graph.get_deepsearch_agent. After that
run completes, this module uses the same ChatOpenAI configuration (graph.get_deepsearch_llm)
with structured output to fill DeepSearchHandoffPayload for the API. That is not a second
ReAct agent; it is one parsing pass over the transcript, then deterministic citation cleanup.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agents.deepsearch.graph import get_deepsearch_llm
from backend.config import (
    HANDOFF_EVIDENCE_EXCERPT_CHARS,
    HANDOFF_EVIDENCE_MAX_DOCUMENT_CHUNKS,
    HANDOFF_TOOL_TRACE_PREVIEW_CHARS,
    HANDOFF_TRANSCRIPT_MAX_CHARS,
    HANDOFF_WEB_EVIDENCE_EXCERPT_CHARS,
)
from backend.models.pydantic_models import DeepSearchHandoffPayload
from backend.prompts.deepsearch_agent_prompt import build_deepsearch_handoff_prompt
from database.models import RunRecord

logger = logging.getLogger(__name__)

_TEMPORAL_WEB_TOOL = "web_search_temporal_tool"
_DOCUMENT_TOOL = "document_search_tool"
_DOCUMENT_PAGE_OCR_TOOL = "document_page_ocr_tool"


def _message_text(content: object) -> str:
    """Extract plain text from a LangChain message content value.

    Args:
        content: String or structured content blocks stored on a message.

    Returns:
        Concatenated text, or an empty string when no text is available.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block.get("content"), str):
                    parts.append(block["content"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return ""


def _url_normalize_key(url: str) -> str:
    """Create a comparison key for a web URL without query or fragment data.

    Args:
        url: Candidate absolute or scheme-less URL.

    Returns:
        Lowercased scheme and host plus a normalized path.
    """
    parsed = urlparse(unquote(url.strip()))
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def _tool_json(message: ToolMessage) -> Any | None:
    """Decode the JSON-serialized return value of a tool message.

    Args:
        message: LangChain tool-result message to decode.

    Returns:
        Decoded JSON data, or None when the content is empty or invalid JSON.
    """
    raw = _message_text(message.content)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _document_chunks_from_tool_results(agent_result: dict) -> dict[str, dict[str, Any]]:
    """Collect canonical document metadata keyed by tool-returned chunk ID.

    Args:
        agent_result: LangGraph result containing the completed message history.

    Returns:
        Mapping from retrieved chunk IDs to canonical source metadata and text.
    """
    chunks: dict[str, dict[str, Any]] = {}
    for message in agent_result.get("messages", []):
        if not isinstance(message, ToolMessage) or getattr(message, "name", None) != _DOCUMENT_TOOL:
            continue
        data = _tool_json(message)
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            chunk_id = str(item.get("chunk_id") or "").strip()
            if not chunk_id:
                continue
            chunks.setdefault(
                chunk_id,
                {
                    "chunk_id": chunk_id,
                    "source": str(item.get("source") or "").strip(),
                    "file_id": str(item.get("file_id") or "").strip(),
                    "source_session_id": str(item.get("source_session_id") or "").strip(),
                    "pages": [int(page) for page in item.get("pages") or []],
                    "text": str(item.get("text") or "").strip(),
                    "score": float(item.get("score") or 0.0),
                },
            )
    for message in agent_result.get("messages", []):
        if not isinstance(message, ToolMessage) or getattr(message, "name", None) != _DOCUMENT_PAGE_OCR_TOOL:
            continue
        data = _tool_json(message)
        if not isinstance(data, dict):
            continue
        chunk_id = str(data.get("chunk_id") or "").strip()
        canonical_chunk = chunks.get(chunk_id)
        if canonical_chunk is None:
            continue
        ocr_text = str(data.get("ocr_text") or "").strip()
        page_number = data.get("page_number")
        if (
            not ocr_text
            or not isinstance(page_number, int)
            or page_number not in canonical_chunk["pages"]
        ):
            continue
        canonical_chunk["text"] = (
            f"[fresh OCR verification for page {page_number}]\n{ocr_text}\n\n"
            f"[native retrieved text]\n{canonical_chunk['text']}"
        )
        if page_number not in canonical_chunk["pages"]:
            canonical_chunk["pages"].append(page_number)
            canonical_chunk["pages"].sort()
    return chunks


def _web_sources_from_temporal_tool_results(agent_result: dict) -> dict[str, dict[str, Any]]:
    """Collect canonical web metadata keyed by normalized tool-returned URL.

    Args:
        agent_result: LangGraph result with a messages list.

    Returns:
        Map from normalized URL key to canonical URL, title, and returned content.
    """
    call_queries: dict[str, str] = {}
    for message in agent_result.get("messages", []):
        for call in getattr(message, "tool_calls", []) or []:
            if not isinstance(call, dict) or call.get("name") != _TEMPORAL_WEB_TOOL:
                continue
            args = call.get("args") or {}
            if isinstance(args, dict):
                call_queries[str(call.get("id") or "")] = str(args.get("query") or "")

    sources: dict[str, dict[str, Any]] = {}
    for message in agent_result.get("messages", []):
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "name", None) != _TEMPORAL_WEB_TOOL:
            continue
        data = _tool_json(message)
        if not isinstance(data, dict):
            continue
        for item in data.get("results") or []:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            u = str(item["url"]).strip()
            if u:
                key = _url_normalize_key(u)
                source = sources.setdefault(
                    key,
                    {"url": u, "title": "", "content": "", "queries": []},
                )
                source["title"] = source["title"] or str(item.get("title") or "").strip()
                content = str(item.get("content") or "").strip()
                if len(content) > len(source["content"]):
                    source["content"] = content
                query = call_queries.get(str(getattr(message, "tool_call_id", "")), "")
                if query and query not in source["queries"]:
                    source["queries"].append(query)
    return sources


def _web_evidence_excerpt(content: str, queries: list[str]) -> str:
    """Select query-centered web evidence plus trailing notes and disclaimers.

    Args:
        content: Full text returned for one web result.
        queries: Search queries associated with that result URL.

    Returns:
        Bounded excerpt favoring the requested chemical or technical phrase.
    """
    compact = " ".join(content.split())
    if len(compact) <= HANDOFF_WEB_EVIDENCE_EXCERPT_CHARS:
        return compact

    lowered = compact.lower()
    generic_words = {
        "archived",
        "barrier",
        "barriers",
        "chemical",
        "clothing",
        "group",
        "hour",
        "niosh",
        "protective",
        "recommendations",
        "table",
    }
    candidates: list[tuple[int, int, int, str]] = []
    for query in queries:
        words = [word.strip(".,:;()[]{}\"'").lower() for word in query.split()]
        words = [word for word in words if len(word) >= 4]
        for size in (3, 2, 1):
            for index in range(len(words) - size + 1):
                phrase_words = words[index : index + size]
                phrase = " ".join(phrase_words)
                occurrence_count = lowered.count(phrase)
                if occurrence_count:
                    distinctive = sum(word not in generic_words for word in phrase_words)
                    candidates.append((distinctive, size, -occurrence_count, phrase))

    best_term = max(candidates, default=(0, 0, 0, ""))[3]
    center = lowered.find(best_term) if best_term else -1
    if center < 0:
        return compact[:HANDOFF_WEB_EVIDENCE_EXCERPT_CHARS]

    tail_chars = min(2000, HANDOFF_WEB_EVIDENCE_EXCERPT_CHARS // 6)
    qualification_chars = min(3000, HANDOFF_WEB_EVIDENCE_EXCERPT_CHARS // 4)
    focus_chars = HANDOFF_WEB_EVIDENCE_EXCERPT_CHARS - tail_chars - qualification_chars
    start = max(0, center - focus_chars // 3)
    focus = compact[start : start + focus_chars]
    qualification_terms = (
        "footnote",
        "scope",
        "assumption",
        "uncertainty",
        "warning",
        "limitations",
        "limitation",
        "disclaimer",
        "conditions",
        "additional information",
        "should be confirmed",
        "confirm with",
        "vendor",
        "manufacturer",
    )
    qualification_center = next(
        (lowered.find(term) for term in qualification_terms if lowered.find(term) >= 0),
        -1,
    )
    if qualification_center >= 0:
        qualification_start = max(0, qualification_center - qualification_chars // 3)
        qualification = compact[
            qualification_start : qualification_start + qualification_chars
        ]
    else:
        qualification = ""
    tail = compact[-tail_chars:]
    return (
        f"{focus} ... [qualification / limitation text] ... {qualification} "
        f"... [page ending / notes] ... {tail}"
    )


def _match_allowed_web_source(
    requested: str,
    allowed: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve an extracted URL to canonical tool metadata, or None if not allowed.

    Args:
        requested: URL string from the handoff extractor.
        allowed: Map from normalized URL to canonical web metadata.

    Returns:
        Canonical URL and title from the tool output, or None.
    """
    key = _url_normalize_key(requested)
    if key in allowed:
        return allowed[key]
    for candidate in allowed.values():
        candidate_url = candidate["url"]
        if candidate_url == requested or _url_normalize_key(candidate_url) == key:
            return candidate
    return None


def evidence_inventory_from_result(agent_result: dict) -> str:
    """Build a compact authoritative citation inventory for handoff extraction.

    Args:
        agent_result: LangGraph result containing document and web tool messages.

    Returns:
        Newline-delimited evidence identifiers with short text excerpts.
    """
    lines: list[str] = []
    chunks = sorted(
        _document_chunks_from_tool_results(agent_result).values(),
        key=lambda chunk: chunk["score"],
        reverse=True,
    )[:HANDOFF_EVIDENCE_MAX_DOCUMENT_CHUNKS]
    for chunk in chunks:
        excerpt = " ".join(chunk["text"].split())[:HANDOFF_EVIDENCE_EXCERPT_CHARS]
        lines.append(
            "DOCUMENT "
            f"chunk_id={chunk['chunk_id']} file_id={chunk['file_id']} "
            f"source_session_id={chunk['source_session_id']} "
            f"source={json.dumps(chunk['source'])} pages={json.dumps(chunk['pages'])} "
            f"score={chunk['score']:.6f} "
            f"excerpt={json.dumps(excerpt)}"
        )
    for source in _web_sources_from_temporal_tool_results(agent_result).values():
        excerpt = _web_evidence_excerpt(source["content"], source["queries"])
        lines.append(
            f"WEB url={json.dumps(source['url'])} title={json.dumps(source['title'])} "
            f"excerpt={json.dumps(excerpt)}"
        )
    return "\n".join(lines)


def _sanitize_citations(payload: dict[str, Any], agent_result: dict) -> None:
    """Keep only tool-backed citations and replace model metadata with canonical values.

    Args:
        payload: Handoff dict; citations list is updated in place.
        agent_result: LangGraph result used to read tool outputs.
    """
    allowed_chunks = _document_chunks_from_tool_results(agent_result)
    allowed_web_sources = _web_sources_from_temporal_tool_results(agent_result)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for row in payload.get("citations") or []:
        if not isinstance(row, dict):
            continue
        url = (row.get("url") or "").strip()
        chunk_id = (row.get("chunk_id") or "").strip()

        # A tool-backed URL wins even if the model mislabeled it as a document.
        if url.startswith("http"):
            canonical_web = _match_allowed_web_source(url, allowed_web_sources)
            if canonical_web is None:
                continue
            dedupe_key = ("web", canonical_web["url"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "type": "web",
                    "source": "",
                    "chunk_id": "",
                    "file_id": "",
                    "pages": [],
                    "url": canonical_web["url"],
                    "title": canonical_web["title"],
                }
            )
            continue

        if chunk_id:
            canonical_chunk = allowed_chunks.get(chunk_id)
            if canonical_chunk is None:
                continue
            dedupe_key = ("document", chunk_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "type": "document",
                    "source": canonical_chunk["source"],
                    "chunk_id": canonical_chunk["chunk_id"],
                    "file_id": canonical_chunk["file_id"],
                    "pages": canonical_chunk["pages"],
                    "url": "",
                    "title": canonical_chunk["source"],
                }
            )
            continue

    payload["citations"] = rows
    if not rows:
        payload["confidence"] = "low"
    elif payload.get("open_questions") and str(payload.get("confidence", "")).lower() == "high":
        payload["confidence"] = "medium"


def _sanitize_claims(payload: dict[str, Any], agent_result: dict) -> None:
    """Keep only claims linked to exact document chunks or web results.

    Args:
        payload: Extracted handoff mapping whose claims are updated in place.
        agent_result: LangGraph result containing authoritative tool messages.

    Returns:
        None.
    """
    allowed_chunks = _document_chunks_from_tool_results(agent_result)
    allowed_web = _web_sources_from_temporal_tool_results(agent_result)
    claims: list[dict[str, Any]] = []
    seen_statements: set[str] = set()

    for row in payload.get("claims") or []:
        if not isinstance(row, dict):
            continue
        statement = str(row.get("statement") or "").strip()
        if not statement:
            continue

        chunk_ids: list[str] = []
        for value in row.get("chunk_ids") or []:
            chunk_id = str(value).strip()
            if chunk_id in allowed_chunks and chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)

        urls: list[str] = []
        for value in row.get("urls") or []:
            requested = str(value).strip()
            if not requested.startswith("http"):
                continue
            canonical = _match_allowed_web_source(requested, allowed_web)
            if canonical is not None and canonical["url"] not in urls:
                urls.append(canonical["url"])

        if not chunk_ids and not urls:
            continue
        statement_key = statement.casefold()
        if statement_key in seen_statements:
            continue
        seen_statements.add(statement_key)
        claims.append({"statement": statement, "chunk_ids": chunk_ids, "urls": urls})

    payload["claims"] = claims
    payload["facts"] = [claim["statement"] for claim in claims]


def _citations_from_claims(claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert validated claim references into citation candidates.

    Args:
        claims: Sanitized claims containing tool-backed chunk IDs and URLs.

    Returns:
        Minimal citation rows for canonicalization against tool output.
    """
    citations: list[dict[str, str]] = []
    for claim in claims:
        citations.extend(
            {"type": "document", "chunk_id": chunk_id}
            for chunk_id in claim.get("chunk_ids") or []
        )
        citations.extend(
            {"type": "web", "url": url}
            for url in claim.get("urls") or []
        )
    return citations


def _page_label(pages: list[int]) -> str:
    """Format one-based page numbers for a concise citation label.

    Args:
        pages: Ordered source-page numbers attached to a retrieved chunk.

    Returns:
        A page or page-range label, or an empty string when pages are unavailable.
    """
    if not pages:
        return ""
    if len(pages) == 1:
        return f"p. {pages[0]}"
    return f"pp. {min(pages)}-{max(pages)}"


def _grounded_answer_from_claims(
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    """Render a concise answer whose every bullet links to validated evidence.

    Args:
        claims: Sanitized atomic claims.
        citations: Canonical document and web citation rows.

    Returns:
        Markdown answer built only from supported claims, or a clear insufficiency message.
    """
    if not claims:
        return (
            "I could not produce a claim-level grounded answer from the retrieved evidence. "
            "Additional or more relevant sources are needed."
        )

    by_chunk = {
        row["chunk_id"]: row
        for row in citations
        if row.get("type") == "document" and row.get("chunk_id")
    }
    by_url = {
        row["url"]: row
        for row in citations
        if row.get("type") == "web" and row.get("url")
    }
    lines = ["Evidence-grounded answer:", ""]
    for claim in claims:
        labels: list[str] = []
        for chunk_id in claim.get("chunk_ids") or []:
            row = by_chunk.get(chunk_id)
            if row is None:
                continue
            page_label = _page_label(row.get("pages") or [])
            location = f", {page_label}" if page_label else ""
            labels.append(f"{row['source']}{location}, chunk {chunk_id}")
        for url in claim.get("urls") or []:
            row = by_url.get(url)
            if row is not None:
                labels.append(f"{row.get('title') or row['url']}: {row['url']}")
        evidence = "; ".join(labels)
        lines.append(f"- {claim['statement']} [{evidence}]")
    return "\n".join(lines)


def final_answer_from_result(agent_result: dict) -> str:
    """Return the latest non-empty assistant text from the agent message list.

    Args:
        agent_result: LangGraph invoke result containing a messages list.

    Returns:
        Final assistant reply text, or an empty string if none.
    """
    for message in reversed(agent_result.get("messages", [])):
        if not isinstance(message, AIMessage):
            continue
        text = _message_text(message.content)
        if text:
            return text
    return ""


def tool_trace_from_result(agent_result: dict) -> list[dict[str, Any]]:
    """Build a compact timeline of tool calls and tool results.

    Args:
        agent_result: LangGraph invoke result containing a messages list.

    Returns:
        Ordered entries with kind call or result, tool name, args or preview.
    """
    trace: list[dict[str, Any]] = []
    for message in agent_result.get("messages", []):
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                if isinstance(tc, dict):
                    name, args, tc_id = tc.get("name"), tc.get("args"), tc.get("id")
                else:
                    name = getattr(tc, "name", None)
                    args = getattr(tc, "args", None)
                    tc_id = getattr(tc, "id", None)
                trace.append({"kind": "call", "name": name, "args": args, "id": tc_id})
        if isinstance(message, ToolMessage):
            preview = _message_text(message.content)
            if len(preview) > HANDOFF_TOOL_TRACE_PREVIEW_CHARS:
                preview = preview[:HANDOFF_TOOL_TRACE_PREVIEW_CHARS] + "…"
            trace.append(
                {
                    "kind": "result",
                    "name": getattr(message, "name", None),
                    "tool_call_id": getattr(message, "tool_call_id", None),
                    "content_preview": preview,
                }
            )
    return trace


def transcript_for_handoff(agent_result: dict) -> str:
    """Serialize messages to text for the handoff extractor, with a length cap.

    Args:
        agent_result: LangGraph invoke result containing a messages list.

    Returns:
        Transcript string, truncated from the start if longer than the cap.
    """
    parts: list[str] = []
    for message in agent_result.get("messages", []):
        label = getattr(message, "type", message.__class__.__name__)
        parts.append(f"{label}: {getattr(message, 'content', '')}")
    text = "\n\n".join(parts)
    if len(text) > HANDOFF_TRANSCRIPT_MAX_CHARS:
        return text[-HANDOFF_TRANSCRIPT_MAX_CHARS:]
    return text


async def build_handoff_payload(
    run: RunRecord,
    agent_result: dict,
) -> dict[str, Any]:
    """Run structured-output ChatOpenAI on the transcript, then sanitize citations.

    Uses get_deepsearch_llm (same settings as the ReAct agent), not a separate OpenAI client.

    Args:
        run: Database row for this run (query snapshot and ids).
        agent_result: LangGraph result after the DeepSearch agent finishes.
    Returns:
        Dict containing a claim-validated answer, canonical citations, and tool trace.
    """
    transcript = transcript_for_handoff(agent_result)
    evidence_inventory = evidence_inventory_from_result(agent_result)
    prompt = build_deepsearch_handoff_prompt(
        query=run.query_snapshot,
        transcript=transcript,
        evidence_inventory=evidence_inventory,
    )
    llm = get_deepsearch_llm().with_structured_output(DeepSearchHandoffPayload)
    parsed = await llm.ainvoke([HumanMessage(content=prompt)])
    if parsed is None:
        raise ValueError("Handoff extraction returned empty content")
    structured = DeepSearchHandoffPayload.model_validate(parsed)
    payload = structured.model_dump()
    if not payload.get("query"):
        payload["query"] = run.query_snapshot

    _sanitize_claims(payload, agent_result)
    payload["citations"] = _citations_from_claims(payload["claims"])
    _sanitize_citations(payload, agent_result)
    payload["answer"] = _grounded_answer_from_claims(
        payload["claims"],
        payload["citations"],
    )
    if not payload["claims"]:
        payload["confidence"] = "low"
    payload["tool_trace"] = tool_trace_from_result(agent_result)
    logger.info("Handoff payload extracted run_id=%s session_id=%s", run.run_id, run.session_id)
    return payload
