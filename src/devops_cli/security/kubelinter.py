"""Red Hat Kube-linter static Kubernetes manifest and Helm chart linter integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import build_kubelinter_cmd
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_KUBELINTER_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run

logger = logging.getLogger(__name__)


def parse_kubelinter_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Kube-linter JSON output payload into Finding objects."""
    findings: list[Finding] = []
    reports = data.get("Reports") or []

    for report in reports:
        diag = report.get("Diagnostic") or {}
        msg = diag.get("Message") or "Kube-linter static manifest diagnostic warning"
        check_name = diag.get("Check") or "kube-linter-check"

        obj_info = (report.get("Object") or {}).get("K8sObject") or {}
        kind = (obj_info.get("GroupVersionKind") or {}).get("Kind") or "Resource"
        name = obj_info.get("Name") or "unnamed"
        namespace = obj_info.get("Namespace") or "default"
        location_str = (
            f"{target_path}:{kind}/{name}" if target_path else f"{kind}/{name} ({namespace})"
        )

        findings.append(
            Finding(
                severity="MEDIUM",
                location=location_str,
                title=f"[{check_name}] K8s Security Lint Warning",
                description=f"{msg} for {kind} '{name}' in namespace '{namespace}'.",
                fix=f"Update K8s manifest spec for {kind} '{name}' to resolve {check_name}",
                confidence_score=None,
            )
        )

    return findings


def run_kubelinter_scan(target: Path = DEFAULT_CURRENT_PATH) -> list[Finding]:
    """Execute Kube-linter scanner subprocess and return parsed findings."""
    from devops_cli.telemetry import trace_span

    with trace_span(
        "security.scan.kubelinter",
        attributes={"target": str(target)},
    ) as span_h:
        if is_dry_run():
            return [
                Finding(
                    severity="MEDIUM",
                    location=f"{target}:Deployment/dry-run-spec",
                    title="[DRY-RUN] Simulated Kube-linter Manifest Audit",
                    description="Kube-linter static audit simulation mode active.",
                    fix="No action required (dry-run mode)",
                    confidence_score=None,
                )
            ]

        cmd = build_kubelinter_cmd(target)
        findings: list[Finding] = []

        try:
            proc = run_subprocess(cmd, timeout=DEFAULT_KUBELINTER_TIMEOUT_SECONDS, check=False)
            if proc.returncode == 127:
                span_h.set_attribute("tool.available", False)
            elif proc.stdout:
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    findings = parse_kubelinter_json(data, target_path=str(target))
        except Exception as exc:
            logger.debug(f"Kube-linter scan execution skipped or failed: {exc}")

        span_h.set_attribute("findings_count", len(findings))
        return findings
