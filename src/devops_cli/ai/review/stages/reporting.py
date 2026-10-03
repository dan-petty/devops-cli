"""The review report's executive summary: its headline, its counts and its patterns.

The headline names what verification confirmed (#948). It used to name the themes of the
first-sorted findings, where a theme was a finding's first reference or its title, so a
hallucinated CVE on an UNVERIFIED finding headlined session `20261001-224227`, and its counts
mixed every status.
"""

from __future__ import annotations

import collections
from collections.abc import Sequence

from devops_cli.ai.review.category_metrics import resolve_finding_category
from devops_cli.ai.review_schema import DefectClass, SavedFinding
from devops_cli.config.constants import (
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_INFO,
    CONST_SEVERITY_ORDER,
    CONST_STATUS_MITIGATED,
    CONST_STATUS_UNVERIFIED,
    CONST_STATUS_VERIFIED,
    CONST_VERIFICATION_UNAVAILABLE,
)
from devops_cli.config.defaults import DEFAULT_REVIEW_HEADLINE_THEMES
from devops_cli.models.vulnerability import DependencySpec, NetworkReference

_SEVERITY_LABELS: dict[str, str] = {
    "CRITICAL": "Critical",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
    "INFO": "Informational",
}
# An UNVERIFIED finding the verifier never reached because verification itself failed.
_UNAVAILABLE = "UNAVAILABLE"
# How the headline counts each group: VERIFIED and UNVERIFIED together, the findings verification
# never reached and the MITIGATED ones listed apart.
_COUNTED_GROUPS: tuple[tuple[str, str], ...] = (
    (CONST_STATUS_VERIFIED, "verified"),
    (CONST_STATUS_UNVERIFIED, "unverified"),
)
_APART_GROUPS: tuple[tuple[str, str], ...] = (
    (_UNAVAILABLE, "not verified because verification was unavailable"),
    (CONST_STATUS_MITIGATED, "mitigated"),
)


def _severity(finding: SavedFinding) -> str:
    """A finding's severity, INFO when it has none."""
    return (finding.severity or CONST_SEVERITY_INFO).upper()


def _severity_rank(finding: SavedFinding) -> int:
    severity = _severity(finding)
    return CONST_SEVERITY_ORDER.index(severity) if severity in CONST_SEVERITY_ORDER else 99


def _status_group(finding: SavedFinding) -> str:
    unavailable = (finding.verification_note or "").startswith(CONST_VERIFICATION_UNAVAILABLE)
    if finding.status == CONST_STATUS_UNVERIFIED and unavailable:
        return _UNAVAILABLE
    return finding.status


def _join(parts: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c`."""
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _severity_breakdown(findings: Sequence[SavedFinding]) -> str:
    counts = collections.Counter(_severity(f) for f in findings)
    return ", ".join(
        f"{counts[severity]} {_SEVERITY_LABELS[severity]}"
        for severity in CONST_SEVERITY_ORDER
        if counts[severity]
    )


def _group_counts(
    groups: dict[str, list[SavedFinding]], labels: tuple[tuple[str, str], ...]
) -> list[str]:
    return [
        f"{len(groups[key])} {label} ({_severity_breakdown(groups[key])})"
        for key, label in labels
        if groups.get(key)
    ]


def status_counts(findings: Sequence[SavedFinding]) -> tuple[list[str], list[str]]:
    """The findings counted by status, each status with its severities: VERIFIED and
    UNVERIFIED, then, listed apart, those verification never reached and the MITIGATED ones.

    Counting them together reported 76 findings the verifier never saw and 28 MITIGATED ones
    as defects.
    """
    groups: dict[str, list[SavedFinding]] = collections.defaultdict(list)
    for finding in findings:
        groups[_status_group(finding)].append(finding)
    return _group_counts(groups, _COUNTED_GROUPS), _group_counts(groups, _APART_GROUPS)


def format_status_counts(findings: Sequence[SavedFinding]) -> str:
    """The report's sentences counting the findings by status (`status_counts`)."""
    counted, apart = status_counts(findings)
    sentences = [f"{_join(counted)}."] if counted else []
    if apart:
        sentences.append(f"Listed apart: {_join(apart)}.")
    return " ".join(sentences)


def status_summary_lines(findings: Sequence[SavedFinding]) -> list[str]:
    """The report summary's line counting its findings by status; none for no findings."""
    counts = format_status_counts(findings)
    return [f"By status: {counts}"] if counts else []


def _reported(findings: Sequence[SavedFinding]) -> str:
    """How many findings the review reported, and their counts by status."""
    counts = format_status_counts(findings)
    return f"**{len(findings)} reportable finding(s)**" + (f": {counts}" if counts else ".")


def verified_themes(
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
    themes = [cls.label for cls, _ in verified_themes(findings)]
    severe = any(_severity(f) in (CONST_SEVERITY_CRITICAL, CONST_SEVERITY_HIGH) for f in verified)
    prefix = "High-priority remediation" if severe else "Remediation"
    return f"{prefix} is recommended for the verified findings{_recurring(themes)}."


def _recurring(themes: Sequence[str]) -> str:
    """The clause naming the classes verified findings recur in, the first few by name."""
    named = list(themes[:DEFAULT_REVIEW_HEADLINE_THEMES])
    if len(themes) > len(named):
        named.append(f"{len(themes) - len(named)} more listed under Key Bad Patterns")
    return f", which recur in {_join(named)}" if named else ""


def extract_good_patterns(
    all_deps: list[DependencySpec] | None = None,
    all_nets: list[NetworkReference] | None = None,
) -> list[str]:
    """Extract key positive patterns supported by concrete tool outputs."""
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


def extract_bad_patterns(reportable_findings: list[SavedFinding]) -> list[str]:
    """The defect classes that recur among VERIFIED findings, one line each."""
    themes = verified_themes(reportable_findings)
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


def synthesize_report_executive_summary(
    reportable_findings: list[SavedFinding],
    all_deps: list[DependencySpec] | None = None,
    all_nets: list[NetworkReference] | None = None,
    errored_files: dict[str, str] | None = None,
    analyzer_line: str | None = None,
) -> list[str]:
    """Construct Markdown lines for the Executive Summary section at the top of the review report.

    `analyzer_line` says which static analyzers ran and what they found, computed from the scan.
    """
    if errored_files:
        summary_stmt = (
            f"The automated review encountered errors on **{len(errored_files)} file(s)** "
            f"(e.g. AI provider offline or communication failure). "
            f"Review could not be completed for those files. "
            f"Across successfully analyzed files it reported {_reported(reportable_findings)}"
        )
    elif not reportable_findings:
        summary_stmt = (
            "The automated multi-persona review evaluated the target scope with "
            "**0 reportable defects** across successfully analyzed files."
        )
    else:
        summary_stmt = (
            f"The automated multi-persona review reported {_reported(reportable_findings)} "
            f"{_remediation_statement(reportable_findings)}"
        )

    lines = ["## Executive Summary", summary_stmt]
    if analyzer_line:
        lines.extend(["", analyzer_line])

    good_patterns = extract_good_patterns(all_deps=all_deps, all_nets=all_nets)
    if good_patterns:
        lines.append("")
        lines.append("### Key Good Patterns Observed")
        lines.extend(f"- {pattern}" for pattern in good_patterns)

    lines.append("")
    lines.append("### Key Bad Patterns Observed")
    lines.extend(f"- {pattern}" for pattern in extract_bad_patterns(reportable_findings))

    lines.append("")
    return lines
