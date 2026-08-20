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
