"""PyCQA Bandit static Python security scanner integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_BANDIT
from devops_cli.config.defaults import (
    DEFAULT_BANDIT_SEVERITY,
    DEFAULT_CURRENT_PATH,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _parse_single_bandit_result(res: dict[str, Any], target_path: str = "") -> Finding:
    """Parse an individual Bandit result entry into a Finding model."""
    test_id = res.get("test_id") or "BANDIT"
    test_name = res.get("test_name") or "security_issue"
    filename = res.get("filename") or target_path or "workspace"
    line_num = res.get("line_number")
    issue_text = res.get("issue_text") or "Security flaw detected by Bandit"
    sev = str(res.get("issue_severity") or "MEDIUM").upper()
    more_info = res.get("more_info") or ""

    loc = f"{filename}:{line_num}" if line_num is not None else filename
    fix_msg = f"Remediate {test_name} ({test_id})"
    if more_info:
        fix_msg += f". See {more_info}"

    return Finding(
        severity=sev,
        location=loc,
        title=f"[{test_id}] {issue_text}",
        description=f"Bandit {test_name} flaw detected at line {line_num}: {issue_text}",
        fix=fix_msg,
        confidence_score=None,
    )


def parse_bandit_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Bandit JSON output payload into Finding objects."""
    results = data.get("results") or []
    return [
        _parse_single_bandit_result(res, target_path) for res in results if isinstance(res, dict)
    ]


class BanditScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for PyCQA Bandit."""

    name: str = "bandit"
    binary_name: str = BIN_BANDIT

    def build_command(
        self,
        target_path: Path | list[Path],
        severity_level: str = DEFAULT_BANDIT_SEVERITY,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Bandit."""
        level_flag = "-ll" if severity_level.lower() == "medium" else "-lll"

        if isinstance(target_path, list):
            valid_files = [str(p.resolve()) for p in target_path if p.exists() and p.is_file()]
            if not valid_files:
                return []
            return [self.binary_name, *valid_files, level_flag, "-s", "B608", "-f", "json"]

        if not target_path.exists():
            return []
        target_abs = target_path.resolve()
        if target_abs.is_file():
            return [self.binary_name, str(target_abs), level_flag, "-s", "B608", "-f", "json"]

        return [
            self.binary_name,
            "-r",
            str(target_abs),
            "--exclude",
            ".venv,venv,node_modules,.data,repos,.git",
            level_flag,
            "-s",
            "B608",
            "-f",
            "json",
        ]

    def parse_output(self, data: Any, target_path: Path | list[Path]) -> list[Finding]:
        """Parse Bandit JSON data payload into normalized Finding objects."""
        if not isinstance(data, dict):
            return []
        tgt_str = str(target_path) if isinstance(target_path, Path) else ""
        return parse_bandit_json(data, target_path=tgt_str)

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated Bandit findings for dry-run validation."""
        target_str = (
            str(target_path[0])
            if isinstance(target_path, list) and target_path
            else str(target_path)
        )
        return [
            Finding(
                severity="HIGH",
                location=f"{target_str}:10",
                title="[B602] [DRY-RUN] Simulated Bandit Python Security Finding",
                description="Bandit static security audit simulation mode active.",
                fix="Remediate subprocess invocation (dry-run mode)",
                confidence_score=None,
            )
        ]


def _execute_bandit_subprocess(
    scanner: BanditScanner,
    cmd: list[str],
    target: Path | list[Path],
) -> list[Finding]:
    """Execute Bandit command and parse findings."""
    try:
        proc = run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, check=False)
        if proc.stdout:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return scanner.parse_output(data, target)
    except Exception as exc:
        logger.debug("Bandit scan execution skipped or failed: %s", exc)
    return []


def run_bandit_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    severity_level: str = DEFAULT_BANDIT_SEVERITY,
) -> list[Finding]:
    """Execute Bandit Python security scanner subprocess and return parsed findings."""
    scanner = BanditScanner()
    target_desc = str(target[0]) if isinstance(target, list) and target else str(target)
    with trace_span(
        "security.scan.bandit",
        attributes={"target": target_desc, "severity_level": severity_level},
    ) as span_h:
        if is_dry_run():
            return scanner.dry_run_scan(target)

        cmd = scanner.build_command(target, severity_level=severity_level)
        if not cmd:
            return []

        findings = _execute_bandit_subprocess(scanner, cmd, target)
        span_h.set_attribute("findings_count", len(findings))
        return findings
