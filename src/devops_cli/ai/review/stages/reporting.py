"""Consolidated Markdown Reporting, Terminal Output & Feedback Dataset Logging."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from devops_cli.ai.review_schema import FileReviewPayload, Finding, ReviewResult
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


@trace_span("review.stage.reporting")
def run_reporting(
    payloads: Sequence[FileReviewPayload],
    session_id: str,
    errored_files: dict[str, str] | None = None,
) -> tuple[ReviewResult, str]:
    """Generate consolidated ReviewResult and Markdown report string from completed payloads."""
    all_findings: list[Finding] = []
    for p in payloads:
        if p.findings:
            all_findings.extend(p.findings)

    total_files = len(payloads)

    result = ReviewResult(
        findings=all_findings,
        summary=f"Reviewed {total_files} files with {len(all_findings)} findings across personas.",
    )

    # Build Markdown report lines
    report_lines: list[str] = [
        f"# AI Code Review Report — Session `{session_id}`",
        "",
        f"- **Files Reviewed**: {total_files}",
        f"- **Total Findings**: {len(all_findings)}",
        "",
    ]

    if errored_files:
        report_lines.extend(
            [
                "## Skipped / Errored Files",
                "",
            ]
        )
        for fpath, err_msg in errored_files.items():
            report_lines.append(f"- `{fpath}`: {err_msg}")
        report_lines.append("")

    if not all_findings:
        report_lines.append("✅ **No issues or security vulnerabilities detected.**\n")
    else:
        report_lines.append("## Findings Summary\n")
        for f in all_findings:
            loc = f.location or "unknown"
            report_lines.append(f"### [{f.severity.upper()}] {f.title}")
            report_lines.append(f"- **Location**: `{loc}`")
            report_lines.append(f"- **Description**: {f.description}")
            if f.fix:
                report_lines.append(f"- **Suggested Fix**: {f.fix}")
            report_lines.append("")

    report_md = "\n".join(report_lines)
    return result, report_md
