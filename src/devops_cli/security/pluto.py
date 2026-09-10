"""Fairwinds Pluto deprecated Kubernetes API scanner integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_PLUTO
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_PLUTO_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run
from devops_cli.security.base import BaseSecurityScanner

logger = logging.getLogger(__name__)


def parse_pluto_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Pluto JSON output payload into Finding objects."""
    findings: list[Finding] = []
    items = data.get("items") or []

    for item in items:
        name = item.get("name") or "unnamed"
        kind = item.get("kind") or "Resource"
        api_ver = item.get("apiVersion") or "v1"
        replacement = item.get("replacement") or "apps/v1"
        deprecated = item.get("deprecated", True)
        removed = item.get("removed", False)
        filepath = item.get("filepath") or target_path or "manifest.yaml"

        sev = "HIGH" if removed else ("MEDIUM" if deprecated else "LOW")
        status_word = "Removed" if removed else "Deprecated"

        findings.append(
            Finding(
                severity=sev,
                location=f"{filepath}:{kind}/{name}",
                title=f"[{status_word} API] {kind} '{name}' uses {api_ver}",
                description=(
                    f"K8s API version '{api_ver}' used by {kind} '{name}' is "
                    f"{status_word.lower()} in target version. Upgrade to '{replacement}'."
                ),
                fix=f"Update apiVersion from '{api_ver}' to '{replacement}'",
                confidence_score=None,
            )
        )

    return findings


class PlutoScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Fairwinds Pluto deprecated K8s API detector."""

    name: str = "pluto"
    binary_name: str = BIN_PLUTO

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking Pluto."""
        target_abs = target_path.resolve() if target_path.exists() else Path.cwd().resolve()
        return (
            [self.binary_name, "detect-files", "-f", str(target_abs), "-o", "json"]
            if target_abs.is_file()
            else [self.binary_name, "detect-files", "-d", str(target_abs), "-o", "json"]
        )

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw Pluto JSON payload into Finding models."""
        if isinstance(data, dict):
            return parse_pluto_json(data, target_path=str(target_path))
        return []

    def dry_run_scan(self, target_path: Path, **kwargs: Any) -> list[Finding]:
        """Return simulated Pluto findings for dry-run validation."""
        return [
            Finding(
                severity="HIGH",
                location=f"{target_path}:Deployment/dry-run-spec",
                title="[DRY-RUN] Simulated Pluto Deprecated K8s API Detection",
                description="Pluto deprecated API detection simulation mode active.",
                fix="Update apiVersion to apps/v1 (dry-run mode)",
                confidence_score=None,
            )
        ]


def run_pluto_scan(target: Path = DEFAULT_CURRENT_PATH) -> list[Finding]:
    """Execute Pluto deprecated API scanner subprocess and return parsed findings."""
    from devops_cli.telemetry import trace_span

    scanner = PlutoScanner()
    with trace_span(
        "security.scan.pluto",
        attributes={"target": str(target)},
    ) as span_h:
        if is_dry_run():
            return scanner.dry_run_scan(target)

        cmd = scanner.build_command(target)
        findings: list[Finding] = []
        try:
            proc = run_subprocess(cmd, timeout=DEFAULT_PLUTO_TIMEOUT_SECONDS, check=False)
            if proc.returncode == 127:
                span_h.set_attribute("tool.available", False)
            elif proc.stdout:
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    findings = scanner.parse_output(data, target)
        except Exception as exc:
            logger.debug(f"Pluto scan execution skipped or failed: {exc}")

        span_h.set_attribute("findings_count", len(findings))
        return findings
