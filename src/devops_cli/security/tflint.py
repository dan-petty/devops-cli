"""TFLint Terraform/OpenTofu static linter integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.telemetry import trace_span


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
        """Parse the one JSON object that `tflint --format json` writes into Finding models.

        The shape is that of `formatter/json.go` of tflint v0.65.0, and its severities are
        `error`, `warning` and `info` (`toSeverity` in `formatter/formatter.go`).
        """
        issues = data.get("issues", []) if isinstance(data, dict) else []
        return [_parse_tflint_issue(issue) for issue in issues]


@trace_span("security.tflint")
def run_tflint_scan(
    target_dir: Path,
    config_file: Path | None = None,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
) -> ScanOutcome:
    """Execute TFLint static analysis on target_dir and return scan outcome."""
    scanner = TflintScanner()
    return scanner.scan(target_dir, timeout=timeout, config_file=config_file)
