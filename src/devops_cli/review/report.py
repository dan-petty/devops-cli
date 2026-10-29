"""The review report: review.md and the terminal view of one review session (#1008).

The report is a function of one `ReportInput`. It reads no review orchestrator and opens no
file: `ReviewPipelineOrchestrator.generate_consolidated_report` collects, deduplicates and
persists the session, reads the review history and the knowledge-base drift the report shows,
builds the input once, and calls `render_markdown` and `render_console`.

The executive summary's headline names what a verdict confirmed (#948). It used to name the
themes of the first-sorted findings, where a theme was a finding's first reference or its title,
so a hallucinated CVE on an UNVERIFIED finding headlined session `20261001-224227`, and its
counts mixed every status.
"""

from __future__ import annotations

import collections
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.ai.review.category_metrics import (
    format_category_baseline_markdown,
    resolve_finding_category,
)
from devops_cli.ai.review.sanitization import balance_markdown_fences, escape_markdown_title
from devops_cli.ai.review.tool_runs import tool_runs_section
from devops_cli.ai.review_schema import (
    DefectClass,
    Finding,
    SavedFinding,
    compute_verdict_distributions,
    format_clean_text_field,
    is_field_discriminating,
    strip_outer_markdown_bold,
)
from devops_cli.config.constants import (
    CONST_DEPENDENCY_SEVERITY_CLEAN,
    CONST_DEPENDENCY_VULNERABLE_SEVERITIES,
    CONST_REVIEW_CONSOLE_PANEL_SEVERITIES,
    CONST_REVIEW_CONSOLE_TABLE_SEVERITIES,
    CONST_REVIEW_STATUS_ORDER,
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_INFO,
    CONST_SEVERITY_ORDER,
    CONST_STATUS_MITIGATED,
    CONST_STATUS_UNVERIFIED,
    CONST_STATUS_VERIFIED,
)
from devops_cli.config.defaults import DEFAULT_REVIEW_HEADLINE_THEMES
from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output import (
    escape_text,
    get_console,
    print_info,
    print_panel,
    print_success,
    print_table,
)
from devops_cli.review.analysis import render_model_analysis_markdown
from devops_cli.security.reference_extractor import (
    deduplicate_network_references,
    is_example_or_invalid_network_target,
    sort_network_references,
)

if TYPE_CHECKING:
    from devops_cli.ai.kb import DriftManual
    from devops_cli.ai.review.history import ReviewHistory
    from devops_cli.output import Console
    from devops_cli.review.analysis import AnalysisReport
    from devops_cli.security.tool_executor import ToolRun


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportInput:
    """Everything the report of one review session shows, collected before it renders."""

    session_id: str
    session_name: str
    generated_at: str
    report_path: Path
    findings_path: Path
    reportable_findings: Sequence[SavedFinding]
    # The consolidated findings and the raised candidates; the report's pools fall back from
    # the candidates to these to the reportable findings, as they are given.
    all_findings: Sequence[SavedFinding] | None = None
    candidate_findings: Sequence[SavedFinding] | None = None
    dependencies: Sequence[DependencySpec] = ()
    network_references: Sequence[NetworkReference] = ()
    symbol_delta: Mapping[str, int] | None = None
    files_reviewed: int = 0
    errored_files: Mapping[str, str] = field(default_factory=dict)
    partial_context: bool = False
    full_output: bool = False
    # The executive summary's analyzer line, computed from the scan's analyzer states.
    analyzer_line: str | None = None
    static_analyzers: Mapping[str, str] = field(default_factory=dict)
    static_analyzer_notes: Mapping[str, str] = field(default_factory=dict)
    coverage: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    tool_runs: Sequence[ToolRun] = ()
    admitted_scanner_findings: Sequence[Any] = ()
    complexity_deltas: Sequence[Mapping[str, Any]] = ()
    analysis_report: AnalysisReport | None = None
    # The knowledge-base drift the report lists when no group analysis ran.
    reference_drift: Sequence[DriftManual] = ()
    # The review history the category baseline compares with; None renders no baseline.
    history: ReviewHistory | None = None


# ── Severities ────────────────────────────────────────────────────────────────

_SEVERITY_LABELS: dict[str, str] = {
    "CRITICAL": "Critical",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
    "INFO": "Informational",
}
_CONSOLE_SEVERITY_COUNT_STYLES: dict[str, str] = {
    "CRITICAL": "[bold red]{cnt} Critical[/bold red]",
    "HIGH": "[red]{cnt} High[/red]",
    "MEDIUM": "[yellow]{cnt} Medium[/yellow]",
    "LOW": "[cyan]{cnt} Low[/cyan]",
    "INFO": "[green]{cnt} Info[/green]",
}


def _severity(finding: SavedFinding) -> str:
    """A finding's severity, INFO when it has none."""
    return (finding.severity or CONST_SEVERITY_INFO).upper()


def _severity_rank(finding: SavedFinding) -> int:
    severity = _severity(finding)
    return CONST_SEVERITY_ORDER.index(severity) if severity in CONST_SEVERITY_ORDER else 99


def _severity_counts(findings: Iterable[SavedFinding]) -> Counter[str]:
    """How many findings have each severity: the one count of the summary and the terminal."""
    return Counter(_severity(f) for f in findings)


def _severity_breakdown(findings: Sequence[SavedFinding]) -> str:
    counts = _severity_counts(findings)
    return ", ".join(
        f"{counts[severity]} {_SEVERITY_LABELS[severity]}"
        for severity in CONST_SEVERITY_ORDER
        if counts[severity]
    )


# ── Executive summary ─────────────────────────────────────────────────────────

# How the headline counts each group: VERIFIED and UNVERIFIED together, the MITIGATED ones
# listed apart.
_COUNTED_GROUPS: tuple[tuple[str, str], ...] = (
    (CONST_STATUS_VERIFIED, "verified"),
    (CONST_STATUS_UNVERIFIED, "unverified"),
)
_APART_GROUPS: tuple[tuple[str, str], ...] = ((CONST_STATUS_MITIGATED, "mitigated"),)


