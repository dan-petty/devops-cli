"""Fairwinds Pluto deprecated Kubernetes API scanner integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_PLUTO, build_pluto_cmd
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
)
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome

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
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking Pluto."""
        target_abs = target_path.resolve() if target_path.exists() else target_path
        return build_pluto_cmd(target_abs, binary_name=self.binary_name)

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


def run_pluto_scan(target: Path = DEFAULT_CURRENT_PATH, *, isolated: bool = False) -> ScanOutcome:
    """Execute Pluto deprecated API scanner and return scan outcome; `isolated` for a review.

    Pluto reads no config or ignore file, so an isolated scan only runs it outside the tree.
    """
    scanner = PlutoScanner()
    return scanner.scan(target, isolated=isolated)
