"""Gitleaks Sub-Millisecond Secret Pre-Filter scanner integration."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import DefectClass, Finding
from devops_cli.config.commands import BIN_GITLEAKS, build_gitleaks_cmd
from devops_cli.config.constants import CONST_REVIEW_SCAN_GITLEAKS_CONFIG
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.core.repo import find_repo_root, is_ignored_by_git
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.security.base import (
    BaseSecurityScanner,
    ScannerConfigFile,
    ScanOutcome,
    merge_outcomes,
)

logger = logging.getLogger(__name__)


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
        # Every Gitleaks finding is a secret's exposure, whatever words its rule uses.
        category=DefectClass.SECRET_EXPOSURE.value,
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


def _is_safe_file(path: Path, root: Path | None) -> bool:
    """Validate that path exists, is a regular file, not a symlink, and contained within root."""
    if not path.exists() or not path.is_file() or path.is_symlink():
        return False
    if root is not None:
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                return False
        except OSError:
            return False
    return True


def _resolve_scan_files(target: Path | list[Path], *, ignore_tests: bool = False) -> list[Path]:
    """Resolve flat list of regular non-hidden files from target path or list."""
    if isinstance(target, list):
        candidates = [p for p in target if _is_safe_file(p, find_repo_root(p))]
    elif not target.exists():
        return []
    elif target.is_file():
        candidates = [target] if _is_safe_file(target, find_repo_root(target)) else []
    else:
        root = find_repo_root(target)
        candidates = [
            p
            for p in target.rglob("*")
            if _is_safe_file(p, root) and not is_ignored_by_git(root, p)
        ]
    if ignore_tests:
        return [p for p in candidates if not _is_test_file(p)]
    return candidates


class GitleaksScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Gitleaks secret detection."""

    name: str = "gitleaks"
    binary_name: str = BIN_GITLEAKS
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # Gitleaks reads `.gitleaks.toml` from the scanned source and `.gitleaksignore` from its
    # working directory unless each is named.
    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = (
        ScannerConfigFile("--config", "gitleaks.toml", CONST_REVIEW_SCAN_GITLEAKS_CONFIG),
        ScannerConfigFile("--gitleaks-ignore-path", ".gitleaksignore", ""),
    )

    def scan(
        self,
        target_path: Any,
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
        **kwargs: Any,
    ) -> ScanOutcome:
        """Scan a path, or each file of a list, since Gitleaks takes one source per run."""
        if not self._check_binary() and not self._is_dry_run():
            return ScanOutcome(
                "not installed", [], f"Binary '{self.binary_name}' not found on PATH"
            )
        if not isinstance(target_path, list):
            return super().scan(target_path, timeout=timeout, **kwargs)
        files = _resolve_scan_files(target_path)
        if not files:
            return ScanOutcome("not_applicable", [], "No scannable files in the target list")
        return merge_outcomes(
            [BaseSecurityScanner.scan(self, f, timeout=timeout, **kwargs) for f in files]
        )

    def build_command(
        self,
        target_path: Path | list[Path],
        no_git: bool = True,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Gitleaks."""
        cmd_target = target_path if isinstance(target_path, Path) else target_path[0]
        return build_gitleaks_cmd(cmd_target, no_git=no_git)

    def parse_output(self, data: Any, target_path: Path | list[Path]) -> list[Finding]:
        """Parse raw Gitleaks JSON findings into Finding models."""
        if isinstance(data, list):
            return parse_gitleaks_json(data)
        return []

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated Gitleaks findings for dry-run simulation."""
        target_desc = (
            str(target_path[0])
            if isinstance(target_path, list) and target_path
            else str(target_path)
        )
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


def run_gitleaks_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    no_git: bool = True,
    ignore_tests: bool = False,
    *,
    isolated: bool = False,
) -> ScanOutcome:
    """Execute Gitleaks secret scanner subprocess or fallback pattern scan; `isolated` for a
    review (#972)."""
    if isinstance(target, Path) and target.is_file() and ignore_tests and _is_test_file(target):
        return ScanOutcome("ran", [], "Test file ignored")

    if isinstance(target, list) and ignore_tests:
        target = [p for p in target if not _is_test_file(p)]

    outcome = GitleaksScanner().scan(target, isolated=isolated, no_git=no_git)
    if ignore_tests and outcome.findings:
        filtered = [
            f for f in outcome.findings if not _is_test_file(_extract_location_path(f.location))
        ]
        kept = ScanOutcome(outcome.status, filtered, outcome.reason)
        kept.started_utc, kept.ended_utc = outcome.started_utc, outcome.ended_utc
        return kept
    return outcome