def _join(parts: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c`."""
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _group_counts(
    groups: dict[str, list[SavedFinding]], labels: tuple[tuple[str, str], ...]
) -> list[str]:
    return [
        f"{len(groups[key])} {label} ({_severity_breakdown(groups[key])})"
        for key, label in labels
        if groups.get(key)
    ]


def _status_counts(findings: Sequence[SavedFinding]) -> tuple[list[str], list[str]]:
    """The findings counted by status, each status with its severities: VERIFIED and
    UNVERIFIED, then, listed apart, the MITIGATED ones, which counted together were reported as
    defects.
    """
    groups: dict[str, list[SavedFinding]] = collections.defaultdict(list)
    for finding in findings:
        groups[finding.status].append(finding)
    return _group_counts(groups, _COUNTED_GROUPS), _group_counts(groups, _APART_GROUPS)


def _format_status_counts(findings: Sequence[SavedFinding]) -> str:
    """The report's sentences counting the findings by status (`_status_counts`)."""
    counted, apart = _status_counts(findings)
    sentences = [f"{_join(counted)}."] if counted else []
    if apart:
        sentences.append(f"Listed apart: {_join(apart)}.")
    return " ".join(sentences)


def _status_summary_lines(findings: Sequence[SavedFinding]) -> list[str]:
    """The report summary's line counting its findings by status; none for no findings."""
    counts = _format_status_counts(findings)
    return [f"By status: {counts}"] if counts else []


def _reported(findings: Sequence[SavedFinding]) -> str:
    """How many findings the review reported, and their counts by status."""
    counts = _format_status_counts(findings)
    return f"**{len(findings)} reportable finding(s)**" + (f": {counts}" if counts else ".")


def _verified_themes(
    findings: Sequence[SavedFinding],
) -> list[tuple[DefectClass, list[SavedFinding]]]:
    """The defect classes that recur among VERIFIED findings, most severe first, then the most
    frequent. A class seen once is no theme, and neither is `other`."""
    groups: dict[DefectClass, list[SavedFinding]] = collections.defaultdict(list)
    for finding in findings:
        if finding.status == CONST_STATUS_VERIFIED:
            groups[DefectClass(resolve_finding_category(finding))].append(finding)
    recurring = [
        (cls, members)
        for cls, members in groups.items()
        if len(members) > 1 and cls is not DefectClass.OTHER
    ]
    return sorted(
        recurring,
        key=lambda item: (min(map(_severity_rank, item[1])), -len(item[1]), item[0].value),
    )


def _remediation_statement(findings: Sequence[SavedFinding]) -> str:
    """What the verified findings call for, and the classes they recur in."""
    verified = [f for f in findings if f.status == CONST_STATUS_VERIFIED]
    if not verified:
        return "No finding was verified."
    themes = [cls.label for cls, _ in _verified_themes(findings)]
    severe = any(_severity(f) in (CONST_SEVERITY_CRITICAL, CONST_SEVERITY_HIGH) for f in verified)
    prefix = "High-priority remediation" if severe else "Remediation"
    return f"{prefix} is recommended for the verified findings{_recurring(themes)}."


def _recurring(themes: Sequence[str]) -> str:
    """The clause naming the classes verified findings recur in, the first few by name."""
    named = list(themes[:DEFAULT_REVIEW_HEADLINE_THEMES])
    if len(themes) > len(named):
        named.append(f"{len(themes) - len(named)} more listed under Key Bad Patterns")
    return f", which recur in {_join(named)}" if named else ""


def _good_patterns(
    all_deps: Sequence[DependencySpec], all_nets: Sequence[NetworkReference]
) -> list[str]:
    """Key positive patterns supported by concrete tool outputs."""
    patterns: list[str] = []

    if all_deps:
        queried_deps = [
            d
            for d in all_deps
            if getattr(d, "queried", False) or (d.severity or "").upper() == "CLEAN"
        ]
        if queried_deps and not any(
            (d.severity or "").upper() in ("CRITICAL", "HIGH") for d in queried_deps
        ):
            patterns.append(
                f"**Supply Chain & Lockfile Integrity**: {len(queried_deps)} external "
                "dependencies queried against vulnerability databases with zero critical/high CVEs."
            )

    if all_nets:
        local_count = sum(1 for n in all_nets if n.is_local)
        ext_count = len(all_nets) - local_count
        patterns.append(
            f"**Network Reference Review**: {len(all_nets)} network reference(s) identified "
            f"({local_count} local, {ext_count} external)."
        )

    return patterns


def _bad_patterns(reportable_findings: Sequence[SavedFinding]) -> list[str]:
    """The defect classes that recur among VERIFIED findings, one line each."""
    themes = _verified_themes(reportable_findings)
    if not themes:
        return [
            "No critical anti-patterns or recurring defect patterns identified among the "
            "verified findings."
        ]
    return [
        f"**{cls.label}**: {len(members)} verified finding(s) identified (highest severity: "
        f"{_severity(min(members, key=_severity_rank))}), "
        f"for example at `{members[0].location.strip('`')}`."
        for cls, members in themes
    ]


def _executive_summary(report: ReportInput) -> list[str]:
    """The Executive Summary section at the top of the review report."""
    findings = report.reportable_findings
    if report.errored_files:
        summary_stmt = (
            f"The automated review encountered errors on **{len(report.errored_files)} file(s)**: "
            f"a stage could not read or build them, and the table of skipped and errored files "
            f"gives each stage and reason. "
            f"Review could not be completed for those files. "
            f"Across successfully analyzed files it reported {_reported(findings)}"
        )
    elif not findings:
        summary_stmt = (
            "The automated review evaluated the target scope with "
            "**0 reportable defects** across successfully analyzed files."
        )
    else:
        summary_stmt = (
            f"The automated review reported {_reported(findings)} "
            f"{_remediation_statement(findings)}"
        )

    lines = ["## Executive Summary", summary_stmt]
    if report.analyzer_line:
        lines.extend(["", report.analyzer_line])

    good_patterns = _good_patterns(report.dependencies, report.network_references)
    if good_patterns:
        lines.append("")
        lines.append("### Key Good Patterns Observed")
        lines.extend(f"- {pattern}" for pattern in good_patterns)

    lines.append("")
    lines.append("### Key Bad Patterns Observed")
    lines.extend(f"- {pattern}" for pattern in _bad_patterns(findings))

    lines.append("")
    return lines


# ── review.md ─────────────────────────────────────────────────────────────────

# The review.md sections the terminal points at for what it only summarizes (#987).
_REPORT_DEPENDENCIES_SECTION = "External Dependencies"
_REPORT_NETWORK_SECTION = "Network References & Endpoints"


def format_markdown_fix(fix: str) -> str:
    """Format fix recommendation safely into Markdown without unbalancing code fences."""
    clean_fix = strip_outer_markdown_bold(fix.strip())
    if not clean_fix:
        return ""

    balanced_fix, has_fences = balance_markdown_fences(clean_fix)
    if has_fences:
        return f"- **Fix Recommendation**:\n\n{balanced_fix}"

    max_backticks = max((len(m) for m in re.findall(r"`+", clean_fix)), default=0)
    fence = "`" * max(3, max_backticks + 1)
    return f"- **Fix Recommendation**:\n{fence}\n{clean_fix}\n{fence}"


def _format_markdown_description(description: str) -> str:
    """Format finding description into indented Markdown list item preserving paragraphs."""
    clean_desc = strip_outer_markdown_bold(description.strip())
    if not clean_desc:
        return ""
    balanced_desc, _ = balance_markdown_fences(clean_desc)
    lines = balanced_desc.splitlines()
    if len(lines) <= 1:
        return f"- **Description**: {balanced_desc}"
    indented = (
        lines[0] + "\n" + "\n".join(f"  {line}" if line.strip() else "" for line in lines[1:])
    )
    return f"- **Description**: {indented}"


def _findings_table(reportable_findings: Sequence[SavedFinding]) -> list[str]:
    """Summary table of reportable findings."""
    if not reportable_findings:
        return ["✅ **No critical issues found during review.**"]

    lines = [
        "| Severity | Location | Title | Status | Producer |",
        "|---|---|---|---|---|",
    ]
    for f in reportable_findings:
        clean_sev = (f.severity or "INFORMATIONAL").replace("|", "\\|").replace("\n", " ").strip()
        clean_loc = f.location.strip("`").replace("|", "\\|").replace("\n", " ").strip()
        clean_title = escape_markdown_title(f.title, is_table=True)
        clean_status = f.status.replace("|", "\\|").replace("\n", " ").strip()
        clean_producer = f.producer.replace("|", "\\|").replace("\n", " ").strip()
        lines.append(
            f"| **{clean_sev}** | `{clean_loc}` | {clean_title} | {clean_status} | {clean_producer} |"
        )
    return lines


def _detailed_findings_section(reportable_findings: Sequence[SavedFinding]) -> list[str]:
    """Detailed findings section with balanced code blocks and clean formatting."""
    if not reportable_findings:
        return []

    lines = ["", "## Detailed Findings"]
    for idx, f in enumerate(reportable_findings, 1):
        clean_title = escape_markdown_title(f.title, is_table=False)
        clean_loc = f.location.strip("`").strip()
        lines.append(f"### {idx}. [{(f.severity or 'INFORMATIONAL').upper()}] {clean_title}")
        lines.append(f"- **Location**: `{clean_loc}`")
        lines.append(f"- **Producer**: {f.producer}")
        lines.append(f"- **Status**: {f.status}")
        if f.status == "MITIGATED" and f.invalidation_reason:
            lines.append(f"- **Mitigation**: {f.invalidation_reason.strip()}")
        desc_line = _format_markdown_description(f.description)
        if desc_line:
            lines.append(desc_line)
        if f.fix:
            fix_md = format_markdown_fix(f.fix)
            if fix_md:
                lines.append(fix_md)
        lines.append("")
    return lines


def _reported_network_references(
    references: Sequence[NetworkReference],
) -> list[NetworkReference]:
    """The network references the report lists: no examples, each once, in report order."""
    filtered = [
        n
        for n in references
        if not getattr(n, "is_example", False)
        and not is_example_or_invalid_network_target(getattr(n, "target", ""))
    ]
    return sort_network_references(deduplicate_network_references(filtered))


def _dependencies_table(all_deps: Sequence[DependencySpec]) -> list[str]:
    """External dependencies audit table."""
    lines = [f"## {_REPORT_DEPENDENCIES_SECTION} (OSV.dev)"]
    if not all_deps:
        lines.extend(["✅ **No external dependencies declared in review scope.**", ""])
        return lines

    lines.extend(
        [
            "| Severity | Dependency | Version Range | Ecosystem | Security Status | Location |",
            "|---|---|---|---|---|---|",
        ]
    )
    for dep in all_deps:
        sev_upper = (dep.severity or "").upper()
        if sev_upper in ("UNCHECKED", "NOT_QUERIED", "NOT QUERIED"):
            sev_badge = "UNCHECKED"
        elif sev_upper not in ("CLEAN", "NONE", "INFO"):
            sev_badge = f"**{dep.severity}**"
        else:
            sev_badge = dep.severity
        loc_str = f"`{dep.location}`" if dep.location else "—"
        lines.append(
            f"| {sev_badge} | `{dep.name}` | `{dep.version_range}` | {dep.ecosystem} | "
            f"{dep.security_status} | {loc_str} |"
        )
    lines.append("")
    return lines


def _network_table(all_nets: Sequence[NetworkReference]) -> list[str]:
    """Network endpoints and references audit table."""
    sorted_md_nets = _reported_network_references(all_nets)

    lines = [f"## {_REPORT_NETWORK_SECTION} (Shodan InternetDB & Cloudflare Radar)"]
    if not sorted_md_nets:
        lines.extend(
            [
                "✅ **No network endpoints or remote addresses referenced in review scope.**",
                "",
            ]
        )
        return lines

    lines.extend(
        [
            "| Target | Type | Scope | Security Status | Location |",
            "|---|---|---|---|---|",
        ]
    )
    for net in sorted_md_nets:
        scope_str = "Local" if net.is_local else "External"
        loc_str = f"`{net.location}`" if net.location else "—"
        lines.append(
            f"| `{net.target}` | {net.reference_type} | {scope_str} | "
            f"{net.security_status} | {loc_str} |"
        )
    lines.append("")
    return lines


def _category_baseline_section(
    all_findings: Sequence[SavedFinding] | None,
    reportable_findings: Sequence[SavedFinding],
    history: ReviewHistory | None,
) -> list[str]:
    """The category false-positive baseline, over the history given; none without one."""
    findings_to_use = all_findings if all_findings is not None else reportable_findings
    if not findings_to_use or history is None:
        return []
    return format_category_baseline_markdown(findings_to_use, history)


def verdict_distributions_section(
    candidate_findings: Sequence[Finding | SavedFinding] | None,
) -> list[str]:
    """The Markdown table of verdict field distributions and whether each discriminates."""
    if not candidate_findings:
        return []
    dists = compute_verdict_distributions(candidate_findings)
    lines = [
        "## Verdict Field Distributions",
        "",
        "| Verdict Field | Distribution | Discriminates? |",
        "|---|---|---|",
    ]
    field_order = [
        ("status", "Status"),
        ("reportable", "Reportable"),
        ("verified", "Verified"),
        ("mitigated", "Mitigated"),
    ]
    for key, label in field_order:
        counts = dists.get(key, {})
        dist_str = ", ".join(f"`{k}`: {v}" for k, v in sorted(counts.items()) if v > 0) or "None"
        discriminates = "Yes" if is_field_discriminating(counts) else "**No (never discriminates)**"
        lines.append(f"| `{label}` | {dist_str} | {discriminates} |")
    lines.append("")
    return lines


def static_analyzers_section(analyzers: Mapping[str, str], notes: Mapping[str, str]) -> list[str]:
    """Which static analyzers ran, so a scan with no findings is not read as clean."""
    if not analyzers:
        return []
    rows = []
    for name, state in analyzers.items():
        reason = notes.get(name)
        result = f"{state}: {reason}" if reason else state
        cell = " ".join(result.split()).replace("|", "\\|")
        rows.append(f"| {name} | {cell} |")
    return ["## Static Analyzers", "| Analyzer | Result |", "|---|---|", *rows, ""]


def coverage_section(coverage: Mapping[str, Mapping[str, str]]) -> list[str]:
    """The coverage matrix, one row per (tool, file)."""
    if not coverage:
        return []
    rows = [
        f"| {tool.replace('|', r'\|')} | `{fpath.replace('|', r'\|')}` | {status.replace('|', r'\|')} |"
        for tool in sorted(coverage)
        for fpath, status in sorted(coverage[tool].items())
    ]
    return ["## Coverage", "| Tool | File | Status |", "|---|---|---|", *rows, ""]


def _finding_rows(findings: Iterable[Any]) -> list[str]:
    return [
        f"| **{getattr(f, 'severity', 'MEDIUM')}** | `{getattr(f, 'location', '') or getattr(f, 'location_display', '') or getattr(f, 'path', '')}` | {escape_markdown_title(getattr(f, 'title', '') or getattr(f, 'message', ''), is_table=True)} |"
        for f in findings
    ]


def introduced_findings_section(findings: Sequence[Any]) -> list[str]:
    """The Introduced Findings section (#871)."""
    introduced = [
        f
        for f in findings
        if getattr(f, "introduced", True) and getattr(f, "state", "OPEN") != "SUPPRESSED"
    ]
    if not introduced:
        return []
    return [
        "## Introduced Findings",
        "| Severity | Location | Title |",
        "|---|---|---|",
        *_finding_rows(introduced),
        "",
    ]


def preexisting_findings_section(findings: Sequence[Any]) -> list[str]:
    """The Pre-existing Findings in Changed Files section (#871)."""
    preexisting = [
        f
        for f in findings
        if not getattr(f, "introduced", True) and getattr(f, "state", "OPEN") != "SUPPRESSED"
    ]
    if not preexisting:
        return []
    return [
        "## Pre-existing Findings in Changed Files",
        "| Severity | Location | Title |",
        "|---|---|---|",
        *_finding_rows(preexisting),
        "",
    ]


def _is_suppressed(finding: Any) -> bool:
    return getattr(finding, "state", "") == "SUPPRESSED" or getattr(
        finding, "suppressed_by_change", False
    )


def suppressed_findings_section(findings: Sequence[Any], admitted: Sequence[Any] = ()) -> list[str]:
    """The Suppressed Findings section: the suppressed admitted scanner findings, then the
    suppressed findings (#871)."""
    suppressed = [f for f in admitted if _is_suppressed(f)]
    suppressed.extend(f for f in findings if _is_suppressed(f))
    if not suppressed:
        return []
    rows: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for f in suppressed:
        # Admitted findings carry path and line apart; location_display joins them, so two
        # suppressions of one rule in one file stay two rows.
        loc = (
            getattr(f, "location_display", "")
            or getattr(f, "location", "")
            or getattr(f, "path", "")
        )
        key = (loc, getattr(f, "rule_id", ""), getattr(f, "title", ""))
        if key in seen:
            continue
        seen.add(key)
        sev = getattr(f, "severity", "MEDIUM")
        reason = getattr(f, "suppression_reason", "Inline marker") or "Inline marker"
        expiry = getattr(f, "suppression_expiry", None) or "None"
        by = (
            "suppressed by this change"
            if getattr(f, "suppressed_by_change", False)
            else "review.toml/base marker"
        )
        rows.append(f"| **{sev}** | `{loc}` | {reason} | {expiry} | {by} |")
    return [
        "## Suppressed Findings",
        "| Severity | Location | Reason | Expiry | Suppressed By |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ]


def _complexity_section(deltas: Sequence[Mapping[str, Any]]) -> list[str]:
    """The before/after Complexity table of the changed functions (#873)."""
    if not deltas:
        return []
    rows = [
        f"| `{d['file']}` | `{d['function']}` | {d['before'] if d['before'] is not None else '—'} | {d['after'] if d['after'] is not None else '—'} |"
        for d in deltas
    ]
    return [
        "## Complexity",
        "| File | Function | Before | After |",
        "|---|---|---|---|",
        *rows,
        "",
    ]


def _analysis_section(
    analysis_report: AnalysisReport | None, drift: Sequence[DriftManual]
) -> list[str]:
    """The group analysis, or, when none ran, the knowledge-base drift."""
    if analysis_report is not None:
        return render_model_analysis_markdown(analysis_report)
    if not drift:
        return []
    lines = ["## Reference coverage: drift", ""]
    lines.extend(f"- `{d.path}`: {d.reason}" for d in sorted(drift, key=lambda x: x.path))
    lines.append("")
    return lines


def _errored_files_section(errored_files: Mapping[str, str]) -> list[str]:
    if not errored_files:
        return []
    lines = ["## Skipped / Errored Files", "| File Path | Stage / Error Reason |", "|---|---|"]
    for fpath, reason in sorted(errored_files.items()):
        clean_f = fpath.replace("|", "\\|").replace("\n", " ").strip()
        clean_r = reason.replace("|", "\\|").replace("\n", " ").strip()
        lines.append(f"| `{clean_f}` | {clean_r} |")
    lines.append("")
    return lines


def _summary_section(report: ReportInput) -> list[str]:
    findings = report.reportable_findings
    lines = [
        "## Summary of Reportable Findings",
        f"Total Findings: **{len(findings)}**",
        *_status_summary_lines(findings),
    ]
    delta = report.symbol_delta
    if delta and any(delta.values()):
        lines.append(
            f"Symbol Delta: **+{delta.get('added', 0)}** / "
            f"**-{delta.get('removed', 0)}** / "
            f"**={delta.get('retained', 0)}**"
        )
    lines.append("")
    return lines


def render_markdown(report: ReportInput) -> str:
    """review.md of the session."""
    findings = report.reportable_findings
    lines = [
        f"# Code Review Report (Session `{report.session_id}`)",
        f"*Generated at: {report.generated_at}*",
    ]
    if report.partial_context:
        lines.append("*Context: partial context*")
    lines.append("")
    lines.extend(_executive_summary(report))
    lines.extend(_summary_section(report))
    lines.extend(_findings_table(findings))
    lines.extend(_detailed_findings_section(findings))
    lines.extend(introduced_findings_section(findings))
    lines.extend(preexisting_findings_section(findings))
    lines.extend(
        suppressed_findings_section(
            report.all_findings or findings, report.admitted_scanner_findings
        )
    )
    lines.extend(_complexity_section(report.complexity_deltas))
    lines.extend(_dependencies_table(report.dependencies))
    lines.extend(_network_table(report.network_references))
    lines.extend(static_analyzers_section(report.static_analyzers, report.static_analyzer_notes))
    lines.extend(coverage_section(report.coverage))
    lines.extend(tool_runs_section(report.tool_runs))
    # The session is not published, so it is not in the history it is compared to.
    lines.extend(
        _category_baseline_section(
            report.candidate_findings or report.all_findings, findings, report.history
        )
    )
    lines.extend(verdict_distributions_section(report.candidate_findings or report.all_findings))
    lines.extend(_analysis_section(report.analysis_report, report.reference_drift))
    lines.extend(_errored_files_section(report.errored_files))
    return "\n".join(lines)


# ── The terminal ──────────────────────────────────────────────────────────────

_CONSOLE_FINDING_COLUMNS: list[Any] = [
    ("#", "dim"),
    ("Severity", "center"),
    ("Location", "bold cyan"),
    "Title",
    ("Status", "center"),
    ("Producer", "dim"),
    ("Conf", "dim"),
]
_CONSOLE_SEVERITY_BADGES: dict[str, str] = {
    "CRITICAL": "[bold red]CRITICAL[/bold red]",
    "HIGH": "[red]HIGH[/red]",
    "MEDIUM": "[yellow]MEDIUM[/yellow]",
    "LOW": "[cyan]LOW[/cyan]",
    "INFO": "[green]INFO[/green]",
}
_CONSOLE_STATUS_BADGES: dict[str, str] = {
    "VERIFIED": "[green]VERIFIED[/green]",
    "FLAGGED": "[yellow]FLAGGED[/yellow]",
    "MITIGATED": "[cyan]MITIGATED[/cyan]",
    "INVALIDATED": "[red]INVALIDATED[/red]",
}
_CONSOLE_DEPENDENCY_COLUMNS: list[Any] = [
    ("Severity", "center"),
    ("Dependency", "bold cyan"),
    "Version Range",
    "Ecosystem",
    "Security Status",
    ("Location", "dim"),
]
_CONSOLE_NO_DEPENDENCIES_ROW = [
    "[green]CLEAN[/green]",
    "No external package dependencies declared in reviewed files",
    "—",
    "—",
    "[green]✓ Clean (0 dependencies)[/green]",
    "—",
]
_CONSOLE_NETWORK_COLUMNS: list[Any] = [
    ("Target", "bold cyan"),
    "Type",
    "Scope",
    "Security Status",
    ("Location", "dim"),
]
_CONSOLE_NO_NETWORK_ROW = [
    "No network endpoints or remote addresses referenced in reviewed files",
    "—",
    "—",
    "[green]✓ Clean (0 endpoints)[/green]",
    "—",
]
_DEP_SEV_STYLES: dict[str, tuple[str, str]] = {
    "CRITICAL": ("[bold red]CRITICAL[/bold red]", "[bold red]{status}[/bold red]"),
    "HIGH": ("[red]HIGH[/red]", "[red]{status}[/red]"),
    "MEDIUM": ("[yellow]MEDIUM[/yellow]", "[yellow]{status}[/yellow]"),
    "LOW": ("[cyan]LOW[/cyan]", "[cyan]{status}[/cyan]"),
    "CLEAN": ("[green]CLEAN[/green]", "[green]{status}[/green]"),
    "UNCHECKED": ("[dim]UNCHECKED[/dim]", "[dim]{status}[/dim]"),
    "NOT_QUERIED": ("[dim]NOT QUERIED[/dim]", "[dim]{status}[/dim]"),
}
_DEFAULT_DEP_SEV_STYLE: tuple[str, str] = ("[dim]UNCHECKED[/dim]", "[dim]{status}[/dim]")


def _finding_status_badge(status: str) -> str:
    """A color-styled badge for a finding's verification status."""
    st_upper = status.upper()
    if st_upper == "VERIFIED":
        return "[green]✓ VERIFIED[/green]"
    if st_upper == "MITIGATED":
        return "[cyan]~ MITIGATED[/cyan]"
    if st_upper == "INVALIDATED":
        return "[red]✗ INVALIDATED[/red]"
    return f"[yellow]? {status}[/yellow]"


def _dependency_row(d: DependencySpec) -> list[str]:
    """A dependency's table cells, its text escaped."""
    sev_str, status_template = _DEP_SEV_STYLES.get(d.severity.upper(), _DEFAULT_DEP_SEV_STYLE)
    status_str = status_template.format(status=escape_text(d.security_status))

    return [
        sev_str,
        escape_text(d.name),
        escape_text(d.version_range),
        escape_text(d.ecosystem),
        status_str,
        escape_text(d.location) or "—",
    ]


def _network_reference_row(n: NetworkReference) -> list[str]:
    """A network reference's table cells, its text escaped."""
    scope_str = "[dim]Local[/dim]" if n.is_local else "[bold cyan]External[/bold cyan]"
    if "⚠️" in n.security_status:
        color = "red"
    elif "UNCHECKED" in n.security_status.upper():
        color = "yellow"
    else:
        color = "cyan" if n.is_local else "green"
    return [
        escape_text(n.target),
        escape_text(n.reference_type),
        scope_str,
        f"[{color}]{escape_text(n.security_status)}[/{color}]",
        escape_text(n.location) or "—",
    ]


def _finding_row(finding_index: int, finding: SavedFinding) -> list[str]:
    """A finding's findings-table cells, its text escaped."""
    sev_upper = (finding.severity or "INFORMATIONAL").upper()
    confidence = finding.confidence_score
    return [
        str(finding_index),
        _CONSOLE_SEVERITY_BADGES.get(sev_upper, f"[white]{sev_upper}[/white]"),
        escape_text(finding.location),
        escape_text(finding.title.strip()),
        _CONSOLE_STATUS_BADGES.get(finding.status.upper(), f"[dim]{finding.status}[/dim]"),
        escape_text(finding.producer),
        f"{int(confidence * 100)}%" if confidence is not None else "—",
    ]


def _in_order(labels: Iterable[str], order: Sequence[str]) -> list[str]:
    """`labels` in `order`, followed alphabetically by any that `order` does not name."""
    rank = {label: index for index, label in enumerate(order)}
    return sorted(labels, key=lambda label: (rank.get(label, len(rank)), label))


def _format_counts(counts: Counter[str], order: Sequence[str]) -> str:
    """`1 CRITICAL, 2 HIGH`: each label's count, in `order`."""
    return ", ".join(f"{counts[label]} {label}" for label in _in_order(counts, order))


def _is_vulnerable_dependency(dependency: DependencySpec) -> bool:
    return dependency.severity.upper() in CONST_DEPENDENCY_VULNERABLE_SEVERITIES


def _is_flagged_network_reference(reference: NetworkReference) -> bool:
    return reference.reputation is not None and reference.reputation.is_malicious


def _dependency_line(
    dependencies: Sequence[DependencySpec], vulnerable: Sequence[DependencySpec]
) -> str:
    """One line for the dependency scan: scanned, vulnerable by severity, and not checked."""
    if not dependencies:
        return "Dependencies: none declared in the reviewed files."
    by_severity = _format_counts(
        Counter(d.severity.upper() for d in vulnerable), CONST_SEVERITY_ORDER
    )
    unchecked = sum(
        1
        for d in dependencies
        if not _is_vulnerable_dependency(d)
        and d.severity.upper() != CONST_DEPENDENCY_SEVERITY_CLEAN
    )
    counts = [
        f"{len(dependencies)} scanned",
        f"{len(vulnerable)} vulnerable" + (f" ({by_severity})" if vulnerable else ""),
        *([f"{unchecked} not checked"] if unchecked else []),
    ]
    return (
        f"Dependencies: {', '.join(counts)}. "
        f'All are listed under "{_REPORT_DEPENDENCIES_SECTION}" in review.md.'
    )


def _network_line(
    references: Sequence[NetworkReference], flagged: Sequence[NetworkReference]
) -> str:
    """One line for the network references: found, local and external, and flagged."""
    if not references:
        return "Network references: none in the reviewed files."
    local = sum(1 for r in references if r.is_local)
    return (
        f"Network references: {len(references)} found ({local} local, "
        f"{len(references) - local} external), {len(flagged)} flagged by reputation. "
        f'All are listed under "{_REPORT_NETWORK_SECTION}" in review.md.'
    )


def select_console_findings(
    reportable_findings: Sequence[SavedFinding], *, full_output: bool
) -> tuple[list[tuple[int, SavedFinding]], list[tuple[int, SavedFinding]], list[SavedFinding]]:
    """The numbered findings for the table and for detail panels, and those only counted."""
    numbered = list(enumerate(reportable_findings, 1))
    if full_output:
        return numbered, numbered, []
    tabled = [
        (index, finding)
        for index, finding in numbered
        if _severity(finding) in CONST_REVIEW_CONSOLE_TABLE_SEVERITIES
    ]
    panelled = [
        (index, finding)
        for index, finding in tabled
        if _severity(finding) in CONST_REVIEW_CONSOLE_PANEL_SEVERITIES
    ]
    minor = [
        finding
        for finding in reportable_findings
        if _severity(finding) not in CONST_REVIEW_CONSOLE_TABLE_SEVERITIES
    ]
    return tabled, panelled, minor


def _minor_findings_line(report: ReportInput, minor: Sequence[SavedFinding]) -> tuple[str, str]:
    """Count the findings left out of the table by status and name review.md; return that
    line and the command that lists them."""
    severities = _in_order({_severity(f) for f in minor}, CONST_SEVERITY_ORDER)
    statuses = _format_counts(Counter(f.status.upper() for f in minor), CONST_REVIEW_STATUS_ORDER)
    filters = " ".join(f"--severity {severity}" for severity in severities)
    command = f"devops review findings {report.session_name} {filters} --details"
    return (
        f"Not shown: {len(minor)} {' and '.join(severities)} finding(s) ({statuses}). "
        f"They are in {report.report_path}; list them with:",
        command,
    )


def render_finding_panel(
    console: Console | None, finding: SavedFinding, finding_index: int
) -> None:
    """Print one finding's detail panel, with its remediation and references."""
    from devops_cli.output import SEV_COLOR_MAP

    sev_upper = (finding.severity or "INFORMATIONAL").upper()
    sev_color = SEV_COLOR_MAP.get(sev_upper, "white")
    st_badge = _finding_status_badge(finding.status)
    title_header = f"[{sev_color} bold]Finding #{finding_index}: [{sev_upper}] {escape_text(finding.title)}[/{sev_color} bold]  {st_badge}"
    panel_lines = [
        f"[bold]Location:[/bold] [cyan]{escape_text(finding.location)}[/cyan]  |  [bold]Producer:[/bold] [magenta]{escape_text(finding.producer)}[/magenta]",
    ]
    if finding.description:
        clean_desc = escape_text(format_clean_text_field(finding.description).strip())
        panel_lines.extend(["", "[bold]Description:[/bold]", clean_desc])
    if finding.fix:
        clean_fix = escape_text(format_clean_text_field(finding.fix).strip())
        panel_lines.extend(["", "[bold]Suggested Fix:[/bold]", clean_fix])
    if finding.invalidation_reason:
        clean_inv = escape_text(finding.invalidation_reason.strip())
        label = "Mitigation" if finding.status == "MITIGATED" else "Invalidation Reason"
        panel_lines.extend(["", f"[bold yellow]{label}:[/bold yellow] {clean_inv}"])
    if finding.references:
        refs_list = (
            finding.references
            if isinstance(finding.references, list)
            else [str(finding.references)]
        )
        panel_lines.extend(["", f"[dim]References: {escape_text(', '.join(refs_list))}[/dim]"])

    print_panel(
        "\n".join(panel_lines),
        title=title_header,
        border_style=sev_color,
        console=console,
    )


def _print_findings(report: ReportInput, console: Console | None) -> None:
    """The findings table and detail panels.

    Unless `full_output`, the table lists MEDIUM and above, panels follow for HIGH and above,
    and the rest are counted on one line naming review.md and the command that lists them.
    Each finding keeps its number in review.md.
    """
    if not report.reportable_findings:
        print_success("No reportable findings across reviewed files.", console=console)
        return

    tabled, panelled, minor = select_console_findings(
        report.reportable_findings, full_output=report.full_output
    )
    if tabled:
        print_table(
            title="Code Review Findings",
            columns=_CONSOLE_FINDING_COLUMNS,
            rows=[_finding_row(index, finding) for index, finding in tabled],
            console=console,
        )
    if minor:
        summary, command = _minor_findings_line(report, minor)
        print_info(summary, prefix=False, console=console, safe=True)
        # Soft wrap keeps the command on one line at any width, so it copies as is.
        (console or get_console()).print(
            f"  {command}", markup=False, highlight=False, soft_wrap=True
        )
    for finding_index, finding in panelled:
        render_finding_panel(console, finding, finding_index)


def _print_dependencies(report: ReportInput, console: Console | None) -> None:
    """The dependency security audit.

    Unless `full_output`, one summary line and then only the vulnerable packages.
    """
    all_deps = report.dependencies
    if not report.full_output:
        vulnerable = [d for d in all_deps if _is_vulnerable_dependency(d)]
        line = _dependency_line(all_deps, vulnerable)
        print_info(line, prefix=False, console=console, safe=True)
        if vulnerable:
            print_table(
                title="Vulnerable Dependencies (OSV.dev)",
                columns=_CONSOLE_DEPENDENCY_COLUMNS,
                rows=[_dependency_row(d) for d in vulnerable],
                console=console,
            )
        return
    print_table(
        title="External Dependencies Security Audit (OSV.dev)",
        columns=_CONSOLE_DEPENDENCY_COLUMNS,
        rows=[_dependency_row(d) for d in all_deps] or [_CONSOLE_NO_DEPENDENCIES_ROW],
        console=console,
    )


def _print_network_references(report: ReportInput, console: Console | None) -> None:
    """The network references audit.

    Unless `full_output`, one summary line and then only the endpoints flagged by reputation.
    """
    sorted_nets = _reported_network_references(report.network_references)
    if not report.full_output:
        flagged = [n for n in sorted_nets if _is_flagged_network_reference(n)]
        line = _network_line(sorted_nets, flagged)
        print_info(line, prefix=False, console=console, safe=True)
        if flagged:
            print_table(
                title="Flagged Network References (Shodan & Cloudflare Radar)",
                columns=_CONSOLE_NETWORK_COLUMNS,
                rows=[_network_reference_row(n) for n in flagged],
                console=console,
            )
        return
    print_table(
        title="Network References & Endpoints Security Audit (Shodan & Cloudflare Radar)",
        columns=_CONSOLE_NETWORK_COLUMNS,
        rows=[_network_reference_row(n) for n in sorted_nets] or [_CONSOLE_NO_NETWORK_ROW],
        console=console,
    )


def _print_errored_files(report: ReportInput, console: Console | None) -> None:
    """The table of skipped and errored files."""
    if not report.errored_files:
        return

    columns = [
        ("File Path", "bold red"),
        ("Stage / Error Details", "yellow"),
    ]
    rows = [[fpath, reason] for fpath, reason in sorted(report.errored_files.items())]
    print_table(
        title="Skipped / Errored Files During Review",
        columns=columns,
        rows=rows,
        border_style="yellow",
        console=console,
    )


def _findings_count(reportable_findings: Sequence[SavedFinding]) -> tuple[str, str]:
    """The terminal's count of the findings by severity, and their verification rate."""
    if not reportable_findings:
        return "[bold green]0 findings (Clean)[/bold green]", "[green]✓ All clean[/green]"

    counts = _severity_counts(reportable_findings)
    sev_parts = [
        _CONSOLE_SEVERITY_COUNT_STYLES[severity].format(cnt=counts[severity])
        for severity in CONST_SEVERITY_ORDER
        if counts[severity]
    ]
    sev_breakdown = ", ".join(sev_parts) if sev_parts else "None"
    findings_str = f"{len(reportable_findings)} ({sev_breakdown})"

    ver_count = sum(
        1 for finding in reportable_findings if (finding.status or "").upper() == "VERIFIED"
    )
    ver_pct = ver_count / len(reportable_findings)
    ver_rate_str = f"{ver_count}/{len(reportable_findings)} verified ({ver_pct:.0%})"
    return findings_str, ver_rate_str


def _dependency_summary(all_deps: Sequence[DependencySpec]) -> str:
    """The external dependency audit's summary."""
    if not all_deps:
        return "0 scanned"
    vuln_count = sum(
        1
        for dep in all_deps
        if (dep.severity or "").upper()
        not in ("CLEAN", "NONE", "INFO", "NOT_QUERIED", "NOT QUERIED", "UNCHECKED")
    )
    queried_count = sum(
        1
        for dep in all_deps
        if getattr(dep, "queried", False)
        or (dep.severity or "").upper() in ("CLEAN", "CRITICAL", "HIGH", "MEDIUM", "LOW")
    )
    if vuln_count:
        vuln_note = f" ([red]{vuln_count} vulnerable[/red])"
    elif queried_count and queried_count == len(all_deps):
        vuln_note = " ([green]clean[/green])"
    elif queried_count:
        vuln_note = f" ([green]{queried_count} clean[/green], [dim]{len(all_deps) - queried_count} unchecked[/dim])"
    else:
        vuln_note = " ([dim]unchecked[/dim])"
    return f"{len(all_deps)} audited{vuln_note}"


def _network_summary(all_nets: Sequence[NetworkReference]) -> str:
    """The network endpoints audit's summary."""
    if not all_nets:
        return "0 detected"
    external_count = sum(1 for net in all_nets if not net.is_local)
    local_count = sum(1 for net in all_nets if net.is_local)
    return f"{len(all_nets)} audited ({external_count} External, {local_count} Local)"


def verdict_distribution_rows(findings_pool: Sequence[Finding | SavedFinding]) -> list[list[str]]:
    """The verdict field distributions, as rows of the terminal's summary table."""
    if not findings_pool:
        return []
    dists = compute_verdict_distributions(findings_pool)
    status_counts = dists.get("status", {})
    status_str = ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items()) if v > 0) or "0"
    rep_counts = dists.get("reportable", {})
    rep_disc = is_field_discriminating(rep_counts)
    rep_str = f"{rep_counts.get('true', 0)} true, {rep_counts.get('false', 0)} false"
    if not rep_disc and sum(rep_counts.values()) > 0:
        rep_str += " [bold yellow](does not discriminate)[/bold yellow]"

    ver_counts = dists.get("verified", {})
    ver_disc = is_field_discriminating(ver_counts)
    ver_str = f"{ver_counts.get('true', 0)} true, {ver_counts.get('false', 0)} false"
    if not ver_disc and sum(ver_counts.values()) > 0:
        ver_str += " [dim](does not discriminate)[/dim]"

    return [
        ["Verdict Status", status_str],
        ["Verdict Reportable", rep_str],
        ["Verdict Verified", ver_str],
    ]


