"""PyCQA Bandit static Python security scanner integration."""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_BANDIT
from devops_cli.config.constants import CONST_BANDIT_INI_NAME, CONST_REVIEW_SCAN_BANDIT_INI
from devops_cli.config.defaults import (
    DEFAULT_BANDIT_SEVERITY,
    DEFAULT_CURRENT_PATH,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.security.base import BaseSecurityScanner, ScannerConfigFile, ScanOutcome


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


def _ini_names_targets(ini: Path) -> bool:
    """Whether Bandit's `ini` file names the targets to scan, read as Bandit reads it.

    Bandit takes a file it cannot read or parse as no file, and one that names no targets, as
    its documented example does, leaves them to the command line; given none, Bandit exits 2.
    """
    config = configparser.ConfigParser()
    try:
        config.read(ini, encoding="utf-8")
        return bool(config.get("bandit", "targets", fallback=""))
    except configparser.Error, UnicodeDecodeError:
        return False


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
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # Bandit reads a `.bandit` file it finds under a directory target unless `--ini` names one.
    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = (
        ScannerConfigFile("--ini", CONST_BANDIT_INI_NAME, CONST_REVIEW_SCAN_BANDIT_INI),
    )

    def scan(
        self,
        target_path: Any,
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
        *,
        isolated: bool = False,
        **kwargs: Any,
    ) -> ScanOutcome:
        """Scan as every scanner does; only an unisolated scan reads the tree's own `.bandit`.

        A review's scan is isolated and takes nothing from the tree under review (#972).
        """
        return super().scan(
            target_path, timeout, isolated=isolated, tree_config=not isolated, **kwargs
        )

    def build_command(
        self,
        target_path: Path | list[Path],
        severity_level: str = DEFAULT_BANDIT_SEVERITY,
        *,
        tree_config: bool = False,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Bandit.

        `-q` keeps stdout to the JSON report: past 50 files Bandit draws a progress bar there.

        A directory whose own `.bandit` names its targets, scanned with `tree_config`, is scanned
        as that file says, as the tree's own `bandit -r --ini .bandit` is: Bandit runs from the
        directory, takes its targets from the file and walks each directory among them, and the
        tree's `# nosec` markers hold. On this repository that is the run `devops ci security`
        makes, so the code-scanning upload reports what the gate fails on. Any other scan, such as
        one of a tree whose `.bandit` names no targets, names its targets and ignores `# nosec`,
        which a review's admission judges itself (#871).
        """
        threshold = ["--severity-level", severity_level.lower()]
        output = ["-q", *threshold, "-f", "json"]

        if isinstance(target_path, list):
            valid_files = [str(p.resolve()) for p in target_path if p.exists() and p.is_file()]
            if not valid_files:
                return []
            return [self.binary_name, *valid_files, "--ignore-nosec", *output]

        if not target_path.exists():
            return []
        target_abs = target_path.resolve()
        if target_abs.is_file():
            return [self.binary_name, str(target_abs), "--ignore-nosec", *output]

        tree_ini = target_abs / CONST_BANDIT_INI_NAME
        if tree_config and _ini_names_targets(tree_ini):
            return [self.binary_name, "-r", "--ini", str(tree_ini), *output]

        return [
            self.binary_name,
            "-r",
            str(target_abs),
            "--exclude",
            ".venv,venv,node_modules,.data,repos,.git",
            "--ignore-nosec",
            *output,
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


def run_bandit_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    severity_level: str = DEFAULT_BANDIT_SEVERITY,
    *,
    isolated: bool = False,
) -> ScanOutcome:
    """Execute Bandit Python security scanner subprocess and return scan outcome; `isolated` for
    a review (#972)."""
    scanner = BanditScanner()
    return scanner.scan(target, isolated=isolated, severity_level=severity_level)
