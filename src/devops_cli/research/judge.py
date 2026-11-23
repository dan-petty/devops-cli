"""Research judge agent evaluating findings with read-only tools (#3909)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol

from pydantic import BaseModel, Field

from devops_cli.ai.client.factory import build_agent
from devops_cli.ai.tools import Tool
from devops_cli.ai.toolsets import FunctionToolset, create_function_toolset
from devops_cli.research.models import Component, ComponentKind, Ecosystem
from devops_cli.security.prompt_injection import scan_injection_text

if TYPE_CHECKING:
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


class JudgeStop(BaseModel):
    """Reason and limit when judge loop stops early."""

    setting: str
    value: int
    count: int = 0


class JudgeLimits(BaseModel):
    """Execution limits for the judge agent."""

    record_limit: int | None = None
    daily_token_limit: int | None = None
    tokens_used_today: int = 0


def judge_limits_from_settings(settings: Any) -> JudgeLimits:
    """Build JudgeLimits from application settings."""
    from devops_cli.config.settings import setting_default

    research_cfg = getattr(settings, "research", None)
    judge_cfg = getattr(research_cfg, "judge", None) if research_cfg else None
    record_limit = getattr(judge_cfg, "record_limit", None) if judge_cfg else None
    if record_limit is None:
        record_limit = int(setting_default("research.judge.record_limit"))
    daily_token_limit = getattr(judge_cfg, "daily_token_limit", None) if judge_cfg else None
    if daily_token_limit is None:
        daily_token_limit = int(setting_default("research.judge.daily_token_limit"))
    return JudgeLimits(
        record_limit=record_limit,
        daily_token_limit=daily_token_limit,
    )


class JudgeReport(BaseModel):
    """Outcome of a judge run over records."""

    findings: list[JudgeFinding] = Field(default_factory=list)
    dropped: list[JudgeFinding] = Field(default_factory=list)
    withheld: list[str] = Field(default_factory=list)
    stop: JudgeStop | None = None
    tokens_used: int = 0


class ReadOnlyCorpus(Protocol):
    """Protocol for read-only research corpus access."""

    def record_text(self, record_id: str) -> str | None: ...
    def holds_url(self, url: str) -> bool: ...
    def stored_texts(self, query: str, regex: bool = False) -> list[str]: ...
    def components(self) -> list[Component]: ...
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]: ...


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


def _record_text(record: Any) -> str:
    """Extract text content from a record."""
    if isinstance(record, dict):
        return str(
            record.get(
                "text",
                record.get(
                    "summary",
                    record.get("body", record.get("details", record.get("description", ""))),
                ),
            )
        )
    for attr in ("text", "summary", "body", "details", "description"):
        val = getattr(record, attr, None)
        if val is not None:
            return str(val)
    return str(record)


def _record_id(record: Any) -> str:
    """Extract identifier from a record."""
    if isinstance(record, dict):
        return str(record.get("id", record.get("record_id", record.get("advisory_id", ""))))
    for attr in ("id", "record_id", "advisory_id"):
        val = getattr(record, attr, None)
        if val is not None:
            return str(val)
    return str(record)


def withheld_record_ids(records: Sequence[Any]) -> list[str]:
    """Run injection scanner on record texts and return ids of flagged records."""
    flagged: list[str] = []
    for rec in records:
        text = _record_text(rec)
        rec_id = _record_id(rec)
        findings = scan_injection_text(text, location=rec_id)
        if findings:
            flagged.append(rec_id)
    return flagged


def judge_records(
    records: Sequence[Any],
    corpus: ReadOnlyCorpus,
    model: Any,
    limits: JudgeLimits | None = None,
) -> JudgeReport:
    """Evaluate candidate records with the judge agent subject to limits."""
    report = JudgeReport()
    flagged_ids = set(withheld_record_ids(records))
    report.withheld = [
        rec_id for rec_id in (_record_id(r) for r in records) if rec_id in flagged_ids
    ]

    agent = build_judge_agent(model, corpus)
    records_judged = 0

    for record in records:
        rec_id = _record_id(record)
        if rec_id in flagged_ids:
            continue

        current_tokens = (limits.tokens_used_today if limits else 0) + report.tokens_used
        if (
            limits
            and limits.daily_token_limit is not None
            and current_tokens >= limits.daily_token_limit
        ):
            report.stop = JudgeStop(
                setting="research.judge.daily_token_limit",
                value=limits.daily_token_limit,
                count=records_judged,
            )
            break

        if limits and limits.record_limit is not None and records_judged >= limits.record_limit:
            report.stop = JudgeStop(
                setting="research.judge.record_limit",
                value=limits.record_limit,
                count=records_judged,
            )
            break

        rec_text = _record_text(record)
        prompt = f"Evaluate record {rec_id}:\n{rec_text}"
        result = agent.run_sync(prompt)
        records_judged += 1

        usage = getattr(result, "usage", None)
        if usage is not None:
            report.tokens_used += getattr(usage, "total_tokens", 0)

        finding = result.output
        if isinstance(finding, JudgeFinding):
            check = check_judged_citations([finding], corpus)
            if check.kept:
                report.findings.append(finding)
            if check.dropped:
                report.dropped.extend(check.dropped)

    return report


class EvalRecord(BaseModel):
    """Evaluation record with component metadata."""

    id: str
    text: str
    url: str
    component: Component


class LabeledJudgment(BaseModel):
    """A record paired with its expected verdict label."""

    record: EvalRecord
    label: JudgeVerdict


LABELED_FINDINGS: Final[tuple[LabeledJudgment, ...]] = (
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-01",
            text="CVE-2026-1001 critical vulnerability in fastapi version 0.115.0 allows arbitrary code execution",
            url="https://example.com/advisory/rec-eval-01",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="fastapi",
                version="0.115.0",
                file="pyproject.toml",
                line=25,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-02",
            text="GHSA-2026-0002 high severity memory leak in uvloop 0.21.0 under heavy load",
            url="https://example.com/advisory/rec-eval-02",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="uvloop",
                version="0.21.0",
                file="pyproject.toml",
                line=40,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-03",
            text="Security issue in pydantic 2.10.0 affects input model parsing",
            url="https://example.com/advisory/rec-eval-03",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="pydantic",
                version="2.10.0",
                file="pyproject.toml",
                line=15,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-04",
            text="Vulnerability in actions/checkout@v4.1.0 allows environment manipulation",
            url="https://example.com/advisory/rec-eval-04",
            component=Component(
                kind=ComponentKind.ACTION,
                ecosystem=Ecosystem.GITHUB_ACTIONS,
                name="actions/checkout",
                version="v4.1.0",
                file=".github/workflows/ci.yml",
                line=12,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-05",
            text="Docker base image debian:trixie-slim contains critical openssl flaw",
            url="https://example.com/advisory/rec-eval-05",
            component=Component(
                kind=ComponentKind.CONTAINER_IMAGE,
                ecosystem=Ecosystem.DOCKER,
                name="debian",
                version="trixie-slim",
                file="Dockerfile",
                line=1,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-06",
            text="CVE-2026-2006 prototype pollution in lodash 4.17.21 used by dashboard build",
            url="https://example.com/advisory/rec-eval-06",
            component=Component(
                kind=ComponentKind.NODE_PACKAGE,
                ecosystem=Ecosystem.NPM,
                name="lodash",
                version="4.17.21",
                file="package.json",
                line=18,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-07",
            text="Helm chart ingress-nginx 4.11.0 ingress validation bypass",
            url="https://example.com/advisory/rec-eval-07",
            component=Component(
                kind=ComponentKind.CHART,
                ecosystem=Ecosystem.HELM,
                name="ingress-nginx",
                version="4.11.0",
                file="k8s/helmfile.yaml",
                line=30,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-08",
            text="Terraform aws provider 5.70.0 credential leakage vulnerability",
            url="https://example.com/advisory/rec-eval-08",
            component=Component(
                kind=ComponentKind.TERRAFORM_PROVIDER,
                ecosystem=Ecosystem.TERRAFORM,
                name="hashicorp/aws",
                version="5.70.0",
                file="terraform/main.tf",
                line=5,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-09",
            text="Ruff linter tool 0.9.0 command injection vulnerability in configuration parser",
            url="https://example.com/advisory/rec-eval-09",
            component=Component(
                kind=ComponentKind.TOOL,
                ecosystem=Ecosystem.UNKNOWN,
                name="ruff",
                version="0.9.0",
                file="pyproject.toml",
                line=85,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-10",
            text="Devcontainer feature ghcr.io/devcontainers/features/docker-in-docker:2 privileged escape",
            url="https://example.com/advisory/rec-eval-10",
            component=Component(
                kind=ComponentKind.DEVCONTAINER_FEATURE,
                ecosystem=Ecosystem.DEVCONTAINER_FEATURE,
                name="docker-in-docker",
                version="2",
                file=".devcontainer/devcontainer.json",
                line=14,
            ),
        ),
        label=JudgeVerdict.yes,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-11",
            text="Advisory affects fastapi version 0.80.0 only, pinned version is 0.115.0",
            url="https://example.com/advisory/rec-eval-11",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="fastapi",
                version="0.115.0",
                file="pyproject.toml",
                line=25,
            ),
        ),
        label=JudgeVerdict.no,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-12",
            text="Flaw in unpinned django framework component not present in project tree",
            url="https://example.com/advisory/rec-eval-12",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="django",
                version="5.0.0",
                file="pyproject.toml",
                line=0,
            ),
        ),
        label=JudgeVerdict.no,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-13",
            text="Security release notes for kubernetes 1.28.0; project cluster runs 1.32.0",
            url="https://example.com/advisory/rec-eval-13",
            component=Component(
                kind=ComponentKind.TOOL,
                ecosystem=Ecosystem.UNKNOWN,
                name="kubectl",
                version="1.32.0",
                file=".tool-versions",
                line=2,
            ),
        ),
        label=JudgeVerdict.no,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-14",
            text="Advisory for node-sass package which is not installed or pinned in this repo",
            url="https://example.com/advisory/rec-eval-14",
            component=Component(
                kind=ComponentKind.NODE_PACKAGE,
                ecosystem=Ecosystem.NPM,
                name="node-sass",
                version="9.0.0",
                file="package.json",
                line=0,
            ),
        ),
        label=JudgeVerdict.no,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-15",
            text="Advisory GHSA-xxxx applies strictly to Windows platform builds, project runs on Linux",
            url="https://example.com/advisory/rec-eval-15",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="pywin32",
                version="306",
                file="pyproject.toml",
                line=0,
            ),
        ),
        label=JudgeVerdict.no,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-16",
            text="Documentation typo fix announcement for requests library with no security impact",
            url="https://example.com/advisory/rec-eval-16",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="requests",
                version="2.32.3",
                file="pyproject.toml",
                line=55,
            ),
        ),
        label=JudgeVerdict.no,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-17",
            text="Unconfirmed report of potential race condition in anyio with insufficient reproduction data",
            url="https://example.com/advisory/rec-eval-17",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="anyio",
                version="4.6.0",
                file="pyproject.toml",
                line=32,
            ),
        ),
        label=JudgeVerdict.unknown,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-18",
            text="Disputed CVE against python urllib3 with conflicting vendor assessments",
            url="https://example.com/advisory/rec-eval-18",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="urllib3",
                version="2.2.3",
                file="pyproject.toml",
                line=60,
            ),
        ),
        label=JudgeVerdict.unknown,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-19",
            text="Notice of upcoming deprecation for click 8.x argument parser flags without exploit details",
            url="https://example.com/advisory/rec-eval-19",
            component=Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="click",
                version="8.1.7",
                file="pyproject.toml",
                line=12,
            ),
        ),
        label=JudgeVerdict.unknown,
    ),
    LabeledJudgment(
        record=EvalRecord(
            id="rec-eval-20",
            text="Third-party benchmark claim regarding valkey latency anomalies with incomplete environment spec",
            url="https://example.com/advisory/rec-eval-20",
            component=Component(
                kind=ComponentKind.CONTAINER_IMAGE,
                ecosystem=Ecosystem.DOCKER,
                name="valkey/valkey",
                version="8.0.0",
                file="k8s/valkey.yaml",
                line=18,
            ),
        ),
        label=JudgeVerdict.unknown,
    ),
)


def false_negative_ids(
    labeled: Sequence[LabeledJudgment],
    judged: Sequence[JudgeFinding] | JudgeReport,
) -> list[str]:
    """Return record ids where true label is 'yes' but judge returned 'no'."""
    findings = judged.findings if isinstance(judged, JudgeReport) else list(judged)
    finding_by_id: dict[str, JudgeFinding] = {}
    for f in findings:
        for rec_id in f.evidence_record_ids:
            finding_by_id[rec_id] = f

    fn: list[str] = []
    for idx, item in enumerate(labeled):
        rec_id = _record_id(item.record)
        finding = finding_by_id.get(rec_id)
        if finding is None and idx < len(findings):
            finding = findings[idx]
        if item.label == JudgeVerdict.yes and finding is not None:
            if finding.affects_us == JudgeVerdict.no:
                fn.append(rec_id)
    return fn


def judge_agreement_rate(
    labeled: Sequence[LabeledJudgment],
    judged: Sequence[JudgeFinding] | JudgeReport,
) -> float:
    """Calculate agreement rate between labeled records and judge findings."""
    if not labeled:
        return 1.0
    findings = judged.findings if isinstance(judged, JudgeReport) else list(judged)
    finding_by_id: dict[str, JudgeFinding] = {}
    for f in findings:
        for rec_id in f.evidence_record_ids:
            finding_by_id[rec_id] = f

    agree = 0
    for idx, item in enumerate(labeled):
        rec_id = _record_id(item.record)
        finding = finding_by_id.get(rec_id)
        if finding is None and idx < len(findings):
            finding = findings[idx]
        if finding is not None and finding.affects_us == item.label:
            agree += 1

    return agree / len(labeled)
