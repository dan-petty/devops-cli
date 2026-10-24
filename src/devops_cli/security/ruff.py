"""Astral Ruff static Python linter security and review scanner integration (#873)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_RUFF
from devops_cli.config.constants import (
    CONST_DEFAULT_REVIEW_ADVISORY_RULES,
    CONST_RUFF_CACHE_DIR_ENV,
    CONST_RUFF_CACHE_DIR_NAME,
    CONST_RUFF_CONFIG_FILE_NAMES,
    CONST_SARIF_LEVEL_TO_SEVERITY,
    CONST_SARIF_LEVEL_WARNING,
    CONST_SARIF_LEVELS,
)
from devops_cli.config.defaults import DEFAULT_CURRENT_PATH
from devops_cli.core.process import run_subprocess  # noqa: F401
from devops_cli.core.repo import resolve_data_path
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome, ToolCacheDir

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor


def _extract_physical_location(loc_dict: dict[str, Any]) -> tuple[str, int | None, int | None]:
    """Extract file path, start line, and end line from a SARIF physical location dict."""
    phys = loc_dict.get("physicalLocation")
    if not isinstance(phys, dict):
        return "", None, None
    uri = ""
    artifact = phys.get("artifactLocation")
    if isinstance(artifact, dict):
        uri = artifact.get("uri", "")
    region = phys.get("region")
    if isinstance(region, dict):
        start = region.get("startLine")
        end = region.get("endLine", start)
        return uri, start, end
    return uri, None, None


def _parse_sarif_result_to_finding(
    res: dict[str, Any],
    rules_by_id: dict[str, dict[str, Any]],
    default_path: str = "",
) -> Finding:
    """Parse a single SARIF result into a Finding object."""
    rule_id = res.get("ruleId") or "RUFF"
    rule_desc = rules_by_id.get(rule_id, {})
    message = res.get("message", {}).get("text") or "Ruff finding detected"

    uri, start_line, end_line = "", None, None
    locations = res.get("locations")
    if isinstance(locations, list) and locations and isinstance(locations[0], dict):
        uri, start_line, end_line = _extract_physical_location(locations[0])

    path_str = uri or default_path or "workspace"
    if start_line is not None and end_line is not None and start_line != end_line:
        loc = f"{path_str}:{start_line}-{end_line}"
    elif start_line is not None:
        loc = f"{path_str}:{start_line}"
    else:
        loc = path_str

    level = res.get("level")
    sev = (
        CONST_SARIF_LEVEL_TO_SEVERITY.get(level, "MEDIUM")
        if isinstance(level, str) and level in CONST_SARIF_LEVELS
        else CONST_SARIF_LEVEL_TO_SEVERITY[CONST_SARIF_LEVEL_WARNING]
    )

    help_uri = rule_desc.get("helpUri", "")
    fix_msg = f"Remediate {rule_id}"
    if help_uri:
        fix_msg += f". See {help_uri}"

    return Finding(
        severity=sev,
        location=loc,
        title=f"[{rule_id}] {message}",
        description=f"Ruff {rule_id}: {message}",
        fix=fix_msg,
        confidence_score=None,
    )


def parse_ruff_sarif(data: dict[str, Any], default_path: str = "") -> list[Finding]:
    """Parse Ruff SARIF payload into a list of Finding objects."""
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        return []
    run_obj = runs[0]
    if not isinstance(run_obj, dict):
        return []

    rules_by_id: dict[str, dict[str, Any]] = {}
    driver = run_obj.get("tool", {}).get("driver", {})
    if isinstance(driver, dict):
        for r in driver.get("rules", []):
            if isinstance(r, dict) and "id" in r:
                rules_by_id[r["id"]] = r

    results = run_obj.get("results") or []
    return [
        _parse_sarif_result_to_finding(res, rules_by_id, default_path)
        for res in results
        if isinstance(res, dict)
    ]


def _extract_line_from_location(location: str) -> int | None:
    """Extract line number from location string formatted as path:line or path:start-end."""
    parts = location.rsplit(":", 1)
    if len(parts) < 2:
        return None
    line_part = parts[1].split("-")[0]
    try:
        return int(line_part)
    except ValueError:
        return None


def _extract_path_from_location(location: str) -> str:
    """Extract file path from location string."""
    parts = location.rsplit(":", 1)
    if len(parts) == 2 and any(char.isdigit() for char in parts[1]):
        return parts[0]
    return location


def _finding_rule_id(finding: Finding) -> str:
    """Extract rule ID from finding title formatted as [RULE] ..."""
    if finding.title.startswith("[") and "]" in finding.title:
        return finding.title[1 : finding.title.index("]")]
    return ""


def _is_in_diff_hunks(
    path: str,
    line: int | None,
    diff_hunks: dict[str, list[tuple[int, int]]],
) -> bool:
    """Check if file line falls within any diff hunk for that file."""
    if line is None:
        return False
    hunks = diff_hunks.get(path) or []
    if not hunks:
        hunks = next((h for p, h in diff_hunks.items() if Path(p).name == Path(path).name), [])
    return any(start <= line <= end for start, end in hunks)


def _group_path_review_findings(
    advisory_findings: list[Finding],
) -> list[Finding]:
    """Group path review advisory findings by (rule, file)."""
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in advisory_findings:
        rule = _finding_rule_id(f)
        path = _extract_path_from_location(f.location)
        groups[(rule, path)].append(f)

    grouped_findings: list[Finding] = []
    for (rule, path), group in sorted(groups.items()):
        lines = [str(_extract_line_from_location(f.location) or 0) for f in group]
        first_line = lines[0] if lines else "1"
        grouped_findings.append(
            Finding(
                severity="LOW",
                location=f"{path}:{first_line}",
                title=f"[{rule}] {len(group)} advisory finding(s) in {path}",
                description=f"Ruff advisory rule {rule} detected {len(group)} occurrence(s) in {path} at line(s): {', '.join(lines)}",
                fix=f"Review and address {rule} advisory warnings in {path}",
                confidence_score=None,
            )
        )
    return grouped_findings


def filter_or_group_advisories(
    findings: list[Finding],
    advisory_rules: Sequence[str] = CONST_DEFAULT_REVIEW_ADVISORY_RULES,
    diff_hunks: dict[str, list[tuple[int, int]]] | None = None,
    *,
    is_branch_or_pr: bool = False,
) -> list[Finding]:
    """Filter advisory rules to diff hunks on PR/branch reviews, or group on path reviews."""
    advisory_set = set(advisory_rules)
    standard_findings: list[Finding] = []
    advisory_findings: list[Finding] = []

    for f in findings:
        rule = _finding_rule_id(f)
        if rule in advisory_set:
            advisory_findings.append(f)
        else:
            standard_findings.append(f)

    if not advisory_findings:
        return standard_findings

    if is_branch_or_pr and diff_hunks:
        kept_advisories = [
            f
            for f in advisory_findings
            if _is_in_diff_hunks(
                _extract_path_from_location(f.location),
                _extract_line_from_location(f.location),
                diff_hunks,
            )
        ]
        return [*standard_findings, *kept_advisories]

    if not is_branch_or_pr:
        grouped = _group_path_review_findings(advisory_findings)
        return [*standard_findings, *grouped]

    return standard_findings


def _ruff_cache_dir(tree: Path) -> Path:
    """The Ruff cache of the reviews of `tree`, in the data cache directory, as the mypy cache is.

    Ruff keys its entries by the package of each file, so the reviews of one tree read the entries
    of the reviews before. The directory of each tree is its own, so no tree writes the cache of
    another (#972).
    """
    from devops_cli.config.settings import load_settings

    key = hashlib.sha256(str(tree.resolve()).encode()).hexdigest()[:16]
    return resolve_data_path(load_settings().data.cache_dir) / CONST_RUFF_CACHE_DIR_NAME / key


class RuffScanner(BaseSecurityScanner):
    """Declarative security and lint scanner adapter for Astral Ruff."""

    name: str = "ruff"
    binary_name: str = BIN_RUFF
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # Ruff reads the config file nearest to each file it checks, whatever directory it starts in.
    config_names: ClassVar[tuple[str, ...]] = CONST_RUFF_CONFIG_FILE_NAMES
    config_search_upward: ClassVar[bool] = True

    def build_command(
        self,
        target_path: Path | list[Path],
        advisory_rules: Sequence[str] = CONST_DEFAULT_REVIEW_ADVISORY_RULES,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Ruff producing SARIF."""
        from devops_cli.review.canary import (
            parse_requires_python_target_version,
            resolve_ruff_target_version,
        )

        cmd = [self.binary_name, "check", "--output-format=sarif"]
        raw_target_ver = kwargs.get("target_version")
        target_ver = (
            parse_requires_python_target_version(raw_target_ver)
            if isinstance(raw_target_ver, str)
            else resolve_ruff_target_version(kwargs.get("tree"))
        )
        if target_ver:
            cmd.append(f"--target-version={target_ver}")
        if advisory_rules:
            cmd.append(f"--extend-select={','.join(advisory_rules)}")

        if isinstance(target_path, list):
            valid_files = [str(p.resolve()) for p in target_path if p.exists() and p.is_file()]
            if not valid_files:
                return []
            return [*cmd, *valid_files]

        if not target_path.exists():
            return []
        return [*cmd, str(target_path.resolve())]

    def cache_dirs(self, tree: Path) -> tuple[ToolCacheDir, ...]:
        """The Ruff cache of `tree`, outside the tree (#772 Part D, #2096). The scan starts in a new
        scratch directory, which the sandbox binds read-only, so Ruff could keep no cache there,
        and `RUFF_CACHE_DIR` wins over a `cache-dir` that the config of the tree names."""
        return (ToolCacheDir(CONST_RUFF_CACHE_DIR_ENV, _ruff_cache_dir(tree)),)

    def parse_output(self, data: Any, target_path: Path | list[Path]) -> list[Finding]:
        """Parse Ruff SARIF JSON payload into Finding objects."""
        if not isinstance(data, dict):
            return []
        tgt_str = str(target_path) if isinstance(target_path, Path) else ""
        return parse_ruff_sarif(data, default_path=tgt_str)

    def dry_run_scan(self, target_path: Path | list[Path], **kwargs: Any) -> list[Finding]:
        """Return simulated Ruff findings for dry-run validation."""
        target_str = (
            str(target_path[0])
            if isinstance(target_path, list) and target_path
            else str(target_path)
        )
        return [
            Finding(
                severity="MEDIUM",
                location=f"{target_str}:1",
                title="[BLE001] [DRY-RUN] Simulated Ruff blind exception finding",
                description="Ruff static inspection dry-run simulation mode active.",
                fix="Catch specific exception instead of Exception (dry-run mode)",
                confidence_score=None,
            )
        ]


def _infer_ruff_tree(target: Path | list[Path], tree: Path | None) -> Path | None:
    """Resolve candidate project root directory for reading `pyproject.toml`."""
    if tree is not None:
        return tree
    if isinstance(target, Path):
        return target if target.is_dir() else target.parent
    if target:
        first = target[0]
        return first if first.is_dir() else first.parent
    return None


def run_ruff_scan(
    target: Path | list[Path] = DEFAULT_CURRENT_PATH,
    *,
    advisory_rules: Sequence[str] = CONST_DEFAULT_REVIEW_ADVISORY_RULES,
    diff_hunks: dict[str, list[tuple[int, int]]] | None = None,
    is_branch_or_pr: bool = False,
    isolated: bool = False,
    tree: Path | None = None,
    target_version: str | None = None,
    require_version: bool = False,
    tool_executor: ToolExecutor | None = None,
) -> ScanOutcome:
    """Execute Ruff scan producing SARIF findings with advisory rule filtering."""
    from devops_cli.review.canary import (
        parse_requires_python_target_version,
        resolve_ruff_target_version,
    )

    eff_tree = _infer_ruff_tree(target, tree)
    resolved_ver = (
        parse_requires_python_target_version(target_version)
        if target_version is not None
        else resolve_ruff_target_version(eff_tree)
    )
    if resolved_ver is None and (require_version or tree is not None or isolated):
        return ScanOutcome(
            status="coverage_gap",
            findings=[],
            reason="missing requires-python in pyproject.toml",
        )
    scanner = RuffScanner(tool_executor)
    outcome = scanner.scan(
        target,
        isolated=isolated,
        advisory_rules=advisory_rules,
        tree=eff_tree,
        target_version=resolved_ver,
    )
    if outcome.findings:
        filtered = filter_or_group_advisories(
            outcome.findings,
            advisory_rules=advisory_rules,
            diff_hunks=diff_hunks,
            is_branch_or_pr=is_branch_or_pr,
        )
        return ScanOutcome(status=outcome.status, findings=filtered, reason=outcome.reason)
    return outcome
