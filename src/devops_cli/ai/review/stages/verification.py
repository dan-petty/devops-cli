"""Finding Verification, AST Alignment & Confidence Calibration."""

from __future__ import annotations

import logging
from pathlib import Path

from devops_cli.ai.review.verification import _deterministic_pre_verification
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


@trace_span("review.stage.verification")
def run_verification(
    payload: FileReviewPayload,
    repo_root: Path | None = None,
) -> list[SavedFinding]:
    """Verify raw findings against deterministic AST rules and filter hallucinations."""
    if not payload.findings:
        return []

    verified_findings: list[SavedFinding] = []
    for f in payload.findings:
        checked = _deterministic_pre_verification(f, repo_root=repo_root)
        if isinstance(checked, SavedFinding):
            verified_findings.append(checked)
        else:
            verified_findings.append(SavedFinding.model_validate(checked.model_dump()))

    return verified_findings
