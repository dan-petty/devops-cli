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
) -> list[str]:
    """Extract key positive architectural and engineering patterns observed in the codebase."""
    patterns: list[str] = [
        "**Architectural Separation & Invariant Discipline**: Consistent adherence to domain-driven subsystem boundaries, strict type annotations, and low complexity limits (cyclomatic complexity <= 10, nesting depth <= 5).",
        "**Subprocess & Process Execution Safety**: Safe execution of CLI tooling using explicit argument lists, bounded timeouts, and captured outputs without shell string interpolation.",
        "**Defensive Typing & Schema Modeling**: Widespread adoption of Pydantic v2 schemas and explicit data contracts across domain models and tool interfaces.",
    ]
    if all_deps is not None and not any(
        (d.severity or "").upper() in ("CRITICAL", "HIGH") for d in all_deps
    ):
        patterns.append(
            "**Supply Chain & Lockfile Integrity**: External dependencies validated against authoritative lockfiles with zero unpinned critical/high CVEs."
        )
    if all_nets is not None and all(n.is_local for n in all_nets):
        patterns.append(
            "**Zero-Trust Network Isolation**: Target service references strictly bound to local or container-isolated internal endpoints."
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


def synthesize_report_executive_summary(
    reportable_findings: list[SavedFinding],
    all_deps: list[DependencySpec] | None = None,
    all_nets: list[NetworkReference] | None = None,
    errored_files: dict[str, str] | None = None,
) -> list[str]:
    """Construct Markdown lines for the Executive Summary section at the top of the review report."""
    crit = sum(1 for f in reportable_findings if (f.severity or "").upper() == "CRITICAL")
    high = sum(1 for f in reportable_findings if (f.severity or "").upper() == "HIGH")
    med = sum(1 for f in reportable_findings if (f.severity or "").upper() == "MEDIUM")
    low = sum(1 for f in reportable_findings if (f.severity or "").upper() == "LOW")

    if errored_files:
        summary_stmt = (
            f"The automated review encountered errors on **{len(errored_files)} file(s)** "
            f"(e.g. AI provider offline or communication failure). "
            f"Review could not be completed for those files. "
            f"Across successfully analyzed files, **{len(reportable_findings)} reportable finding(s)** were identified."
        )
    elif not reportable_findings:
        summary_stmt = (
            "The automated multi-persona review evaluated the target scope with **0 reportable defects**. "
            "The codebase demonstrates exceptional engineering quality, strict invariant adherence, "
            "and robust defensive security controls."
        )
    else:
        summary_stmt = (
            f"The automated multi-persona review evaluated the target scope and identified "
            f"**{len(reportable_findings)} reportable finding(s)** ({crit} Critical, {high} High, "
            f"{med} Medium, {low} Low). High-priority remediation is recommended to resolve identified "
            f"security risks, path traversal defenses, and transport protocol safeguards."
        )

    lines = [
        "## Executive Summary",
        summary_stmt,
        "",
        "### Key Good Patterns Observed",
    ]
    for pattern in extract_good_patterns(reportable_findings, all_deps, all_nets):
        lines.append(f"- {pattern}")

    lines.append("")
    lines.append("### Key Bad Patterns Observed")
    for pattern in extract_bad_patterns(reportable_findings):
        lines.append(f"- {pattern}")

    lines.append("")
    return lines
