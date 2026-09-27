from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator


class ProcessedChunk(BaseModel):
    """One text chunk tied to a session, user, and stored file.

    Attributes:
        chunk_id: Short id (8 hex chars from a UUID).
        text: Chunk text.
        source: Original filename for this document (from PreprocessDocument).
        session_id: Session this chunk belongs to.
        user_id: Owning user for the session.
        file_id: Stored file id for this document.
        content_hash: SHA-256 hash of the original file content.
    """

    chunk_id: str = Field(..., description="8-character hex id (uuid4 prefix)")
    text: str = Field(..., description="Chunk text")
    source: str = Field(..., description="Original filename")
    session_id: str = Field(..., description="Session id for this upload/chunk batch")
    user_id: str = Field(..., description="User id for the session")
    file_id: str = Field(..., description="Stored file id")
    content_hash: str = Field(
        ...,
        description="SHA-256 hash of the original file content",
    )
    pages: list[int] = Field(
        default_factory=list,
        description="One-based source pages represented in the chunk when available",
    )


class EmbeddedChunk(BaseModel):
    """A processed chunk plus its embedding vector (for vector store upsert)."""

    chunk: ProcessedChunk = Field(..., description="Chunk metadata and text")
    embedding: list[float] = Field(..., description="Dense vector from the embedding model")


class CreateSessionRequest(BaseModel):
    """Request body for creating a session.

    Attributes:
        user_id: ID of the user.
        user_query: User query.
    """
    user_id: str = Field(..., description="ID of the user")
    user_query: str = Field(..., description="User query")


class CreateSessionResponse(BaseModel):
    """Response body for creating a session.

    Attributes:
        session_id: ID of the created session.
    """
    session_id: str = Field(..., description="ID of the created session")


class FileInfo(BaseModel):
    """One stored file metadata entry (upload or generated)."""

    file_id: str = Field(..., description="Id for the stored file")
    filename: str = Field(..., description="Filename on disk")
    content_hash: str = Field(
        ...,
        description="SHA-256 hash of the stored file content",
    )


class FileUploadResponse(BaseModel):
    """Response after uploading one or more files for a session."""

    session_id: str = Field(
        ...,
        description="Session id; files are stored under data/<session_id>/uploads/",
    )
    files: list[FileInfo] = Field(..., description="Per-file ids and names")


class FileIngestionOutput(BaseModel):
    """Outcome of ingesting one file (parse → embed → upsert)."""

    filename: str = Field(..., description="Original filename")
    file_id: str = Field(..., description="Stored file id")
    ok: bool = Field(..., description="Whether all steps succeeded")
    chunk_count: int = Field(0, description="Embedded chunks written when ok")
    error: str | None = Field(None, description="Error message when ok is false")


class SessionFilesIngestionOutput(BaseModel):
    """Aggregate outcome for processing all uploads in a session."""

    session_id: str = Field(..., description="Session id")
    files: list[FileIngestionOutput] = Field(default_factory=list, description="Per-file results")

    @computed_field
    @property
    def all_ok(self) -> bool:
        """Indicate whether every file in a nonempty ingestion batch succeeded.

        Returns:
            True when at least one result exists and all results are successful.
        """
        return bool(self.files) and all(f.ok for f in self.files)

class RetrievedChunk(BaseModel):
    """One chunk returned from vector search (for RAG or agent tools)."""

    chunk_id: str = Field(..., description="Chunk id from ingest payload")
    text: str = Field(..., description="Chunk text")
    source: str = Field(..., description="Source filename or label")
    file_id: str = Field(..., description="Stored file id")
    source_session_id: str = Field(
        ...,
        description="Session where the retrieved source file was originally uploaded",
    )
    pages: list[int] = Field(default_factory=list, description="One-based source page numbers")
    score: float = Field(..., description="Similarity score from Qdrant (cosine)")


class WebSearchResult(BaseModel):
    """One normalized web search hit returned by the web search tool."""

    title: str = Field(default="", description="Result title")
    url: str = Field(..., description="Canonical URL")
    snippet: str = Field(default="", description="Short snippet from provider")
    content: str = Field(default="", description="Expanded extracted content")
    source_domain: str = Field(default="", description="Domain parsed from URL")
    published_at: str | None = Field(default=None, description="Published timestamp if provided")
    score: float | None = Field(default=None, description="Provider relevance score")
    query: str = Field(..., description="Query used for this search")


