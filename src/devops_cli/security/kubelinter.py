"""Red Hat Kube-linter static Kubernetes manifest and Helm chart linter integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import DefectClass, Finding, defect_class
from devops_cli.config.commands import BIN_KUBELINTER, build_kubelinter_cmd
from devops_cli.config.constants import CONST_REVIEW_SCAN_KUBELINTER_CONFIG
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
)
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScannerConfigFile, ScanOutcome

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
    """The kind, name and namespace of the Kubernetes object a Kube-linter report is about.

    The namespace is empty when the manifest names none; it is not guessed.
    """
    obj_info = (report.get("Object") or {}).get("K8sObject") or {}
    kind = (obj_info.get("GroupVersionKind") or {}).get("Kind") or "Resource"
    return kind, obj_info.get("Name") or "unnamed", obj_info.get("Namespace") or ""


def _category(check: str, message: str) -> str:
    """The class the check name or the message names, else a security misconfiguration.

    kube-linter checks manifests for misconfiguration, so a check whose words name no class,
    or only `security`, is one.
    """
    vague = {DefectClass.OTHER, DefectClass.SECURITY}
    named = (defect_class(text) for text in (check, message))
    return next((c for c in named if c not in vague), DefectClass.SECURITY_MISCONFIGURATION).value


def _finding_from_report(report: dict[str, Any], target_path: str) -> Finding:
    """One Kube-linter report as a Finding at its manifest and object.

    kube-linter writes `Check` and `Remediation` beside `Diagnostic`, which holds `Message`.
    The manifest is the report's `FilePath`, or `target_path` when it names none; the object
    is `Kind/namespace/name`, or `Kind/name` without a namespace.
    """
    check = report["Check"]
    message = report["Diagnostic"]["Message"]
    kind, name, namespace = _reported_object(report)
    symbol = f"{kind}/{namespace}/{name}" if namespace else f"{kind}/{name}"
    file_path = ((report.get("Object") or {}).get("Metadata") or {}).get("FilePath")
    return Finding(
        severity="MEDIUM",
        location=f"{_manifest_location(file_path or target_path)}:{symbol}",
        title=f"[{check}] {message}",
        description=f"{message} for {kind} '{name}'.",
        fix=report.get("Remediation")
        or f"Update K8s manifest spec for {kind} '{name}' to resolve {check}",
        category=_category(check, message),
        confidence_score=None,
    )


def parse_kubelinter_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Kube-linter JSON output payload into Finding objects."""
    return [_finding_from_report(report, target_path) for report in data.get("Reports") or []]


class KubelinterScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Red Hat Kube-linter."""

    name: str = "kubelinter"
    binary_name: str = BIN_KUBELINTER
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # kube-linter reads `.kube-linter.yaml` from its working directory without `--config`.
    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = (
        ScannerConfigFile("--config", "kube-linter.yaml", CONST_REVIEW_SCAN_KUBELINTER_CONFIG),
    )

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking Kube-linter."""
        target_abs = target_path.resolve() if target_path.exists() else target_path
        return build_kubelinter_cmd(target_abs)

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


def run_kubelinter_scan(
    target: Path = DEFAULT_CURRENT_PATH, *, isolated: bool = False
) -> ScanOutcome:
    """Execute Kube-linter scanner and return scan outcome; `isolated` for a review (#972)."""
    scanner = KubelinterScanner()
    return scanner.scan(target, isolated=isolated)


__all__ = [
    "KubelinterScanner",
    "parse_kubelinter_json",
    "run_kubelinter_scan",
]
