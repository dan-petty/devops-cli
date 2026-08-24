"""Derailed Popeye Kubernetes cluster health and resource sanitizer integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import build_popeye_cmd
from devops_cli.config.defaults import DEFAULT_POPEYE_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run

logger = logging.getLogger(__name__)


def parse_popeye_json(data: dict[str, Any]) -> list[Finding]:
    """Parse Popeye cluster audit JSON payload into Finding objects."""
    findings: list[Finding] = []
    popeye_data = data.get("popeye") or data
    sanitizers = popeye_data.get("sanitizers") or []

    level_to_sev = {0: "INFO", 1: "LOW", 2: "MEDIUM", 3: "HIGH"}

    for s in sanitizers:
        sanitizer_name = s.get("sanitizer") or "cluster"
        issues = s.get("issues") or {}

        for res_id, res_issues in issues.items():
            for issue in res_issues:
                msg = issue.get("message") or f"Resource health issue in {res_id}"
                lvl = issue.get("level") if isinstance(issue.get("level"), int) else 2
                sev = level_to_sev.get(lvl, "MEDIUM")

                findings.append(
                    Finding(
                        severity=sev,
                        location=f"k8s:{sanitizer_name}/{res_id}",
                        title=f"[{sanitizer_name.upper()}] Cluster Sanitizer Finding",
                        description=msg,
                        fix=f"Review and adjust Kubernetes specification for {res_id}",
                        confidence_score=0.9,
                    )
                )

    return findings


def run_popeye_scan() -> list[Finding]:
    """Execute Popeye K8s cluster sanitizer subprocess and return parsed findings."""
    from devops_cli.telemetry import trace_span

    with trace_span(
        "security.scan.popeye",
        attributes={},
    ) as span_h:
        if is_dry_run():
            return [
                Finding(
                    severity="MEDIUM",
                    location="k8s:pods/default/dry-run-pod",
                    title="[DRY-RUN] Simulated Popeye Cluster Health Audit Result",
                    description="Popeye cluster health audit simulation mode active.",
                    fix="No action required (dry-run mode)",
                    confidence_score=1.0,
                )
            ]

        cmd = build_popeye_cmd()
        findings: list[Finding] = []

        try:
            proc = run_subprocess(cmd, timeout=DEFAULT_POPEYE_TIMEOUT_SECONDS, check=False)
            if proc.returncode == 127:
                span_h.set_attribute("tool.available", False)
            elif proc.stdout:
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    findings = parse_popeye_json(data)
        except Exception as exc:
            logger.debug(f"Popeye execution skipped or failed: {exc}")

        span_h.set_attribute("findings_count", len(findings))
        return findings
