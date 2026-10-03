"""TFLint Terraform/OpenTofu static linter integration."""

from __future__ import annotations

import logging
import shutil  # noqa: F401
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _build_unrestricted_cidr_finding(rel_str: str, idx: int) -> Finding:
    """Build finding for unrestricted CIDR block."""
    return Finding(
        severity="HIGH",
        location=f"{rel_str}:{idx}",
        title="Unrestricted CIDR block in security group rule",
        description="Security group allows unrestricted access (0.0.0.0/0).",
        fix="Restrict CIDR blocks to specific trusted IP ranges.",
    )


def _is_security_context_line(lower_line: str) -> bool:
    """Return True if line indicates security group or ingress rule context."""
    return any(
        kw in lower_line
        for kw in (
            "security_group",
            "ingress",
            "aws_security_group",
            "azurerm_network_security_rule",
            "google_compute_firewall",
        )
    )


class _TfBlockContext:
    """Tracks HCL security group and CIDR block nesting context across lines."""

    def __init__(self) -> None:
        self.in_security: bool = False
        self.in_cidr: bool = False
        self.sec_brace_depth: int = 0
        self.brace_depth: int = 0

    def update(self, line: str, lower_line: str) -> bool:
        """Update context from line and return True if 0.0.0.0/0 matches unrestricted rule."""
        if _is_security_context_line(lower_line):
            self.in_security = True
            self.sec_brace_depth = self.brace_depth

        if "cidr_blocks" in lower_line or "cidr" in lower_line:
            self.in_cidr = True

        matches = "0.0.0.0/0" in line and (self.in_cidr or self.in_security or "cidr" in lower_line)

        self.brace_depth += line.count("{") - line.count("}")
        if "]" in line:
            self.in_cidr = False
        if self.brace_depth <= self.sec_brace_depth:
            self.in_security = False

        return matches


def _inspect_tf_file_fallback(f: Path, rel_root: Path) -> list[Finding]:
    """Check single Terraform file for open CIDR blocks and exposed security groups."""
    findings: list[Finding] = []
    try:
        rel_str = str(f.relative_to(rel_root)) if f.is_relative_to(rel_root) else f.name
        ctx = _TfBlockContext()
        with f.open("r", encoding="utf-8", errors="replace") as fp:
            for idx, line in enumerate(fp, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "//")):
                    continue
                if ctx.update(stripped, stripped.lower()):
                    findings.append(_build_unrestricted_cidr_finding(rel_str, idx))
    except Exception as exc:
        logger.debug("Failed reading %s in tflint fallback: %s", f, exc)
    return findings


def _run_native_fallback_tf_lint(target_dir: Path) -> list[Finding]:
    """Fallback static checks for Terraform files when tflint is not installed."""
    findings: list[Finding] = []
    if target_dir.is_symlink():
        return findings

    resolved = target_dir.resolve()
    if resolved.is_dir():
        tf_files = [p for p in resolved.rglob("*.tf") if not p.is_symlink()]
    else:
        tf_files = [resolved] if not resolved.is_symlink() else []
    rel_root = resolved if resolved.is_dir() else resolved.parent

    for f in tf_files:
        if f.is_file() and not f.is_symlink():
            findings.extend(_inspect_tf_file_fallback(f, rel_root))

    return findings


def _parse_tflint_issue(issue: dict[str, Any]) -> Finding:
    """Transform single TFLint issue JSON object into a normalized Finding."""
    rule_name = issue.get("rule", {}).get("name", "terraform-lint")
    message = issue.get("message", "Lint warning")
    range_info = issue.get("range", {})
    file_name = range_info.get("filename", "")
    start_line = range_info.get("start", {}).get("line", 1)
    rule_severity = issue.get("rule", {}).get("severity", "WARNING").upper()

    severity = "MEDIUM"
    if rule_severity == "ERROR":
        severity = "HIGH"
    elif rule_severity == "INFO":
        severity = "LOW"

    return Finding(
        severity=severity,
        location=f"{file_name}:{start_line}" if file_name else f":{start_line}",
        title=f"[{rule_name}] {message}",
        description=message,
        fix="Update Terraform block to satisfy provider rule constraints.",
    )


class TflintScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for TFLint Terraform linter."""

    name: str = "tflint"
    binary_name: str = "tflint"
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = True

    def build_command(
        self,
        target_path: Path,
        config_file: Path | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking TFLint."""
        cmd = [self.binary_name, "--format", "json"]
        if config_file and config_file.exists():
            cmd.extend(["--config", str(config_file)])
        return cmd

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw TFLint JSON payload into Finding models."""
        issues = data.get("issues", []) if isinstance(data, dict) else []
        return [_parse_tflint_issue(issue) for issue in issues]

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        """Execute native fallback static inspection for Terraform files."""
        return _run_native_fallback_tf_lint(target_path)


@trace_span("security.tflint")
def run_tflint_scan(
    target_dir: Path,
    config_file: Path | None = None,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
) -> ScanOutcome:
    """Execute TFLint static analysis on target_dir and return scan outcome."""
    scanner = TflintScanner()
    return scanner.scan(target_dir, timeout=timeout, config_file=config_file)
