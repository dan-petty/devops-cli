"""TFLint Terraform/OpenTofu static linter integration."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _run_native_fallback_tf_lint(target_dir: Path) -> list[Finding]:
    """Fallback static checks for Terraform files when tflint is not installed."""
    findings: list[Finding] = []
    resolved = target_dir.resolve()
    tf_files = list(resolved.rglob("*.tf")) if resolved.is_dir() else [resolved]

    for f in tf_files:
        if not f.is_file():
            continue
        try:
            rel_str = str(f.relative_to(resolved if resolved.is_dir() else resolved.parent))
            content = f.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                is_open_cidr = "0.0.0.0/0" in stripped and "cidr_blocks" in stripped
                is_sg_open = "0.0.0.0/0" in stripped and "aws_security_group" in content
                if is_open_cidr or is_sg_open:
                    findings.append(
                        Finding(
                            severity="HIGH",
                            location=f"{rel_str}:{idx}",
                            title="Unrestricted CIDR block in security group rule",
                            description="Security group allows unrestricted access (0.0.0.0/0).",
                            fix="Restrict CIDR blocks to specific trusted IP ranges.",
                        )
                    )
        except Exception as exc:
            logger.debug("Failed reading %s in tflint fallback: %s", f, exc)

    return findings


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
        proc = subprocess.run(
            cmd,
            cwd=str(target_dir if target_dir.is_dir() else target_dir.parent),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if not proc.stdout.strip():
            return []

        data = json.loads(proc.stdout)
        issues = data.get("issues", [])
        findings: list[Finding] = []

        for issue in issues:
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

            findings.append(
                Finding(
                    severity=severity,
                    location=f"{file_name}:{start_line}" if file_name else f":{start_line}",
                    title=f"[{rule_name}] {message}",
                    description=message,
                    fix="Update Terraform block to satisfy provider rule constraints.",
                )
            )

        return findings
    except Exception as exc:
        logger.debug("TFLint error: %s", exc)
        return _run_native_fallback_tf_lint(target_dir)
