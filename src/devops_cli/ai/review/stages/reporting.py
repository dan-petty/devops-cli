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

        # 2. Save Markdown Report
        md_lines = [
            f"# Consolidated Code Review Report — Session {session_id}",
            "",
            f"- **Files Reviewed:** {n_files}",
            f"- **Total Findings:** {len(reportable_findings)}",
            "",
            "## Findings Summary",
            "",
            "| # | Severity | Location | Title | Status |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for idx, f in enumerate(reportable_findings, 1):
            md_lines.append(f"| {idx} | {f.severity} | `{f.location}` | {f.title} | {f.status} |")

        report_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        print_success(
            f"Consolidated review completed for session {session_id} "
            f"({len(reportable_findings)} finding(s) saved to {session_dir})"
        )
        return report_path
