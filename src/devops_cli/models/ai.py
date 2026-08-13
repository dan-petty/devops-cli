"""Shared domain models for AI/LLM client messages."""

from __future__ import annotations

from typing import Literal

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
