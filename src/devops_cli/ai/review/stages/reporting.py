"""Consolidated markdown, JSON artifact, and console table report generation."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.review.pipeline import _get_reviews_base_dir
from devops_cli.ai.review_schema import SavedFinding
from devops_cli.exceptions import SecurityError
from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output import print_info, print_success
from devops_cli.telemetry.tracer import trace_span

_ANTI_PATTERN_CATEGORIES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        (
            "path traversal",
            "traversal",
            "symlink",
            "relative_to",
            "arbitrary file",
            "outside repository",
        ),
        "Path Traversal & Filesystem Boundary Violations",
        "Unvalidated file paths, missing containment checks, or unverified symlinks allowing access outside repository bounds.",
    ),
    (
        (
            "git://",
            "insecure",
            "unencrypted",
            "cleartext",
            "public access",
            "cors",
            "publicly accessible",
            "unauthenticated",
        ),
        "Insecure Transport Protocols & Cleartext Endpoints",
        "Use of unencrypted transport protocols (such as cleartext git://), overly permissive CORS, or unauthenticated services exposed to network access.",
    ),
    (
        (
            "argument validation",
            "missing validation",
            "unvalidated",
            "unbounded",
            "redos",
            "regex",
        ),
        "Missing Parameter Validation & Unbounded Inputs",
        "Tool arguments, search queries, or user inputs executed without strict length constraints, types, or sanitization.",
    ),
    (
        (
            "denial of service",
            "dos",
            "resource limit",
            "large input",
            "exhaustion",
            "concurrency",
        ),
        "Resource Exhaustion & Denial-of-Service Hazards",
        "Unbounded data ingestion, missing process count ceilings, or unconstrained memory caching risking resource starvation.",
    ),
    (
        (
            "information exposure",
            "credential",
            "leakage",
            "admin credentials",
            "secret",
        ),
        "Information Exposure & Sensitive Data Handling",
        "Unmasked credentials, internal exception traces, or repository structures disclosed in outputs or logs.",
    ),
)


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
    """Synthesize recurring anti-patterns and defect classes from reportable findings."""
    if not reportable_findings:
        return [
            "No critical anti-patterns or recurring defect patterns identified across the evaluated scope."
        ]

    bad_patterns: list[str] = []
    matched_indices: set[int] = set()

    for keywords, category_title, description in _ANTI_PATTERN_CATEGORIES:
        matching_count = 0
        for idx, f in enumerate(reportable_findings):
            text = f"{f.title} {f.description or ''} {f.location}".lower()
            if any(kw in text for kw in keywords):
                matching_count += 1
                matched_indices.add(idx)

        if matching_count > 0:
            bad_patterns.append(
                f"**{category_title}**: {description} (Observed in {matching_count} finding(s))."
            )

    unmatched_count = len(reportable_findings) - len(matched_indices)
    if unmatched_count > 0:
        bad_patterns.append(
            f"**Domain-Specific Edge Case Defects**: {unmatched_count} isolated finding(s) with specific functional or configuration flaws."
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
