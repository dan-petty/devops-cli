"""Shared domain models for AI/LLM client messages."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single message in a multi-turn LLM conversation."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to the dict format expected by provider HTTP APIs."""
        return {"role": self.role, "content": self.content}


class FileAnalysisMeta(BaseModel):
    """Metadata attributes for an individual file in an analysis session."""

    path: str
    size_bytes: int = 0
    line_count: int = 0
    char_count: int = 0
    language: str = "text"
    primary_purpose: str = ""
    key_symbols: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    change_type: str = "existing"
    pseudocode: list[str] | None = None
    last_updated: str | None = None
    last_analyzed: str | None = None
    complexity_score: str | None = None
    confidence_score: float | None = None
    quality_score: float | None = None
    content_hash: str | None = None


class ProjectAnalysisMeta(BaseModel):
    """Project-level metadata attributes for an analysis session."""

    title: str
    target_type: Literal["branch", "pr", "path"]
    target_reference: str
    timestamp: str
    total_files: int
    total_lines: int
    total_chars: int
    languages: list[str]
    primary_purpose: str
    key_symbols: list[str]
    dependencies: list[str]
    enhanced: bool = False
    last_analyzed: str | None = None
    confidence_score: float | None = None
    quality_score: float | None = None


class AnalysisMetadata(BaseModel):
    """Top-level schema for .data/analysis/*-metadata.json files."""

    project: ProjectAnalysisMeta
    files: list[FileAnalysisMeta]


class MCPToolInfo(BaseModel):
    """Information for a registered FastMCP server tool."""

    name: str
    description: str

    def __getitem__(self, item: str) -> str:
        return str(getattr(self, item))

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)


class ScratchpadEntry(BaseModel):
    """An individual structured reasoning record within an AI agent scratchpad."""

    persona: str
    stage: str
    hypothesis: str = ""
    notes: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    timestamp: str = ""


