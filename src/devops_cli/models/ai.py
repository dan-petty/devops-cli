"""Shared domain models for AI/LLM client messages."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    """A single message in a multi-turn LLM conversation."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to the dict format expected by provider HTTP APIs."""
        return {"role": self.role, "content": self.content}


class SegmentMeta(BaseModel):
    """Structured, machine-readable metadata for a review segment."""

    index: int
    filenames: list[str]
    primary_purpose: str
    key_symbols: list[str]
    dependencies: list[str]
    change_types: list[str]
    char_count: int
    first_lines: list[str]
    last_lines: list[str]
    pseudocode: list[str] | None = None
    complexity: str | None = None

    @property
    def summary(self) -> str:
        """Formatted summary string for backward compatibility with markdown reports."""
        parts = [f"**Primary purpose** — {self.primary_purpose}"]
        if self.key_symbols:
            symbols_str = ", ".join(f"`{s}`" for s in self.key_symbols)
            parts.append(f"**Key symbols** — {symbols_str}")
        if self.dependencies:
            deps_str = ", ".join(f"`{d}`" for d in self.dependencies)
            parts.append(f"**External dependencies** — {deps_str}")
        return "\n".join(parts)


class ReviewMeta(BaseModel):
    """Top-level review session metadata containing segment-level attributes."""

    title: str
    total_segments: int
    total_chars: int
    all_files: list[str]
    segments: list[SegmentMeta]


class FileAnalysisMeta(BaseModel):
    """Metadata attributes for an individual file in an analysis session."""

    path: str
    size_bytes: int
    line_count: int
    char_count: int
    language: str
    primary_purpose: str
    key_symbols: list[str]
    dependencies: list[str]
    change_type: str = "existing"
    pseudocode: list[str] | None = None
    last_updated: str | None = None
    last_analyzed: str | None = None
    complexity_score: str | None = None


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


class AnalysisMetadata(BaseModel):
    """Top-level schema for .data/analysis/*-metadata.json files."""

    project: ProjectAnalysisMeta
    files: list[FileAnalysisMeta]
