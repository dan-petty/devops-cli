"""The sweep: files one intake candidate for each actionable finding that no issue carries (#3899).

The sweep takes the advisories of the pins (`find_advisories`), and no model decides what a
finding is. A finding is actionable when its severity is critical or high: OSV matched the
pinned version to the affected ranges, so each finding affects its pin. An actionable finding
that no issue carries goes to roadmap intake as one candidate, which ends with the marker
`research-finding: <source id>`. One issue search reads the markers that issues carry, so a second
sweep files nothing again. Intake keeps its duplicate flag: the sweep never drops a candidate and
never closes an issue.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Final

from devops_cli.config.constants import (
    CONST_RESEARCH_FINDING_MARKER,
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_ORDER,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.security import SecurityError
from devops_cli.github.client import GitHubClient
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.research.advisories import advisory_requests
from devops_cli.research.models import (
    AdvisoryFinding,
    AdvisoryReport,
    Inventory,
    SweepEntry,
    SweepReport,
    SweepResult,
)
from devops_cli.roadmap.intake.intake import (
    CandidateOutcome,
    Filer,
    NewCandidate,
    Outcome,
    dry_run_intake,
    intake_candidate,
)
from devops_cli.roadmap.intake.intake_model import IntakeModel
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length
from devops_cli.roadmap.request_plan import planned_session_read
from devops_cli.roadmap.stores.store import RoadmapStore
from devops_cli.telemetry.instruments import RESEARCH_OPEN_FINDINGS, bounded_label, emit

# The severities that file a candidate. OSV writes them in upper case.
ACTIONABLE_SEVERITIES: Final[frozenset[str]] = frozenset(
    {CONST_SEVERITY_CRITICAL, CONST_SEVERITY_HIGH}
)
_MARKER = re.compile(rf"<!-- {re.escape(CONST_RESEARCH_FINDING_MARKER)}: (\S+) -->")
_OSV_URL: Final[str] = "https://osv.dev/vulnerability/{id}"


def source_id(finding: AdvisoryFinding) -> str:
    """The id of a finding, which its marker carries: the ecosystem, the package at its pinned
    version, and the advisory. A new pin of the same package, or another advisory, is a new
    finding."""
    component = finding.component
    return f"{component.ecosystem.value}:{component.name}@{component.version}:{finding.advisory_id}"


def finding_marker(finding: AdvisoryFinding) -> str:
    """The marker line that the issue filed from a finding carries. An HTML comment: GitHub does
    not show it, and the issue search finds the text in it."""
    return f"<!-- {CONST_RESEARCH_FINDING_MARKER}: {source_id(finding)} -->"


def carried_source_ids(body: str) -> frozenset[str]:
    """The source id of every finding marker in an issue body."""
    return frozenset(_MARKER.findall(body))


def is_actionable(finding: AdvisoryFinding) -> bool:
    """Whether the finding files a candidate."""
    return finding.severity.upper() in ACTIONABLE_SEVERITIES


def _title(finding: AdvisoryFinding) -> str:
    """`fix(deps): update <package> for <advisory>`. A summary over the limit of a title names the
    ecosystem in place of the package: the body holds the package."""
    named = f"update {finding.component.name} for {finding.advisory_id}"
    if summary_length(named) > SUMMARY_MAX_CHARS:
        named = f"update {finding.component.ecosystem.value} package for {finding.advisory_id}"
    return f"fix(deps): {named}"


def finding_candidate(finding: AdvisoryFinding) -> NewCandidate:
    """The intake candidate of an actionable finding.

    The body is built from the public fields of the advisory: ids, the OSV URL of each id, the
    package and its pinned version, the affected range and the fixed version. It holds no path
    of the inventory, so no host name or address of the repository reaches a public issue.
    """
    texts = MESSAGES.research
    component = finding.component
    ids = [finding.advisory_id, *finding.aliases]
    fixed = finding.fixed_version or texts.sweep_no_fix
    lines = [
        texts.sweep_body_problem,
        "",
        texts.sweep_body_affected.format(
            name=component.name,
            version=component.version,
            ecosystem=component.ecosystem.value,
            severity=finding.severity,
            advisory=finding.advisory_id,
        ),
        "",
        finding.summary,
        "",
        texts.sweep_body_expected.format(fixed=fixed),
        "",
        texts.sweep_body_advisories,
        *(f"- {advisory}: {_OSV_URL.format(id=advisory)}" for advisory in ids),
        f"- {texts.sweep_body_range}: {finding.affected_range}",
        "",
        finding_marker(finding),
    ]
    return NewCandidate(title=_title(finding), body="\n".join(lines), filed_by=Filer.AGENT)


def _search_request(repo: str) -> PlannedRequest:
    """The first page of the search that reads the markers, as a dry run lists it."""
    from urllib.parse import urlencode

    from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE

    query = f'"{CONST_RESEARCH_FINDING_MARKER}" in:body is:issue repo:{repo}'
    page = {"q": query, "per_page": DEFAULT_GH_REST_PER_PAGE, "page": 1}
    texts = MESSAGES.research
    return planned_session_read(
        f"/search/issues?{urlencode(page)}",
        texts.sweep_search_target,
        repeat=texts.sweep_search_repeat,
    )


def sweep_dry_run(inventory: Inventory, repo: str) -> SweepReport:
    """What a real sweep of `inventory` requests, listed in order. It makes no request.

    The findings come from OSV, so the requests of intake are those for one placeholder candidate:
    a real run makes them for each actionable finding.
    """
    placeholder = NewCandidate(title=MESSAGES.research.sweep_placeholder_title, body="")
    intake = dry_run_intake(repo, new=placeholder)
    planned = [
        *advisory_requests(inventory),
        _search_request(repo),
        *intake.requests,
        *intake.writes,
    ]
    return SweepReport(dry_run=True, requests=[request.line() for request in planned])


def open_findings(findings: Sequence[AdvisoryFinding]) -> dict[str, int]:
    """The findings by severity. Each severity of the scale is a key, with zero when it has no
    finding, so the gauge of a severity that is clean goes back to zero."""
    counted = Counter(finding.severity.upper() for finding in findings)
    scale = {severity: counted.pop(severity, 0) for severity in CONST_SEVERITY_ORDER}
    return {**scale, **dict(sorted(counted.items()))}


def _entry(
    finding: AdvisoryFinding,
    result: SweepResult,
    *,
    issue: int | None = None,
    possible_duplicate: int | None = None,
    reason: str = "",
) -> SweepEntry:
    return SweepEntry(
        source_id=source_id(finding),
        advisory_id=finding.advisory_id,
        name=finding.component.name,
        version=finding.component.version,
        severity=finding.severity,
        result=result,
        issue=issue,
        possible_duplicate=possible_duplicate,
        reason=reason,
    )


def _carriers(repo: str, client: GitHubClient | None) -> dict[str, int]:
    """The lowest issue number that carries each source id, from one issue search over the issues
    of `repo`, open and closed."""
    session_client = client or get_github_session().client
    numbers: defaultdict[str, list[int]] = defaultdict(list)
    for issue in session_client.search_issue_bodies(repo, CONST_RESEARCH_FINDING_MARKER):
        for carried in carried_source_ids(issue.body or ""):
            numbers[carried].append(issue.number)
    return {carried: min(held) for carried, held in numbers.items()}


def _outcome_entry(finding: AdvisoryFinding, outcome: CandidateOutcome) -> SweepEntry:
    decision = outcome.decision
    if decision.outcome is Outcome.SKIP:
        return _entry(
            finding,
            SweepResult.SKIPPED,
            possible_duplicate=decision.possible_duplicate,
            reason=decision.reason,
        )
    result = SweepResult.FILED if outcome.number is not None else SweepResult.PLANNED
    return _entry(
        finding,
        result,
        issue=outcome.number,
        possible_duplicate=decision.possible_duplicate,
    )


def run_sweep(
    report: AdvisoryReport,
    *,
    repo: str,
    store: RoadmapStore,
    model: IntakeModel,
    confirm: bool,
    client: GitHubClient | None = None,
) -> SweepReport:
    """Sweep the findings of `report`: file each actionable finding that no issue carries.

    A candidate whose text looks like a secret raises `SecurityError` before any request. Intake
    files and places each candidate with `confirm`, and only decides it without. Intake's
    duplicate flag stays on: the entry keeps `possible_duplicate`, and nothing is closed. A write
    that fails stops the sweep, and each issue filed before it carries its marker, so the next
    sweep leaves that finding out.
    """
    candidates = {
        source_id(finding): finding_candidate(finding)
        for finding in report.findings
        if is_actionable(finding)
    }
    for finding in report.findings:
        if is_actionable(finding):
            try:
                candidates[source_id(finding)].refuse_secrets()
            except SecurityError as exc:
                message = MESSAGES.research.sweep_secret.format(advisory=finding.advisory_id)
                raise SecurityError(message) from exc
    carriers = _carriers(repo, client) if candidates else {}
    entries: list[SweepEntry] = []
    seen: set[str] = set()
    for finding in report.findings:
        identity = source_id(finding)
        if identity in seen:
            continue
        seen.add(identity)
        if identity not in candidates:
            entries.append(_entry(finding, SweepResult.NOT_ACTIONABLE))
        elif identity in carriers:
            entries.append(_entry(finding, SweepResult.FILED_BEFORE, issue=carriers[identity]))
        else:
            outcome = intake_candidate(
                store, candidates[identity], repo=repo, model=model, confirm=confirm
            )
            entries.append(_outcome_entry(finding, outcome))
    return SweepReport(
        entries=entries,
        open_findings=open_findings(report.findings),
        failed=len(report.failures),
    )


def record_open_findings(report: SweepReport) -> None:
    """Set the gauge of open findings, one value for each severity."""
    for severity, count in report.open_findings.items():
        emit(RESEARCH_OPEN_FINDINGS, count, {"severity": bounded_label(severity.lower())})


def digest_lines(report: SweepReport) -> list[str]:
    """The digest of a sweep: one line for each finding with its result, then a summary."""
    texts = MESSAGES.research
    if not report.entries:
        return [texts.sweep_none]
    templates = {
        SweepResult.FILED: texts.sweep_filed,
        SweepResult.PLANNED: texts.sweep_planned,
        SweepResult.FILED_BEFORE: texts.sweep_filed_before,
        SweepResult.NOT_ACTIONABLE: texts.sweep_not_actionable,
        SweepResult.SKIPPED: texts.sweep_skipped,
    }
    lines: list[str] = []
    for entry in report.entries:
        line = templates[entry.result].format(
            severity=entry.severity,
            name=entry.name,
            version=entry.version,
            advisory=entry.advisory_id,
            number=entry.issue,
            reason=entry.reason,
        )
        if entry.possible_duplicate is not None:
            line += " " + texts.sweep_possible_duplicate.format(number=entry.possible_duplicate)
        lines.append(line)
    counted = Counter(entry.result for entry in report.entries)
    severities = ", ".join(
        f"{severity.lower()} {count}" for severity, count in report.open_findings.items()
    )
    lines.append(
        texts.sweep_summary.format(
            filed=counted[SweepResult.FILED],
            planned=counted[SweepResult.PLANNED],
            before=counted[SweepResult.FILED_BEFORE],
            other=counted[SweepResult.NOT_ACTIONABLE] + counted[SweepResult.SKIPPED],
            severities=severities,
        )
    )
    return lines
