"""Research judge agent evaluating findings with read-only tools (#3909)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol

from pydantic import BaseModel, Field

from devops_cli.ai.client.factory import build_agent
from devops_cli.ai.tools import Tool
from devops_cli.ai.toolsets import FunctionToolset, create_function_toolset

if TYPE_CHECKING:
    from devops_cli.research.models import Component
    from devops_cli.roadmap.intake.intake import NewCandidate


class JudgeVerdict(StrEnum):
    """Verdict of a judge evaluation."""

    yes = "yes"
    no = "no"
    unknown = "unknown"


class JudgeFinding(BaseModel):
    """Structured finding from judge agent."""

    affects_us: JudgeVerdict
    why: str
    severity: str
    action: str
    evidence_record_ids: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)


class CitationCheck(BaseModel):
    """Outcome of citation check on judged findings."""

    kept: list[JudgeFinding]
    dropped: list[JudgeFinding]
    reasons: list[str]


class ReadOnlyCorpus(Protocol):
    """Protocol for read-only research corpus access."""

    def record_text(self, record_id: str) -> str | None:
        """Lookup stored text by record id."""
        ...

    def holds_url(self, url: str) -> bool:
        """Check if URL exists in corpus."""
        ...

    def stored_texts(self, query: str, regex: bool = False) -> list[str]:
        """Match stored texts."""
        ...

    def components(self) -> list[Component]:
        """List tracked components."""
        ...

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search repository via RAG."""
        ...


JUDGE_INSTRUCTIONS: Final[str] = (
    "You are the DevOps CLI research judge. Your task is to evaluate new records against "
    "the project's components and code to determine whether an advisory or release affects us. "
    "Set affects_us to 'yes', 'no', or 'unknown'. "
    "Explain why, set severity and recommended action, and cite each claim with evidence "
    "record ids and evidence URLs."
)


def build_judge_toolset(corpus: ReadOnlyCorpus) -> FunctionToolset[Any]:
    """Construct the read-only toolset for the research judge agent."""

    def store_lookup(record_id: str) -> str:
        """Lookup advisory or release text in the store by its record id."""
        return corpus.record_text(record_id) or ""

    def repository_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search repository code for references via RAG."""
        return corpus.search(query, limit=limit)

    def component_list() -> list[dict[str, Any]]:
        """List the project components and inventory pins."""
        return [comp.model_dump() for comp in corpus.components()]

    def match_stored_text(pattern: str, is_regex: bool = False) -> list[str]:
        """Search or match text across stored records."""
        return corpus.stored_texts(pattern, regex=is_regex)

    return create_function_toolset(
        tools=[
            Tool.from_function(store_lookup, name="store_lookup"),
            Tool.from_function(repository_search, name="repository_search"),
            Tool.from_function(component_list, name="component_list"),
            Tool.from_function(match_stored_text, name="match_stored_text"),
        ],
        id="research_judge_toolset",
    )


def build_judge_agent(model: Any, corpus: ReadOnlyCorpus) -> Any:
    """Build the configured research judge agent."""
    return build_agent(
        model=model,
        output_type=JudgeFinding,
        instructions=JUDGE_INSTRUCTIONS,
        toolsets=[build_judge_toolset(corpus)],
    )


def check_judged_citations(
    findings: Sequence[JudgeFinding],
    corpus: ReadOnlyCorpus,
) -> CitationCheck:
    """Verify evidence citations against the read-only corpus."""
    kept: list[JudgeFinding] = []
    dropped: list[JudgeFinding] = []
    reasons: list[str] = []

    for finding in findings:
        drop_reason: str | None = None
        for rec_id in finding.evidence_record_ids:
            if corpus.record_text(rec_id) is None:
                drop_reason = f"Record id {rec_id} not found in store"
                break
        if drop_reason is None:
            for url in finding.evidence_urls:
                if not corpus.holds_url(url):
                    drop_reason = f"URL {url} not found in store"
                    break
        if drop_reason is not None:
            dropped.append(finding)
            reasons.append(drop_reason)
        else:
            kept.append(finding)

    return CitationCheck(kept=kept, dropped=dropped, reasons=reasons)


def judge_intake_candidate(judgment: JudgeFinding, record: Any = None) -> NewCandidate:
    """Build an intake candidate for an actionable judged finding."""
    from devops_cli.roadmap.intake.intake import Filer, NewCandidate

    component = getattr(record, "component", None)
    advisory_id = getattr(record, "advisory_id", getattr(record, "id", None))
    if advisory_id is None and judgment.evidence_record_ids:
        advisory_id = judgment.evidence_record_ids[0]
    advisory_id = advisory_id or "advisory"

    if component is not None and hasattr(component, "name"):
        title = f"fix(deps): update {component.name} for {advisory_id}"
    else:
        title = f"fix(deps): update component for {advisory_id}"

    lines = [
        "### Problem",
        "",
        judgment.why,
        "",
        "### Expected",
        "",
        judgment.action,
        "",
        "### Details",
        f"- Severity: {judgment.severity}",
        f"- Affects us: {judgment.affects_us}",
    ]
    if judgment.evidence_record_ids:
        lines.append(f"- Evidence records: {', '.join(judgment.evidence_record_ids)}")
    if judgment.evidence_urls:
        lines.append(f"- Evidence URLs: {', '.join(judgment.evidence_urls)}")

    return NewCandidate(title=title, body="\n".join(lines), filed_by=Filer.AGENT)


def file_judged_findings(
    findings: Sequence[JudgeFinding | tuple[JudgeFinding, Any]],
    corpus: ReadOnlyCorpus,
    file_candidate: Callable[[NewCandidate], Any],
) -> CitationCheck:
    """Check citations and file intake candidates for actionable findings."""
    pairs: list[tuple[JudgeFinding, Any]] = [
        item if isinstance(item, tuple) else (item, None) for item in findings
    ]
    judgments = [pair[0] for pair in pairs]
    check = check_judged_citations(judgments, corpus)

    kept_set = set(id(f) for f in check.kept)
    for judgment, record in pairs:
        if id(judgment) in kept_set and judgment.affects_us == JudgeVerdict.yes:
            candidate = judge_intake_candidate(judgment, record)
            file_candidate(candidate)

    return check
