"""Derailed Popeye Kubernetes cluster health and resource sanitizer integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_POPEYE, build_popeye_cmd
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome

logger = logging.getLogger(__name__)


_LEVEL_TO_SEV = {0: "INFO", 1: "LOW", 2: "MEDIUM", 3: "HIGH"}


def _parse_single_popeye_issue(sanitizer_name: str, res_id: str, issue: dict[str, Any]) -> Finding:
    """Construct Finding from single Popeye issue entry."""
    msg = issue.get("message") or f"Resource health issue in {res_id}"
    lvl_raw = issue.get("level")
    lvl: int = lvl_raw if isinstance(lvl_raw, int) else 2
    sev = _LEVEL_TO_SEV.get(lvl, "MEDIUM")
    return Finding(
        severity=sev,
        location=f"k8s:{sanitizer_name}/{res_id}",
        title=f"[{sanitizer_name.upper()}] Cluster Sanitizer Finding",
        description=msg,
        fix=f"Review and adjust Kubernetes specification for {res_id}",
        confidence_score=None,
    )


def _parse_sanitizer_findings(sanitizer: dict[str, Any]) -> list[Finding]:
    """Extract findings from a single sanitizer entry."""
    sanitizer_name = sanitizer.get("sanitizer") or "cluster"
    issues = sanitizer.get("issues") or {}
    findings: list[Finding] = []
    for res_id, res_issues in issues.items():
        for issue in res_issues:
            findings.append(_parse_single_popeye_issue(sanitizer_name, res_id, issue))
    return findings


def parse_popeye_json(data: dict[str, Any]) -> list[Finding]:
    """Parse Popeye cluster audit JSON payload into Finding objects."""
    popeye_data = data.get("popeye") or data
    sanitizers = popeye_data.get("sanitizers") or []
    findings: list[Finding] = []
    for s in sanitizers:
        findings.extend(_parse_sanitizer_findings(s))
    return findings


class PopeyeScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Derailed Popeye cluster sanitizer."""

    name: str = "popeye"
    binary_name: str = BIN_POPEYE
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

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
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Popeye."""
        ctx = context if context and context != "current" else None
        return build_popeye_cmd(context=ctx)

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


def run_popeye_scan(
    namespace: str | None = None,
    context: str | None = None,
    save_output: bool = True,
) -> ScanOutcome:
    """Execute Popeye sanitizer and return scan outcome."""
    scanner = PopeyeScanner()
    effective_context = context or "current"
    return scanner.scan(Path.cwd(), namespace=namespace, context=effective_context)
