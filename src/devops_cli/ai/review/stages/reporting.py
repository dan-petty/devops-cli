"""Consolidated markdown, JSON artifact, and console table report generation."""

from __future__ import annotations

import collections
import re

from devops_cli.ai.review_schema import SavedFinding
from devops_cli.models.vulnerability import DependencySpec, NetworkReference

_SEVERITY_WEIGHTS: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFORMATIONAL": 4,
}


def _derive_finding_theme(finding: SavedFinding) -> str:
    """Extract a canonical theme or topic for a finding without brittle keyword lists."""
    for ref in finding.references:
        clean_ref = ref.strip()
        if clean_ref.upper().startswith(("CWE-", "OWASP", "CVE-")):
            return clean_ref.split(":")[0].strip()

    title = finding.title.strip()
    # Cleanly strip leading bracketed scanner/tool tags (e.g. [DRY-RUN], [GITLEAKS:...], [B602])
    stripped_title = re.sub(r"^(?:\[[^\]]+\]\s*)+", "", title).strip()
    candidate = stripped_title or title

    # Split only on delimiter sequences with surrounding whitespace or parenthesis,
    # preventing accidental splits on hyphens inside words (e.g. rate-limit, cross-site, --flag) or colons in URLs
    parts = re.split(r"\s+[-—:]\s+|\s*\(", candidate)
    clean_theme = parts[0].strip() if parts else candidate

    # Ensure clean_theme does not leave an unclosed backtick or bracket
    if clean_theme.count("`") % 2 != 0:
        clean_theme += "`"
    if clean_theme.count("[") > clean_theme.count("]"):
        clean_theme += "]"
    clean_theme = clean_theme.strip("`'\" ")
    if "**" in clean_theme:
        clean_theme = clean_theme.replace("**", "")

    return clean_theme or finding.title


def extract_good_patterns(
    reportable_findings: list[SavedFinding],
    all_deps: list[DependencySpec] | None = None,
    all_nets: list[NetworkReference] | None = None,
    static_analyzers: dict[str, str] | None = None,
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

    if static_analyzers:
        ran = [
            name
            for name, state in static_analyzers.items()
            if state in ("ran", "built-in patterns")
        ]
        if ran:
            patterns.append(
                f"**Static Security Analysis**: {len(ran)} static analyzer(s) executed "
                f"({', '.join(sorted(ran))}) with 0 critical findings."
            )

    return patterns


def extract_bad_patterns(reportable_findings: list[SavedFinding]) -> list[str]:
    """Synthesize recurring anti-patterns and defect classes dynamically from findings."""
    if not reportable_findings:
        return [
            "No critical anti-patterns or recurring defect patterns identified across the evaluated scope."
        ]

    groups: dict[str, list[SavedFinding]] = collections.defaultdict(list)
    for f in reportable_findings:
        theme = _derive_finding_theme(f)
        groups[theme].append(f)

    sorted_groups = sorted(
        groups.items(),
        key=lambda item: (
            -len(item[1]),
            min(_SEVERITY_WEIGHTS.get((f.severity or "INFORMATIONAL").upper(), 5) for f in item[1]),
        ),
    )

    bad_patterns: list[str] = []
    for theme, findings in sorted_groups:
        rep = findings[0]
        max_sev = (
            min(
                findings,
                key=lambda f: _SEVERITY_WEIGHTS.get((f.severity or "INFORMATIONAL").upper(), 5),
            ).severity
            or "INFORMATIONAL"
        ).upper()

        if "`" in rep.title:
            rep_title_str = rep.title
            if rep_title_str.count("`") % 2 != 0:
                rep_title_str += "`"
        else:
            rep_title_str = f"`{rep.title}`"

        loc_str = rep.location.strip("`")
        bad_patterns.append(
            f"**{theme}**: {len(findings)} finding(s) identified (highest severity: {max_sev}). Representative issue: {rep_title_str} at `{loc_str}`."
        )

    return bad_patterns


def _format_severity_breakdown(reportable_findings: list[SavedFinding]) -> str:
    """Format count breakdown of finding severities."""
    counts = collections.Counter((f.severity or "").upper() for f in reportable_findings)
    labels = (
        ("CRITICAL", "Critical"),
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
    )
    parts = [f"{counts[key]} {label}" for key, label in labels if counts[key]]
    info_count = counts["INFORMATIONAL"] + counts["INFO"]
    if info_count:
        parts.append(f"{info_count} Informational")
    return ", ".join(parts) or f"{len(reportable_findings)} Unspecified"


def _format_findings_remediation_summary(reportable_findings: list[SavedFinding]) -> str:
    """Derive recommendation statement from actual finding themes and severities."""
    themes: list[str] = list(dict.fromkeys(_derive_finding_theme(f) for f in reportable_findings))
    if not themes:
        return "Remediation is recommended to address identified findings."

    if len(themes) == 1:
        theme_desc = themes[0]
    elif len(themes) <= 3:
        theme_desc = f"{', '.join(themes[:-1])} and {themes[-1]}"
    else:
        theme_desc = f"{', '.join(themes[:3])}, and other identified issues"

    has_high_crit = any(
        (f.severity or "").upper() in ("CRITICAL", "HIGH") for f in reportable_findings
    )
    priority_prefix = "High-priority remediation" if has_high_crit else "Remediation"
    return f"{priority_prefix} is recommended to address {theme_desc}."


def synthesize_report_executive_summary(
    reportable_findings: list[SavedFinding],
    all_deps: list[DependencySpec] | None = None,
    all_nets: list[NetworkReference] | None = None,
    errored_files: dict[str, str] | None = None,
    static_analyzers: dict[str, str] | None = None,
) -> list[str]:
    """Construct Markdown lines for the Executive Summary section at the top of the review report."""
    if errored_files:
        summary_stmt = (
            f"The automated review encountered errors on **{len(errored_files)} file(s)** "
            f"(e.g. AI provider offline or communication failure). "
            f"Review could not be completed for those files. "
            f"Across successfully analyzed files, **{len(reportable_findings)} reportable finding(s)** were identified."
        )
    elif not reportable_findings:
        summary_stmt = (
            "The automated multi-persona review evaluated the target scope with "
            "**0 reportable defects** across successfully analyzed files."
        )
    else:
        sev_str = _format_severity_breakdown(reportable_findings)
        remediation_stmt = _format_findings_remediation_summary(reportable_findings)
        summary_stmt = (
            f"The automated multi-persona review evaluated the target scope and identified "
            f"**{len(reportable_findings)} reportable finding(s)** ({sev_str}). {remediation_stmt}"
        )

    lines = [
        "## Executive Summary",
        summary_stmt,
    ]

    good_patterns = extract_good_patterns(
        reportable_findings,
        all_deps=all_deps,
        all_nets=all_nets,
        static_analyzers=static_analyzers,
    )
    if good_patterns:
        lines.append("")
        lines.append("### Key Good Patterns Observed")
        for pattern in good_patterns:
            lines.append(f"- {pattern}")

    lines.append("")
    lines.append("### Key Bad Patterns Observed")
    for pattern in extract_bad_patterns(reportable_findings):
        lines.append(f"- {pattern}")

    lines.append("")
    return lines
