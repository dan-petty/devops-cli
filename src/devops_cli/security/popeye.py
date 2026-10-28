"""Derailed Popeye Kubernetes cluster health and resource sanitizer integration."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_POPEYE, build_popeye_cmd
from devops_cli.config.constants import CONST_POPEYE_RESOURCE_GROUPS, CONST_POPEYE_SCAN_DIR_PREFIX
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import KubeApiNetwork, ToolExecutor

logger = logging.getLogger(__name__)


_LEVEL_TO_SEV = {0: "INFO", 1: "LOW", 2: "MEDIUM", 3: "HIGH"}


def _named_context(context: str | None) -> str | None:
    """The context that a scan names, or None for the current context, which a scan names as
    `current` or not at all."""
    return context if context and context != "current" else None


def _popeye_finding(linter: str, resource: str, issue: dict[str, Any]) -> Finding:
    """One issue of a Popeye report as a Finding at its linter, its resource and, for an issue of
    one container, that container."""
    group = issue["group"]
    location = f"k8s:{linter}/{resource}"
    if group not in CONST_POPEYE_RESOURCE_GROUPS:
        location = f"{location}/{group}"
    message = issue["message"]
    return Finding(
        severity=_LEVEL_TO_SEV[issue["level"]],
        location=location,
        title=message,
        description=f"Popeye linter '{linter}' on {resource}: {message}",
        fix=f"Review and adjust Kubernetes specification for {resource}",
        confidence_score=None,
    )


def parse_popeye_json(data: dict[str, Any]) -> list[Finding]:
    """The findings of a Popeye 0.22 JSON report: one for each issue.

    `popeye.sections` holds one section for each linter. Its `issues` maps each resource,
    `<namespace>/<name>`, to the issues that Popeye found on it, each with `group`, `gvr`, `level`
    and `message`. A section with no issue holds none.
    """
    return [
        _popeye_finding(section["linter"], resource, issue)
        for section in data["popeye"]["sections"]
        for resource, issues in (section.get("issues") or {}).items()
        for issue in issues
    ]


class PopeyeScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Derailed Popeye cluster sanitizer."""

    name: str = "popeye"
    binary_name: str = BIN_POPEYE
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def __init__(self, tool_executor: ToolExecutor | None = None) -> None:
        """Start Popeye through `tool_executor`; without one, in the sandbox (#2132).

        Popeye selects the network profile `kube-api` (`tool_network`), which only the sandbox
        runs. A host that cannot start the sandbox runs no Popeye scan: the scan reports a coverage
        gap with the cause.
        """
        if tool_executor is None:
            from devops_cli.security.tool_executor import SandboxToolExecutor

            tool_executor = SandboxToolExecutor()
        super().__init__(tool_executor)

    def is_applicable(self, target_path: Path, **kwargs: Any) -> tuple[bool, str]:
        """Verify cluster context presence before invoking Popeye."""
        context = kwargs.get("context")
        if not context:
            return False, "Popeye requires a Kubernetes cluster context (--context)"
        return True, ""

    def build_command(
        self,
        target_path: Path,
        context: str | None = None,
        namespace: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Popeye over `namespace`, or every namespace."""
        return build_popeye_cmd(context=_named_context(context), namespace=namespace)

    def tool_network(self, context: str | None = None, **kwargs: Any) -> KubeApiNetwork:
        """The network profile `kube-api` for the context of the scan: Popeye reads the API server
        of that context, and no other network (#2132)."""
        from devops_cli.security.tool_executor import KubeApiNetwork

        return KubeApiNetwork(context=_named_context(context))

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw Popeye cluster JSON payload into Finding models."""
        if isinstance(data, dict):
            return parse_popeye_json(data)
        return []

    def dry_run_scan(self, target_path: Path, **kwargs: Any) -> list[Finding]:
        """Return simulated Popeye findings for dry-run validation."""
        return [
            Finding(
                severity="LOW",
                location="k8s:cluster/dry-run-node",
                title="[DRY-RUN] Simulated Popeye Kubernetes Cluster Scan",
                description="Popeye cluster sanitation simulation mode active.",
                fix="No action required (dry-run mode)",
                confidence_score=None,
            )
        ]


def run_popeye_scan(namespace: str | None = None, context: str | None = None) -> ScanOutcome:
    """Run Popeye over `namespace`, else over the namespace of the context, of the context
    `context`, else of the current context, and return the outcome of the scan.

    Popeye reads the cluster, not a tree. It runs in the sandbox with the network profile
    `kube-api`, from a new empty directory: the sandbox shows the tool the directory that a scan
    starts in, and Popeye needs no file there (#2132).
    """
    scanner = PopeyeScanner()
    with tempfile.TemporaryDirectory(prefix=CONST_POPEYE_SCAN_DIR_PREFIX) as empty:
        return scanner.scan(Path(empty), namespace=namespace, context=context or "current")
