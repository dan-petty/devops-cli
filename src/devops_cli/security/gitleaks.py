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
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
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


def _scan_line_for_secrets(line: str, file_path: Path, line_idx: int) -> list[Finding]:
    """Test line against fallback secret patterns and return matching findings."""
    matches: list[Finding] = []
    fix_msg = "Revoke and rotate secret immediately. Move credentials to OS Keyring or environment variables."
    for desc, sev, pattern in _FALLBACK_SECRET_PATTERNS:
        if pattern.search(line):
            matches.append(
                Finding(
                    severity=sev,
                    location=f"{file_path}:{line_idx}",
                    title=f"[GITLEAKS] Secret detected: {desc}",
                    description=f"Potential uncommitted {desc} pattern identified at line {line_idx}.",
                    fix=fix_msg,
                    confidence_score=None,
                )
            )
    return matches


def _scan_file_native_secrets(file_path: Path) -> list[Finding]:
    """Fallback scanner using built-in high-precision secret patterns."""
    if not file_path.exists() or not file_path.is_file():
        return []

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.debug("Failed reading %s for native secret scan: %s", file_path, exc)
        return []

    findings: list[Finding] = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        findings.extend(_scan_line_for_secrets(line, file_path, line_idx))
    return findings


def _parse_single_gitleaks_item(item: dict[str, Any]) -> Finding:
    """Transform raw Gitleaks JSON item into a structured Finding model."""
    rule_id = str(item.get("RuleID") or item.get("Description") or "secret")
    desc = str(item.get("Description") or rule_id)
    file_path = str(item.get("File") or "workspace")
    start_line = item.get("StartLine") or item.get("Line")

    loc = f"{file_path}:{start_line}" if start_line else file_path
    is_critical = any(
        k in rule_id.lower() for k in ("key", "token", "pat", "secret", "password", "cred")
    )
    return Finding(
        severity="CRITICAL" if is_critical else "HIGH",
        location=loc,
        title=f"[GITLEAKS:{rule_id}] {desc}",
        description=f"Gitleaks detected secret rule pattern '{rule_id}' at {loc}: {desc}",
        fix="Remove plaintext credentials from source control and store securely in OS Keyring.",
        confidence_score=None,
    )


def parse_gitleaks_json(data: list[dict[str, Any]]) -> list[Finding]:
    """Parse Gitleaks JSON report into canonical Finding models."""
    return [_parse_single_gitleaks_item(item) for item in data]


def _extract_location_path(location: str) -> Path:
    """Extract normalized Path from canonical location string 'path/file.ext:line' or 'C:\\path\\file.ext:line'."""
    clean_loc = re.sub(r":\d+(?:-\d+)?$", "", location.strip()).replace("\\", "/")
    return Path(clean_loc)


def _is_test_file(path: Path | str) -> bool:
    """Check whether path represents a test file or resides within a test directory."""
    raw = str(path).replace("\\", "/")
    norm_path = Path(raw)
    name = norm_path.name.lower()
    if name.startswith("test_") or name.endswith(("_test.py", "_test.go", "_test.ts", "_test.js")):
        return True
    parts = {p.lower() for p in norm_path.parts}
    return bool({"tests", "test", "__tests__"}.intersection(parts))


def _resolve_scan_files(target: Path | list[Path], *, ignore_tests: bool = False) -> list[Path]:
    """Resolve flat list of regular non-hidden files from target path or list."""
    if isinstance(target, list):
        candidates = [p for p in target if p.exists() and p.is_file()]
    elif not target.exists():
        return []
    elif target.is_file():
        candidates = [target]
    else:
        candidates = [
            p
            for p in target.rglob("*")
            if p.is_file() and not any(part.startswith(".") for part in p.parts)
        ]
    if ignore_tests:
        return [p for p in candidates if not _is_test_file(p)]
    return candidates


def run_gitleaks_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    no_git: bool = True,
    ignore_tests: bool = False,
) -> list[Finding]:
    """Execute Gitleaks secret scanner subprocess or fallback pattern scan."""
    if isinstance(target, Path) and target.is_file() and ignore_tests and _is_test_file(target):
        return []

    target_desc = str(target[0]) if isinstance(target, list) and target else str(target)

    with trace_span("security.scan.gitleaks", attributes={"target": target_desc}) as span_h:
        if is_dry_run():
            return [
                Finding(
                    severity="CRITICAL",
                    location=f"{target_desc}:1",
                    title="[GITLEAKS:simulated-secret] [DRY-RUN] Simulated Secret Detection",
                    description="Gitleaks secret pre-filter simulation mode active.",
                    fix="Revoke simulated test secret (dry-run mode)",
                    confidence_score=None,
                )
            ]

        files_to_scan = _resolve_scan_files(target, ignore_tests=ignore_tests)
        cmd_target = target if isinstance(target, Path) else target[0]
        cmd = build_gitleaks_cmd(cmd_target, no_git=no_git)

        try:
            proc = run_subprocess(cmd, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, check=False)
            if proc.stdout and proc.stdout.strip().startswith(("[", "{")):
                data = json.loads(proc.stdout)
                if isinstance(data, list):
                    parsed = parse_gitleaks_json(data)
                    if ignore_tests:
                        parsed = [
                            f
                            for f in parsed
                            if not _is_test_file(_extract_location_path(f.location))
                        ]
                    span_h.set_attribute("findings_count", len(parsed))
                    return parsed

        except FileNotFoundError, OSError, subprocess.SubprocessError:
            pass
        except Exception as exc:
            logger.debug("Gitleaks execution skipped or failed: %s", exc)

        findings: list[Finding] = []
        for fp in files_to_scan:
            findings.extend(_scan_file_native_secrets(fp))

        span_h.set_attribute("findings_count", len(findings))
        return findings
