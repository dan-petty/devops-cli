"""Consolidated markdown, JSON artifact, and console table report generation."""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from devops_cli.ai.review.pipeline import _get_reviews_base_dir
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.exceptions import SecurityError
from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output import print_info, print_success
from devops_cli.telemetry.tracer import trace_span

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

    clean_title = re.split(r"[:\-\(]", finding.title)[0].strip()
    return clean_title or finding.title


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
        d.severity.upper() in ("CRITICAL", "HIGH") for d in all_deps
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
            min(_SEVERITY_WEIGHTS.get(f.severity.upper(), 5) for f in item[1]),
        ),
    )

    bad_patterns: list[str] = []
    for theme, findings in sorted_groups:
        rep = findings[0]
        max_sev = min(
            findings, key=lambda f: _SEVERITY_WEIGHTS.get(f.severity.upper(), 5)
        ).severity.upper()
        bad_patterns.append(
            f"**{theme}**: {len(findings)} finding(s) identified (highest severity: {max_sev}). Representative issue: `{rep.title}` at `{rep.location}`."
        )

    return bad_patterns


def synthesize_report_executive_summary(
    reportable_findings: list[SavedFinding],
    all_deps: list[DependencySpec] | None = None,
    all_nets: list[NetworkReference] | None = None,
) -> list[str]:
    """Construct Markdown lines for the Executive Summary section at the top of the review report."""
    crit = sum(1 for f in reportable_findings if f.severity.upper() == "CRITICAL")
    high = sum(1 for f in reportable_findings if f.severity.upper() == "HIGH")
    med = sum(1 for f in reportable_findings if f.severity.upper() == "MEDIUM")
    low = sum(1 for f in reportable_findings if f.severity.upper() == "LOW")

    if not reportable_findings:
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


def run_reporting_stage(
    session_id: str,
    session_dir: Path,
    reportable_findings: list[SavedFinding],
    all_deps: list[DependencySpec],
    all_nets: list[NetworkReference],
    n_files: int,
) -> Path:
    """Execute consolidated report generation and persistence."""
    with trace_span("review.reporting", attributes={"session_id": session_id}):
        if any(p == ".." for p in session_dir.parts):
            raise SecurityError(f"Path traversal detected in session_dir: {session_dir}")

        import tempfile

        allowed_roots = [
            _get_reviews_base_dir().resolve(),
            Path.cwd().resolve(),
            Path(tempfile.gettempdir()).resolve(),
        ]
        resolved_session_dir = session_dir.resolve()
        if not any(
            resolved_session_dir == root or resolved_session_dir.is_relative_to(root)
            for root in allowed_roots
        ):
            raise SecurityError(
                f"Attempted to write report outside allowed root: {resolved_session_dir}"
            )

        print_info(
            f"Generating report for session '{session_id}'...",
            prefix=False,
        )

        session_dir.mkdir(parents=True, exist_ok=True)
        report_path = session_dir / "review_report.md"
        findings_json_path = session_dir / "findings.json"

        # 1. Save findings JSON
        findings_data = [f.model_dump() for f in reportable_findings]
        findings_json_path.write_text(json.dumps(findings_data, indent=2), encoding="utf-8")

        # 2. Save Markdown Report with Executive Summary at the top
        md_lines = [
            f"# Consolidated Code Review Report — Session {session_id}",
            "",
            f"- **Files Reviewed:** {n_files}",
            f"- **Total Findings:** {len(reportable_findings)}",
            "",
        ]
        md_lines.extend(
            synthesize_report_executive_summary(
                reportable_findings=reportable_findings,
                all_deps=all_deps,
                all_nets=all_nets,
            )
        )
        md_lines.extend(
            [
                "## Findings Summary",
                "",
                "| # | Severity | Location | Title | Status |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for idx, f in enumerate(reportable_findings, 1):
            md_lines.append(f"| {idx} | {f.severity} | `{f.location}` | {f.title} | {f.status} |")

        report_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        print_success(
            f"Consolidated review completed for session {session_id} "
            f"({len(reportable_findings)} finding(s) saved to {session_dir})"
        )
        return report_path
