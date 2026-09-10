"""Semgrep Static AST Pattern Matcher security scanner integration."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_SEMGREP, build_semgrep_cmd
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run
from devops_cli.lang import MESSAGES
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


_SEMGREP_SEVERITY_MAP: dict[str, str] = {
    "ERROR": "HIGH",
    "WARNING": "MEDIUM",
    "INFO": "LOW",
    "INVENTORY": "INFO",
}


def _format_semgrep_location(path_str: str, start_line: int | None, end_line: int | None) -> str:
    """Format finding location string from line ranges."""
    if start_line is not None and end_line is not None and start_line != end_line:
        return f"{path_str}:{start_line}-{end_line}"
    if start_line is not None:
        return f"{path_str}:{start_line}"
    return path_str


def _build_semgrep_fix_hints(check_id: str, metadata: dict[str, Any]) -> str:
    """Construct remediation hint string from check ID and metadata."""
    hints: list[str] = [f"Remediate {check_id}"]
    cve = metadata.get("cve")
    if cve:
        hints.append(f"CVE: {cve}")
    owasp = metadata.get("owasp")
    if owasp:
        hints.append(f"OWASP: {owasp}")
    return ". ".join(hints)


def _parse_semgrep_result(res: dict[str, Any], default_path: str = "") -> Finding:
    """Convert a single Semgrep JSON result dictionary into a Finding model."""
    check_id = str(res.get("check_id") or "SEMGREP")
    path_str = str(res.get("path") or default_path or "workspace")
    start_line = res.get("start", {}).get("line")
    end_line = res.get("end", {}).get("line")

    extra: dict[str, Any] = res.get("extra") or {}
    raw_msg = mask_secrets(str(extra.get("message") or MESSAGES.scan.semgrep_default_message))
    raw_sev = str(extra.get("severity") or "MEDIUM").upper()
    sev = _SEMGREP_SEVERITY_MAP.get(raw_sev, raw_sev)

    loc = _format_semgrep_location(path_str, start_line, end_line)
    fix = _build_semgrep_fix_hints(check_id, extra.get("metadata") or {})

    return Finding(
        severity=sev,
        location=loc,
        title=f"[{check_id}] {raw_msg[:80]}",
        description=f"Semgrep AST flaw ({check_id}) at {loc}: {raw_msg}",
        fix=fix,
        confidence_score=None,
    )


def parse_semgrep_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Semgrep JSON output into canonical Finding models."""
    results = data.get("results") or []
    return [
        _parse_semgrep_result(res, default_path=target_path)
        for res in results
        if isinstance(res, dict)
    ]


def _resolve_target_description(target: Path | list[Path]) -> str:
    """Format human-readable target string for telemetry and reporting."""
    if isinstance(target, list) and target:
        return str(target[0])
    return str(target)


def _build_scan_command(target: Path | list[Path], config: str) -> list[str] | None:
    """Construct subprocess command for file list or directory target."""
    if isinstance(target, list):
        valid_files = [str(p.resolve()) for p in target if p.exists() and p.is_file()]
        if not valid_files:
            return None
        return [
            BIN_SEMGREP,
            "scan",
            "--json",
            "--config",
            config,
            "--quiet",
            *valid_files,
        ]

    if not target.exists():
        return None
    return build_semgrep_cmd(
        target_path=target.resolve(),
        config=config,
        exclude_paths=[
            ".venv",
            "venv",
            "node_modules",
            ".data",
            "repos",
            ".git",
        ],
    )


def _build_dry_run_finding(target_str: str) -> Finding:
    """Generate mock finding for dry-run simulation mode."""
    return Finding(
        severity="HIGH",
        location=f"{target_str}:15",
        title="[SEMGREP:generic-ast-flaw] [DRY-RUN] Simulated AST Pattern Match",
        description="Semgrep AST pattern matching simulation mode active.",
        fix="Remediate code pattern (dry-run mode)",
        confidence_score=None,
    )


def _execute_and_parse_semgrep(cmd: list[str], target_path: str = "") -> list[Finding]:
    """Execute Semgrep subprocess and parse JSON output."""
    try:
        proc = run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, check=False)
        if proc.stdout and proc.stdout.strip().startswith("{"):
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return parse_semgrep_json(data, target_path=target_path)
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        logger.debug("Semgrep CLI not available or execution failed: %s", exc)
    except Exception as exc:
        logger.debug("Semgrep scan parsing failed: %s", exc)
    return []


class SemgrepScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Semgrep static AST pattern matcher."""

    name: str = "semgrep"
    binary_name: str = BIN_SEMGREP

    def build_command(
        self,
        target_path: Path | list[Path],
        config: str = DEFAULT_SEMGREP_CONFIG,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Semgrep."""
        cmd = _build_scan_command(target_path, config)
        return cmd or []

    def parse_output(self, data: Any, target_path: Path | list[Path]) -> list[Finding]:
        """Parse raw Semgrep JSON payload into Finding models."""
        if isinstance(data, dict):
            tgt_str = str(target_path) if isinstance(target_path, Path) else ""
            return parse_semgrep_json(data, target_path=tgt_str)
        return []

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated Semgrep findings for dry-run simulation."""
        target_desc = _resolve_target_description(target_path)
        return [_build_dry_run_finding(target_desc)]


def run_semgrep_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    config: str = DEFAULT_SEMGREP_CONFIG,
) -> list[Finding]:
    """Execute Semgrep AST pattern scanner subprocess and return parsed findings."""
    scanner = SemgrepScanner()
    target_desc = _resolve_target_description(target)

    with trace_span(
        "security.scan.semgrep",
        attributes={"target": target_desc, "config": config},
    ) as span_h:
        if is_dry_run():
            return scanner.dry_run_scan(target)

        cmd = scanner.build_command(target, config=config)
        if not cmd:
            return []

        tgt_str = str(target) if isinstance(target, Path) else ""
        findings = _execute_and_parse_semgrep(cmd, target_path=tgt_str)
        span_h.set_attribute("findings_count", len(findings))
        return findings
