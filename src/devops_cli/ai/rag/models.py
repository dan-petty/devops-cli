"""Pydantic domain models for Retrieval-Augmented Generation (RAG)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CodeChunk(BaseModel):
    """A semantic chunk of code or documentation with precise line attribution."""

    model_config = ConfigDict(frozen=False)

    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str = "python"
    doc_type: str = "code"  # "code" | "doc" | "manifest"
    category: str = "code"  # "code" | "docs" | "iac" | "config" | "api_spec" | "architecture"
    project_name: str = "default"
    section_path: list[str] = Field(default_factory=list)
    symbol_names: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""


class SearchResult(BaseModel):
    """A single vector search result with similarity score and chunk payload."""

    model_config = ConfigDict(frozen=False)

    chunk: CodeChunk
    score: float
    rerank_score: float | None = None
    rank_factors: dict[str, float] = Field(default_factory=dict)


class RAGContext(BaseModel):
    """Aggregated retrieval context formatted for LLM system/user prompts."""

    model_config = ConfigDict(frozen=False)

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    formatted_text: str = ""

    @property
    def has_results(self) -> bool:
        """Return True if any search results are present."""
        return len(self.results) > 0


class IndexStats(BaseModel):
    """Summary statistics for a vector collection."""

    model_config = ConfigDict(frozen=False)

    collection_name: str
    total_vectors: int = 0
    vector_size: int = 0
    indexed_files: int = 0
    last_indexed_at: str | None = None
