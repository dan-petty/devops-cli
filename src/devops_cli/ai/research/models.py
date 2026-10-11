"""Data models for agentic information foraging and scent trail exploration."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MarginaliaType(StrEnum):
    """Supported marginalia annotation types."""

    ASSUMPTION = "ASSUMPTION"
    HYPOTHESIS = "HYPOTHESIS"
    CONTRADICTION = "CONTRADICTION"
    QUESTION = "QUESTION"
    TODO = "TODO"


class MarginaliaRecord(BaseModel):
    """A file-anchored observation, hypothesis, contradiction, question, or note."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(description="File path relative to repo root.")
    file_hash: str = Field(description="SHA-256 digest of normalized relative file path.")
    type: Literal["ASSUMPTION", "HYPOTHESIS", "CONTRADICTION", "QUESTION", "TODO"] = Field(
        description="Marginalia annotation classification."
    )
    content: str = Field(description="Annotation text or observation.")
    anchor: str = Field(description="Anchor reference: file path, AST node id, or line range.")
    created_at: str = Field(description="ISO 8601 UTC timestamp of creation.")
    session_id: str | None = Field(
        default=None, description="Optional active session or agent run ID."
    )


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
    marginalia: list[MarginaliaRecord] = Field(
        default_factory=list,
        description="Prior marginalia annotations attached to this file.",
    )


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


class KnowledgeGapType(StrEnum):
    """Classification of epistemic uncertainty."""

    GAP = "GAP"
    AMBIGUITY = "AMBIGUITY"
    UNDERSPECIFIED_CONTRACT = "UNDERSPECIFIED_CONTRACT"


class KnowledgeGap(BaseModel):
    """An identified gap, ambiguity, or underspecified contract in task requirements."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["GAP", "AMBIGUITY", "UNDERSPECIFIED_CONTRACT"] = Field(
        description="Classification of uncertainty: GAP, AMBIGUITY, or UNDERSPECIFIED_CONTRACT."
    )
    description: str = Field(
        description="Description of what is missing, uncertain, or underspecified."
    )
    rationale: str = Field(
        description="Short rationale explaining why this uncertainty impedes execution."
    )


class ClarifyingQuestion(BaseModel):
    """A concise, targeted diagnostic question to eliminate uncertainty."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(
        description="Concise, targeted clarifying question addressing a specific gap."
    )
    target_gap: str = Field(description="The gap, ambiguity, or contract this question clarifies.")
    rationale: str = Field(
        description="Rationale explaining why answering this question eliminates uncertainty."
    )


class CodeLookupInstruction(BaseModel):
    """A concrete instruction to inspect code or symbols to resolve a gap."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str = Field(description="Concrete file path, symbol name, or search term to inspect.")
    lookup_type: Literal["file", "symbol", "search"] = Field(
        description="Type of lookup: file, symbol, or search."
    )
    rationale: str = Field(description="Information to extract from this code inspection.")
    target_gap: str = Field(description="The gap or contract this lookup resolves.")


class SocraticInquiryResult(BaseModel):
    """Structured output of metacognitive Socratic inquiry."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(description="Task description analyzed.")
    summary: str = Field(
        default="", description="Metacognitive summary of epistemic knowledge state."
    )
    gaps: list[KnowledgeGap] = Field(
        default_factory=list,
        description="Identified knowledge gaps, ambiguities, and underspecified contracts.",
    )
    questions: list[ClarifyingQuestion] = Field(
        default_factory=list,
        description="Targeted clarifying questions bounded by max_probes.",
    )
    lookups: list[CodeLookupInstruction] = Field(
        default_factory=list,
        description="Targeted code lookup instructions bounded by max_probes.",
    )
