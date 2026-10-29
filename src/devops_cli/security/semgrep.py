"""Semgrep Static AST Pattern Matcher security scanner integration."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from itertools import batched
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Final

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_SEMGREP, build_semgrep_cmd
from devops_cli.config.constants import (
    CONST_SEMGREP_EXCLUDED_DIRECTORIES,
    CONST_SEMGREP_EXCLUDED_EXTENSIONS,
)
from devops_cli.config.defaults import (
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_SEMGREP_REVIEW_BATCH_FILES,
)
from devops_cli.lang import MESSAGES
from devops_cli.security.base import (
    BaseSecurityScanner,
    MaterializedTargets,
    ScanOutcome,
    materialize_targets,
    merge_outcomes,
    relativize_scan_path,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.security.semgrep_registry import (
    CachedRuleset,
    cached_ruleset,
    is_registry_id,
    warn_of_old_cache,
)

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor

_SEMGREP_SEVERITY_MAP: dict[str, str] = {
    "ERROR": "HIGH",
    "WARNING": "MEDIUM",
    "INFO": "LOW",
    "INVENTORY": "INFO",
}


# The registry rules that a review's Semgrep scan leaves out, by rule id only, each with its
# reason (#1024). The rule text stays in the registry, whose licence does not let the repository
# copy it. Any other scan runs every rule of its config.
_REVIEW_EXCLUDED_RULES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "python.lang.security.audit.non-literal-import.non-literal-import": (
            "It flags each import of a name held in a variable. On this repository the names "
            "came from literals, static maps or `__getattr__`, and each of its findings in the "
            "labelled reviews was false."
        ),
        "python.lang.security.audit.exec-detected.exec-detected": (
            "It flags each `exec`. Its one finding in the labelled reviews of this repository, a "
            "test that runs a documented snippet of the repository, was false."
        ),
    }
)


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


def _parse_semgrep_result(
    res: dict[str, Any],
    default_path: str = "",
    scan_root: Path | str | None = None,
) -> Finding:
    """Convert a single Semgrep JSON result dictionary into a Finding model."""
    from devops_cli.review.rules_pack import normalize_pack_check_id

    check_id = normalize_pack_check_id(str(res.get("check_id") or "SEMGREP"))
    raw_path = str(res.get("path") or default_path or "workspace")
    path_str = relativize_scan_path(raw_path, scan_root) if scan_root else raw_path
    start_line = res.get("start", {}).get("line")
    end_line = res.get("end", {}).get("line")

    extra: dict[str, Any] = res.get("extra") or {}
    raw_msg = mask_secrets(str(extra.get("message") or MESSAGES.scan.semgrep_default_message))
    if raw_path and raw_path != path_str and raw_path in raw_msg:
        raw_msg = raw_msg.replace(raw_path, path_str)
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


def parse_semgrep_json(
    data: dict[str, Any],
    target_path: str = "",
    scan_root: Path | str | None = None,
) -> list[Finding]:
    """Parse Semgrep JSON output into canonical Finding models."""
    results = data.get("results") or []
    return [
        _parse_semgrep_result(res, default_path=target_path, scan_root=scan_root)
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


def rules_configs(
    config: str, ruleset: CachedRuleset | None, *, in_workdir: bool = False
) -> list[str]:
    """The `--config` values a scan of `config` takes besides the rule pack (#1144).

    A config that is no registry id is its own value. A registry id is read offline from its
    cached file `ruleset`, named as `./<file>` in the scan's working directory: the cache
    directory, or, `in_workdir`, a review's working directory that holds the ruleset's bytes.
    Semgrep returns plain rule ids for a config in its working directory and ids led by the
    dotted path of the directory for any other. A registry id with no cached file leaves the
    rule pack alone.
    """
    if not is_registry_id(config):
        return [config]
    if ruleset is None:
        return []
    return [os.path.join(os.curdir, ruleset.workdir_name if in_workdir else ruleset.path.name)]


def semgrep_scan_command(
    targets: Sequence[Path | str],
    configs: Sequence[str],
    exclude_paths: Sequence[str] = (),
    exclude_rules: Sequence[str] = (),
) -> list[str]:
    """The Semgrep scan of `targets` with `configs` and devops-cli's rule pack, which runs with
    whatever configs a scan names (#1144)."""
    from devops_cli.review.rules_pack import RULE_PACK_DIR

    return build_semgrep_cmd(targets, [*configs, str(RULE_PACK_DIR)], exclude_paths, exclude_rules)


def _files_command(
    names: list[str], configs: list[str], exclude_rules: Sequence[str] = ()
) -> list[str] | None:
    """The command that scans the named files; None when none is named."""
    return semgrep_scan_command(names, configs, exclude_rules=exclude_rules) if names else None


def _build_scan_command(
    target: Path | list[Path] | MaterializedTargets,
    config: str,
    ruleset: CachedRuleset | None = None,
) -> list[str] | None:
    """Construct subprocess command for materialized targets, a file list or a directory.

    Only a review's isolated scan materializes its targets, so only it leaves out the rules of
    `_REVIEW_EXCLUDED_RULES`."""
    if isinstance(target, MaterializedTargets):
        configs = rules_configs(config, ruleset, in_workdir=True)
        return _files_command(target.names, configs, tuple(_REVIEW_EXCLUDED_RULES))
    configs = rules_configs(config, ruleset)
    if isinstance(target, list):
        return _files_command([str(p.resolve()) for p in _scannable_files(target)], configs)

    if not target.exists():
        return None
    return semgrep_scan_command([target.resolve()], configs, CONST_SEMGREP_EXCLUDED_DIRECTORIES)


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


def _registry_rules_missing(outcome: ScanOutcome, config: str) -> ScanOutcome:
    """The outcome of a scan that ran on the rule pack alone for want of the cached registry
    ruleset `config`: a coverage gap that names the fetch command and keeps the files the scan
    left out. A gap that has a reason of its own keeps it before the fetch command, as when the
    host could not start the sandbox (#2096). A scan that did not run, as in a dry run, keeps its
    outcome."""
    if outcome.status not in ("ran", "coverage_gap"):
        return outcome
    missing = MESSAGES.review.registry_not_cached.format(ruleset=config)
    gap = ScanOutcome(
        "coverage_gap",
        outcome.findings,
        "; ".join(dict.fromkeys(reason for reason in (outcome.reason, missing) if reason)),
        outcome.unscanned,
    )
    gap.started_utc, gap.ended_utc = outcome.started_utc, outcome.ended_utc
    return gap


class SemgrepScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Semgrep static AST pattern matcher."""

    name: str = "semgrep"
    binary_name: str = BIN_SEMGREP
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    def scan(
        self,
        target_path: Any,
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
        *,
        isolated: bool = False,
        **kwargs: Any,
    ) -> ScanOutcome:
        """Scan with `config`, a registry id such as `p/default` read offline from the cached
        ruleset (#1144): `ruleset` when the caller passes the one it read, else the one this reads,
        with a warning on stderr when it is older than a day.

        With no cached ruleset the scan runs on devops-cli's rule pack alone, and its outcome is a
        coverage gap that names `devops review rules fetch`.
        """
        config = kwargs.get("config", DEFAULT_SEMGREP_CONFIG)
        ruleset = kwargs.pop("ruleset", None)
        if not is_registry_id(config):
            return super().scan(target_path, timeout, isolated=isolated, **kwargs)
        if ruleset is None:
            ruleset = cached_ruleset(config)
            if ruleset is not None:
                warn_of_old_cache(config, ruleset)
        outcome = super().scan(target_path, timeout, isolated=isolated, ruleset=ruleset, **kwargs)
        return outcome if ruleset else _registry_rules_missing(outcome, config)

    def ruleset_files(self, target_path: Any, cwd: Path, **kwargs: Any) -> tuple[Path, ...]:
        """The rule files a scan reads: devops-cli's rule pack, and each file that a `--config`
        names from `cwd`, among them the cached registry ruleset (#772).

        A review's scan reads the copy of the registry ruleset in its working directory. A config
        that is a URL or a directory names no file here.
        """
        from devops_cli.review.rules_pack import discover_pack_rules

        configs = rules_configs(
            kwargs.get("config", DEFAULT_SEMGREP_CONFIG),
            kwargs.get("ruleset"),
            in_workdir=isinstance(target_path, MaterializedTargets),
        )
        named = (Path(cwd, config) for config in configs)
        pack = (rule for rule, _ in discover_pack_rules().values())
        return (*pack, *(path for path in named if path.is_file()))

    def _resolve_cwd(self, target_path: Any, **kwargs: Any) -> Path:
        """The directory that holds the cached ruleset a scan reads, else the target's.

        Semgrep returns plain rule ids for a config in its working directory, so a scan outside a
        review runs from the cache directory and names every target by its absolute path. It
        still reads the target's own `.semgrepignore` and `.gitignore` (#1144).
        """
        ruleset = kwargs.get("ruleset")
        return ruleset.path.parent if ruleset else super()._resolve_cwd(target_path)

    def build_command(
        self,
        target_path: Path | list[Path] | MaterializedTargets,
        config: str = DEFAULT_SEMGREP_CONFIG,
        ruleset: CachedRuleset | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Semgrep."""
        cmd = _build_scan_command(target_path, config, ruleset)
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
        self,
        target_path: Any,
        workdir: Path,
        *,
        tree: Path | None = None,
        ruleset: CachedRuleset | None = None,
        **kwargs: Any,
    ) -> Any:
        """A review's targets, linked or copied from `tree` under `workdir` (#1079), and the
        cached registry ruleset `ruleset`, written there to be read as a local config (#1144).

        Semgrep 1.178.0 takes a target that is a regular file under its working directory as
        it is; for any other it starts a `semgrep-core` process that walks the target's whole
        checkout, so a review's 333 targets named from outside ran past the timeout. The ruleset
        is written first, under a name made of its digest, so that no file of the tree can take
        its place as the config. The file holds the bytes that were read and hashed, not the
        cached file, which a fetch can replace while the review runs.
        """
        if tree is None or not isinstance(target_path, list):
            return target_path
        if ruleset is not None:
            (workdir / ruleset.workdir_name).write_bytes(ruleset.body)
        return materialize_targets(_scannable_files(target_path), tree, workdir)

    def unscanned_files(self, data: Any, target_path: Any) -> dict[str, str]:
        """The files of a review that Semgrep's report does not list under `paths.scanned`.

        Semgrep scans a file it is named only when a loaded rule applies to its language, and
        lists the files it scanned. A report with no such list says nothing of the files. A scan
        of a directory names no file, so it can leave none out (#1144).
        """
        paths = data.get("paths") if isinstance(data, dict) else None
        scanned = paths.get("scanned") if isinstance(paths, dict) else None
        if not isinstance(target_path, MaterializedTargets) or not isinstance(scanned, list):
            return {}
        listed = {target_path.tree_path(str(path)) for path in scanned}
        return {
            name: MESSAGES.scan.semgrep_file_not_scanned
            for name in target_path.origins
            if name not in listed
        }

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated Semgrep findings for dry-run simulation."""
        target_desc = _resolve_target_description(target_path)
        return [_build_dry_run_finding(target_desc)]


def _sanitize_semgrep_origin_result(
    res: dict[str, Any],
    staged: MaterializedTargets,
) -> dict[str, Any]:
    """Relativize a Semgrep result path and message to the scanned tree."""
    orig_p = str(res.get("path") or "")
    rel_p = staged.tree_path(orig_p)
    updated = {**res, "path": rel_p}
    extra = res.get("extra")
    if isinstance(extra, dict) and orig_p and orig_p != rel_p:
        msg = extra.get("message")
        if isinstance(msg, str) and orig_p in msg:
            updated["extra"] = {**extra, "message": msg.replace(orig_p, rel_p)}
    return updated


def _reported_at_origin(data: dict[str, Any], staged: MaterializedTargets) -> dict[str, Any]:
    """Semgrep's report with each result's path, as its command named it, in the scanned tree."""
    results = [
        _sanitize_semgrep_origin_result(res, staged)
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
    scanner: SemgrepScanner,
    files: list[Path],
    tree: Path,
    config: str,
    ruleset: CachedRuleset | None,
    timeout: float,
) -> ScanOutcome:
    """Scan a review's files in batches, each isolated and under its own timeout (#1079)."""
    batches = [
        list(batch) for batch in batched(files, DEFAULT_SEMGREP_REVIEW_BATCH_FILES, strict=False)
    ] or [[]]
    outcomes = [
        scanner.scan(
            batch, timeout=timeout, isolated=True, config=config, tree=tree, ruleset=ruleset
        )
        for batch in batches
    ]
    return merge_outcomes(
        [
            _batch_outcome(outcome, index, len(batches), len(batch))
            for index, (outcome, batch) in enumerate(zip(outcomes, batches, strict=True), 1)
        ]
    )


def run_semgrep_scan(
    target: Path | list[Path],
    config: str = DEFAULT_SEMGREP_CONFIG,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    *,
    reviewed_tree: Path | None = None,
    ruleset: CachedRuleset | None = None,
    tool_executor: ToolExecutor | None = None,
) -> ScanOutcome:
    """Execute Semgrep AST pattern scanner and return scan outcome; `reviewed_tree` for a review.

    A registry-id `config` such as `p/default` is read offline from its cached ruleset (#1144):
    `ruleset` when the caller passes the one it read, else the one the scan reads. With none the
    scan runs on devops-cli's rule pack alone, and its outcome is a coverage gap that names
    `devops review rules fetch`.

    A review's scan is isolated (#972): Semgrep runs from a temporary directory, takes its rules
    from `--config` alone, and finds there only its targets, linked or copied from the reviewed
    tree at their paths in it, so it names each `./<path>` relative to its working directory and
    takes none as an option or its stdin (#1079). It applies no `.semgrepignore` to a file named
    on its command line. The targets are scanned in
    batches of `DEFAULT_SEMGREP_REVIEW_BATCH_FILES`, each under its own timeout.
    """
    scanner = SemgrepScanner(tool_executor)
    if reviewed_tree is None:
        return scanner.scan(target, timeout=timeout, config=config, ruleset=ruleset)
    files = _scannable_files(target if isinstance(target, list) else [target])
    return _scan_reviewed_files(scanner, files, reviewed_tree, config, ruleset, timeout)
