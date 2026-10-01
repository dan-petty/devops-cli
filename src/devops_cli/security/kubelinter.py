"""Red Hat Kube-linter static Kubernetes manifest and Helm chart linter integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_KUBELINTER, build_kubelinter_cmd
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
)
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome

logger = logging.getLogger(__name__)


def _manifest_location(target_path: str) -> str:
    """The scanned manifest's path relative to the working tree the scan runs in.

    A path outside that tree is named by its file name alone.
    """
    if not target_path:
        return ""
    manifest = Path(target_path)
    try:
        from devops_cli.core.repo import find_worktree_root

        return str(manifest.resolve().relative_to(find_worktree_root(Path.cwd())))
    except Exception:
        return manifest.name


def _reported_object(report: dict[str, Any]) -> tuple[str, str, str]:
    """The kind, name and namespace of the Kubernetes object a Kube-linter report is about."""
    obj_info = (report.get("Object") or {}).get("K8sObject") or {}
    kind = (obj_info.get("GroupVersionKind") or {}).get("Kind") or "Resource"
    return kind, obj_info.get("Name") or "unnamed", obj_info.get("Namespace") or "default"


def _finding_from_report(report: dict[str, Any], manifest: str) -> Finding:
    """One Kube-linter report as a Finding located at `manifest`, or at its object when empty."""
    diag = report.get("Diagnostic") or {}
    msg = diag.get("Message") or "Kube-linter static manifest diagnostic warning"
    check_name = diag.get("Check") or "kube-linter-check"
    kind, name, namespace = _reported_object(report)
    location_str = f"{manifest}:{kind}/{name}" if manifest else f"{kind}/{name} ({namespace})"

    return Finding(
        severity="MEDIUM",
        location=location_str,
        title=f"[{check_name}] K8s Security Lint Warning",
        description=f"{msg} for {kind} '{name}' in namespace '{namespace}'.",
        fix=f"Update K8s manifest spec for {kind} '{name}' to resolve {check_name}",
        confidence_score=None,
    )


def parse_kubelinter_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Kube-linter JSON output payload into Finding objects."""
    manifest = _manifest_location(target_path)
    return [_finding_from_report(report, manifest) for report in data.get("Reports") or []]


class KubelinterScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Red Hat Kube-linter."""

    name: str = "kubelinter"
    binary_name: str = BIN_KUBELINTER
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking Kube-linter."""
        return build_kubelinter_cmd(target_path)

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw Kube-linter JSON payload into Finding models."""
        if isinstance(data, dict):
            return parse_kubelinter_json(data, target_path=str(target_path))
        return []

    def dry_run_scan(self, target_path: Path, **kwargs: Any) -> list[Finding]:
        """Return simulated Kube-linter findings for dry-run simulation."""
        return [
            Finding(
                severity="MEDIUM",
                location=f"{target_path}:Deployment/dry-run-spec",
                title="[DRY-RUN] Simulated Kube-linter Manifest Audit",
                description="Kube-linter static audit simulation mode active.",
                fix="No action required (dry-run mode)",
                confidence_score=None,
            )
        ]


def run_kubelinter_scan(target: Path = DEFAULT_CURRENT_PATH) -> ScanOutcome:
    """Execute Kube-linter scanner and return scan outcome."""
    scanner = KubelinterScanner()
    return scanner.scan(target)
