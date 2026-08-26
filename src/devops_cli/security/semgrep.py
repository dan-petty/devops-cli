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
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def parse_semgrep_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Semgrep JSON output into canonical Finding models."""
    findings: list[Finding] = []
    results = data.get("results") or []

    for res in results:
        check_id = res.get("check_id") or "SEMGREP"
        path_str = res.get("path") or target_path or "workspace"
        start_line = res.get("start", {}).get("line")
        end_line = res.get("end", {}).get("line")

        extra = res.get("extra") or {}
        raw_msg = extra.get("message") or "Code pattern flaw detected by Semgrep"
        raw_sev = str(extra.get("severity") or "MEDIUM").upper()

        sev_map = {
            "ERROR": "HIGH",
            "WARNING": "MEDIUM",
            "INFO": "LOW",
            "INVENTORY": "INFO",
        }
        sev = sev_map.get(raw_sev, raw_sev)

        if start_line is not None and end_line is not None and start_line != end_line:
            loc = f"{path_str}:{start_line}-{end_line}"
        elif start_line is not None:
            loc = f"{path_str}:{start_line}"
        else:
            loc = path_str

        metadata = extra.get("metadata") or {}
        cve = metadata.get("cve")
        owasp = metadata.get("owasp")

        fix_hints: list[str] = [f"Remediate {check_id}"]
        if cve:
            fix_hints.append(f"CVE: {cve}")
        if owasp:
            fix_hints.append(f"OWASP: {owasp}")

        findings.append(
            Finding(
                severity=sev,
                location=loc,
                title=f"[{check_id}] {raw_msg[:80]}",
                description=f"Semgrep AST flaw ({check_id}) at {loc}: {raw_msg}",
                fix=". ".join(fix_hints),
                confidence_score=None,
            )
        )

    return findings


def run_semgrep_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    config: str = DEFAULT_SEMGREP_CONFIG,
) -> list[Finding]:
    """Execute Semgrep AST pattern scanner subprocess and return parsed findings."""
    target_desc = str(target[0]) if isinstance(target, list) and target else str(target)

    with trace_span(
        "security.scan.semgrep",
        attributes={"target": target_desc, "config": config},
    ) as span_h:
        if is_dry_run():
            target_str = str(target[0]) if isinstance(target, list) and target else str(target)
            return [
                Finding(
                    severity="HIGH",
                    location=f"{target_str}:15",
                    title="[SEMGREP:generic-ast-flaw] [DRY-RUN] Simulated AST Pattern Match",
                    description="Semgrep AST pattern matching simulation mode active.",
                    fix="Remediate code pattern (dry-run mode)",
                    confidence_score=None,
                )
            ]

        if isinstance(target, list):
            valid_files = [str(p.resolve()) for p in target if p.exists() and p.is_file()]
            if not valid_files:
                return []
            cmd = [
                BIN_SEMGREP,
                "scan",
                "--json",
                "--config",
                config,
                "--quiet",
                *valid_files,
            ]
        else:
            if not target.exists():
                return []
            cmd = build_semgrep_cmd(
                target_path=target.resolve(),
                config=config,
                exclude_paths=[".venv", "venv", "node_modules", ".data", "repos", ".git"],
            )

        findings: list[Finding] = []
        try:
            proc = run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, check=False)
            if proc.stdout and proc.stdout.strip().startswith("{"):
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    tgt_str = str(target) if isinstance(target, Path) else ""
                    findings = parse_semgrep_json(data, target_path=tgt_str)
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            logger.debug("Semgrep CLI not available or execution failed: %s", exc)
        except Exception as exc:
            logger.debug("Semgrep scan parsing failed: %s", exc)

        span_h.set_attribute("findings_count", len(findings))
        return findings
