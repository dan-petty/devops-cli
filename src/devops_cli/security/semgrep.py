"""Semgrep Static AST Pattern Matcher security scanner integration."""

from __future__ import annotations

from itertools import batched
from pathlib import Path
from typing import Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_SEMGREP, build_semgrep_cmd
from devops_cli.config.constants import CONST_SEMGREP_EXCLUDED_EXTENSIONS
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_SEMGREP_REVIEW_BATCH_FILES,
)
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.dry_run.state import is_dry_run  # noqa: F401
from devops_cli.lang import MESSAGES
from devops_cli.security.base import (
    BaseSecurityScanner,
    MaterializedTargets,
    ScanOutcome,
    materialize_targets,
    merge_outcomes,
)
from devops_cli.security.sanitizer import mask_secrets

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


def _scannable_files(targets: list[Path]) -> list[Path]:
    """The files of a target list Semgrep scans: regular files with no excluded extension."""
    return [
        p
        for p in targets
        if p.is_file() and p.suffix.lower() not in CONST_SEMGREP_EXCLUDED_EXTENSIONS
    ]


def _files_command(names: list[str], config: str) -> list[str] | None:
    """The command that scans the named files; None when none is named."""
    if not names:
        return None
    return [BIN_SEMGREP, "scan", "--json", "--config", config, "--quiet", *names]


def _build_scan_command(
    target: Path | list[Path] | MaterializedTargets, config: str
) -> list[str] | None:
    """Construct subprocess command for materialized targets, a file list or a directory."""
    if isinstance(target, MaterializedTargets):
        return _files_command(target.names, config)
    if isinstance(target, list):
        return _files_command([str(p.resolve()) for p in _scannable_files(target)], config)

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


class SemgrepScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Semgrep static AST pattern matcher."""

    name: str = "semgrep"
    binary_name: str = BIN_SEMGREP
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def build_command(
        self,
        target_path: Path | list[Path] | MaterializedTargets,
        config: str = DEFAULT_SEMGREP_CONFIG,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Semgrep."""
        cmd = _build_scan_command(target_path, config)
        return cmd or []

    def parse_output(
        self, data: Any, target_path: Path | list[Path] | MaterializedTargets
    ) -> list[Finding]:
        """Parse raw Semgrep JSON payload into Finding models, each in the scanned tree."""
        if not isinstance(data, dict):
            return []
        if isinstance(target_path, MaterializedTargets):
            return parse_semgrep_json(_reported_at_origin(data, target_path))
        tgt_str = str(target_path) if isinstance(target_path, Path) else ""
        return parse_semgrep_json(data, target_path=tgt_str)

    def isolated_targets(
        self, target_path: Any, workdir: Path, *, tree: Path | None = None, **kwargs: Any
    ) -> Any:
        """A review's targets, linked or copied from `tree` under `workdir` (#1079).

        Semgrep 1.178.0 takes a target that is a regular file under its working directory as
        it is; for any other it starts a `semgrep-core` process that walks the target's whole
        checkout, so a review's 333 targets named from outside ran past the timeout.
        """
        if tree is None or not isinstance(target_path, list):
            return target_path
        return materialize_targets(_scannable_files(target_path), tree, workdir)

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated Semgrep findings for dry-run simulation."""
        target_desc = _resolve_target_description(target_path)
        return [_build_dry_run_finding(target_desc)]


def _reported_at_origin(data: dict[str, Any], staged: MaterializedTargets) -> dict[str, Any]:
    """Semgrep's report with each result's path, as its command named it, in the scanned tree."""
    results = [
        {**res, "path": staged.origin(str(res.get("path") or ""))}
        for res in data.get("results") or []
        if isinstance(res, dict)
    ]
    return {**data, "results": results}


def _batch_outcome(outcome: ScanOutcome, batch: int, batches: int, files: int) -> ScanOutcome:
    """A batch's outcome; a failed one of several says which it was and how many files it lost."""
    if outcome.status != "failed" or batches == 1:
        return outcome
    reason = MESSAGES.scan.semgrep_batch_failed.format(
        batch=batch, batches=batches, files=files, reason=outcome.reason
    )
    labelled = ScanOutcome(outcome.status, outcome.findings, reason)
    labelled.started_utc, labelled.ended_utc = outcome.started_utc, outcome.ended_utc
    return labelled


def _scan_reviewed_files(
    scanner: SemgrepScanner, files: list[Path], tree: Path, config: str, timeout: float
) -> ScanOutcome:
    """Scan a review's files in batches, each isolated and under its own timeout (#1079)."""
    batches = [
        list(batch) for batch in batched(files, DEFAULT_SEMGREP_REVIEW_BATCH_FILES, strict=False)
    ] or [[]]
    outcomes = [
        scanner.scan(batch, timeout=timeout, isolated=True, config=config, tree=tree)
        for batch in batches
    ]
    return merge_outcomes(
        [
            _batch_outcome(outcome, index, len(batches), len(batch))
            for index, (outcome, batch) in enumerate(zip(outcomes, batches, strict=True), 1)
        ]
    )


def run_semgrep_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    config: str = DEFAULT_SEMGREP_CONFIG,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    *,
    reviewed_tree: Path | None = None,
) -> ScanOutcome:
    """Execute Semgrep AST pattern scanner and return scan outcome; `reviewed_tree` for a review.

    A review's scan is isolated (#972): Semgrep runs from a temporary directory, takes its rules
    from `--config` alone, and finds there only its targets, linked or copied from the reviewed
    tree at their paths in it, so it names each `./<path>` relative to its working directory and
    takes none as an option or its stdin (#1079). It applies no `.semgrepignore` to a file named
    on its command line. The targets are scanned in
    batches of `DEFAULT_SEMGREP_REVIEW_BATCH_FILES`, each under its own timeout.
    """
    scanner = SemgrepScanner()
    if reviewed_tree is None:
        return scanner.scan(target, timeout=timeout, config=config)
    files = _scannable_files(target if isinstance(target, list) else [target])
    return _scan_reviewed_files(scanner, files, reviewed_tree, config, timeout)
