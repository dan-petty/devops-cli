"""Fairwinds Pluto deprecated Kubernetes API scanner integration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_PLUTO, build_pluto_cmd
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
)
from devops_cli.review.manifests import manifest_object_key
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.security.kubelinter import manifest_location

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


def _pluto_finding(item: dict[str, Any], target_path: str) -> Finding:
    """One item of a Pluto report as a Finding at its manifest and object.

    Pluto writes the object's `name` and `namespace` and its `api`: `kind`, `version`,
    `deprecated-in`, `removed-in` and `replacement-api`, which is empty when Kubernetes has no
    replacement. `filePath` is Pluto's working directory joined to the path that it read, so from
    another directory it climbs out with `..`. The object is `Kind/namespace/name`, or `Kind/name`
    without a namespace, as kube-linter names it.
    """
    api = item["api"]
    kind, version, name = api["kind"], api["version"], item["name"]
    namespace = item.get("namespace") or ""
    symbol = manifest_object_key(kind, name, namespace)
    removed = bool(item.get("removed"))
    status, release = (
        ("removed", api["removed-in"]) if removed else ("deprecated", api["deprecated-in"])
    )
    replacement = api.get("replacement-api") or ""
    manifest = os.path.normpath(item["filePath"]) if item.get("filePath") else target_path
    if replacement:
        moved = f"Use {replacement}."
        fix = f"Change apiVersion from {version} to {replacement}."
    else:
        moved = "Kubernetes has no replacement API."
        fix = f"Remove {kind} '{name}': no Kubernetes API replaces {version}."
    return Finding(
        severity="HIGH" if removed else "MEDIUM",
        location=f"{manifest_location(manifest)}:{symbol}",
        title=f"[{status.title()} API] {kind} '{name}' uses {version}",
        description=f"{kind} '{name}' uses {version}, which Kubernetes {status} in {release}. {moved}",
        fix=fix,
        confidence_score=None,
    )


def parse_pluto_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """The findings of a Pluto JSON report: one for each item. A report that finds nothing has no
    `items`."""
    return [_pluto_finding(item, target_path) for item in data.get("items") or []]


class PlutoScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Fairwinds Pluto deprecated K8s API detector."""

    name: str = "pluto"
    binary_name: str = BIN_PLUTO
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking Pluto."""
        from devops_cli.review.canary import (
            normalize_kubernetes_version,
            resolve_review_kubernetes_version,
        )

        target_abs = target_path.resolve() if target_path.exists() else target_path
        k8s_ver = normalize_kubernetes_version(
            kwargs.get("kubernetes_version")
        ) or resolve_review_kubernetes_version(tree=kwargs.get("tree"))
        target_versions = f"k8s={k8s_ver}" if k8s_ver else None
        return build_pluto_cmd(
            target_abs,
            binary_name=self.binary_name,
            target_versions=target_versions,
            cwd=kwargs.get("cwd"),
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


def run_pluto_scan(
    target: Path = DEFAULT_CURRENT_PATH,
    *,
    isolated: bool = False,
    tree: Path | None = None,
    kubernetes_version: str | None = None,
    require_version: bool = False,
    tool_executor: ToolExecutor | None = None,
) -> ScanOutcome:
    """Execute Pluto deprecated API scanner and return scan outcome; `isolated` for a review.

    Pluto reads no config or ignore file, so an isolated scan only runs it outside the tree.
    """
    from devops_cli.review.canary import (
        normalize_kubernetes_version,
        resolve_review_kubernetes_version,
    )

    k8s_ver = normalize_kubernetes_version(kubernetes_version) or resolve_review_kubernetes_version(
        tree=tree
    )
    if k8s_ver is None and (require_version or tree is not None):
        return ScanOutcome(
            status="coverage_gap",
            findings=[],
            reason="missing review.kubernetes_version in .devops/review.toml",
        )
    scanner = PlutoScanner(tool_executor)
    return scanner.scan(
        target,
        isolated=isolated,
        tree=tree,
        kubernetes_version=k8s_ver,
    )


__all__ = [
    "PlutoScanner",
    "parse_pluto_json",
    "run_pluto_scan",
]
