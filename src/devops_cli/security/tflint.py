"""TFLint Terraform/OpenTofu static linter integration."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
from devops_cli.core.serialization import extract_json_block
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


def _inspect_tf_file_fallback(f: Path, rel_root: Path) -> list[Finding]:
    """Check single Terraform file for open CIDR blocks and exposed security groups."""
    findings: list[Finding] = []
    try:
        rel_str = str(f.relative_to(rel_root)) if f.is_relative_to(rel_root) else f.name
        content = f.read_text(encoding="utf-8", errors="replace")
        for idx, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            is_open_cidr = "0.0.0.0/0" in stripped and "cidr_blocks" in stripped
            is_sg_open = "0.0.0.0/0" in stripped and "aws_security_group" in content
            if is_open_cidr or is_sg_open:
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


@trace_span("security.tflint")
def run_tflint_scan(
    target_dir: Path,
    config_file: Path | None = None,
    timeout: float = DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
) -> list[Finding]:
    """Execute TFLint static analysis on target_dir and return normalized findings."""
    tflint_bin = shutil.which("tflint")
    if not tflint_bin:
        logger.debug("TFLint binary not found; running fallback inspection.")
        return _run_native_fallback_tf_lint(target_dir)

    cmd = [tflint_bin, "--format", "json"]
    if config_file and config_file.exists():
        cmd.extend(["--config", str(config_file)])

    try:
        cwd_dir = target_dir if target_dir.is_dir() else target_dir.parent
        proc = subprocess.run(
            cmd,
            cwd=str(cwd_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if not proc.stdout.strip():
            return []

        data = extract_json_block(proc.stdout)
        issues = data.get("issues", []) if isinstance(data, dict) else []
        return [_parse_tflint_issue(issue) for issue in issues]
    except Exception as exc:
        logger.debug("TFLint error: %s", exc)
        return _run_native_fallback_tf_lint(target_dir)