class StartRunRequest(BaseModel):
    """Body for POST /runs."""

    session_id: str = Field(..., description="Session id with stored query and uploads")
    user_id: str = Field(
        ...,
        description="Must match session owner; used for vector search user_id filter.",
    )


class StartRunResponse(BaseModel):
    """Response body for start run endpoint."""

    run_id: str = Field(..., description="Created run id")
    status: str = Field(..., description="Initial run status")


class GetRunResponse(BaseModel):
    """Run details returned by get run endpoint."""

    run_id: str = Field(..., description="Run id")
    session_id: str = Field(..., description="Session id")
    status: str = Field(..., description="Run status")
    query_snapshot: str = Field(..., description="Query snapshot at run creation")
    final_answer: str | None = Field(default=None, description="Final generated answer")
    error_message: str | None = Field(default=None, description="Failure details if any")


class AgentOutputResponse(BaseModel):
    """Structured artifact generated by an agent run."""

    output_id: str = Field(..., description="Agent output id")
    session_id: str = Field(..., description="Session id")
    run_id: str = Field(..., description="Run id")
    agent_name: str = Field(..., description="Agent name")
    output_type: str = Field(..., description="Output type")
    payload: dict[str, Any] = Field(..., description="Structured handoff payload")


class DeepSearchCitation(BaseModel):
    """One evidence item for DeepSearch output."""

    type: str = Field(..., description="Citation source type: doc or web")
    source: str = Field(default="", description="Document source label if available")
    chunk_id: str = Field(default="", description="Chunk id for document citations when available")
    file_id: str = Field(default="", description="Stored file id for document citations")
    pages: list[int] = Field(default_factory=list, description="One-based source page numbers")
    url: str = Field(default="", description="URL for web citations when available")
    title: str = Field(default="", description="Title for web citations when available")

    @model_validator(mode="before")
    @classmethod
    def _coerce_llm_nulls(cls, data: Any) -> Any:
        """Normalize nullable or non-string citation fields emitted by an LLM.

        Args:
            data: Raw citation value supplied before Pydantic validation.

        Returns:
            A normalized citation mapping, or the original non-mapping value.
        """
        if not isinstance(data, dict):
            return data
        d = dict(data)
        s = lambda v: "" if v is None else v if isinstance(v, str) else str(v)
        for k in ("source", "chunk_id", "file_id", "url", "title"):
            if k in d:
                d[k] = s(d[k])
        pages = d.get("pages")
        if pages is None:
            d["pages"] = []
        if "type" in d:
            t = d["type"]
            d["type"] = "unknown" if t in (None, "") else s(t)
        return d


class DeepSearchClaim(BaseModel):
    """One answer claim and the exact tool evidence asserted to support it."""

    statement: str = Field(..., description="Atomic factual statement presented to the user")
    chunk_ids: list[str] = Field(
        default_factory=list,
        description="Exact document chunk ids supporting the statement",
    )
    urls: list[str] = Field(
        default_factory=list,
        description="Exact web-result URLs supporting the statement",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_llm_values(cls, data: Any) -> Any:
        """Normalize nullable claim collections emitted by an LLM.

        Args:
            data: Raw claim value supplied before Pydantic validation.

        Returns:
            A normalized claim mapping, or the original non-mapping value.
        """
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        normalized["statement"] = str(normalized.get("statement") or "").strip()
        normalized["chunk_ids"] = normalized.get("chunk_ids") or []
        normalized["urls"] = normalized.get("urls") or []
        return normalized


class DeepSearchHandoffPayload(BaseModel):
    """Structured payload persisted for downstream agent handoff."""

    query: str = Field(..., description="Original user query snapshot")
    answer: str = Field(..., description="Final grounded answer")
    claims: list[DeepSearchClaim] = Field(
        default_factory=list,
        description="Atomic claims with exact tool evidence references",
    )
    citations: list[DeepSearchCitation] = Field(default_factory=list, description="Evidence references")
    facts: list[str] = Field(default_factory=list, description="Atomic facts extracted from evidence")
    open_questions: list[str] = Field(default_factory=list, description="Unresolved questions or missing evidence")
    confidence: str = Field(default="unknown", description="Confidence level: low, medium, high, or unknown")
