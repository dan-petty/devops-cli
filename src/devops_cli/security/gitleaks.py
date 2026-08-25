"""Gitleaks Sub-Millisecond Secret Pre-Filter scanner integration."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import build_gitleaks_cmd
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

# Native high-precision fallback patterns for secrets when gitleaks binary is not in PATH
_FALLBACK_SECRET_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "AWS Access Key ID",
        "HIGH",
        re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
    ),
    (
        "GitHub Personal Access Token",
        "CRITICAL",
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,255}"),
    ),
    (
        "OpenAI API Key",
        "CRITICAL",
        re.compile(r"sk-[A-Za-z0-9-_]{32,128}"),
    ),
    (
        "Private Key Block",
        "CRITICAL",
        re.compile(r"-----BEGIN\s+(?:RSA|OPENSSH|EC|DSA|PGP|ENCRYPTED)?\s*PRIVATE KEY-----"),
    ),
    (
        "Slack Token",
        "HIGH",
        re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*"),
    ),
    (
        "Stripe API Key",
        "HIGH",
        re.compile(r"(?:sk|rk)_(?:test|live)_[0-9a-zA-Z]{24,99}"),
    ),
)


def _scan_file_native_secrets(file_path: Path) -> list[Finding]:
    """Fallback scanner using built-in high-precision secret patterns."""
    findings: list[Finding] = []
    if not file_path.exists() or not file_path.is_file():
        return findings

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.debug("Failed reading %s for native secret scan: %s", file_path, exc)
        return findings

    for line_idx, line in enumerate(content.splitlines(), start=1):
        for desc, sev, pattern in _FALLBACK_SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        severity=sev,
                        location=f"{file_path}:{line_idx}",
                        title=f"[GITLEAKS] Secret detected: {desc}",
                        description=(
                            f"Potential uncommitted {desc} pattern identified at line {line_idx}."
                        ),
                        fix=(
                            "Revoke and rotate secret immediately. "
                            "Move credentials to OS Keyring or environment variables."
                        ),
                        confidence_score=None,
                    )
                )
    return findings


def parse_gitleaks_json(data: list[dict[str, Any]]) -> list[Finding]:
    """Parse Gitleaks JSON report into canonical Finding models."""
    findings: list[Finding] = []
    for item in data:
        rule_id = item.get("RuleID") or item.get("Description") or "secret"
        desc = item.get("Description") or rule_id
        file_path = item.get("File") or "workspace"
        start_line = item.get("StartLine") or item.get("Line")
        secret_match = item.get("Match") or ""
        masked_secret = secret_match[:4] + "..." if len(secret_match) > 4 else "***"

        loc = f"{file_path}:{start_line}" if start_line else file_path
        is_critical = any(
            k in rule_id.lower() for k in ("key", "token", "pat", "secret", "password", "cred")
        )
        findings.append(
            Finding(
                severity="CRITICAL" if is_critical else "HIGH",
                location=loc,
                title=f"[GITLEAKS:{rule_id}] {desc}",
                description=(f"Gitleaks detected secret match ({masked_secret}) at {loc}: {desc}"),
                fix=(
                    "Remove plaintext credentials from source control "
                    "and store securely in OS Keyring."
                ),
                confidence_score=None,
            )
        )
    return findings


def run_gitleaks_scan(
    target: Path | list[Path] = Path("."),
    no_git: bool = True,
) -> list[Finding]:
    """Execute Gitleaks secret scanner subprocess or fallback pattern scan."""
    target_desc = str(target[0]) if isinstance(target, list) and target else str(target)

    with trace_span(
        "security.scan.gitleaks",
        attributes={"target": target_desc},
    ) as span_h:
        if is_dry_run():
            target_str = str(target[0]) if isinstance(target, list) and target else str(target)
            return [
                Finding(
                    severity="CRITICAL",
                    location=f"{target_str}:1",
                    title="[GITLEAKS:simulated-secret] [DRY-RUN] Simulated Secret Detection",
                    description="Gitleaks secret pre-filter simulation mode active.",
                    fix="Revoke simulated test secret (dry-run mode)",
                    confidence_score=None,
                )
            ]

        # Determine target file list or directory
        files_to_scan: list[Path] = []
        if isinstance(target, list):
            files_to_scan = [p for p in target if p.exists() and p.is_file()]
        elif target.exists():
            if target.is_file():
                files_to_scan = [target]
            else:
                files_to_scan = [
                    p
                    for p in target.rglob("*")
                    if p.is_file() and not any(part.startswith(".") for part in p.parts)
                ]

        # Try executing CLI binary
        cmd = build_gitleaks_cmd(target if isinstance(target, Path) else target[0], no_git=no_git)
        try:
            proc = run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, check=False)
            if proc.stdout and proc.stdout.strip().startswith(("[", "{")):
                data = json.loads(proc.stdout)
                if isinstance(data, list):
                    parsed = parse_gitleaks_json(data)
                    span_h.set_attribute("findings_count", len(parsed))
                    return parsed
        except FileNotFoundError, OSError, subprocess.SubprocessError:
            pass
        except Exception as exc:
            logger.debug("Gitleaks execution skipped or failed: %s", exc)

        # Fallback to native regex scanner across targets
        findings: list[Finding] = []
        for fp in files_to_scan:
            findings.extend(_scan_file_native_secrets(fp))

        span_h.set_attribute("findings_count", len(findings))
        return findings
