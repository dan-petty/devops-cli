"""Mypy static Python type checker security and review scanner integration (#873)."""

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_MYPY
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import main_worktree_root
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.security.normalization import normalize_severity

_MYPY_LINE_RE = re.compile(
    r"^(?P<path>[^:\n]+):(?P<line>\d+)(?::(?P<col>\d+))?: (?P<sev>[^:\n]+): (?P<msg>.+?)(?:  \[(?P<code>[^\]]+)\])?$"
)


def hash_file(file_path: Path) -> str | None:
    """Compute sha256 hexadecimal hash of a file if it exists."""
    if not file_path.is_file():
        return None
    try:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    except OSError:
        return None


def verify_uv_lock_match(worktree: Path, checkout: Path) -> bool:
    """Verify that worktree and checkout have identical uv.lock hashes."""
    wt_hash = hash_file(worktree / "uv.lock")
    co_hash = hash_file(checkout / "uv.lock")
    return wt_hash is not None and co_hash is not None and wt_hash == co_hash


def parse_mypy_line(line: str, default_path: str = "") -> Finding | None:
    """Parse a single mypy console output line into a Finding object."""
    match = _MYPY_LINE_RE.match(line.strip())
    if not match:
        return None

    path_str = match.group("path") or default_path or "workspace"
    line_num = match.group("line")
    sev_raw = match.group("sev").strip().lower()
    if sev_raw == "note":
        return None

    msg = match.group("msg").strip()
    code = match.group("code") or "type-check"

    sev = normalize_severity(sev_raw)
    loc = f"{path_str}:{line_num}"

    return Finding(
        severity=sev,
        location=loc,
        title=f"[{code}] {msg}",
        description=f"mypy type error {code} at {loc}: {msg}",
        fix=f"Resolve typing conflict for {code}",
        confidence_score=None,
    )


def parse_mypy_output(raw_output: str, default_path: str = "") -> list[Finding]:
    """Parse complete mypy text output into a list of Finding objects."""
    findings: list[Finding] = []
    for line in raw_output.splitlines():
        finding = parse_mypy_line(line, default_path)
        if finding is not None:
            findings.append(finding)
    return findings


class MypyScanner(BaseSecurityScanner):
    """Declarative scanner adapter for mypy static type checking."""

    name: str = "mypy"
    binary_name: str = BIN_MYPY
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def build_command(self, target_path: Path | list[Path], **kwargs: Any) -> list[str]:
        """Build argument command list for invoking mypy."""
        cmd = [self.binary_name, "--no-error-summary"]
        if isinstance(target_path, list):
            valid_files = [str(p.resolve()) for p in target_path if p.exists() and p.is_file()]
            if not valid_files:
                return []
            return [*cmd, *valid_files]

        if not target_path.exists():
            return []
        return [*cmd, str(target_path.resolve())]

    def parse_output(self, data: Any, target_path: Path | list[Path]) -> list[Finding]:
        """Parse raw mypy text output into Finding objects."""
        if not isinstance(data, str):
            return []
        tgt_str = str(target_path) if isinstance(target_path, Path) else ""
        return parse_mypy_output(data, default_path=tgt_str)

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated mypy findings for dry-run validation."""
        target_str = (
            str(target_path[0])
            if isinstance(target_path, list) and target_path
            else str(target_path)
        )
        return [
            Finding(
                severity="HIGH",
                location=f"{target_str}:1",
                title="[assignment] [DRY-RUN] Incompatible types in assignment",
                description="mypy type validation dry-run simulation mode active.",
                fix="Resolve type mismatch (dry-run mode)",
                confidence_score=None,
            )
        ]


def run_mypy_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    *,
    tree: Path | None = None,
    checkout_root: Path | None = None,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
) -> ScanOutcome:
    """Run mypy on changed modules with project config and uv.lock environment validation."""
    effective_tree = tree if tree is not None else Path.cwd()
    effective_checkout = (
        checkout_root if checkout_root is not None else main_worktree_root(effective_tree)
    )

    # Environment check: uv.lock hash match
    if not verify_uv_lock_match(effective_tree, effective_checkout):
        return ScanOutcome(
            status="coverage_gap",
            findings=[],
            reason="worktree uv.lock hash does not match checkout; uv sync never runs on a reviewed tree",
        )

    # Environment isolation: python -I with checkout's .venv python and dedicated cache
    venv_python = effective_checkout / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.is_file() else sys.executable

    files: list[Path] = []
    if isinstance(target, list):
        files = [p for p in target if p.is_file() and p.suffix == ".py"]
    elif isinstance(target, Path) and target.is_file() and target.suffix == ".py":
        files = [target]
    elif isinstance(target, Path) and target.is_dir():
        files = [p for p in target.rglob("*.py") if p.is_file()]

    if not files:
        return ScanOutcome(status="no files", findings=[])

    config_file = effective_tree / "pyproject.toml"
    if not config_file.is_file():
        config_file = effective_checkout / "pyproject.toml"

    with tempfile.TemporaryDirectory(prefix="devops-mypy-cache-") as tmp_cache:
        cmd = [
            python_bin,
            "-I",
            "-m",
            "mypy",
            *(["--config-file", str(config_file.resolve())] if config_file.is_file() else []),
            "--cache-dir",
            tmp_cache,
            "--no-error-summary",
            *[str(f.resolve()) for f in files],
        ]
        proc = run_subprocess(cmd, cwd=effective_tree, check=False, timeout=timeout)
        raw_out = (proc.stdout or "") + (proc.stderr or "")
        findings = parse_mypy_output(raw_out, default_path=str(effective_tree))
        return ScanOutcome(status="ran", findings=findings)
