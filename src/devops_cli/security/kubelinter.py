"""Red Hat Kube-linter static Kubernetes manifest and Helm chart linter integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_KUBELINTER_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run

logger = logging.getLogger(__name__)

CONST_KUBELINTER_TIMEOUT_SECONDS = DEFAULT_KUBELINTER_TIMEOUT_SECONDS


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
                confidence_score=0.9,
            )
        )

    return findings


def run_kubelinter_scan(target: Path = Path(".")) -> list[Finding]:
    """Execute Kube-linter scanner subprocess and return parsed findings."""
    if is_dry_run():
        return [
            Finding(
                severity="MEDIUM",
                location=f"{target}:Deployment/dry-run-spec",
                title="[DRY-RUN] Simulated Kube-linter Manifest Audit",
                description="Kube-linter static audit simulation mode active.",
                fix="No action required (dry-run mode)",
                confidence_score=1.0,
            )
        ]

    cmd = ["kube-linter", "lint", str(target), "--format", "json"]

    try:
        proc = run_subprocess(cmd, timeout=CONST_KUBELINTER_TIMEOUT_SECONDS)
        if proc.stdout:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return parse_kubelinter_json(data, target_path=str(target))
    except Exception as exc:
        logger.debug(f"Kube-linter scan execution skipped or failed: {exc}")

    return []