class ScratchpadBuffer(BaseModel):
    """Structured multi-turn reasoning scratchpad buffer for agentic pipeline turns."""

    session_id: str = "default-session"
    max_entries: int = 10
    max_chars: int = 4000
    keep_recent: int = 3
    summary: str = ""
    entries: list[ScratchpadEntry] = Field(default_factory=list)

    def add_entry(
        self,
        persona: str,
        stage: str,
        hypothesis: str = "",
        notes: list[str] | None = None,
        key_findings: list[str] | None = None,
    ) -> ScratchpadEntry:
        """Append a new reasoning entry to the scratchpad buffer."""
        from datetime import UTC, datetime

        entry = ScratchpadEntry(
            persona=persona,
            stage=stage,
            hypothesis=hypothesis,
            notes=notes or [],
            key_findings=key_findings or [],
            timestamp=datetime.now(UTC).isoformat(),
        )
        self.entries.append(entry)
        self.auto_summarize_if_needed()
        return entry

    @property
    def total_chars(self) -> int:
        """Total character length across all scratchpad hypotheses, notes, and findings."""
        return sum(
            len(e.hypothesis) + sum(len(n) for n in e.notes) + sum(len(k) for k in e.key_findings)
            for e in self.entries
        )

    def should_summarize(self) -> bool:
        """Return True if entry count or total character threshold is exceeded."""
        return len(self.entries) > self.max_entries or self.total_chars > self.max_chars

    def auto_summarize_if_needed(self, llm_client: Any | None = None) -> bool:
        """Automatically compress older scratchpad entries into a summary if size
        limits are reached.
        """
        if not self.should_summarize() or len(self.entries) <= self.keep_recent:
            return False

        cutoff = len(self.entries) - self.keep_recent
        to_summarize = self.entries[:cutoff]
        to_keep = self.entries[cutoff:]

        bullets: list[str] = []
        if self.summary:
            bullets.append(self.summary)
        for e in to_summarize:
            n_str = (", ".join(e.notes))[:80] if e.notes else ""
            h_str = e.hypothesis[:100]
            entry_line = f"[{e.persona.upper()}/{e.stage}] {h_str}"
            if n_str:
                entry_line += f" ({n_str})"
            bullets.append(entry_line)

        new_summary = " -> ".join(bullets)
        if len(new_summary) > self.max_chars // 2:
            new_summary = new_summary[: (self.max_chars // 2) - 3] + "..."

        self.summary = new_summary
        self.entries = to_keep
        return True

    def render_context_summary(self) -> str:
        """Render a concise markdown summary of intermediate scratchpad reasoning."""
        if not self.entries and not self.summary:
            return ""
        lines: list[str] = ["### Scratchpad Reasoning Context"]
        if self.summary:
            lines.append(f"- **[ACCUMULATED SUMMARY]**: {self.summary}")
        for entry in self.entries:
            lines.append(f"- **[{entry.persona.upper()} | {entry.stage}]**: {entry.hypothesis}")
            for note in entry.notes:
                lines.append(f"  • {note}")
        return "\n".join(lines)


# ── AI Review & MCP Request/Response Resource Models ─────────────────────────


class ReviewPathRequest(BaseModel):
    """Request parameters for AI code review on local filesystem paths."""

    target: str = Field(default=".", description="File or directory path to review")
    pattern: str = Field(default="*", description="Glob pattern filter")
    persona: str = Field(default="devsecops", description="Reviewer persona to activate")
    all_files: bool = Field(default=False, description="Review all files matching pattern")


class ReviewBranchRequest(BaseModel):
    """Request parameters for AI code review on a git branch diff."""

    branch: str = Field(default="", description="Branch to review (empty for active branch)")
    base: str = Field(default="main", description="Target base branch to diff against")
    persona: str = Field(default="devsecops", description="Reviewer persona to activate")


class ReviewPRRequest(BaseModel):
    """Request parameters for AI code review on a GitHub Pull Request."""

    number: int = Field(..., description="GitHub Pull Request number")
    post: bool = Field(default=False, description="Post inline review comments directly to PR")
    persona: str = Field(default="devsecops", description="Reviewer persona to activate")


class ReviewFindingsRequest(BaseModel):
    """Request parameters for inspecting saved review findings."""

    session_id: str = Field(default="", description="Specific review session ID (empty for latest)")
    status_filter: str = Field(
        default="", description="Filter by status (VERIFIED, INVALIDATED, etc.)"
    )


class FindingSummaryEntry(BaseModel):
    """Compact summary for a review finding."""

    finding_id: str = Field(..., description="Unique finding identifier")
    title: str = Field(..., description="Finding title")
    severity: str = Field(..., description="Severity level")
    location: str = Field(..., description="Location in canonical file.ext:line format")
    status: str = Field(default="VERIFIED", description="Verification status")
    persona: str = Field(default="devsecops", description="Originating persona")


class ReviewFindingsResult(BaseModel):
    """Result report of review findings."""

    session_id: str = Field(default="", description="Queried review session ID")
    total_findings: int = Field(default=0, description="Total count of findings discovered")
    findings: list[FindingSummaryEntry] = Field(
        default_factory=list, description="List of finding summary records"
    )


class VerifyFindingRequest(BaseModel):
    """Request parameters for human verification or invalidation of a review finding."""

    finding_id: str = Field(..., description="Target finding ID or title substring")
    action: Literal["verify", "invalidate", "mitigate"] = Field(
        default="verify", description="Verification status to apply"
    )
    reason: str = Field(
        default="", description="Explanation or justification for the status update"
    )
    session_id: str = Field(default="", description="Review session ID (empty for latest)")


class VerifyFindingResult(BaseModel):
    """Result of finding verification status update."""

    finding_id: str = Field(..., description="Updated finding identifier")
    updated_status: str = Field(..., description="New verification status")
    success: bool = Field(default=True, description="Whether status was updated cleanly")


class ReviewStatsRequest(BaseModel):
    """Request parameters for querying review accuracy and session statistics."""

    limit_sessions: int = Field(default=10, description="Number of recent sessions to analyze")


class ReviewStatsResult(BaseModel):
    """Aggregated statistics on code review accuracy, findings, and personas."""

    total_sessions_analyzed: int = Field(default=0, description="Count of reviewed sessions")
    total_findings: int = Field(default=0, description="Total findings across analyzed sessions")
    verified_findings: int = Field(default=0, description="Count of verified findings")
    invalidated_findings: int = Field(default=0, description="Count of invalidated false positives")
    accuracy_rate: float = Field(default=1.0, description="Verified findings ratio (0.0 - 1.0)")
    persona_distribution: dict[str, int] = Field(
        default_factory=dict, description="Finding counts grouped by persona"
    )


class ExportFeedbackRequest(BaseModel):
    """Request parameters for exporting invalidated review feedback for benchmark datasets."""

    output_path: str = Field(
        default="", description="Custom output destination path (.jsonl format)"
    )


class ExportFeedbackResult(BaseModel):
    """Report from feedback dataset export."""

    output_path: str = Field(..., description="Path to generated JSONL dataset")
    total_records_exported: int = Field(default=0, description="Count of feedback records written")
    success: bool = Field(default=True, description="Whether export completed cleanly")


class RAGChunkResult(BaseModel):
    """A matched text chunk returned from RAG hybrid search."""

    file_path: str = Field(..., description="Source file location")
    chunk_index: int = Field(default=0, description="Chunk sequence index")
    content: str = Field(..., description="Extracted code or documentation text")
    score: float = Field(default=0.0, description="Hybrid retrieval relevance score")


class RAGSearchRequest(BaseModel):
    """Request parameters for semantic & hybrid BM25 search across repository codebase."""

    query: str = Field(..., description="Natural language or code query string")
    top_k: int = Field(default=5, description="Maximum number of context chunks to retrieve")
    hybrid: bool = Field(
        default=True, description="Use reciprocal rank fusion of BM25 and dense vectors"
    )


class RAGSearchResult(BaseModel):
    """Retrieval results from RAG codebase index."""

    query: str = Field(..., description="Original search query")
    chunks: list[RAGChunkResult] = Field(
        default_factory=list, description="Retrieved context chunks"
    )
    total_chunks: int = Field(default=0, description="Count of returned chunks")


class RAGIndexRequest(BaseModel):
    """Request parameters for building or refreshing RAG vector and BM25 index."""

    target_dir: str = Field(default=".", description="Root directory to index")
    force_refresh: bool = Field(default=False, description="Re-index all files regardless of cache")


class RAGIndexResult(BaseModel):
    """Result report from RAG indexing operation."""

    target_dir: str = Field(..., description="Indexed directory path")
    indexed_files: int = Field(default=0, description="Count of files parsed and embedded")
    total_chunks_created: int = Field(default=0, description="Total vector and BM25 chunks indexed")
    success: bool = Field(default=True, description="Whether indexing completed cleanly")


class TelemetryStatusRequest(BaseModel):
    """Request parameters for querying active OpenTelemetry and Prometheus status."""

    include_metrics: bool = Field(default=True, description="Include in-memory metric counters")


class TelemetryStatusResult(BaseModel):
    """Operational status report for distributed tracing and Prometheus metrics."""

    tracing_enabled: bool = Field(
        default=True, description="Whether OTel distributed tracing is active"
    )
    otlp_endpoint: str = Field(default="", description="Configured OTLP collector endpoint")
    service_name: str = Field(
        default="devops-cli", description="Registered OpenTelemetry service name"
    )
    metrics_count: int = Field(
        default=0, description="Count of registered in-memory Prometheus metrics"
    )
    active_spans_count: int = Field(default=0, description="Active distributed spans count")


class TelemetryTestSpanRequest(BaseModel):
    """Request parameters for sending a test telemetry span to OTLP collector."""

    name: str = Field(default="test.manual_span", description="Span operation name")
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Custom span key-value attributes"
    )


class TelemetryTestSpanResult(BaseModel):
    """Result from manual telemetry span emission."""

    trace_id: str = Field(..., description="Generated 32-hex trace ID")
    span_id: str = Field(..., description="Generated 16-hex span ID")
    sent: bool = Field(default=True, description="Whether the span was exported to collector")
