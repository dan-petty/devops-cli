"""Static Analysis & Secret Pre-Filter Aggregation."""

from __future__ import annotations

import logging
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.security.bandit import run_bandit_scan
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.trivy import run_trivy_scan
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


@trace_span("review.stage.static_scan")
def run_static_scan(
    target_path: Path,
    enable_gitleaks: bool = True,
    enable_semgrep: bool = True,
    enable_bandit: bool = True,
    enable_trivy: bool = False,
) -> list[Finding]:
    """Execute static security pre-filters and return normalized findings."""
    aggregated_findings: list[Finding] = []

    if enable_gitleaks:
        try:
            gitleaks_findings = run_gitleaks_scan(target_path)
            aggregated_findings.extend(gitleaks_findings)
        except Exception as exc:
            logger.debug("Gitleaks scan failed: %s", exc)

    if enable_semgrep:
        try:
            semgrep_findings = run_semgrep_scan(target_path)
            aggregated_findings.extend(semgrep_findings)
        except Exception as exc:
            logger.debug("Semgrep scan failed: %s", exc)

    if enable_bandit:
        try:
            bandit_findings = run_bandit_scan(target_path)
            aggregated_findings.extend(bandit_findings)
        except Exception as exc:
            logger.debug("Bandit scan failed: %s", exc)

    if enable_trivy:
        try:
            trivy_findings = run_trivy_scan(target_path)
            aggregated_findings.extend(trivy_findings)
        except Exception as exc:
            logger.debug("Trivy scan failed: %s", exc)

    return aggregated_findings
