"""Data models for agentic information foraging and scent trail exploration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ForageEdge(BaseModel):
    """A directed edge between two file nodes in the repository."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Source file path relative to repo root.")
    target: str = Field(description="Target file path relative to repo root.")
    edge_type: Literal["import", "markdown_link", "git_co_change"] = Field(
        description="Type of relational edge."
    )
    detail: str = Field(
        default="",
        description="Descriptive context (imported symbol, href, commit count).",
    )
    weight: float = Field(
        default=1.0,
        description="Heuristic edge weight or frequency score.",
    )


class ForageNode(BaseModel):
    """A visited or evaluated node in the information foraging trail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(description="File path relative to repo root.")
    score: float = Field(description="BM25 semantic relevance score against query.")
    depth: int = Field(default=0, description="Hop distance from the starting anchor.")
    edge_type: str | None = Field(default=None, description="Edge type that led to this node.")
    detail: str = Field(default="", description="Edge detail that led to this node.")


class BacktrackEvent(BaseModel):
    """An event recording the crawler backtracking from a low-scent branch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_node: str = Field(description="Node path where the trail grew cold.")
    to_node: str = Field(description="Frontier node backtracked to.")
    reason: str = Field(default="low_scent", description="Reason for backtracking.")
    score: float = Field(description="Scent score at the abandonment point.")
    threshold: float = Field(description="Relevance threshold that triggered backtracking.")


class ForageTrail(BaseModel):
    """Complete results of an information foraging exploration run."""

    model_config = ConfigDict(extra="forbid")

    anchor: str = Field(description="Starting anchor node path or keyword.")
    query: str = Field(description="Inquiry text used for scent calculation.")
    visited_nodes: list[ForageNode] = Field(
        default_factory=list,
        description="Ordered sequence of visited nodes along the trail.",
    )
    edges: list[ForageEdge] = Field(
        default_factory=list,
        description="All traversed edges in the trail.",
    )
    backtrack_events: list[BacktrackEvent] = Field(
        default_factory=list,
        description="Backtracking decisions made when scent grew cold.",
    )
    cycles_detected: list[list[str]] = Field(
        default_factory=list,
        description="Cycles detected and avoided [source, target].",
    )
    ranked_trail: list[ForageNode] = Field(
        default_factory=list,
        description="Nodes ranked by relevance scent score.",
    )