def _status_rows(reportable_findings: Sequence[SavedFinding]) -> list[list[str]]:
    """The terminal summary's row counting the findings by status, as the report does (#948)."""
    if not reportable_findings:
        return []
    counted, apart = _status_counts(reportable_findings)
    listed_apart = f"; listed apart: {', '.join(apart)}" if apart else ""
    return [["By Status", f"{', '.join(counted) or 'none'}{listed_apart}"]]


def _print_summary(report: ReportInput, console: Console | None) -> None:
    """The review summary table."""
    findings = report.reportable_findings
    findings_str, ver_rate_str = _findings_count(findings)
    findings_pool: Sequence[SavedFinding] = (
        report.candidate_findings
        if report.candidate_findings is not None
        else (report.all_findings if report.all_findings is not None else findings)
    )
    inval_count = sum(1 for f in findings_pool if (f.status or "").upper() == "INVALIDATED")
    total_count = len(findings_pool)
    fp_rate = (inval_count / total_count) if total_count > 0 else 0.0
    fp_rate_str = f"{inval_count}/{total_count} ({fp_rate:.1%})"

    rows = [
        ["Session ID", f"[cyan]{report.session_id}[/cyan]"],
        ["Files Reviewed", str(report.files_reviewed)],
    ]
    if report.errored_files:
        rows.append(
            [
                "Skipped / Errored Files",
                f"[bold red]{len(report.errored_files)} file(s) skipped[/bold red]",
            ]
        )
    rows.extend(
        [
            ["Reportable Findings", findings_str],
            *_status_rows(findings),
            ["Verification Rate", ver_rate_str],
            ["False Positive Rate", fp_rate_str],
        ]
    )
    delta = report.symbol_delta
    if delta and any(delta.values()):
        rows.append(
            [
                "Symbol Delta",
                f"+{delta.get('added', 0)} / -{delta.get('removed', 0)} / ={delta.get('retained', 0)}",
            ]
        )
    rows.extend(verdict_distribution_rows(findings_pool))
    rows.extend(
        [
            ["Dependencies", _dependency_summary(report.dependencies)],
            ["Network Endpoints", _network_summary(report.network_references)],
            ["Markdown Report", str(report.report_path)],
            ["Findings JSON", str(report.findings_path)],
        ]
    )

    print_table(
        title="Review Summary",
        columns=[("Metric", "bold"), "Result"],
        rows=rows,
        border_style="cyan",
        console=console,
    )


def render_console(report: ReportInput, console: Console | None = None) -> None:
    """Print the terminal view of the session: errored files, findings, dependencies, network
    references and the summary."""
    _print_errored_files(report, console)
    _print_findings(report, console)
    _print_dependencies(report, console)
    _print_network_references(report, console)
    _print_summary(report, console)
