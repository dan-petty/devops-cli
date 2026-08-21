"""PyCQA Bandit static Python security scanner integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_BANDIT
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run

logger = logging.getLogger(__name__)

CONST_BANDIT_TIMEOUT_SECONDS = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS


def parse_bandit_json(data: dict[str, Any], target_path: str = "") -> list[Finding]:
    """Parse Bandit JSON output payload into Finding objects."""
    findings: list[Finding] = []
    results = data.get("results") or []

    for res in results:
        test_id = res.get("test_id") or "BANDIT"
        test_name = res.get("test_name") or "security_issue"
        filename = res.get("filename") or target_path or "workspace"
        line_num = res.get("line_number")
        issue_text = res.get("issue_text") or "Security flaw detected by Bandit"
        sev = str(res.get("issue_severity") or "MEDIUM").upper()
        conf = str(res.get("issue_confidence") or "MEDIUM").upper()
        more_info = res.get("more_info") or ""

        confidence_val = 0.95 if conf == "HIGH" else (0.85 if conf == "MEDIUM" else 0.7)

        loc = f"{filename}:{line_num}" if line_num is not None else filename
        fix_msg = f"Remediate {test_name} ({test_id})"
        if more_info:
            fix_msg += f". See {more_info}"

        findings.append(
            Finding(
                severity=sev,
                location=loc,
                title=f"[{test_id}] {issue_text}",
                description=f"Bandit {test_name} flaw detected at line {line_num}: {issue_text}",
                fix=fix_msg,
                confidence_score=confidence_val,
            )
        )

    return findings


def run_bandit_scan(
    target: Path = Path("."),
    severity_level: str = "medium",
) -> list[Finding]:
    """Execute Bandit Python security scanner subprocess and return parsed findings."""
    if is_dry_run():
        return [
            Finding(
                severity="HIGH",
                location=f"{target}:10",
                title="[B602] [DRY-RUN] Simulated Bandit Python Security Finding",
                description="Bandit static security audit simulation mode active.",
                fix="Remediate subprocess invocation (dry-run mode)",
                confidence_score=1.0,
            )
        ]

    if not target.exists():
        return []

    target_abs = target.resolve()
    level_flag = "-ll" if severity_level.lower() == "medium" else "-lll"

    if target_abs.is_file():
        cmd = [
            BIN_BANDIT,
            str(target_abs),
            level_flag,
            "-s",
            "B608",
            "-f",
            "json",
        ]
    else:
        cmd = [
            BIN_BANDIT,
            "-r",
            str(target_abs),
            "--exclude",
            f"{target_abs}/.venv,{target_abs}/venv,{target_abs}/node_modules,{target_abs}/.data",
            level_flag,
            "-s",
            "B608",
            "-f",
            "json",
        ]

    try:
        proc = run_subprocess(cmd, timeout=CONST_BANDIT_TIMEOUT_SECONDS, check=False)
        if proc.stdout:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return parse_bandit_json(data, target_path=str(target))
    except Exception as exc:
        logger.debug("Bandit scan execution skipped or failed: %s", exc)

    return []
