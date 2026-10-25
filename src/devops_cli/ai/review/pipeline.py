"""Pipeline Orchestrator for Code Reviews.

Example:
    >>> from devops_cli.ai.client import LLMClient
    >>> from devops_cli.ai.review import ReviewPipelineOrchestrator
    >>>
    >>> from pathlib import Path
    >>> orchestrator = ReviewPipelineOrchestrator(
    ...     session_id="session-001", target_dir=Path("/path/to/checkout")
    ... )
    >>> metadata = orchestrator.run_pre_analysis_refresh(["src/main.py"])
    >>> payloads = orchestrator.init_per_file_payloads(["src/main.py"], metadata)
    >>> data_out, report_md = orchestrator.generate_consolidated_report(payloads)
"""

from __future__ import annotations

import hashlib
import inspect
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from devops_cli.ai.analyze.cache import load_cached_analysis
from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.analyze.symbols import (
    BaseRevision,
    SymbolDelta,
    change_symbol_delta,
    with_symbol_delta,
)
from devops_cli.ai.client.network import uses_gateway_slots
from devops_cli.ai.review.category_metrics import format_category_baseline_markdown
from devops_cli.ai.review.cited_code import record_cited_code
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.path_classes import (
    is_fixture_path,
    load_path_classes,
    load_review_config,
)
from devops_cli.ai.review.profile import active_profiler
from devops_cli.ai.review.protocol import ReviewLLMClient
from devops_cli.ai.review.review_environment import reviewed_tree
from devops_cli.ai.review.sanitization import (
    balance_markdown_fences,
    escape_markdown_title,
)
from devops_cli.ai.review.verdicts import (
    apply_verdict,
    assert_verdict_invariants,
)
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    ReviewSessionPayload,
    SavedFinding,
    compute_verdict_distributions,
    format_clean_text_field,
    is_field_discriminating,
    sort_findings,
    strip_outer_markdown_bold,
)
from devops_cli.config.commands import (
    BIN_BANDIT,
    BIN_GITLEAKS,
    BIN_GOLANGCI_LINT,
    BIN_KUBELINTER,
    BIN_OSV_SCANNER,
    BIN_PLUTO,
    BIN_SEMGREP,
    BIN_TRIVY,
)
from devops_cli.config.constants import (
    CONST_CANARY_TOOL_TO_ANALYZER,
    CONST_DEFAULT_REVIEW_ADVISORY_RULES,
    CONST_DEPENDENCY_SEVERITY_CLEAN,
    CONST_DEPENDENCY_VULNERABLE_SEVERITIES,
    CONST_LOCKFILE_NAMES,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_REVIEW_CONSOLE_PANEL_SEVERITIES,
    CONST_REVIEW_CONSOLE_TABLE_SEVERITIES,
    CONST_REVIEW_GENERATED_FILES,
    CONST_REVIEW_SECRET_SCANNER_RULES,
    CONST_REVIEW_STATUS_ORDER,
    CONST_REVIEW_SYMBOL_DELTA_CHANGE_TYPES,
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_INFO,
    CONST_SEVERITY_ORDER,
)
from devops_cli.config.defaults import (
    DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
    DEFAULT_MAX_COMPLEXITY,
    DEFAULT_REVIEW_CONCURRENCY,
    DEFAULT_REVIEW_MAX_CONCURRENCY,
    DEFAULT_SEMGREP_CONFIG,
)
from devops_cli.core.binaries import check_binary
from devops_cli.core.repo import find_worktree_root
from devops_cli.exceptions import SecurityError
from devops_cli.lang import MESSAGES
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.git import ChangedFile
from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    PackageLookupResult,
    VulnerabilityRecord,
)
from devops_cli.output import (
    escape_text,
    format_location,
    get_console,
    print_info,
    print_panel,
    print_success,
    print_table,
)
from devops_cli.review.session import ReviewSession, ReviewSessionStore
from devops_cli.review.severity import load_severity_caps
from devops_cli.review.suppression import load_review_suppressions
from devops_cli.security.reference_extractor import (
    extract_network_references,
)
from devops_cli.security.sanitizer import (
    mask_secrets,
)
from devops_cli.security.vulnerability_lookup import (
    CloudflareRadarClient,
    ShodanInternetDBClient,
)
from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor
from devops_cli.telemetry import trace_span

if TYPE_CHECKING:
    from devops_cli.security.base import ScanOutcome
    from devops_cli.security.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

_UNIVERSAL_MODULES: set[str] = {
    "__future__",
    "typing",
    "pathlib",
    "os",
    "sys",
    "re",
    "json",
    "logging",
    "time",
    "subprocess",
    "asyncio",
    "datetime",
    "unittest",
    "pytest",
    "abc",
    "collections",
    "collections.abc",
    "math",
    "shutil",
    "tempfile",
    "io",
    "copy",
    "functools",
    "itertools",
    "enum",
    "dataclasses",
    "contextlib",
    "threading",
    "traceback",
    "pydantic",
    "rich",
    "typer",
}

_SEV_ORDER: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
    "CLEAN": -1,
    "NONE": -1,
}


def _resolve_ollama_urls(config: Any) -> list[str]:
    """Safely resolve configured Ollama base URLs handling properties and callables."""
    if not config:
        return []
    raw_urls = getattr(config, "get_ollama_urls", None)
    if callable(raw_urls):
        try:
            raw_urls = raw_urls()
        except Exception:
            raw_urls = None
    if isinstance(raw_urls, list) and raw_urls:
        return [str(u).strip().rstrip("/") for u in raw_urls if str(u).strip()]
    raw_list = getattr(config, "ollama_urls", None)
    if isinstance(raw_list, list) and raw_list:
        return [str(u).strip().rstrip("/") for u in raw_list if str(u).strip()]
    return []


def _review_batch_capacity(config: Any) -> int:
    """How many files the persona stage reviews at once when no concurrency is requested.

    Through the gateway it is the gateway's backend slot sum: every request goes to the one
    gateway, so `ai.ollama_urls` adds no capacity. Otherwise it is every Ollama node's parallel
    slots, and at least `DEFAULT_REVIEW_CONCURRENCY`.
    """
    if uses_gateway_slots(config):
        return DEFAULT_GATEWAY_REVIEW_CONCURRENCY
    raw_par = getattr(config, "ollama_max_parallel", None)
    max_par = raw_par if isinstance(raw_par, int) else 2
    return max(DEFAULT_REVIEW_CONCURRENCY, len(_resolve_ollama_urls(config)) * max_par)


def effective_review_concurrency(config: Any, requested: int | None) -> int | None:
    """The file workers an explicit `--concurrency` gives a review, or None when none was asked.

    A client whose chat calls take the gateway's backend slots gets at most the slot sum; any
    other provider gets what it asked for.
    """
    if requested is None:
        return None
    wanted = max(1, requested)
    return min(wanted, DEFAULT_GATEWAY_REVIEW_CONCURRENCY) if uses_gateway_slots(config) else wanted


def _review_worker_count(
    config: Any, total_files: int, requested: int | None
) -> tuple[int, int | None]:
    """The review stage's file workers, and `requested` when the gateway's slot sum lowered it."""
    effective = effective_review_concurrency(config, requested)
    wanted = (
        min(_review_batch_capacity(config), DEFAULT_REVIEW_MAX_CONCURRENCY)
        if effective is None
        else effective
    )
    lowered = requested is not None and effective is not None and effective < requested
    return (min(total_files, wanted) if total_files > 0 else 1), (requested if lowered else None)


def _try_reuse_cached_analysis_meta(
    old_meta: FileAnalysisMeta,
    file_path: Path,
    bypass_mtime: bool = False,
) -> FileAnalysisMeta | None:
    """The cached metadata of a file whose content still matches it; None for a cache miss.

    With `bypass_mtime`, the content hash alone decides. Otherwise the file must also be no
    newer than the time of the cached analysis. A file that cannot be read, or a cached time that
    does not parse or has no time zone, is a cache miss: the file is analyzed again, and that
    analysis reports a file it cannot read.
    """
    if not (old_meta.last_analyzed and old_meta.pseudocode) or not file_path.is_file():
        return None
    try:
        st = file_path.stat()
        if old_meta.size_bytes and st.st_size != old_meta.size_bytes:
            return None
        cur_hash = hashlib.sha256(file_path.read_bytes(), usedforsecurity=False).hexdigest()
        if bypass_mtime and old_meta.content_hash and cur_hash == old_meta.content_hash:
            return old_meta
        analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
    except (OSError, ValueError) as exc:
        logger.debug("Cached metadata of %s is not reused: %s", file_path, exc)
        return None
    if analyzed_dt.tzinfo is None or st.st_mtime > analyzed_dt.timestamp():
        return None
    if old_meta.content_hash and cur_hash != old_meta.content_hash:
        return None
    return old_meta.model_copy(update={"content_hash": cur_hash})


def _wrap_static_findings(findings: list[Finding], tool: str = "") -> list[SavedFinding]:
    """Wrap generic findings from static analyzers into SavedFindings."""
    wrapped: list[SavedFinding] = []
    for f in findings:
        sf = SavedFinding(
            **f.model_dump(),
            producer=tool,
        )
        if tool:
            object.__setattr__(sf, "_tool", tool)
        if hasattr(f, "_anchor"):
            object.__setattr__(sf, "_anchor", getattr(f, "_anchor"))
        wrapped.append(sf)
    return wrapped


# Manifests whose pins a lockfile beside them resolves; a lockfile's findings attach to one.
_DEPENDENCY_MANIFESTS = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "pipfile",
        "package.json",
        "go.mod",
        "cargo.toml",
        "gemfile",
        "composer.json",
    }
)


def _sibling_file(loc_path: str, file_paths: list[str]) -> str | None:
    """A reviewed file in the same directory as `loc_path`, a dependency manifest first.

    Lockfiles are left out of the persona review for their size, so no payload carries their
    path; a finding in one attaches to the manifest beside it rather than being dropped.
    """
    parent = Path(loc_path).parent.as_posix()
    siblings = [
        fp
        for fp in file_paths
        if Path(fp).parent.as_posix() == parent or parent.endswith(f"/{Path(fp).parent.as_posix()}")
    ]
    manifests = [fp for fp in siblings if Path(fp).name.lower() in _DEPENDENCY_MANIFESTS]
    candidates = manifests or siblings
    return candidates[0] if candidates else None


def _find_matching_file(loc_path: str, file_paths: list[str]) -> str | None:
    """Find the best matching reviewed file path for a finding's location path."""
    for fp in file_paths:
        if fp == loc_path:
            return fp
    for fp in file_paths:
        if loc_path.endswith(f"/{fp}") or fp.endswith(f"/{loc_path}"):
            return fp
    return _sibling_file(loc_path, file_paths)


def _match_static_findings_to_files(
    findings: list[SavedFinding], file_paths: list[str]
) -> dict[str, list[SavedFinding]]:
    """Map findings from static analyzers to corresponding target repository files."""
    by_file: dict[str, list[SavedFinding]] = {}
    for sf in findings:
        loc_path = sf.location.split(":")[0].strip()
        matched = _find_matching_file(loc_path, file_paths)
        if matched:
            if loc_path != matched and (
                loc_path.endswith(f"/{matched}") or matched.endswith(f"/{loc_path}")
            ):
                suffix = sf.location[len(loc_path) :]
                sf.location = f"{matched}{suffix}"
                if loc_path in sf.description:
                    sf.description = sf.description.replace(loc_path, matched)
                if loc_path in sf.title:
                    sf.title = sf.title.replace(loc_path, matched)
            by_file.setdefault(matched, []).append(sf)
    return by_file


def _lockfiles_beside(paths: list[Path]) -> list[Path]:
    """Lockfiles in the directories of the reviewed files.

    The persona review leaves lockfiles out for their size, and the scanners saw only reviewed
    files, so no lockfile ever reached Trivy: a vulnerable or tampered pin went unchecked.
    """
    dirs = {path.parent for path in paths}
    return sorted(
        {d / name for d in dirs for name in CONST_REVIEW_GENERATED_FILES if (d / name).is_file()}
    )


def _parse_candidate_location(location: str) -> tuple[str, int | None, int | None, str | None]:
    """Parse candidate finding location into (path, start_line, end_line, logical_location)."""
    if location.startswith(":"):
        return "", None, None, location.lstrip(":").strip() or None

    from devops_cli.ai.review_schema import _parse_location
    from devops_cli.security.normalization import split_location

    raw_path, s_line, e_line = _parse_location(location)
    path_split, _, symbol = split_location(location)
    if s_line is not None:
        return raw_path, s_line, e_line, None
    if symbol:
        return path_split, None, None, symbol
    return raw_path, None, None, None


def _collect_scanner_commit_files(
    worktree_root: Path,
    file_paths: Sequence[str],
    secret_scan_files: Sequence[str],
    resolve_file_path: Callable[[str], Path],
) -> set[str]:
    """Collect commit file relative paths for admission location validation."""
    from devops_cli.core.repo import list_repo_files

    commit_files: set[str] = {
        p.relative_to(worktree_root).as_posix()
        for p in list_repo_files(worktree_root)
        if p.is_relative_to(worktree_root)
    }

    for fp in (*file_paths, *secret_scan_files):
        resolved = resolve_file_path(fp)
        try:
            commit_files.add(resolved.relative_to(worktree_root).as_posix())
        except ValueError, RuntimeError:
            pass
        clean = Path(fp).as_posix().lstrip("/")
        if clean:
            commit_files.add(clean)

    for p in _lockfiles_beside([resolve_file_path(f) for f in file_paths]):
        try:
            commit_files.add(p.relative_to(worktree_root).as_posix())
        except ValueError, RuntimeError:
            pass
        if p.name:
            commit_files.add(p.name)

    return commit_files


def _is_secret_scanner_result(tool: str, rule_id: str) -> bool:
    """Whether a secret scanner reported the result: any Gitleaks rule, or Trivy's secret one."""
    if tool not in CONST_REVIEW_SECRET_SCANNER_RULES:
        return False
    rules = CONST_REVIEW_SECRET_SCANNER_RULES[tool]
    return rules is None or rule_id in rules


def _sanitize_admitted_candidate(
    sf: SavedFinding,
    admitted: Any,
    raw_path: str,
    worktree_root: Path,
) -> None:
    """Normalize finding location, severity, and descriptions to repository-relative form."""
    sf.severity = admitted.severity
    sf.introduced = admitted.introduced
    sf.location = format_location(admitted.path, admitted.line, admitted.end_line)
    sf.fingerprint = getattr(admitted, "fingerprint_v2", "") or getattr(admitted, "fingerprint", "")
    sf.producer = getattr(admitted, "tool", "")
    desc, title = sf.description, sf.title
    if raw_path and raw_path != admitted.path:
        desc = desc.replace(raw_path, admitted.path)
        title = title.replace(raw_path, admitted.path)
    wt_str = str(worktree_root.resolve()).rstrip("/") + "/"
    if wt_str in desc:
        desc = desc.replace(wt_str, "")
    if wt_str in title:
        title = title.replace(wt_str, "")
    sf.description, sf.title = desc, title


def _admit_single_candidate(
    sf: SavedFinding,
    idx: int,
    *,
    session_id: str,
    worktree_root: Path,
    commit_files: set[str],
    file_content_getter: Callable[[str], str | None],
    path_classes: Mapping[str, Sequence[str]] | None = None,
    severity_caps: Mapping[str, str] | None = None,
    suppressions: Sequence[Any] | None = None,
    added_diff_lines: set[tuple[str, int]] | None = None,
    base_fingerprints: set[str] | None = None,
    canary_passed: bool = True,
    rejection_counts: dict[str, int] | None = None,
    manifest_objects: set[str] | None = None,
) -> tuple[Any | None, SavedFinding | None]:
    """Admit a single scanner finding candidate into a frozen finding (#871).

    A suppressed candidate returns its frozen finding and no SavedFinding, so it is listed as
    suppressed but never reported (#1295). Its path class caps its severity, unless a secret
    scanner reported it: a secret in a document or a test is still a secret (#1301).
    """
    from devops_cli.review.admission import admit
    from devops_cli.review.anchors import AdvisoryAnchor, ToolAnchor
    from devops_cli.review.state import FindingState
    from devops_cli.security.normalization import extract_rule_id, strip_rule_prefix

    raw_path, s_line, e_line, logical_loc = _parse_candidate_location(sf.location)
    tool = getattr(sf, "_tool", None) or "scanner"
    anchor = getattr(sf, "_anchor", None)
    if anchor is not None and isinstance(anchor, AdvisoryAnchor):
        r_id = anchor.advisory_id
        tool = getattr(sf, "_tool", None) or anchor.db
    else:
        r_id = extract_rule_id(sf.title, tool)
        if anchor is None:
            anchor = ToolAnchor(run_id=session_id, result_index=idx, rule_id=r_id)

    msg = strip_rule_prefix(sf.title) or sf.description or sf.title
    admitted = admit(
        anchor=anchor,
        tool=tool,
        rule_id=r_id,
        path=raw_path,
        message=msg,
        line=s_line,
        end_line=e_line,
        logical_location=logical_loc,
        description=sf.description,
        fix=sf.fix,
        rule_severity=sf.severity,
        worktree_root=worktree_root,
        commit_files=commit_files,
        file_content_getter=file_content_getter,
        manifest_objects=manifest_objects,
        path_classes=path_classes,
        severity_caps=None if _is_secret_scanner_result(tool, r_id) else severity_caps,
        suppressions=suppressions,
        added_diff_lines=added_diff_lines,
        base_fingerprints=base_fingerprints,
        canary_passed=canary_passed,
        rejection_counts=rejection_counts,
    )
    if admitted is None:
        return None, None
    if admitted.state == FindingState.SUPPRESSED:
        return admitted, None
    _sanitize_admitted_candidate(sf, admitted, raw_path, worktree_root)
    return admitted, sf


def _read_cited_file(
    path_str: str,
    *,
    worktree_root: Path,
    resolve_file_path: Callable[[str], Path],
    coverage_gaps: dict[str, str],
) -> str | None:
    """The text of the file that a finding cites: in `worktree_root`, else where the review
    resolves the path. None when no such file is there.

    A file that is there and cannot be read is a coverage gap: admission cannot check the
    finding against the file's lines and rejects it, so the reason goes into `coverage_gaps`.
    """
    path = worktree_root / path_str
    if not path.is_file():
        path = resolve_file_path(path_str)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _record_coverage_gap(coverage_gaps, path_str, _read_failure("Admission", exc))
        return None


def _collect_manifest_candidates(
    file_paths: Sequence[str],
    secret_scan_files: Sequence[str],
    findings: Sequence[SavedFinding],
) -> list[str]:
    """Collect candidate manifest file paths from reviewed files and finding locations."""
    candidates = [
        p for p in set(file_paths) | set(secret_scan_files) if p.endswith((".yaml", ".yml"))
    ]
    for sf in findings:
        raw_p = sf.location.split(":")[0] if sf.location else ""
        if raw_p.endswith((".yaml", ".yml")) and raw_p not in candidates:
            candidates.append(raw_p)
    return candidates


def _admit_scanner_findings(
    findings: list[SavedFinding],
    *,
    session_id: str,
    worktree_root: Path,
    file_paths: Sequence[str],
    secret_scan_files: Sequence[str],
    resolve_file_path: Callable[[str], Path],
    coverage_gaps: dict[str, str],
    path_classes: Mapping[str, Sequence[str]] | None = None,
    severity_caps: Mapping[str, str] | None = None,
    suppressions: Sequence[Any] | None = None,
    added_diff_lines: set[tuple[str, int]] | None = None,
    base_fingerprints: set[str] | None = None,
    canary_results: Mapping[str, bool] | None = None,
    rejection_counts: dict[str, int] | None = None,
    manifest_objects: set[str] | None = None,
) -> tuple[list[Any], list[SavedFinding]]:
    """Admit static scanner candidates into frozen review findings (#871).

    A cited file that cannot be read goes into `coverage_gaps` with the reason.
    """
    commit_files = _collect_scanner_commit_files(
        worktree_root, file_paths, secret_scan_files, resolve_file_path
    )
    read_cited_file = partial(
        _read_cited_file,
        worktree_root=worktree_root,
        resolve_file_path=resolve_file_path,
        coverage_gaps=coverage_gaps,
    )

    if manifest_objects is None:
        from devops_cli.review.manifests import collect_manifest_objects

        candidates = _collect_manifest_candidates(file_paths, secret_scan_files, findings)
        eff_manifest_objects: set[str] | None = collect_manifest_objects(
            candidates, content_getter=read_cited_file
        )
    else:
        eff_manifest_objects = manifest_objects

    admitted_frozen: list[Any] = []
    admitted_saved: list[SavedFinding] = []

    for idx, sf in enumerate(findings):
        tool_name = str(getattr(sf, "_tool", None) or "scanner").lower()
        tool_canary_ok = (
            canary_results.get(tool_name, canary_results.get(str(getattr(sf, "_tool", "")), True))
            if canary_results is not None
            else True
        )
        frozen, saved = _admit_single_candidate(
            sf,
            idx,
            session_id=session_id,
            worktree_root=worktree_root,
            commit_files=commit_files,
            file_content_getter=read_cited_file,
            path_classes=path_classes,
            severity_caps=severity_caps,
            suppressions=suppressions,
            added_diff_lines=added_diff_lines,
            base_fingerprints=base_fingerprints,
            canary_passed=tool_canary_ok,
            rejection_counts=rejection_counts,
            manifest_objects=eff_manifest_objects,
        )
        if frozen is not None:
            admitted_frozen.append(frozen)
        if saved is not None:
            admitted_saved.append(saved)

    return admitted_frozen, admitted_saved


def _is_scannable_manifest(path: Path) -> bool:
    """Report whether path is a scannable Kubernetes manifest or a mock test path."""
    if not path.exists():
        from unittest.mock import NonCallableMock

        from devops_cli.security.kubelinter import run_kubelinter_scan

        return isinstance(run_kubelinter_scan, NonCallableMock)
    from devops_cli.security.kubeconform import is_kubernetes_manifest

    return is_kubernetes_manifest(path)


def _scan_kubernetes_manifests(
    yaml_paths: list[Path],
    outcomes: dict[str, Any] | None = None,
    *,
    tree: Path | None = None,
    kubernetes_version: str | None = None,
    require_kubernetes_version: bool = False,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Scan Kubernetes YAML manifests with Kube-linter and Pluto.

    Like every scanner a review runs, each runs isolated: from a temporary directory, with
    devops-cli's own config and ignore files, never the reviewed tree's (#972).
    """
    from devops_cli.security.kubelinter import run_kubelinter_scan
    from devops_cli.security.pluto import run_pluto_scan

    manifests = [yp for yp in yaml_paths if _is_scannable_manifest(yp)]
    findings: list[SavedFinding] = []
    total_manifests = len(manifests)
    for yp in manifests:
        kl = run_kubelinter_scan(yp, isolated=True, tool_executor=tool_executor)
        _observe_outcome(outcomes, "Kube-linter", kl, file_path=yp, total_files=total_manifests)
        if kl:
            findings.extend(_wrap_static_findings(kl, tool="kube-linter"))

        pl = run_pluto_scan(
            yp,
            isolated=True,
            tree=tree,
            kubernetes_version=kubernetes_version,
            require_version=require_kubernetes_version,
            tool_executor=tool_executor,
        )
        _observe_outcome(outcomes, "Pluto", pl, file_path=yp, total_files=total_manifests)
        if pl:
            findings.extend(_wrap_static_findings(pl, tool="pluto"))
    return findings


def _scan_container_and_lockfiles(
    container_paths: list[Path],
    outcomes: dict[str, Any] | None = None,
    *,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Scan container files with Trivy."""
    from devops_cli.security.trivy import run_trivy_scan

    findings: list[SavedFinding] = []
    total_containers = len(container_paths)
    for dp in container_paths:
        t_findings = run_trivy_scan(
            dp, scan_type="config", isolated=True, tool_executor=tool_executor
        )
        _observe_outcome(outcomes, "Trivy", t_findings, file_path=dp, total_files=total_containers)
        if t_findings:
            findings.extend(_wrap_static_findings(t_findings, tool="trivy"))
    return findings


def _scan_lockfiles(
    lockfiles: list[Path],
    outcomes: dict[str, Any] | None = None,
    *,
    tree: Path,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Scan the lockfiles of the reviewed `tree` with osv-scanner offline (#1146)."""
    from devops_cli.security.base import ScanOutcome
    from devops_cli.security.osv_scanner import (
        detect_manifest_coverage_gaps,
        get_or_compute_snapshot_digest,
        run_osv_scan,
    )

    if not lockfiles:
        gaps = detect_manifest_coverage_gaps(tree, known_lockfiles=lockfiles)
        if gaps:
            gap_outcome = ScanOutcome("coverage_gap", [], "; ".join(gaps))
            _observe_outcome(outcomes, "osv-scanner", gap_outcome)
        return []

    outcome = run_osv_scan(lockfiles, tree=tree, isolated=True, tool_executor=tool_executor)
    _observe_outcome(outcomes, "osv-scanner", outcome)
    if profiler := active_profiler():
        scanner_digest = getattr(outcome, "snapshot_digest", "") or get_or_compute_snapshot_digest()
        profiler.set_osv_snapshot_digest(scanner_digest)
    if outcome.findings:
        return _wrap_static_findings(outcome.findings, tool="osv-scanner")
    return []


_VERSION_RANGE_MARKERS = (">", "<", "~", "^", "!=", "*", ",", "|", " - ")
# An npm-style wildcard component: 1.x, 2.X.0
_VERSION_WILDCARD = re.compile(r"(?:^|\.)[xX](?:\.|$)")


def _is_exact_version(version: str | None, ecosystem: str) -> bool:
    """Whether a declared version names one release; Cargo reads a bare version as `^version`."""
    if not version:
        return False
    if version.startswith("=="):
        return bool(version.removeprefix("==").strip())
    if (
        ecosystem.lower() == "crates.io"
        or any(marker in version for marker in _VERSION_RANGE_MARKERS)
        or _VERSION_WILDCARD.search(version)
    ):
        return False
    return bool(version.strip().lstrip("="))


def _build_vulnerability_finding(
    fpath: str,
    dep: DependencySpec,
    v: VulnerabilityRecord,
    *,
    session_id: str = "advisory",
) -> SavedFinding:
    """Build a verified SavedFinding with AdvisoryAnchor for a vulnerable dependency (#871)."""
    from devops_cli.review.anchors import AdvisoryAnchor

    eco_map = {
        "pypi": "pypi",
        "npm": "npm",
        "crates.io": "cargo",
        "go": "golang",
    }
    eco_norm = (dep.ecosystem or "").strip().lower()
    purl_type = eco_map.get(eco_norm, eco_norm or "generic")
    ver = (dep.version_range or "").lstrip("= ").strip() or "unknown"
    purl = (
        f"pkg:{purl_type}/{dep.name}@{ver}" if ver != "unknown" else f"pkg:{purl_type}/{dep.name}"
    )

    anchor = AdvisoryAnchor(
        db=v.source or "OSV",
        snapshot=getattr(v, "snapshot", "") or session_id or "default",
        advisory_id=v.id,
        purl=purl,
        locked_version=ver,
    )
    line_num = dep.line_number if dep.line_number and dep.line_number > 0 else 1
    desc = f"Dependency '{dep.name}' ({dep.version_range}) is affected by {v.id}: {v.summary}"
    finding = SavedFinding(
        severity=v.severity,
        location=f"{fpath}:{line_num}",
        title=f"Vulnerable Dependency: {dep.name} ({v.id})",
        description=desc,
        fix=f"Upgrade '{dep.name}' to a patched release.",
        references=[v.details_url] if v.details_url else [],
        verification_criteria=[f"Package '{dep.name}' declared in {fpath}"],
        invalidation_criteria=["Dependency upgraded or patched in lockfile"],
        verified_criteria_matched=[f"Package '{dep.name}' declared in {fpath}"],
        confidence_score=getattr(v, "cvss_score", None),
        producer=(v.source or "OSV").lower(),
        fingerprint=f"osv:{dep.name}:{v.id}",
    )
    setattr(finding, "_tool", (v.source or "OSV").lower())
    setattr(finding, "_anchor", anchor)
    return apply_verdict(finding, "VERIFIED", by="deterministic:vulnerable_dependency")


def _build_malicious_network_finding(
    fpath: str, net: NetworkReference, rep: NetworkReputationRecord
) -> SavedFinding:
    """Build an unverified SavedFinding for an external network target flagged by threat intel."""
    ref_urls = [f"https://internetdb.shodan.io/{rep.ip}"] if rep.ip else []
    desc = f"External host '{net.target}' flagged by {rep.source}: {rep.reputation_summary}"
    return SavedFinding(
        severity="HIGH",
        location=f"{fpath}:{net.line_number or 1}",
        title=f"Suspicious / Vulnerable Network Reference: {net.target}",
        description=desc,
        fix=f"Sanitize or remove external host reference '{net.target}'",
        references=ref_urls,
        verification_criteria=[f"Host '{net.target}' referenced in {fpath}"],
        invalidation_criteria=["Internal test fixture or isolated sandbox"],
        # A host with published CVEs is not proof of a defect in this file: it stays unverified.
        reportable=True,
        confidence_score=None,
        producer="threat_intel",
        fingerprint=f"network:{net.target}",
    )


def _checked_session_dir(session_dir: Path) -> Path:
    """A review session directory, refused when it escapes the places sessions may be written.

    No `..` component, and inside the reviews directory or the system temporary directory. The
    working directory of the process is no such place (#2098).
    """
    import tempfile

    if any(part == ".." for part in session_dir.parts):
        raise SecurityError(f"Path traversal detected in session_dir: {session_dir}")
    allowed = (
        ReviewSessionStore.root(),
        Path(tempfile.gettempdir()).resolve(),
    )
    resolved = session_dir.resolve()
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise SecurityError(f"Session directory {session_dir} is outside allowed root directories")
    return session_dir


def _format_extraction_summary(
    direct_deps_count: int,
    direct_nets_count: int,
    probed_deps_count: int,
    probed_nets_count: int,
) -> str:
    """Format summary string distinguishing in-file references from probed workspace references."""
    if probed_deps_count == 0 and probed_nets_count == 0:
        return (
            f"{direct_deps_count} unique dependency(ies) and {direct_nets_count} network target(s)"
        )

    probed_parts: list[str] = []
    if probed_deps_count > 0:
        probed_parts.append(
            f"{probed_deps_count} project dependencies probed from workspace manifests"
        )
    if probed_nets_count > 0:
        probed_parts.append(f"{probed_nets_count} network targets probed from workspace configs")
    probed_summary = ", ".join(probed_parts)

    if direct_deps_count == 0 and direct_nets_count == 0:
        return f"0 in-file references ({probed_summary})"

    return (
        f"{direct_deps_count} in-file dependency(ies) and {direct_nets_count} in-file network target(s) "
        f"({probed_summary})"
    )


def _fetch_domains_threat_intel(
    radar_client: CloudflareRadarClient,
    domain_targets: list[str],
) -> dict[str, NetworkReputationRecord]:
    """Fetch threat intelligence for domain targets with resilient fallback."""
    if not domain_targets:
        return {}
    try:
        return radar_client.check_domains_batch(domain_targets)
    except Exception:
        return {d: NetworkReputationRecord(target=d, ip="") for d in domain_targets}


def _fetch_ip_threat_intel(
    shodan_client: ShodanInternetDBClient,
    ip: str,
) -> tuple[str, NetworkReputationRecord]:
    """Fetch threat intelligence for a single IP address with fallback."""
    try:
        return ip, shodan_client.check_ip(ip)
    except Exception:
        return ip, NetworkReputationRecord(target=ip, ip=ip)


def _execute_pre_analysis_batch(
    paths_to_analyze: list[tuple[Path, str]], repo: Path, workers: int
) -> tuple[list[FileAnalysisMeta], dict[str, str]]:
    """Analyze each file on a thread, up to `workers` at once: the metadata of each file read,
    and the reason for each file that could not be read, by its path relative to `repo`.

    The analysis is local and calls no model, so the rate limit for model calls does not pace it.
    """

    def _analyze_path(item: tuple[Path, str]) -> FileAnalysisMeta | str:
        path_obj, rel_path = item
        try:
            content = path_obj.read_text(encoding="utf-8", errors="replace")
            size_bytes = path_obj.stat().st_size
        except OSError as exc:
            return _read_failure("Pre-analysis", exc)
        return analyze_single_file(
            rel_path, content, size_bytes, enhanced=True, repo_root=repo, ai_client=None
        )

    max_workers = min(len(paths_to_analyze), max(1, workers), DEFAULT_REVIEW_MAX_CONCURRENCY)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_analyze_path, paths_to_analyze))
    unread = {
        rel_path: result
        for (_, rel_path), result in zip(paths_to_analyze, results, strict=True)
        if isinstance(result, str)
    }
    return [result for result in results if not isinstance(result, str)], unread


def _collect_paths_to_analyze(
    candidates: list[tuple[Path, str]],
    existing_file_metas: dict[str, FileAnalysisMeta],
    force_refresh: bool,
    file_metas: list[FileAnalysisMeta],
    bypass_mtime: bool = False,
) -> list[tuple[Path, str]]:
    """Filter candidate paths and reuse existing analysis metadata where available."""
    paths_to_analyze: list[tuple[Path, str]] = []
    for p, rel_str in candidates:
        if p.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            continue
        old_meta = None if force_refresh else existing_file_metas.get(rel_str)
        if old_meta and (
            reused := _try_reuse_cached_analysis_meta(old_meta, p, bypass_mtime=bypass_mtime)
        ):
            file_metas.append(reused)
        else:
            paths_to_analyze.append((p, rel_str))
    return paths_to_analyze


def _read_reviewed_file(repo: Path, rel_path: str) -> str | None:
    """A reviewed file's text on disk; None when it cannot be read."""
    try:
        return (repo / rel_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("Failed reading %s for its symbol delta: %s", rel_path, exc)
        return None


def _changed_file_symbol_delta(
    meta: FileAnalysisMeta,
    change: ChangedFile | None,
    read_base: Callable[[str], str | None],
    read_head: Callable[[str], str | None],
) -> SymbolDelta:
    """A reviewed file's delta from the review's base; none for a file the diff left alone or
    whose head text cannot be read, since comparing with nothing would list every base symbol
    as removed."""
    if change is None:
        return [], [], []
    head_content = read_head(meta.path)
    if head_content is None:
        return [], [], []
    return change_symbol_delta(change, head_content, read_base)


def _record_symbol_deltas(
    file_metas: list[FileAnalysisMeta], repo: Path, base_revision: BaseRevision | None
) -> list[FileAnalysisMeta]:
    """The session's metadata with each changed Python file's delta and none on any other file,
    so a delta cached by another review or `devops ai analyze branch` never rides along. The
    head is read where the diff ends, or from the reviewed files on disk."""
    if base_revision is None:
        return [with_symbol_delta(m, ([], [], [])) for m in file_metas]
    changes = {
        c.path: c
        for c in base_revision.changes
        if c.change_type in CONST_REVIEW_SYMBOL_DELTA_CHANGE_TYPES
    }
    read_head = base_revision.read_head or partial(_read_reviewed_file, repo)
    return [
        with_symbol_delta(
            m, _changed_file_symbol_delta(m, changes.get(m.path), base_revision.read, read_head)
        )
        for m in file_metas
    ]


# How a static analyzer took part in a review. A scan that found nothing is clean only for the
# analyzers that ran; one that is not installed is skipped by its scanner without an error.
ANALYZER_RAN = "ran"
ANALYZER_BUILTIN_PATTERNS = "built-in patterns"
ANALYZER_NOT_INSTALLED = "not installed"
ANALYZER_NO_FILES = "no files"
ANALYZER_FAILED = "failed"

# (name, binary, the kind of file it scans).
_STATIC_ANALYZERS: tuple[tuple[str, str, str], ...] = (
    ("Bandit", BIN_BANDIT, "python"),
    ("Kube-linter", BIN_KUBELINTER, "yaml"),
    ("Pluto", BIN_PLUTO, "yaml"),
    ("Trivy", BIN_TRIVY, "container"),
    ("Semgrep", BIN_SEMGREP, "any"),
    # Gitleaks also reads the files kept off persona pages (#948).
    ("Gitleaks", BIN_GITLEAKS, "secrets"),
    ("osv-scanner", BIN_OSV_SCANNER, "lockfiles"),
    ("golangci-lint", BIN_GOLANGCI_LINT, "go"),
)
_ANALYZERS_WITH_BUILTIN_PATTERNS: frozenset[str] = frozenset()


def _static_analyzer_state_from_outcome(outcome: Any) -> str:
    """Map a ScanOutcome status to a review static analyzer state string."""
    status = getattr(outcome, "status", None)
    if status == "ran":
        return ANALYZER_RAN
    if isinstance(status, str) and status.startswith("ran; "):
        return status
    if status == "built-in patterns":
        return ANALYZER_BUILTIN_PATTERNS
    if status in ("unavailable", "not installed"):
        return ANALYZER_NOT_INSTALLED
    if status == "failed":
        return ANALYZER_FAILED
    if status == "coverage_gap":
        return "coverage_gap"
    if status in ("not_applicable", "no files"):
        return ANALYZER_NO_FILES
    if status == "dry-run":
        return ANALYZER_RAN
    return ANALYZER_RAN


def _predict_analyzer_state(name: str, binary: str) -> str:
    """Predict analyzer state via binary lookup when execution was not observed."""
    if check_binary(binary):
        return ANALYZER_RAN
    if name in _ANALYZERS_WITH_BUILTIN_PATTERNS:
        return ANALYZER_BUILTIN_PATTERNS
    return ANALYZER_NOT_INSTALLED


def _static_analyzer_states(
    files_by_kind: dict[str, list[Path]],
    observed_outcomes: dict[str, Any] | None = None,
) -> dict[str, str]:
    """How each static analyzer took part: runs, uses built-in patterns, is missing, or has no files."""
    states: dict[str, str] = {}
    outcomes = observed_outcomes or {}
    for name, binary, kind in _STATIC_ANALYZERS:
        if not files_by_kind.get(kind):
            states[name] = ANALYZER_NO_FILES
        elif name in outcomes:
            states[name] = _static_analyzer_state_from_outcome(outcomes[name])
        else:
            states[name] = _predict_analyzer_state(name, binary)
    return states


def _static_analyzer_reasons(
    states: dict[str, str], observed_outcomes: dict[str, Any] | None = None
) -> dict[str, str]:
    """The reason each failed analyzer's scan outcome gave, for the report."""
    outcomes = observed_outcomes or {}
    reasons: dict[str, str] = {}
    for name, state in states.items():
        reason = getattr(outcomes.get(name), "reason", "")
        if (state in (ANALYZER_FAILED, "coverage_gap") or state.startswith("ran; ")) and reason:
            reasons[name] = str(reason)
    return reasons


def _static_analyzer_unscanned(
    observed_outcomes: dict[str, Any] | None = None,
) -> dict[str, dict[str, str]]:
    """The files each analyzer's scan left out, with the reason, for the coverage matrix (#1144)."""
    return {
        name: dict(unscanned)
        for name, outcome in (observed_outcomes or {}).items()
        if (unscanned := getattr(outcome, "unscanned", None))
    }


def _static_analyzer_failed_files(
    observed_outcomes: dict[str, Any] | None = None,
) -> dict[str, dict[str, str]]:
    """The files each analyzer's scan failed on, with the reason, for the coverage matrix (#1140)."""
    return {
        name: dict(failed_files)
        for name, outcome in (observed_outcomes or {}).items()
        if (failed_files := getattr(outcome, "failed_files", None))
    }


def _reasons_with_files_not_scanned(
    reasons: Mapping[str, str], unscanned: Mapping[str, Mapping[str, str]]
) -> dict[str, str]:
    """Each analyzer's reason for the report, with a count of the files it left out added."""
    notes = {
        name: MESSAGES.review.files_not_scanned.format(count=len(files))
        for name, files in unscanned.items()
    }
    return {
        name: "; ".join(part for part in (reasons.get(name), notes.get(name)) if part)
        for name in {**reasons, **notes}
    }


def _resolve_single_tool_state(state: str, reason: str | None, files_left_out: bool = False) -> str:
    """Map single analyzer state and reason to tool-level outcome.

    A coverage gap with no reason of its own and files left out is a scan that ran: it is a gap of
    those files, which the matrix names (#1144).
    """
    if reason and "timed out after" in reason:
        return reason
    if reason == "canary failed":
        return "canary failed"
    if state == "coverage_gap" and files_left_out and not reason:
        return "ran"
    if state == "coverage_gap" or (reason and "uv.lock hash does not match" in str(reason)):
        return f"coverage gap ({reason})" if reason else "coverage gap"
    if state == ANALYZER_FAILED:
        return f"failed({reason})" if reason else "failed"
    if state == ANALYZER_NOT_INSTALLED:
        return "not installed"
    if state in (ANALYZER_RAN, ANALYZER_BUILTIN_PATTERNS) or state.startswith("ran; "):
        return "ran"
    return state


def _resolve_effective_tool_states(
    states: dict[str, str],
    reasons: dict[str, str],
    unscanned: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, str]:
    """Map analyzer states and reasons to tool-level outcomes for coverage calculation."""
    left_out = unscanned or {}
    return {
        tool: _resolve_single_tool_state(state, reasons.get(tool), bool(left_out.get(tool)))
        for tool, state in states.items()
    }


def _is_tool_manifest_match(resolved_path: Path) -> bool:
    """Whether path is a Kubernetes manifest eligible for Pluto / Kube-linter."""
    return resolved_path.suffix in (".yaml", ".yml") and _is_scannable_manifest(resolved_path)


def _is_tool_container_or_lockfile_match(resolved_path: Path) -> bool:
    """Whether path is a Dockerfile or lockfile eligible for Trivy."""
    return resolved_path.name.lower() in (
        "dockerfile",
        "containerfile",
    ) or resolved_path.suffix in (".lock", ".lockb")


def _lookup_file_reason(
    f: str, resolved_path: Path, failure_map: Mapping[str, str] | None
) -> str | None:
    """Look up failure reason for a file from a failure map by exact, resolved, or name match."""
    if not failure_map:
        return None
    if f in failure_map:
        return failure_map[f]
    resolved_str = str(resolved_path)
    if resolved_str in failure_map:
        return failure_map[resolved_str]
    name = resolved_path.name
    if name in failure_map:
        return failure_map[name]
    for key, reason in failure_map.items():
        if Path(key).name == name or key.endswith("/" + f) or f.endswith("/" + key):
            return reason
    return None


def _resolve_tool_file_status(
    tool: str,
    resolved_path: Path,
    tool_state: str | None,
    path_classes: Mapping[str, Sequence[str]],
    not_scanned: str | None = None,
    failed_reason: str | None = None,
) -> str:
    """Resolve status of a single (tool, file) pairing; `not_scanned` is the reason the tool left
    the file out of a scan that ran (#1144)."""
    if tool != "Gitleaks" and is_fixture_path(resolved_path, path_classes):
        return "skipped(fixture)"

    if tool == "Bandit" and resolved_path.suffix != ".py":
        return "skipped(not python)"

    if tool in ("Kube-linter", "Pluto") and not _is_tool_manifest_match(resolved_path):
        return "skipped(not manifest)"

    if tool == "Trivy" and not _is_tool_container_or_lockfile_match(resolved_path):
        return "skipped(not container or lockfile)"

    if failed_reason is not None:
        return f"failed({failed_reason})" if failed_reason else "failed"

    if not_scanned is not None:
        return f"not scanned({not_scanned})"

    if tool_state == "ran":
        return "scanned"

    return tool_state or "not installed"


def _compute_coverage_matrix(
    tools: Sequence[str],
    files: Sequence[str],
    resolve_fn: Callable[[str], Path],
    tool_states: dict[str, str],
    path_classes: Mapping[str, Sequence[str]],
    unscanned: Mapping[str, Mapping[str, str]] | None = None,
    failed_files: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    """Compute (tool, file) coverage matrix recording scanned, skipped, failed, not scanned, etc.

    `unscanned` maps a tool to the files its scan left out and why (#1144)."""
    matrix: dict[str, dict[str, str]] = {}
    for tool in tools:
        tool_state = tool_states.get(tool)
        left_out = (unscanned or {}).get(tool, {})
        left_failed = (failed_files or {}).get(tool, {})
        matrix[tool] = {
            f: _resolve_tool_file_status(
                tool,
                resolve_fn(f),
                tool_state,
                path_classes,
                left_out.get(f),
                _lookup_file_reason(f, resolve_fn(f), left_failed),
            )
            for f in files
        }
    return matrix


def _static_analyzer_summary(states: dict[str, str], findings: int) -> list[str]:
    """Console lines naming the analyzers that ran and those skipped for not being installed."""
    ran = [
        f"{name} (built-in patterns)" if state == ANALYZER_BUILTIN_PATTERNS else name
        for name, state in states.items()
        if state in (ANALYZER_RAN, ANALYZER_BUILTIN_PATTERNS) or state.startswith("ran; ")
    ]
    missing = [name for name, state in states.items() if state == ANALYZER_NOT_INSTALLED]
    failed = [name for name, state in states.items() if state == ANALYZER_FAILED]
    gapped = [name for name, state in states.items() if state == "coverage_gap"]
    lines = (
        [f"    [dim]✓ Static analyzers found {findings} finding(s): {', '.join(ran)} ran[/dim]"]
        if ran
        else ["    [yellow]! No static analyzer ran[/yellow]"]
    )
    if missing:
        lines.append(f"    [yellow]! Not installed, so not run: {', '.join(missing)}[/yellow]")
    if failed:
        lines.append(
            f"    [yellow]! Failed during execution: {', '.join(failed)} "
            "(the report's Static Analyzers table says why)[/yellow]"
        )
    if gapped:
        lines.append(
            f"    [yellow]! Coverage gap: {', '.join(gapped)} "
            "(the report's Static Analyzers table says why)[/yellow]"
        )
    return lines


# The analyzer line's lists after those that ran, in order.
_ANALYZER_LINE_LISTS: tuple[tuple[str, str], ...] = (
    (ANALYZER_BUILTIN_PATTERNS, "Built-in patterns only"),
    ("coverage_gap", "Coverage gap"),
    (ANALYZER_FAILED, "Failed"),
    (ANALYZER_NOT_INSTALLED, "Not installed"),
)


def _static_analysis_line(states: dict[str, str], severities: Counter[str]) -> str | None:
    """The executive summary's analyzer line, computed from the scan (#948).

    An analyzer counts as run only when it ran; one on built-in patterns, one that failed and
    one not installed are named apart, and the critical findings are counted. The line was a
    literal, "with 0 critical findings", while Bandit, Semgrep and Pluto had failed.
    """
    if not states:
        return None
    named: defaultdict[str, list[str]] = defaultdict(list)
    for name, state in sorted(states.items()):
        named[state].append(name)
    ran = [
        name
        for name, state in sorted(states.items())
        if state == ANALYZER_RAN or state.startswith("ran; ")
    ]
    sentences = [
        f"**Static Security Analysis**: {len(ran)} analyzer(s) ran ({', '.join(ran)})."
        if ran
        else "**Static Security Analysis**: no analyzer ran."
    ]
    if ran or named[ANALYZER_BUILTIN_PATTERNS]:
        sentences.append(
            f"Static analyzers reported {severities[CONST_SEVERITY_CRITICAL]} critical finding(s)."
        )
    sentences.extend(
        f"{label}: {', '.join(named[state])}."
        for state, label in _ANALYZER_LINE_LISTS
        if named[state]
    )
    return " ".join(sentences)


def _scan_secrets(
    paths: list[Path],
    outcomes: dict[str, Any] | None = None,
    *,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Run the Gitleaks secret scan."""
    if not paths:
        return []
    from devops_cli.security.gitleaks import run_gitleaks_scan

    gl = run_gitleaks_scan(paths, ignore_tests=True, isolated=True, tool_executor=tool_executor)
    _observe_outcome(outcomes, "Gitleaks", gl)
    return _wrap_static_findings(gl, tool="gitleaks")


def _scan_semgrep(
    paths: list[Path],
    outcomes: dict[str, Any] | None = None,
    *,
    tree: Path,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Run Semgrep AST static analysis on the reviewed files of `tree`, linked or copied under
    its working directory (#1079), with the cached registry ruleset (#1144)."""
    if not paths:
        return []
    from devops_cli.security.semgrep import run_semgrep_scan
    from devops_cli.security.semgrep_registry import cached_ruleset, warn_of_old_cache

    ruleset = cached_ruleset(DEFAULT_SEMGREP_CONFIG)
    if ruleset is not None:
        if profiler := active_profiler():
            profiler.set_semgrep_registry_digest(ruleset.digest)
        warn_of_old_cache(DEFAULT_SEMGREP_CONFIG, ruleset, to_stderr=False)
    sg = run_semgrep_scan(paths, reviewed_tree=tree, ruleset=ruleset, tool_executor=tool_executor)
    _observe_outcome(outcomes, "Semgrep", sg)
    return _wrap_static_findings(sg, tool="semgrep")


def _run_seconds(outcome: Any) -> float | None:
    """How long a scan ran, from its start and end; None when it did not record them."""
    started = getattr(outcome, "started_utc", None)
    ended = getattr(outcome, "ended_utc", None)
    if not (started and ended):
        return None
    return (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds()


def _compute_multi_file_status(total: int, failed_count: int) -> str:
    """Compute scanner status across multiple files: 'ran', 'ran; N of M files failed', or 'failed' (#1140)."""
    if failed_count == 0:
        return ANALYZER_RAN
    if failed_count < total:
        return f"ran; {failed_count} of {total} files failed"
    return ANALYZER_FAILED


def _extract_file_failures(
    outcome: Any, path_str: str, failed_files: dict[str, str], reasons: list[str]
) -> None:
    """Extract failure information for a file outcome into failed_files and reasons (#1140)."""
    st = getattr(outcome, "status", None) or "ran"
    reason = getattr(outcome, "reason", "")
    if st == ANALYZER_FAILED:
        failed_files[path_str] = reason or "failed"
        if reason and reason not in reasons:
            reasons.append(reason)
    elif getattr(outcome, "failed_files", None):
        for fp, r in outcome.failed_files.items():
            failed_files[str(fp)] = r
            if r and r not in reasons:
                reasons.append(r)


def _merge_outcome_payload(existing: ScanOutcome, outcome: Any) -> None:
    """Merge findings and timestamps from an outcome into existing ScanOutcome (#1140)."""
    if isinstance(outcome, list):
        for f in outcome:
            if f not in existing.findings:
                existing.findings.append(f)
                existing.append(f)
    started = getattr(outcome, "started_utc", None)
    ended = getattr(outcome, "ended_utc", None)
    if started:
        existing.started_utc = (
            min(existing.started_utc, started) if existing.started_utc else started
        )
    if ended:
        existing.ended_utc = max(existing.ended_utc, ended) if existing.ended_utc else ended


def _init_aggregated_outcome(
    outcome: Any,
    file_path: Path | str,
    total_files: int,
) -> ScanOutcome:
    """Initialize an aggregated ScanOutcome from the first observed file outcome (#1140)."""
    from devops_cli.security.base import ScanOutcome

    path_str = str(file_path)
    failed_files: dict[str, str] = {}
    reasons: list[str] = []
    _extract_file_failures(outcome, path_str, failed_files, reasons)

    findings = (
        list(getattr(outcome, "findings", []))
        if hasattr(outcome, "findings")
        else (list(outcome) if isinstance(outcome, list) else [])
    )
    res = ScanOutcome(
        status=_compute_multi_file_status(total_files, len(failed_files)),
        findings=findings,
        reason="; ".join(reasons),
        failed_files=failed_files,
        file_statuses={path_str: getattr(outcome, "status", None) or "ran"},
    )
    res.started_utc = getattr(outcome, "started_utc", None)
    res.ended_utc = getattr(outcome, "ended_utc", None)
    return res


def _update_aggregated_outcome(
    existing: ScanOutcome,
    outcome: Any,
    file_path: Path | str,
    total_files: int,
) -> None:
    """Fold an additional file scan outcome into an existing aggregated ScanOutcome (#1140)."""
    path_str = str(file_path)
    reasons = [r for r in existing.reason.split("; ") if r]

    existing.file_statuses[path_str] = getattr(outcome, "status", None) or "ran"
    _extract_file_failures(outcome, path_str, existing.failed_files, reasons)

    existing.status = _compute_multi_file_status(total_files, len(existing.failed_files))
    existing.reason = "; ".join(reasons)
    _merge_outcome_payload(existing, outcome)


def _observe_outcome(
    outcomes: dict[str, Any] | None,
    name: str,
    outcome: Any,
    file_path: Path | str | None = None,
    total_files: int | None = None,
) -> None:
    """Keep an analyzer's outcome for the report, recording per-file status when provided,
    and add the time the scan ran to the review's profile (#1140)."""
    if outcomes is not None:
        if file_path is not None:
            from devops_cli.security.base import ScanOutcome

            existing = outcomes.get(name)
            tf = (
                total_files
                if total_files is not None
                else (len(getattr(existing, "_file_statuses", {})) + 1 if existing else 1)
            )
            if existing is None or not isinstance(existing, ScanOutcome):
                outcomes[name] = _init_aggregated_outcome(outcome, file_path, tf)
            else:
                _update_aggregated_outcome(existing, outcome, file_path, tf)
        else:
            if name not in outcomes or getattr(outcome, "status", None) in (
                ANALYZER_FAILED,
                "coverage_gap",
            ):
                outcomes[name] = outcome

    seconds = _run_seconds(outcome)
    if seconds is not None and (profiler := active_profiler()):
        profiler.add_static_analyzer_seconds(name, seconds)


def _call_scanner_helper(
    func: Any,
    paths: list[Path],
    outcomes: dict[str, Any],
    **kwargs: Any,
) -> list[SavedFinding]:
    """Invoke scanner helper with outcomes dict and optional keyword arguments."""
    try:
        sig = inspect.signature(func)
        accepts_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        supported_kw = (
            kwargs if accepts_var_kw else {k: v for k, v in kwargs.items() if k in sig.parameters}
        )
        if "outcomes" in sig.parameters or accepts_var_kw:
            res = func(paths, outcomes=outcomes, **supported_kw)
            return list(res) if isinstance(res, list) else []
    except ValueError, TypeError:
        pass
    try:
        res = func(paths, outcomes=outcomes)
    except TypeError:
        res = func(paths)
    return list(res) if isinstance(res, list) else []


def _get_finding_status_badge(status: str) -> str:
    """Return color-styled badge for finding verification status."""
    st_upper = status.upper()
    if st_upper == "VERIFIED":
        return "[green]✓ VERIFIED[/green]"
    if st_upper == "MITIGATED":
        return "[cyan]~ MITIGATED[/cyan]"
    if st_upper == "INVALIDATED":
        return "[red]✗ INVALIDATED[/red]"
    return f"[yellow]? {status}[/yellow]"


_DEP_SEV_STYLES: dict[str, tuple[str, str]] = {
    "CRITICAL": ("[bold red]CRITICAL[/bold red]", "[bold red]{status}[/bold red]"),
    "HIGH": ("[red]HIGH[/red]", "[red]{status}[/red]"),
    "MEDIUM": ("[yellow]MEDIUM[/yellow]", "[yellow]{status}[/yellow]"),
    "LOW": ("[cyan]LOW[/cyan]", "[cyan]{status}[/cyan]"),
    "CLEAN": ("[green]CLEAN[/green]", "[green]{status}[/green]"),
    "UNCHECKED": ("[dim]UNCHECKED[/dim]", "[dim]{status}[/dim]"),
    "NOT_QUERIED": ("[dim]NOT QUERIED[/dim]", "[dim]{status}[/dim]"),
}
_DEFAULT_DEP_SEV_STYLE: tuple[str, str] = ("[dim]UNCHECKED[/dim]", "[dim]{status}[/dim]")


def _format_dependency_table_row(d: DependencySpec) -> list[str]:
    """Format a single dependency specification into table cell strings, its text escaped."""
    sev_str, status_template = _DEP_SEV_STYLES.get(d.severity.upper(), _DEFAULT_DEP_SEV_STYLE)
    status_str = status_template.format(status=escape_text(d.security_status))

    return [
        sev_str,
        escape_text(d.name),
        escape_text(d.version_range),
        escape_text(d.ecosystem),
        status_str,
        escape_text(d.location) or "—",
    ]


def _format_network_ref_table_row(n: NetworkReference) -> list[str]:
    """Format a single network reference into table cell strings, its text escaped."""
    scope_str = "[dim]Local[/dim]" if n.is_local else "[bold cyan]External[/bold cyan]"
    color = "red" if "⚠️" in n.security_status else ("cyan" if n.is_local else "green")
    return [
        escape_text(n.target),
        escape_text(n.reference_type),
        scope_str,
        f"[{color}]{escape_text(n.security_status)}[/{color}]",
        escape_text(n.location) or "—",
    ]


# The review.md sections the terminal points at for what it only summarizes (#987).
_REPORT_DEPENDENCIES_SECTION = "External Dependencies"
_REPORT_NETWORK_SECTION = "Network References & Endpoints"

_CONSOLE_FINDING_COLUMNS: list[Any] = [
    ("#", "dim"),
    ("Severity", "center"),
    ("Location", "bold cyan"),
    "Title",
    ("Status", "center"),
    ("Producer", "dim"),
    ("Conf", "dim"),
]
_CONSOLE_SEVERITY_BADGES: dict[str, str] = {
    "CRITICAL": "[bold red]CRITICAL[/bold red]",
    "HIGH": "[red]HIGH[/red]",
    "MEDIUM": "[yellow]MEDIUM[/yellow]",
    "LOW": "[cyan]LOW[/cyan]",
    "INFO": "[green]INFO[/green]",
}
_CONSOLE_STATUS_BADGES: dict[str, str] = {
    "VERIFIED": "[green]VERIFIED[/green]",
    "FLAGGED": "[yellow]FLAGGED[/yellow]",
    "MITIGATED": "[cyan]MITIGATED[/cyan]",
    "INVALIDATED": "[red]INVALIDATED[/red]",
}
_CONSOLE_DEPENDENCY_COLUMNS: list[Any] = [
    ("Severity", "center"),
    ("Dependency", "bold cyan"),
    "Version Range",
    "Ecosystem",
    "Security Status",
    ("Location", "dim"),
]
_CONSOLE_NO_DEPENDENCIES_ROW = [
    "[green]CLEAN[/green]",
    "No external package dependencies declared in reviewed files",
    "—",
    "—",
    "[green]✓ Clean (0 dependencies)[/green]",
    "—",
]
_CONSOLE_NETWORK_COLUMNS: list[Any] = [
    ("Target", "bold cyan"),
    "Type",
    "Scope",
    "Security Status",
    ("Location", "dim"),
]
_CONSOLE_NO_NETWORK_ROW = [
    "No network endpoints or remote addresses referenced in reviewed files",
    "—",
    "—",
    "[green]✓ Clean (0 endpoints)[/green]",
    "—",
]


def _format_console_finding_row(finding_index: int, finding: SavedFinding) -> list[str]:
    """Format a finding into findings-table cells, its text escaped."""
    sev_upper = (finding.severity or "INFORMATIONAL").upper()
    confidence = finding.confidence_score
    return [
        str(finding_index),
        _CONSOLE_SEVERITY_BADGES.get(sev_upper, f"[white]{sev_upper}[/white]"),
        escape_text(finding.location),
        escape_text(finding.title.strip()),
        _CONSOLE_STATUS_BADGES.get(finding.status.upper(), f"[dim]{finding.status}[/dim]"),
        escape_text(finding.producer),
        f"{int(confidence * 100)}%" if confidence is not None else "—",
    ]


def _console_severity(finding: SavedFinding) -> str:
    """The severity the terminal sorts a finding by: table, panel, or the summary line."""
    return (finding.severity or CONST_SEVERITY_INFO).upper()


def _in_order(labels: Iterable[str], order: Sequence[str]) -> list[str]:
    """`labels` in `order`, followed alphabetically by any that `order` does not name."""
    rank = {label: index for index, label in enumerate(order)}
    return sorted(labels, key=lambda label: (rank.get(label, len(rank)), label))


def _format_counts(counts: Counter[str], order: Sequence[str]) -> str:
    """`1 CRITICAL, 2 HIGH`: each label's count, in `order`."""
    return ", ".join(f"{counts[label]} {label}" for label in _in_order(counts, order))


def _is_vulnerable_dependency(dependency: DependencySpec) -> bool:
    return dependency.severity.upper() in CONST_DEPENDENCY_VULNERABLE_SEVERITIES


def _is_flagged_network_reference(reference: NetworkReference) -> bool:
    return reference.reputation is not None and reference.reputation.is_malicious


def _format_dependency_console_line(
    dependencies: list[DependencySpec], vulnerable: list[DependencySpec]
) -> str:
    """One line for the dependency scan: scanned, vulnerable by severity, and not checked."""
    if not dependencies:
        return "Dependencies: none declared in the reviewed files."
    by_severity = _format_counts(
        Counter(d.severity.upper() for d in vulnerable), CONST_SEVERITY_ORDER
    )
    unchecked = sum(
        1
        for d in dependencies
        if not _is_vulnerable_dependency(d)
        and d.severity.upper() != CONST_DEPENDENCY_SEVERITY_CLEAN
    )
    counts = [
        f"{len(dependencies)} scanned",
        f"{len(vulnerable)} vulnerable" + (f" ({by_severity})" if vulnerable else ""),
        *([f"{unchecked} not checked"] if unchecked else []),
    ]
    return (
        f"Dependencies: {', '.join(counts)}. "
        f'All are listed under "{_REPORT_DEPENDENCIES_SECTION}" in review.md.'
    )


def _format_network_console_line(
    references: list[NetworkReference], flagged: list[NetworkReference]
) -> str:
    """One line for the network references: found, local and external, and flagged."""
    if not references:
        return "Network references: none in the reviewed files."
    local = sum(1 for r in references if r.is_local)
    return (
        f"Network references: {len(references)} found ({local} local, "
        f"{len(references) - local} external), {len(flagged)} flagged by reputation. "
        f'All are listed under "{_REPORT_NETWORK_SECTION}" in review.md.'
    )


def _format_error_detail(stage: str, exc: Exception, max_len: int = 256) -> str:
    """Format, sanitize, and bound exception detail string for logging, display, and reports."""
    msg = mask_secrets(f"{stage}: {exc}").strip()
    if len(msg) > max_len:
        return msg[: max_len - 3] + "..."
    return msg


def _read_failure(stage: str, exc: OSError) -> str:
    """Why `stage` could not read a file, without the absolute path that the error names."""
    return f"{stage}: {exc.strerror}" if exc.strerror else _format_error_detail(stage, exc)


def _record_coverage_gap(coverage_gaps: dict[str, str], path: str, reason: str) -> None:
    """Keep `reason` as a coverage gap of `path`, after a different reason it has already."""
    known = coverage_gaps.get(path)
    if known is None:
        coverage_gaps[path] = reason
    elif reason not in known:
        coverage_gaps[path] = f"{known}; {reason}"


def _status_rows(reportable_findings: list[SavedFinding]) -> list[list[str]]:
    """The terminal summary's row counting the findings by status, as the report does (#948)."""
    from devops_cli.ai.review.stages.reporting import status_counts

    if not reportable_findings:
        return []
    counted, apart = status_counts(reportable_findings)
    listed_apart = f"; listed apart: {', '.join(apart)}" if apart else ""
    return [["By Status", f"{', '.join(counted) or 'none'}{listed_apart}"]]


def _scanned_routed_files(
    orchestrator: ReviewPipelineOrchestrator, findings_by_file: dict[str, list[SavedFinding]]
) -> list[str]:
    """The files kept off persona pages in which the secret scan found something."""
    return [f for f in orchestrator.secret_scan_files if findings_by_file.get(f)]


def _resolve_review_added_diff_lines(
    existing: set[tuple[str, int]] | None,
    added_diff_lines: set[tuple[str, int]] | None,
    pages: Sequence[str] | None,
    diff_text_by_file: Mapping[str, str] | None,
) -> set[tuple[str, int]]:
    """Determine effective set of added diff lines from arguments, pages, or diff maps."""
    eff = set(added_diff_lines or existing or ())
    if eff:
        return eff
    from devops_cli.review.diff import extract_added_diff_lines

    if pages:
        for p in pages:
            eff |= extract_added_diff_lines(p)
    elif diff_text_by_file:
        for fpath, dtext in diff_text_by_file.items():
            eff |= extract_added_diff_lines(dtext, default_path=fpath)
    return eff


@dataclass(frozen=True, slots=True)
class ScannerFileBuckets:
    """Classified file paths targeted by static analyzers (#871)."""

    python: list[Path] = field(default_factory=list)
    yaml: list[Path] = field(default_factory=list)
    container: list[Path] = field(default_factory=list)
    lockfiles: list[Path] = field(default_factory=list)
    any_files: list[Path] = field(default_factory=list)
    leak_targets: list[Path] = field(default_factory=list)
    go: list[Path] = field(default_factory=list)

    def as_kind_map(self) -> dict[str, list[Path]]:
        """Map scanner domain kinds for reporting without coupling tool collections."""
        return {
            "python": self.python,
            "yaml": self.yaml,
            "container": self.container,
            "lockfiles": self.lockfiles,
            "any": self.any_files,
            "secrets": self.leak_targets,
            "go": self.go,
        }


def _classify_scanner_files(
    all_resolved: Sequence[Path],
    extra_scan_paths: Sequence[Path] = (),
    path_classes: Mapping[str, Sequence[str]] | None = None,
) -> ScannerFileBuckets:
    """Group resolved candidate file paths by static analyzer domain (#871, #1146)."""
    py_paths = [
        p for p in all_resolved if p.suffix == ".py" and not is_fixture_path(p, path_classes)
    ]
    yaml_paths = [
        p
        for p in all_resolved
        if p.suffix in (".yaml", ".yml")
        and _is_scannable_manifest(p)
        and not is_fixture_path(p, path_classes)
    ]
    lockfiles = _lockfiles_beside(list(all_resolved))
    docker_paths = sorted(
        {
            p
            for p in all_resolved
            if (
                p.name.lower() in ("dockerfile", "containerfile")
                or p.name.lower().startswith(("dockerfile.", "containerfile."))
            )
            and not is_fixture_path(p, path_classes)
        }
    )
    lock_paths = sorted(
        {
            p
            for p in all_resolved
            if (p.name in CONST_LOCKFILE_NAMES or p.suffix in (".lock", ".lockb"))
            and not is_fixture_path(p, path_classes)
        }
        | {p for p in lockfiles if not is_fixture_path(p, path_classes)}
    )
    semgrep_paths = [p for p in all_resolved if not is_fixture_path(p, path_classes)]
    go_paths = [
        p for p in all_resolved if p.suffix == ".go" and not is_fixture_path(p, path_classes)
    ]
    return ScannerFileBuckets(
        python=py_paths,
        yaml=yaml_paths,
        container=docker_paths,
        lockfiles=lock_paths,
        any_files=semgrep_paths,
        leak_targets=list(all_resolved) + list(extra_scan_paths),
        go=go_paths,
    )


def _tool_language_version(tool: str, tree: Path, kubernetes_version: str | None) -> str:
    """Resolve declared language or platform version for `tool` in `tree`."""
    from devops_cli.review.canary import (
        resolve_mypy_python_version,
        resolve_ruff_target_version,
    )

    norm = tool.lower()
    if norm == "ruff":
        return resolve_ruff_target_version(tree) or ""
    if norm == "mypy":
        return resolve_mypy_python_version(tree) or ""
    if norm == "pluto":
        return kubernetes_version or ""
    return ""


def _find_nearest_gomod_root(target: Path, tree: Path | None = None) -> Path:
    """Find directory containing the nearest go.mod for target, bounded by tree (#603)."""
    start_dir = target if target.is_dir() else target.parent
    limit = Path(tree).resolve() if tree is not None else None
    for candidate in (start_dir, *start_dir.parents):
        if (candidate / "go.mod").is_file():
            return candidate
        if limit is not None and candidate == limit:
            break
    return limit if limit is not None else start_dir


def _scan_golangci_lint(
    go_paths: Sequence[Path],
    observed_outcomes: dict[str, Any],
    *,
    tree: Path | None = None,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Execute golangci-lint once per nearest go.mod root and return wrapped findings (#603)."""
    if not go_paths:
        return []
    from devops_cli.security.base import merge_outcomes
    from devops_cli.security.golangci_lint import GolangciLintScanner

    roots: dict[Path, list[Path]] = {}
    for p in go_paths:
        root = _find_nearest_gomod_root(p, tree=tree)
        roots.setdefault(root, []).append(p)

    scanner = GolangciLintScanner(tool_executor=tool_executor)
    outcomes: list[ScanOutcome] = []
    all_findings: list[Finding] = []

    for root_dir in sorted(roots.keys()):
        outcome = scanner.scan(root_dir)
        outcomes.append(outcome)
        all_findings.extend(outcome.findings)

    if outcomes:
        combined = merge_outcomes(outcomes) if len(outcomes) > 1 else outcomes[0]
        _observe_outcome(observed_outcomes, "golangci-lint", combined)

    return _wrap_static_findings(all_findings, tool="golangci-lint")


def _run_scanners_for_buckets(
    buckets: ScannerFileBuckets,
    *,
    tree: Path,
    observed_outcomes: dict[str, Any] | None = None,
    kubernetes_version: str | None = None,
    require_kubernetes_version: bool = False,
    tool_executor: ToolExecutor | None = None,
) -> list[SavedFinding]:
    """Execute Bandit, Kube-linter/Pluto, Trivy, osv-scanner, Gitleaks, Semgrep and golangci-lint
    on the files of the reviewed `tree` (#871)."""
    from devops_cli.security.bandit import run_bandit_scan

    outcomes = observed_outcomes if observed_outcomes is not None else {}
    findings: list[SavedFinding] = []
    if buckets.python:
        bandit_res = run_bandit_scan(
            buckets.python, isolated=True, tree=tree, tool_executor=tool_executor
        )
        if observed_outcomes is not None:
            _observe_outcome(outcomes, "Bandit", bandit_res)
        findings.extend(_wrap_static_findings(bandit_res, tool="bandit"))

    if buckets.yaml:
        findings.extend(
            _call_scanner_helper(
                _scan_kubernetes_manifests,
                buckets.yaml,
                outcomes,
                tree=tree,
                kubernetes_version=kubernetes_version,
                require_kubernetes_version=require_kubernetes_version,
                tool_executor=tool_executor,
            )
        )

    if buckets.container:
        findings.extend(
            _call_scanner_helper(
                _scan_container_and_lockfiles,
                buckets.container,
                outcomes,
                tool_executor=tool_executor,
            )
        )

    findings.extend(
        _scan_lockfiles(buckets.lockfiles, outcomes, tree=tree, tool_executor=tool_executor)
    )

    if buckets.leak_targets:
        findings.extend(
            _call_scanner_helper(
                _scan_secrets, buckets.leak_targets, outcomes, tool_executor=tool_executor
            )
        )

    if buckets.any_files:
        findings.extend(
            _scan_semgrep(buckets.any_files, outcomes, tree=tree, tool_executor=tool_executor)
        )

    if buckets.go and "golangci-lint" not in outcomes:
        go_findings = _scan_golangci_lint(
            buckets.go, outcomes, tree=tree, tool_executor=tool_executor
        )
        matched_go = _match_static_findings_to_files(go_findings, [str(p) for p in buckets.go])
        findings.extend([f for flist in matched_go.values() for f in flist])

    return findings


def _write_base_revision_files(
    base_revision: Any,
    tmp_root: Path,
    candidates: set[str],
) -> list[str]:
    """Write base revision file contents to temporary root directory."""
    written: list[str] = []
    for fp in candidates:
        clean = Path(fp).as_posix().lstrip("/")
        if not clean:
            continue
        try:
            content = base_revision.read(clean)
            if content is not None:
                dest = tmp_root / clean
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8", errors="replace")
                written.append(clean)
        except Exception:
            continue
    return written


def _populate_gomod_for_dir(
    base_revision: Any,
    tmp_root: Path,
    dir_path: Path,
    written_paths: Sequence[str],
    extra_lockfiles: list[str],
) -> None:
    """Populate nearest go.mod from base revision for a directory containing Go files (#603)."""
    curr: Path | None = dir_path
    while curr is not None:
        mod_rel = (curr / "go.mod").as_posix().lstrip("./") or "go.mod"
        if mod_rel in written_paths or mod_rel in extra_lockfiles:
            break
        try:
            mod_content = base_revision.read(mod_rel)
            if mod_content is not None:
                dest = tmp_root / mod_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(mod_content, encoding="utf-8", errors="replace")
                extra_lockfiles.append(mod_rel)
                break
        except (OSError, UnicodeDecodeError, KeyError) as exc:
            logger.debug("Failed reading base revision %s: %s", mod_rel, exc)
        if curr == Path(".") or not curr.parts:
            break
        curr = curr.parent if curr.parent != curr else None


def _write_base_revision_lockfiles(
    base_revision: Any,
    tmp_root: Path,
    written_paths: list[str],
) -> list[str]:
    """Populate base revision lockfiles beside written files."""
    dirs = {Path(p).parent for p in written_paths}
    extra_lockfiles: list[str] = []
    for d in dirs:
        for lf_name in CONST_REVIEW_GENERATED_FILES:
            lf_rel = (d / lf_name).as_posix().lstrip("./")
            if lf_rel in written_paths or lf_rel in extra_lockfiles:
                continue
            try:
                lf_content = base_revision.read(lf_rel)
                if lf_content is not None:
                    lf_dest = tmp_root / lf_rel
                    lf_dest.parent.mkdir(parents=True, exist_ok=True)
                    lf_dest.write_text(lf_content, encoding="utf-8", errors="replace")
                    extra_lockfiles.append(lf_rel)
            except Exception:
                continue
    if any(p.endswith(".go") for p in written_paths):
        for d in dirs:
            _populate_gomod_for_dir(
                base_revision,
                tmp_root,
                d,
                written_paths,
                extra_lockfiles,
            )
    return extra_lockfiles


def _collect_base_revision_fingerprints(
    base_revision: Any,
    *,
    file_paths: Sequence[str],
    secret_scan_files: Sequence[str],
    coverage_gaps: dict[str, str],
    path_classes: Mapping[str, Sequence[str]] | None = None,
    severity_caps: Mapping[str, str] | None = None,
    tool_executor: ToolExecutor | None = None,
) -> set[str]:
    """Scan base revision files to collect pre-existing finding fingerprints (#871).

    A base file that admission cannot read goes into `coverage_gaps` with the reason.
    """
    if base_revision is None or not getattr(base_revision, "read", None):
        return set()

    import tempfile

    with tempfile.TemporaryDirectory(prefix="devops-base-rev-") as tmp_dir_str:
        tmp_root = Path(tmp_dir_str)
        candidates = set(file_paths) | set(secret_scan_files)
        written = _write_base_revision_files(base_revision, tmp_root, candidates)
        if not written:
            return set()

        written.extend(_write_base_revision_lockfiles(base_revision, tmp_root, written))
        base_resolved = [tmp_root / p for p in written if (tmp_root / p).is_file()]
        extra_leak_files = [tmp_root / p for p in secret_scan_files if (tmp_root / p).is_file()]

        buckets = _classify_scanner_files(base_resolved, extra_leak_files, path_classes)
        base_findings = _run_scanners_for_buckets(
            buckets, tree=tmp_root, tool_executor=tool_executor
        )

        base_admitted, _ = _admit_scanner_findings(
            base_findings,
            session_id="base-revision",
            worktree_root=tmp_root,
            file_paths=written,
            secret_scan_files=[],
            resolve_file_path=lambda p: tmp_root / p,
            coverage_gaps=coverage_gaps,
            path_classes=path_classes,
            severity_caps=severity_caps,
        )
        return {bf.fingerprint_v2 for bf in base_admitted if getattr(bf, "fingerprint_v2", None)}


def _audit_single_dep(
    dep: DependencySpec,
    dep_cache: dict[tuple[str, str, str], Any],
) -> list[VulnerabilityRecord]:
    """Audit a single dependency against cache, update its status, and return vulns."""
    d_key = (dep.name, dep.version_range, dep.ecosystem)
    if d_key not in dep_cache:
        dep.queried = False
        dep.severity = "UNCHECKED"
        dep.security_status = "Not Queried"
        return []

    entry = dep_cache[d_key]
    is_pkg_res = isinstance(entry, PackageLookupResult)
    lookup_status = entry.status if is_pkg_res else "ok"
    raw_vulns = entry.vulnerabilities if is_pkg_res else entry
    vulns: list[VulnerabilityRecord] = (
        list(raw_vulns) if isinstance(raw_vulns, (list, tuple)) else []
    )

    if lookup_status != "ok":
        dep.queried = False
        dep.severity = "UNCHECKED"
        dep.security_status = "Lookup Failed"
        return []

    dep.queried = True
    if not vulns:
        dep.severity = "CLEAN"
        dep.security_status = "✓ Clean"
        return []

    dep.vulnerabilities = vulns
    highest_sev = max(
        (v.severity.upper() for v in vulns),
        key=lambda s: _SEV_ORDER.get(s, 0),
        default="MEDIUM",
    )
    dep.severity = highest_sev
    dep.security_status = f"⚠️ {len(vulns)} Known Vuln(s) [{highest_sev}]"
    return vulns


def _parse_review_toml_advisory_and_complexity(
    parsed_cfg: dict[str, Any],
) -> tuple[list[str], int, int | None]:
    """Extract advisory rules, complexity cap and max increase from review.toml dict (#873)."""
    rules = list(CONST_DEFAULT_REVIEW_ADVISORY_RULES)
    cap = DEFAULT_MAX_COMPLEXITY
    max_inc = None

    if "advisory" in parsed_cfg and isinstance(parsed_cfg["advisory"], dict):
        cfg_rules = parsed_cfg["advisory"].get("rules")
        if isinstance(cfg_rules, list):
            rules = [str(r).strip() for r in cfg_rules if str(r).strip()]
    elif "advisory_rules" in parsed_cfg and isinstance(parsed_cfg["advisory_rules"], list):
        rules = [str(r).strip() for r in parsed_cfg["advisory_rules"] if str(r).strip()]

    if "complexity" in parsed_cfg and isinstance(parsed_cfg["complexity"], dict):
        c_cap = parsed_cfg["complexity"].get("max_complexity", parsed_cfg["complexity"].get("cap"))
        if isinstance(c_cap, int):
            cap = c_cap
        c_inc = parsed_cfg["complexity"].get("max_increase")
        if isinstance(c_inc, int):
            max_inc = c_inc

    return rules, cap, max_inc


def _evaluate_session_complexity_deltas(
    python_paths: Sequence[Path],
    target_dir: Path,
    base_revision: Any,
    cap: int,
    max_increase: int | None,
) -> tuple[list[dict[str, Any]], list[Finding]]:
    """Compute complexity deltas and findings across reviewed python files (#873)."""
    if not python_paths:
        return [], []
    from devops_cli.security.complexity import compute_complexity_deltas

    base_files: dict[str, str] = {}
    head_files: dict[str, str] = {}
    wt = reviewed_tree(target_dir)
    for py_p in python_paths:
        try:
            rel_p = py_p.relative_to(wt).as_posix()
        except ValueError, RuntimeError:
            rel_p = py_p.name
        try:
            head_files[rel_p] = py_p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.debug("Failed reading head file %s: %s", rel_p, exc)
        if base_revision is not None and getattr(base_revision, "read", None):
            try:
                base_content = base_revision.read(rel_p)
                if base_content is not None:
                    base_files[rel_p] = base_content
            except (OSError, KeyError, ValueError, RuntimeError) as exc:
                logger.debug("Failed reading base file %s: %s", rel_p, exc)
    return compute_complexity_deltas(
        base_files,
        head_files,
        cap=cap,
        max_increase=max_increase,
    )


class ReviewPipelineOrchestrator:
    """Orchestrates staged code reviews with per-file payloads.

    The orchestrator takes its workspace through its constructor, and from nowhere else (#2098).
    `target_dir` is the absolute path of the reviewed directory: the orchestrator finds the
    reviewed tree, the files and their siblings, the manifests and the review config from it.
    `tool_executor` starts every analyzer, evidence tool and canary of the review. The command
    layer reads the working directory one time and gives these down, so no stage reads it. A
    review that gets no executor runs its tools in the sandbox (`SandboxToolExecutor`, #2096).
    """

    def __init__(
        self,
        session_id: str | None = None,
        llm_client: ReviewLLMClient | None = None,
        verification_client: ReviewLLMClient | None = None,
        *,
        target_dir: Path,
        session_dir: Path | None = None,
        concurrency: int | None = None,
        parallel: bool = True,
        subject: dict[str, str] | None = None,
        full_output: bool = False,
        secret_scan_files: Sequence[str] = (),
        base_revision: BaseRevision | None = None,
        partial_context: bool = False,
        added_diff_lines: set[tuple[str, int]] | None = None,
        threat_intel: bool = False,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        # Imported here: the executor pulls in the sandbox, which a review that does not start a
        # tool does not need.
        from devops_cli.security.tool_executor import RecordingToolExecutor, SandboxToolExecutor

        # One executor for the whole review, so every analyzer starts its tool the same way. It
        # keeps the record of every run, for the report and the profile (#772). The canaries of
        # the tools run on the same executor with no record: a canary checks a tool on a fixture
        # of its own and scans nothing of the review (#1978).
        executor = tool_executor or SandboxToolExecutor()
        self.tool_executor = RecordingToolExecutor(executor)
        self._canary_executor: ToolExecutor = executor
        self.session_id = session_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.base_revision = base_revision
        self.partial_context = partial_context
        self.added_diff_lines: set[tuple[str, int]] = set(added_diff_lines or ())
        self.threat_intel: bool = threat_intel
        self.cyclonedx_inventory: dict[str, Any] = {}
        self.osv_snapshot_digest: str = ""
        self.coverage: dict[str, dict[str, str]] = {}
        from devops_cli.core.repo import find_repo_root

        repo_root = find_repo_root(target_dir)
        self.path_classes = load_path_classes(base_revision, repo_root=repo_root)
        # Files kept off review pages that the secret scan still reads: planning documents,
        # generated references and lockfiles (#948). Neither review nor its payloads
        # take them, except to carry what the scan found.
        self.secret_scan_files = list(secret_scan_files)
        self.target_dir = target_dir
        # Print every finding, dependency and network reference to the terminal, as review.md
        # holds them, rather than the findings that matter and one line for the rest (#987).
        self.full_output = full_output
        # What this session reviews (`history.review_subject`), written with its findings.
        self.subject = subject or {}
        self.concurrency = concurrency
        self.parallel = parallel
        self.session = (
            ReviewSession(session_dir)
            if session_dir
            else ReviewSessionStore.session(self.session_id)
        )
        _checked_session_dir(self.session.directory)
        from devops_cli.dry_run.state import is_dry_run

        if not is_dry_run():
            self.session.create()
        self.llm_client: ReviewLLMClient | None = llm_client
        self.verification_client: ReviewLLMClient | None = verification_client
        # The coverage gaps of the review: each file that a stage could not read or build, with
        # the stage and the reason, for the report's table of skipped and errored files.
        self.errored_files: dict[str, str] = {}
        self.static_analyzers: dict[str, str] = {}
        self.static_analyzer_reasons: dict[str, str] = {}
        self.static_analyzer_failed_files: dict[str, dict[str, str]] = {}
        # The files each analyzer's scan left out, with the reason (#1144).
        self.static_analyzer_unscanned: dict[str, dict[str, str]] = {}
        # The static analyzers' findings by severity, for the report's analyzer line.
        self.static_severities: Counter[str] = Counter()
        self.admitted_scanner_findings: list[Any] = []
        self.base_fingerprints: set[str] = set()
        self.manifest_objects: set[str] | None = None
        # The review.toml the path classes come from: its suppressions, the most severe a
        # scanner finding in each path class is admitted as (#871, #1301), and the advisory
        # rules and complexity limits for the ruff and mypy evidence (#873).
        from devops_cli.review.canary import resolve_review_kubernetes_version

        review_config = load_review_config(base_revision, repo_root)
        self.suppressions: list[Any] = load_review_suppressions(review_config)
        self.severity_caps: dict[str, str] = load_severity_caps(review_config)
        self.kubernetes_version: str | None = resolve_review_kubernetes_version(
            review_config, tree=reviewed_tree(target_dir)
        )
        self.canary_results: dict[str, bool] = {}
        self.rejection_counts: dict[str, int] = {}
        self.complexity_deltas: list[dict[str, Any]] = []
        self.advisory_rules: list[str]
        self.complexity_cap: int
        self.complexity_max_increase: int | None
        self.advisory_rules, self.complexity_cap, self.complexity_max_increase = (
            _parse_review_toml_advisory_and_complexity(review_config)
        )

    def _ensure_tool_canaries(self, tools: Sequence[str]) -> None:
        """Run or read cached canary results for active review tools (#1143).

        A canary that the host cannot sandbox did not run, so it has no result and withholds no
        finding. The scan of its tool runs no tool either, and reports the coverage gap (#2096).
        """
        from devops_cli.dry_run.state import is_dry_run
        from devops_cli.exceptions.sandbox import SandboxUnavailableError
        from devops_cli.review.canary import get_canary_cache, run_tool_canary

        tree = reviewed_tree(self.target_dir)
        cached_by_tool = {k.tool: v.passed for k, v in get_canary_cache().items()}
        for tool in tools:
            norm = tool.lower()
            if norm in self.canary_results:
                continue
            if norm in cached_by_tool:
                self.canary_results[norm] = cached_by_tool[norm]
                continue
            if is_dry_run():
                self.canary_results[norm] = True
                continue
            lang_ver = _tool_language_version(norm, tree, self.kubernetes_version)
            try:
                res = run_tool_canary(
                    norm, language_version=lang_ver, tool_executor=self._canary_executor
                )
            except SandboxUnavailableError:
                continue
            self.canary_results[norm] = res.passed

    def _resolve_file_path(self, fpath: str) -> Path:
        """Resolve fpath to an existing file within target_dir or its repository, never outside.

        A path naming a file outside both, absolute or through `..`, falls back to a sanitized
        path inside the target, which scanners then find missing.
        """
        from devops_cli.core.repo import find_repo_root

        target_root = self.target_dir.resolve()
        repo = find_repo_root(self.target_dir).resolve()
        p = Path(fpath)
        candidates = [p] if p.is_absolute() else [target_root / p, repo / p, target_root / p.name]
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except (ValueError, OSError) as exc:
                logger.debug("Failed resolving path %s: %s", fpath, exc)
                continue
            inside = resolved.is_relative_to(target_root) or resolved.is_relative_to(repo)
            if inside and resolved.exists():
                return resolved
        return target_root / Path(fpath.lstrip("/\\")).name

    def get_server_info(self, client: ReviewLLMClient | None = None) -> str:
        """Describe a client's provider, host and model; the analysis client by default."""
        target = client or self.llm_client
        if not target:
            return "LLM server"
        backend_info = getattr(target, "backend_info", "")
        config = getattr(target, "_config", None)
        model = getattr(config, "model", None) if config else None

        if backend_info and model:
            return f"{backend_info} [model: {model}]"
        if backend_info:
            return str(backend_info)
        if model:
            return f"LLM [model: {model}]"
        return "LLM server"

    _get_server_info = get_server_info

    # ── Stage 1: Pre-Analysis & Metadata Refresh ──────────────────────────────
    @staticmethod
    def _load_pre_analysis_cache(repo: Path, force_refresh: bool) -> dict[str, FileAnalysisMeta]:
        """Load cached file metadata from previous analysis run if available."""
        if force_refresh:
            return {}
        cached_meta = load_cached_analysis(repo)
        if not cached_meta:
            return {}
        return {fmeta.path: fmeta for fmeta in cached_meta.files}

    def _pre_analysis_candidates(self, files: Sequence[str], repo: Path) -> list[tuple[Path, str]]:
        """Each file under review that is on disk, with its path relative to `repo`."""
        paths = {self._resolve_file_path(f) for f in files}
        return sorted(
            (p, str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p))
            for p in paths
            if p.is_file()
        )

    def run_pre_analysis_refresh(
        self,
        files: Sequence[str],
        target_type: Literal["branch", "pr", "path"] = "path",
        target_ref: str = ".",
        force_refresh: bool = False,
        stage_flags: ReviewStageFlags | None = None,
        base_revision: BaseRevision | None = None,
    ) -> dict[str, FileAnalysisMeta]:
        """Refresh the metadata of the files under review, and of no other file in the target.

        A file whose cached metadata still matches its content reuses it; the others are
        analyzed again. The analysis calls no model. With `base_revision`, each Python file the
        reviewed diff changed records its symbol delta from that base before the session
        metadata is saved.
        """
        from devops_cli.ai.analyze.cache import save_analysis_metadata
        from devops_cli.config.defaults import DEFAULT_PRE_ANALYSIS_WORKERS
        from devops_cli.core.repo import find_repo_root
        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run():
            return {}

        if stage_flags is not None and not stage_flags.pre_analysis:
            print_info(
                "[dim]Pre-analysis metadata scan skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return {}

        with trace_span(
            "review.pre_analysis",
            attributes={"target_ref": target_ref, "target_type": target_type},
        ):
            repo = find_repo_root(self.target_dir)
            display_ref = (
                target_ref if target_ref and target_ref != "." else str(self.target_dir.resolve())
            )
            print_info(
                f"[dim]Scanning pre-analysis metadata for '{display_ref}'...[/dim]",
                prefix=False,
            )

            file_metas: list[FileAnalysisMeta] = []
            paths_to_analyze = _collect_paths_to_analyze(
                self._pre_analysis_candidates(files, repo),
                self._load_pre_analysis_cache(repo, force_refresh),
                force_refresh,
                file_metas,
                bypass_mtime=target_type in ("branch", "pr"),
            )
            reused = len(file_metas)
            workers = DEFAULT_PRE_ANALYSIS_WORKERS if self.concurrency is None else self.concurrency
            if paths_to_analyze:
                analyzed, unread = _execute_pre_analysis_batch(paths_to_analyze, repo, workers)
                file_metas.extend(analyzed)
                for rel_path, reason in unread.items():
                    _record_coverage_gap(self.errored_files, rel_path, reason)

            file_metas = _record_symbol_deltas(file_metas, repo, base_revision)
            metadata_by_path = {meta.path: meta for meta in file_metas}
            if file_metas:
                title = f"{repo.name} pre-analysis: {target_ref}"
                save_analysis_metadata(
                    target_type, target_ref, title, file_metas, repo, enhanced=True
                )

            summary = MESSAGES.review.pre_analysis_summary.format(
                count=len(metadata_by_path), analyzed=len(file_metas) - reused, reused=reused
            )
            print_info(f"[dim]  {summary}[/dim]", prefix=False)
            return metadata_by_path

    def _find_matching_metadata(
        self, fpath: str, metadata_by_path: dict[str, FileAnalysisMeta]
    ) -> FileAnalysisMeta | None:
        """Find FileAnalysisMeta for fpath with exact and normalized suffix matching."""
        if fpath in metadata_by_path:
            return metadata_by_path[fpath]

        norm_f = fpath.replace("\\", "/").strip("./")
        for key, meta in metadata_by_path.items():
            norm_k = key.replace("\\", "/").strip("./")
            if norm_k == norm_f or norm_k.endswith("/" + norm_f) or norm_f.endswith("/" + norm_k):
                return meta

        return None

    # ── Stage 2: Per-File Review Session JSON Initialization ──────────────────
    def _run_static_scanners(
        self,
        file_paths: list[str],
        added_diff_lines: set[tuple[str, int]] | None = None,
    ) -> dict[str, list[SavedFinding]]:
        """Run Bandit, Kube-linter, Pluto, Trivy, Semgrep, and Gitleaks static analyzers."""
        static_findings_by_file: dict[str, list[SavedFinding]] = {}
        all_static_findings: list[SavedFinding] = []
        n_paths = len(file_paths)
        try:
            print_info("  • Running static security analyzers...", prefix=False)

            with trace_span(
                "security.static_scanners", attributes={"file_count": n_paths}
            ) as sc_span:
                all_resolved = [self._resolve_file_path(f) for f in file_paths]
                observed_outcomes: dict[str, Any] = {}
                buckets = _classify_scanner_files(
                    all_resolved,
                    [self._resolve_file_path(f) for f in self.secret_scan_files],
                    self.path_classes,
                )
                py_paths = buckets.python
                yaml_paths = buckets.yaml
                docker_lock_paths = buckets.container

                self._ensure_tool_canaries(
                    [
                        *(("bandit",) if py_paths else ()),
                        *(("kube-linter", "pluto") if yaml_paths else ()),
                        *(("semgrep",) if buckets.any_files else ()),
                    ]
                )

                all_static_findings.extend(
                    _run_scanners_for_buckets(
                        buckets,
                        tree=reviewed_tree(self.target_dir),
                        observed_outcomes=observed_outcomes,
                        kubernetes_version=self.kubernetes_version,
                        require_kubernetes_version=True,
                        tool_executor=self.tool_executor,
                    )
                )

                if self.base_revision is not None:
                    self.base_fingerprints = _collect_base_revision_fingerprints(
                        self.base_revision,
                        file_paths=file_paths,
                        secret_scan_files=self.secret_scan_files,
                        coverage_gaps=self.errored_files,
                        path_classes=self.path_classes,
                        severity_caps=self.severity_caps,
                        tool_executor=self.tool_executor,
                    )

                if self.manifest_objects is None:
                    from devops_cli.review.manifests import collect_manifest_objects

                    candidates = _collect_manifest_candidates(
                        file_paths, self.secret_scan_files, all_static_findings
                    )
                    read_for_manifests = partial(
                        _read_cited_file,
                        worktree_root=reviewed_tree(self.target_dir),
                        resolve_file_path=self._resolve_file_path,
                        coverage_gaps=self.errored_files,
                    )
                    self.manifest_objects = collect_manifest_objects(
                        candidates, content_getter=read_for_manifests
                    )

                eff_added = (
                    added_diff_lines
                    if added_diff_lines is not None
                    else getattr(self, "added_diff_lines", None)
                )
                admitted_frozen, admitted_saved = _admit_scanner_findings(
                    all_static_findings,
                    session_id=self.session_id,
                    worktree_root=reviewed_tree(self.target_dir),
                    file_paths=file_paths,
                    secret_scan_files=self.secret_scan_files,
                    resolve_file_path=self._resolve_file_path,
                    coverage_gaps=self.errored_files,
                    path_classes=self.path_classes,
                    severity_caps=self.severity_caps,
                    suppressions=getattr(self, "suppressions", None),
                    added_diff_lines=eff_added,
                    base_fingerprints=getattr(self, "base_fingerprints", None),
                    canary_results=self.canary_results,
                    rejection_counts=self.rejection_counts,
                    manifest_objects=self.manifest_objects,
                )
                self.admitted_scanner_findings = admitted_frozen
                all_static_findings = admitted_saved
                self._record_static_analyzers(
                    buckets.as_kind_map(),
                    observed_outcomes=observed_outcomes,
                )
                self.static_severities = Counter(f.severity for f in all_static_findings)

                tools = [name for name, _, _ in _STATIC_ANALYZERS]
                all_files_to_cover = sorted(set(file_paths) | set(self.secret_scan_files))
                tool_effective_states = _resolve_effective_tool_states(
                    self.static_analyzers,
                    self.static_analyzer_reasons,
                    self.static_analyzer_unscanned,
                )
                self.coverage = _compute_coverage_matrix(
                    tools,
                    all_files_to_cover,
                    self._resolve_file_path,
                    tool_effective_states,
                    self.path_classes,
                    self.static_analyzer_unscanned,
                    failed_files=self.static_analyzer_failed_files,
                )
                active_prof = active_profiler()
                if active_prof:
                    active_prof.set_coverage(self.coverage)
                    active_prof.set_rejections(self.rejection_counts)

                static_findings_by_file = _match_static_findings_to_files(
                    all_static_findings, [*file_paths, *self.secret_scan_files]
                )

                sc_attrs = {
                    "findings_count": len(all_static_findings),
                    "python_files": len(py_paths),
                    "yaml_files": len(yaml_paths),
                    "docker_files": len(docker_lock_paths),
                    "go_files": len(buckets.go),
                }
                sc_span.set_attributes(sc_attrs)

            for line in _static_analyzer_summary(self.static_analyzers, len(all_static_findings)):
                print_info(line, prefix=False)
        except Exception as exc:
            logger.debug("Static security scanning failed or skipped: %s", exc)

        return static_findings_by_file

    def _run_review_evidence(
        self,
        file_paths: list[str],
        added_diff_lines: set[tuple[str, int]] | None = None,
    ) -> dict[str, list[SavedFinding]]:
        """Run Ruff, mypy, and C901 complexity evidence with project settings (#873)."""
        evidence_findings_by_file: dict[str, list[SavedFinding]] = {}
        all_evidence: list[SavedFinding] = []
        try:
            from devops_cli.core.repo import main_worktree_root
            from devops_cli.security.mypy import run_mypy_scan
            from devops_cli.security.ruff import run_ruff_scan

            py_paths = [
                self._resolve_file_path(f)
                for f in file_paths
                if f.endswith(".py") and self._resolve_file_path(f).is_file()
            ]
            if not py_paths:
                return evidence_findings_by_file

            self._ensure_tool_canaries(("ruff", "mypy"))
            rev_tree = reviewed_tree(self.target_dir)
            checkout_root = main_worktree_root(self.target_dir) if self.target_dir else None
            is_branch_pr = self.subject.get("type") in ("branch", "pr")
            hunks = getattr(self, "diff_hunks", None)
            ruff_res = run_ruff_scan(
                py_paths,
                advisory_rules=self.advisory_rules,
                diff_hunks=hunks,
                is_branch_or_pr=is_branch_pr,
                isolated=True,
                tree=rev_tree,
                require_version=True,
                tool_executor=self.tool_executor,
            )
            all_evidence.extend(_wrap_static_findings(ruff_res.findings, tool="ruff"))

            mypy_res = run_mypy_scan(
                py_paths,
                tree=rev_tree,
                checkout_root=checkout_root,
                tool_executor=self.tool_executor,
            )
            all_evidence.extend(_wrap_static_findings(mypy_res.findings, tool="mypy"))

            deltas, c901_findings = _evaluate_session_complexity_deltas(
                py_paths,
                self.target_dir,
                self.base_revision,
                self.complexity_cap,
                self.complexity_max_increase,
            )
            self.complexity_deltas = deltas
            if c901_findings:
                all_evidence.extend(_wrap_static_findings(c901_findings, tool="c901"))

            eff_added = (
                added_diff_lines
                if added_diff_lines is not None
                else getattr(self, "added_diff_lines", None)
            )
            admitted_frozen, admitted_saved = _admit_scanner_findings(
                all_evidence,
                session_id=self.session_id,
                worktree_root=rev_tree,
                file_paths=file_paths,
                secret_scan_files=self.secret_scan_files,
                resolve_file_path=self._resolve_file_path,
                coverage_gaps=self.errored_files,
                path_classes=self.path_classes,
                suppressions=getattr(self, "suppressions", None),
                added_diff_lines=eff_added,
                base_fingerprints=getattr(self, "base_fingerprints", None),
                canary_results=self.canary_results,
                rejection_counts=self.rejection_counts,
                manifest_objects=getattr(self, "manifest_objects", None),
            )
            self.admitted_scanner_findings.extend(admitted_frozen)
            evidence_findings_by_file = _match_static_findings_to_files(admitted_saved, file_paths)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.debug("Review evidence scanning failed: %s", exc)

        return evidence_findings_by_file

    def _record_static_analyzers(
        self,
        files_by_kind: dict[str, list[Path]],
        observed_outcomes: dict[str, Any] | None = None,
    ) -> None:
        """Keep how each analyzer took part, for the report and the review's profile."""
        self.static_analyzers = _static_analyzer_states(files_by_kind, observed_outcomes)
        self.static_analyzer_reasons = _static_analyzer_reasons(
            self.static_analyzers, observed_outcomes
        )
        self.static_analyzer_unscanned = _static_analyzer_unscanned(observed_outcomes)
        self.static_analyzer_failed_files = _static_analyzer_failed_files(observed_outcomes)
        for tool_key, analyzer_name in CONST_CANARY_TOOL_TO_ANALYZER.items():
            if self.canary_results.get(tool_key) is False and (
                self.static_analyzers.get(analyzer_name)
                in (ANALYZER_RAN, ANALYZER_BUILTIN_PATTERNS)
                or (self.static_analyzers.get(analyzer_name) or "").startswith("ran; ")
            ):
                self.static_analyzers[analyzer_name] = ANALYZER_FAILED
                self.static_analyzer_reasons[analyzer_name] = "canary failed"
        if profiler := active_profiler():
            profiler.set_static_analyzers(self.static_analyzers, self._static_analyzer_notes())

    def _fetch_threat_intel(
        self, file_paths: list[str]
    ) -> tuple[
        dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dict[str, NetworkReputationRecord],
    ]:
        """Fetch threat intelligence from Shodan and Cloudflare Radar for network targets (opt-in #1146)."""
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]] = {}
        net_cache: dict[str, NetworkReputationRecord] = {}
        unique_nets: set[tuple[str, str]] = set()

        for fpath in file_paths:
            p_target = self._resolve_file_path(fpath)
            file_nets: list[NetworkReference] = []
            if p_target.is_file():
                try:
                    f_content = p_target.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    reason = _read_failure("Threat intelligence", exc)
                    _record_coverage_gap(self.errored_files, fpath, reason)
                else:
                    file_nets = extract_network_references(f_content, fpath)
            raw_file_data[fpath] = ([], file_nets)
            unique_nets.update((n.target, n.reference_type) for n in file_nets)

        if not unique_nets:
            return raw_file_data, net_cache

        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run():
            return raw_file_data, net_cache

        shodan_client = ShodanInternetDBClient()
        radar_client = CloudflareRadarClient()
        domain_targets = [target for target, rtype in unique_nets if rtype != "ip"]
        ip_targets = [target for target, rtype in unique_nets if rtype == "ip"]
        if domain_targets:
            net_cache.update(_fetch_domains_threat_intel(radar_client, domain_targets))
        if ip_targets:
            with ThreadPoolExecutor(max_workers=min(8, len(ip_targets))) as executor:
                net_cache.update(
                    dict(
                        executor.map(
                            lambda ip: _fetch_ip_threat_intel(shodan_client, ip),
                            ip_targets,
                        )
                    )
                )
        return raw_file_data, net_cache

    def _find_linked_files(
        self,
        fpath: str,
        fmeta: FileAnalysisMeta,
        metadata_by_path: dict[str, FileAnalysisMeta],
    ) -> list[FileAnalysisMeta]:
        """Up to 10 other files under review linked to fpath by symbols, dependencies or imports."""
        meaningful_deps = {d for d in fmeta.dependencies if d and d not in _UNIVERSAL_MODULES}
        meaningful_syms = {s for s in fmeta.key_symbols if s}

        linked: list[FileAnalysisMeta] = []
        for other_path, other_meta in metadata_by_path.items():
            if other_path == fpath:
                continue
            sym_match = any(sym in other_meta.key_symbols for sym in meaningful_syms)
            dep_match = any(
                dep in other_meta.dependencies
                for dep in meaningful_deps
                if dep not in _UNIVERSAL_MODULES
            )
            import_match = any(
                dep.replace(".", "/") in other_path
                or other_path.replace(".py", "").replace("/", ".") in dep
                for dep in meaningful_deps
            )
            if sym_match or dep_match or import_match:
                linked.append(other_meta)
                if len(linked) >= 10:
                    break
        return linked

    def _admit_advisory_finding(
        self,
        raw_finding: SavedFinding,
        fpath: str,
        wt_root: Path,
    ) -> tuple[Any | None, SavedFinding | None]:
        """Attempt to admit an advisory finding candidate against the active worktree."""
        idx = len(getattr(self, "admitted_scanner_findings", []))
        counts = getattr(self, "rejection_counts", None)
        res = _admit_single_candidate(
            raw_finding,
            idx,
            session_id=getattr(self, "session_id", "advisory"),
            worktree_root=wt_root,
            commit_files={fpath, Path(fpath).as_posix().lstrip("/")},
            file_content_getter=partial(
                _read_cited_file,
                worktree_root=wt_root,
                resolve_file_path=self._resolve_file_path,
                coverage_gaps=self.errored_files,
            ),
            path_classes=getattr(self, "path_classes", None),
            suppressions=getattr(self, "suppressions", None),
            added_diff_lines=getattr(self, "added_diff_lines", None),
            base_fingerprints=getattr(self, "base_fingerprints", None),
            rejection_counts=counts,
            manifest_objects=getattr(self, "manifest_objects", None),
        )
        if counts and (prof := active_profiler()):
            prof.set_rejections(counts)
        return res

    def _audit_dep_vulnerability(
        self,
        fpath: str,
        dep: DependencySpec,
        v: VulnerabilityRecord,
        *,
        wt_root: Path | None,
        has_file: bool,
    ) -> SavedFinding | None:
        """Build and admit a single dependency vulnerability candidate (#871).

        Returns None for an advisory admission rejects (#1302) or a suppression covers (#1295).
        """
        raw = _build_vulnerability_finding(
            fpath, dep, v, session_id=getattr(self, "session_id", "advisory")
        )
        if not (has_file and wt_root is not None):
            return raw

        frozen, admitted_sf = self._admit_advisory_finding(raw, fpath, wt_root)
        if frozen is None:
            return None

        if hasattr(self, "admitted_scanner_findings"):
            self.admitted_scanner_findings.append(frozen)
        return admitted_sf

    def _audit_file_dependencies(
        self,
        fpath: str,
        file_deps: list[DependencySpec],
        dep_cache: dict[tuple[str, str, str], Any],
    ) -> list[SavedFinding]:
        """Audit dependencies against vulnerability cache and return any vulnerability findings."""
        findings: list[SavedFinding] = []
        wt_root = reviewed_tree(self.target_dir) if getattr(self, "target_dir", None) else None
        has_file = wt_root is not None and (wt_root / fpath).is_file()

        for dep in file_deps:
            for v in _audit_single_dep(dep, dep_cache):
                sf = self._audit_dep_vulnerability(
                    fpath, dep, v, wt_root=wt_root, has_file=has_file
                )
                if sf is not None:
                    findings.append(sf)
        return findings

    def _audit_file_network_references(
        self,
        fpath: str,
        file_nets: list[NetworkReference],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> list[SavedFinding]:
        """Audit network references against reputation cache and return any suspicious findings."""
        findings: list[SavedFinding] = []
        for net in file_nets:
            rep = net_cache.get(net.target, NetworkReputationRecord(target=net.target, ip=""))
            net.reputation = rep
            if rep.is_malicious:
                net.security_status = f"⚠️ Flagged ({rep.reputation_summary})"
            elif rep.ports:
                net.security_status = f"✓ Safe (Ports: {', '.join(map(str, rep.ports[:3]))})"
            else:
                net.security_status = "✓ Safe / Low Risk"

            if rep.is_malicious:
                findings.append(_build_malicious_network_finding(fpath, net, rep))
        return findings

    def _build_and_persist_single_payload(
        self,
        fpath: str,
        metadata_by_path: dict[str, FileAnalysisMeta],
        static_findings_by_file: dict[str, list[SavedFinding]],
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dep_cache: dict[tuple[str, str, str], PackageLookupResult],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> FileReviewPayload:
        """Construct, validate, and write a single file review tracking JSON payload."""
        fmeta = self._find_matching_metadata(fpath, metadata_by_path) or FileAnalysisMeta(
            path=fpath
        )
        linked = self._find_linked_files(fpath, fmeta, metadata_by_path)
        file_deps, file_nets = raw_file_data.get(fpath, ([], []))

        initial_findings = list(static_findings_by_file.get(fpath, []))
        initial_findings.extend(self._audit_file_dependencies(fpath, file_deps, dep_cache))
        initial_findings.extend(self._audit_file_network_references(fpath, file_nets, net_cache))

        payload = FileReviewPayload(
            file_path=fpath,
            metadata=fmeta,
            linked_files=linked,
            findings=initial_findings,
            external_dependencies=file_deps,
            network_references=file_nets,
        )
        from devops_cli.dry_run.state import is_dry_run

        if not is_dry_run():
            self.session.write_payload(payload)
        return payload

    def _assemble_single_file_payload(
        self,
        fpath: str,
        metadata_by_path: dict[str, FileAnalysisMeta],
        static_findings_by_file: dict[str, list[SavedFinding]],
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dep_cache: dict[tuple[str, str, str], PackageLookupResult],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> FileReviewPayload | None:
        """Safely build and persist single file payload with error logging."""
        try:
            return self._build_and_persist_single_payload(
                fpath,
                metadata_by_path,
                static_findings_by_file,
                raw_file_data,
                dep_cache,
                net_cache,
            )
        except Exception as exc:
            logger.error("Error creating review payload for %s: %s", fpath, exc)
            err_desc = _format_error_detail("Initialization", exc)
            _record_coverage_gap(self.errored_files, fpath, err_desc)
            warn_msg = f"  [yellow]• [bold red]Skipped errored file during init:[/bold red] [bold]{fpath}[/bold] [dim]({err_desc})[/dim][/yellow]"
            print_info(warn_msg, prefix=False)
            return None

    def _assemble_and_persist_payloads(
        self,
        file_paths: list[str],
        metadata_by_path: dict[str, FileAnalysisMeta],
        static_findings_by_file: dict[str, list[SavedFinding]],
        raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]],
        dep_cache: dict[tuple[str, str, str], PackageLookupResult],
        net_cache: dict[str, NetworkReputationRecord],
    ) -> list[FileReviewPayload]:
        """Assemble FileReviewPayload models and persist tracking JSON files."""
        n_paths = len(file_paths)
        print_info(
            f"  • Assembling payload tracking files & linking dependency graphs for {n_paths} file(s)...",
            prefix=False,
        )
        payloads: list[FileReviewPayload] = []
        with trace_span("review.assemble_payloads", attributes={"file_count": n_paths}):
            for fpath in file_paths:
                p = self._assemble_single_file_payload(
                    fpath,
                    metadata_by_path,
                    static_findings_by_file,
                    raw_file_data,
                    dep_cache,
                    net_cache,
                )
                if p is not None:
                    payloads.append(p)

        return payloads

    def init_per_file_payloads(
        self,
        file_paths: list[str],
        metadata_by_path: dict[str, FileAnalysisMeta],
        stage_flags: ReviewStageFlags | None = None,
        diff_text_by_file: Mapping[str, str] | None = None,
        pages: Sequence[str] | None = None,
        added_diff_lines: set[tuple[str, int]] | None = None,
    ) -> list[FileReviewPayload]:
        """Initialize per-file JSON payloads under session files directory."""
        self.added_diff_lines = _resolve_review_added_diff_lines(
            getattr(self, "added_diff_lines", None),
            added_diff_lines,
            pages,
            diff_text_by_file,
        )
        from devops_cli.review.diff import extract_file_diff_hunks

        if pages:
            self.diff_hunks = extract_file_diff_hunks(pages)
        elif diff_text_by_file:
            self.diff_hunks = extract_file_diff_hunks(diff_text_by_file.values())
        else:
            self.diff_hunks = {}
        if not self.diff_hunks and self.added_diff_lines:
            for p, line in self.added_diff_lines:
                self.diff_hunks.setdefault(p, []).append((line, line))

        n_paths = len(file_paths)
        with trace_span("review.init_payloads", attributes={"file_count": n_paths}):
            print_info(
                f"[dim]Initializing payload tracking for {n_paths} file(s)...[/dim]",
                prefix=False,
            )

            # The static scan: the analyzers, then the Ruff, mypy and complexity evidence. With
            # the stage off, no tool starts (#2007).
            static_findings_by_file: dict[str, list[SavedFinding]]
            if stage_flags is not None and not stage_flags.static_scan:
                print_info(
                    "[dim]  • Static analyzers and Ruff, mypy and complexity evidence skipped "
                    "(disabled via flag)[/dim]",
                    prefix=False,
                )
                static_findings_by_file = {f: [] for f in file_paths}
            else:
                static_findings_by_file = self._run_static_scanners(
                    file_paths, added_diff_lines=self.added_diff_lines
                )
                evidence_findings_by_file = self._run_review_evidence(
                    file_paths, added_diff_lines=self.added_diff_lines
                )
                for f_path, f_items in evidence_findings_by_file.items():
                    static_findings_by_file.setdefault(f_path, []).extend(f_items)

            # Concurrently pre-fetch threat intelligence if opt-in (#1146)
            raw_file_data: dict[str, tuple[list[DependencySpec], list[NetworkReference]]] = {}
            dep_cache: dict[tuple[str, str, str], Any] = {}
            net_cache: dict[str, NetworkReputationRecord] = {}

            if getattr(self, "threat_intel", False):
                raw_file_data, net_cache = self._fetch_threat_intel(file_paths)

            # Assemble and persist FileReviewPayload objects; a file kept off persona pages
            # gets one only to carry what the secret scan found in it
            payloads = self._assemble_and_persist_payloads(
                file_paths=[*file_paths, *_scanned_routed_files(self, static_findings_by_file)],
                metadata_by_path=metadata_by_path,
                static_findings_by_file=static_findings_by_file,
                raw_file_data=raw_file_data,
                dep_cache=dep_cache,
                net_cache=net_cache,
            )

            print_info(
                f"[dim]  ✓ Initialized {len(payloads)} file review payload tracking file(s)[/dim]",
                prefix=False,
            )
            return payloads

    def scan_routed_files(
        self, stage_flags: ReviewStageFlags | None = None
    ) -> list[FileReviewPayload]:
        """Secret-scan the files kept off persona pages, with nothing else to review, and give
        each with a finding its payload (#948). No model is called."""
        if stage_flags is not None and not stage_flags.static_scan:
            return []
        findings_by_file = self._run_static_scanners([])
        return self._assemble_and_persist_payloads(
            file_paths=_scanned_routed_files(self, findings_by_file),
            metadata_by_path={},
            static_findings_by_file=findings_by_file,
            raw_file_data={},
            dep_cache={},
            net_cache={},
        )

    # ── Consolidated Report Generation ───────────────────────────────────────
    def _collect_and_deduplicate_findings(
        self, file_payloads: list[FileReviewPayload]
    ) -> list[SavedFinding]:
        """Collect all reportable, non-invalidated findings and consolidate duplicates."""
        unique: dict[tuple[str, str], SavedFinding] = {}
        for payload in file_payloads:
            for f in payload.findings:
                if f.status != "INVALIDATED" and f.reportable:
                    key = (f.fingerprint.strip().lower(), f.location.strip().lower())
                    if key not in unique:
                        unique[key] = f
        return sort_findings(list(unique.values()))

    def _collect_unique_dependencies_and_network_endpoints(
        self, file_payloads: list[FileReviewPayload]
    ) -> tuple[list[DependencySpec], list[NetworkReference]]:
        """Collect deduplicated dependencies and network endpoints across all payloads."""
        from devops_cli.security.reference_extractor import (
            deduplicate_network_references,
            is_example_or_invalid_network_target,
            sort_network_references,
        )

        all_deps: list[DependencySpec] = []
        raw_nets: list[NetworkReference] = []
        for payload in file_payloads:
            for d in payload.external_dependencies:
                if not any(
                    x.name == d.name and x.version_range == d.version_range for x in all_deps
                ):
                    all_deps.append(d)
            for n in payload.network_references:
                if n.is_example or is_example_or_invalid_network_target(n.target):
                    continue
                raw_nets.append(n)
        all_nets = sort_network_references(deduplicate_network_references(raw_nets))
        return all_deps, all_nets

    @staticmethod
    def _format_markdown_fix(fix: str) -> str:
        """Format fix recommendation safely into Markdown without unbalancing code fences."""
        clean_fix = strip_outer_markdown_bold(fix.strip())
        if not clean_fix:
            return ""

        balanced_fix, has_fences = balance_markdown_fences(clean_fix)
        if has_fences:
            return f"- **Fix Recommendation**:\n\n{balanced_fix}"

        max_backticks = max((len(m) for m in re.findall(r"`+", clean_fix)), default=0)
        fence = "`" * max(3, max_backticks + 1)
        return f"- **Fix Recommendation**:\n{fence}\n{clean_fix}\n{fence}"

    @staticmethod
    def _format_markdown_description(description: str) -> str:
        """Format finding description into indented Markdown list item preserving paragraphs."""
        clean_desc = strip_outer_markdown_bold(description.strip())
        if not clean_desc:
            return ""
        balanced_desc, _ = balance_markdown_fences(clean_desc)
        lines = balanced_desc.splitlines()
        if len(lines) <= 1:
            return f"- **Description**: {balanced_desc}"
        indented = (
            lines[0] + "\n" + "\n".join(f"  {line}" if line.strip() else "" for line in lines[1:])
        )
        return f"- **Description**: {indented}"

    @staticmethod
    def _build_findings_table(reportable_findings: list[SavedFinding]) -> list[str]:
        """Render summary table of reportable findings."""
        if not reportable_findings:
            return ["✅ **No critical issues found during review.**"]

        lines = [
            "| Severity | Location | Title | Status | Producer |",
            "|---|---|---|---|---|",
        ]
        for f in reportable_findings:
            clean_sev = (
                (f.severity or "INFORMATIONAL").replace("|", "\\|").replace("\n", " ").strip()
            )
            clean_loc = f.location.strip("`").replace("|", "\\|").replace("\n", " ").strip()
            clean_title = escape_markdown_title(f.title, is_table=True)
            clean_status = f.status.replace("|", "\\|").replace("\n", " ").strip()
            clean_producer = f.producer.replace("|", "\\|").replace("\n", " ").strip()
            lines.append(
                f"| **{clean_sev}** | `{clean_loc}` | {clean_title} | {clean_status} | {clean_producer} |"
            )
        return lines

    @staticmethod
    def _build_detailed_findings_section(reportable_findings: list[SavedFinding]) -> list[str]:
        """Render detailed findings section with balanced code blocks and clean formatting."""
        if not reportable_findings:
            return []

        lines = ["", "## Detailed Findings"]
        for idx, f in enumerate(reportable_findings, 1):
            clean_title = escape_markdown_title(f.title, is_table=False)
            clean_loc = f.location.strip("`").strip()
            lines.append(f"### {idx}. [{(f.severity or 'INFORMATIONAL').upper()}] {clean_title}")
            lines.append(f"- **Location**: `{clean_loc}`")
            lines.append(f"- **Producer**: {f.producer}")
            lines.append(f"- **Status**: {f.status}")
            if f.status == "MITIGATED" and f.invalidation_reason:
                lines.append(f"- **Mitigation**: {f.invalidation_reason.strip()}")
            desc_line = ReviewPipelineOrchestrator._format_markdown_description(f.description)
            if desc_line:
                lines.append(desc_line)
            if f.fix:
                fix_md = ReviewPipelineOrchestrator._format_markdown_fix(f.fix)
                if fix_md:
                    lines.append(fix_md)
            lines.append("")
        return lines

    @staticmethod
    def _build_dependencies_table(all_deps: list[DependencySpec]) -> list[str]:
        """Render external dependencies audit table."""
        lines = [f"## {_REPORT_DEPENDENCIES_SECTION} (OSV.dev)"]
        if not all_deps:
            lines.extend(["✅ **No external dependencies declared in review scope.**", ""])
            return lines

        lines.extend(
            [
                "| Severity | Dependency | Version Range | Ecosystem | Security Status | Location |",
                "|---|---|---|---|---|---|",
            ]
        )
        for dep in all_deps:
            sev_upper = (dep.severity or "").upper()
            if sev_upper in ("UNCHECKED", "NOT_QUERIED", "NOT QUERIED"):
                sev_badge = "UNCHECKED"
            elif sev_upper not in ("CLEAN", "NONE", "INFO"):
                sev_badge = f"**{dep.severity}**"
            else:
                sev_badge = dep.severity
            loc_str = f"`{dep.location}`" if dep.location else "—"
            lines.append(
                f"| {sev_badge} | `{dep.name}` | `{dep.version_range}` | {dep.ecosystem} | "
                f"{dep.security_status} | {loc_str} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _build_network_table(all_nets: list[NetworkReference]) -> list[str]:
        """Render network endpoints and references audit table."""
        from devops_cli.security.reference_extractor import (
            deduplicate_network_references,
            is_example_or_invalid_network_target,
            sort_network_references,
        )

        filtered_md_nets = [
            n
            for n in all_nets
            if not getattr(n, "is_example", False)
            and not is_example_or_invalid_network_target(getattr(n, "target", ""))
        ]
        sorted_md_nets = sort_network_references(deduplicate_network_references(filtered_md_nets))

        lines = [f"## {_REPORT_NETWORK_SECTION} (Shodan InternetDB & Cloudflare Radar)"]
        if not sorted_md_nets:
            lines.extend(
                [
                    "✅ **No network endpoints or remote addresses referenced in review scope.**",
                    "",
                ]
            )
            return lines

        lines.extend(
            [
                "| Target | Type | Scope | Security Status | Location |",
                "|---|---|---|---|---|",
            ]
        )
        for net in sorted_md_nets:
            scope_str = "Local" if net.is_local else "External"
            loc_str = f"`{net.location}`" if net.location else "—"
            lines.append(
                f"| `{net.target}` | {net.reference_type} | {scope_str} | "
                f"{net.security_status} | {loc_str} |"
            )
        lines.append("")
        return lines

    def _build_category_baseline_section(
        self,
        all_findings: list[SavedFinding] | None,
        reportable_findings: list[SavedFinding],
    ) -> list[str]:
        """Render category false positive baseline section if historical data or findings exist."""
        findings_to_use = all_findings if all_findings is not None else reportable_findings
        if not findings_to_use:
            return []
        # The session is not published, so it is not in the history it is compared to.
        return format_category_baseline_markdown(findings_to_use, self.session.directory.parent)

    def _build_verdict_distributions_section(
        self, candidate_findings: list[SavedFinding] | None
    ) -> list[str]:
        """Build Markdown table of verdict field distributions and discrimination status."""
        if not candidate_findings:
            return []
        dists = compute_verdict_distributions(candidate_findings)
        lines = [
            "## Verdict Field Distributions",
            "",
            "| Verdict Field | Distribution | Discriminates? |",
            "|---|---|---|",
        ]
        field_order = [
            ("status", "Status"),
            ("reportable", "Reportable"),
            ("verified", "Verified"),
            ("mitigated", "Mitigated"),
        ]
        for key, label in field_order:
            counts = dists.get(key, {})
            dist_str = (
                ", ".join(f"`{k}`: {v}" for k, v in sorted(counts.items()) if v > 0) or "None"
            )
            discriminates = (
                "Yes" if is_field_discriminating(counts) else "**No (never discriminates)**"
            )
            lines.append(f"| `{label}` | {dist_str} | {discriminates} |")
        lines.append("")
        return lines

    def _build_consolidated_markdown_report(
        self,
        session_id: str,
        generated_at: str,
        reportable_findings: list[SavedFinding],
        all_deps: list[DependencySpec],
        all_nets: list[NetworkReference],
        all_findings: list[SavedFinding] | None = None,
        candidate_findings: list[SavedFinding] | None = None,
        symbol_delta_summary: dict[str, int] | None = None,
    ) -> str:
        from devops_cli.ai.review.stages.reporting import (
            status_summary_lines,
            synthesize_report_executive_summary,
        )

        lines = [
            f"# Code Review Report (Session `{session_id}`)",
            f"*Generated at: {generated_at}*",
        ]
        if self.partial_context:
            lines.append("*Context: partial context*")
        lines.append("")
        lines.extend(
            synthesize_report_executive_summary(
                reportable_findings=reportable_findings,
                all_deps=all_deps,
                all_nets=all_nets,
                errored_files=self.errored_files,
                analyzer_line=_static_analysis_line(self.static_analyzers, self.static_severities),
            )
        )
        summary_lines = [
            "## Summary of Reportable Findings",
            f"Total Findings: **{len(reportable_findings)}**",
            *status_summary_lines(reportable_findings),
        ]
        if symbol_delta_summary and any(symbol_delta_summary.values()):
            summary_lines.append(
                f"Symbol Delta: **+{symbol_delta_summary.get('added', 0)}** / "
                f"**-{symbol_delta_summary.get('removed', 0)}** / "
                f"**={symbol_delta_summary.get('retained', 0)}**"
            )
        summary_lines.append("")
        lines.extend(summary_lines)
        lines.extend(self._build_findings_table(reportable_findings))
        lines.extend(self._build_detailed_findings_section(reportable_findings))
        lines.extend(self._build_introduced_findings_section(reportable_findings))
        lines.extend(self._build_preexisting_findings_section(reportable_findings))
        lines.extend(self._build_suppressed_findings_section(all_findings or reportable_findings))
        lines.extend(self._build_complexity_section())
        lines.extend(self._build_dependencies_table(all_deps))
        lines.extend(self._build_network_table(all_nets))

        lines.extend(self._build_static_analyzers_section())
        lines.extend(self._build_coverage_section())
        lines.extend(self._build_tool_runs_section())

        baseline_lines = self._build_category_baseline_section(
            candidate_findings or all_findings, reportable_findings
        )
        if baseline_lines:
            lines.extend(baseline_lines)

        dist_lines = self._build_verdict_distributions_section(candidate_findings or all_findings)
        if dist_lines:
            lines.extend(dist_lines)

        from devops_cli.review.analysis import render_model_analysis_markdown

        analysis_report = getattr(self, "analysis_report", None)
        if analysis_report is not None:
            lines.extend(render_model_analysis_markdown(analysis_report))
        else:
            from devops_cli.ai.kb import load_matched_kb_manuals

            _, drift = load_matched_kb_manuals(kubernetes_version=self.kubernetes_version)
            if drift:
                lines.append("## Reference coverage: drift")
                lines.append("")
                for d in sorted(drift, key=lambda x: x.path):
                    lines.append(f"- `{d.path}`: {d.reason}")
                lines.append("")

        if self.errored_files:
            lines.append("## Skipped / Errored Files")
            lines.append("| File Path | Stage / Error Reason |")
            lines.append("|---|---|")
            for fpath, reason in sorted(self.errored_files.items()):
                clean_f = fpath.replace("|", "\\|").replace("\n", " ").strip()
                clean_r = reason.replace("|", "\\|").replace("\n", " ").strip()
                lines.append(f"| `{clean_f}` | {clean_r} |")
            lines.append("")

        return "\n".join(lines)

    def _run_group_analysis_stage(self, stage_flags: ReviewStageFlags | None) -> Any:
        """Execute bounded per-group model analysis on admitted scanner findings (#1147)."""
        from devops_cli.ai.review.profile import review_stage
        from devops_cli.dry_run.state import is_dry_run
        from devops_cli.review.analysis import default_environment_facts, run_group_analysis

        if stage_flags is not None and not stage_flags.group_analysis:
            return None
        admitted = getattr(self, "admitted_scanner_findings", None)
        if not admitted or is_dry_run():
            return None
        with review_stage("group_analysis"):
            file_contents: dict[str, str] = {}
            for af in admitted:
                fpath = getattr(af, "path", "")
                if fpath and fpath not in file_contents:
                    resolved = self._resolve_file_path(fpath)
                    if resolved.is_file():
                        file_contents[fpath] = resolved.read_text(
                            encoding="utf-8", errors="replace"
                        )
            env = default_environment_facts(
                admitted,
                kubernetes_version=self.kubernetes_version,
            )
            report = run_group_analysis(
                admitted,
                llm_client=self.llm_client,
                file_contents=file_contents,
                environment=env,
                concurrency=self.concurrency,
            )
            self.session.write_analysis(report)
            self.analysis_report = report
            return report

    def _static_analyzer_notes(self) -> dict[str, str]:
        """Each analyzer's reason as the report says it, with the files it left out counted."""
        return _reasons_with_files_not_scanned(
            self.static_analyzer_reasons, self.static_analyzer_unscanned
        )

    def _build_static_analyzers_section(self) -> list[str]:
        """Which static analyzers ran, so a scan with no findings is not read as clean."""
        if not self.static_analyzers:
            return []
        rows = []
        notes = self._static_analyzer_notes()
        for name, state in self.static_analyzers.items():
            reason = notes.get(name)
            result = f"{state}: {reason}" if reason else state
            cell = " ".join(result.split()).replace("|", "\\|")
            rows.append(f"| {name} | {cell} |")
        return ["## Static Analyzers", "| Analyzer | Result |", "|---|---|", *rows, ""]

    def _build_tool_runs_section(self) -> list[str]:
        """Which tools ran, at which versions, how, and over which config and rules (#772)."""
        from devops_cli.ai.review.tool_runs import tool_runs_section

        return tool_runs_section(self.tool_executor.runs)

    def _build_coverage_section(self) -> list[str]:
        """Coverage matrix per (tool, file) in review.md."""
        if not self.coverage:
            return []
        rows = [
            f"| {tool.replace('|', r'\|')} | `{fpath.replace('|', r'\|')}` | {status.replace('|', r'\|')} |"
            for tool in sorted(self.coverage)
            for fpath, status in sorted(self.coverage[tool].items())
        ]
        return ["## Coverage", "| Tool | File | Status |", "|---|---|---|", *rows, ""]

    def _build_introduced_findings_section(self, findings: list[Any]) -> list[str]:
        """Render Introduced Findings section for review.md (#871)."""
        introduced = [
            f
            for f in findings
            if getattr(f, "introduced", True) and getattr(f, "state", "OPEN") != "SUPPRESSED"
        ]
        if not introduced:
            return []
        rows = [
            f"| **{getattr(f, 'severity', 'MEDIUM')}** | `{getattr(f, 'location', '') or getattr(f, 'location_display', '') or getattr(f, 'path', '')}` | {escape_markdown_title(getattr(f, 'title', '') or getattr(f, 'message', ''), is_table=True)} |"
            for f in introduced
        ]
        return [
            "## Introduced Findings",
            "| Severity | Location | Title |",
            "|---|---|---|",
            *rows,
            "",
        ]

    def _build_preexisting_findings_section(self, findings: list[Any]) -> list[str]:
        """Render Pre-existing Findings in Changed Files section for review.md (#871)."""
        preexisting = [
            f
            for f in findings
            if not getattr(f, "introduced", True) and getattr(f, "state", "OPEN") != "SUPPRESSED"
        ]
        if not preexisting:
            return []
        rows = [
            f"| **{getattr(f, 'severity', 'MEDIUM')}** | `{getattr(f, 'location', '') or getattr(f, 'location_display', '') or getattr(f, 'path', '')}` | {escape_markdown_title(getattr(f, 'title', '') or getattr(f, 'message', ''), is_table=True)} |"
            for f in preexisting
        ]
        return [
            "## Pre-existing Findings in Changed Files",
            "| Severity | Location | Title |",
            "|---|---|---|",
            *rows,
            "",
        ]

    def _build_suppressed_findings_section(self, findings: list[Any]) -> list[str]:
        """Render Suppressed Findings section for review.md (#871)."""
        suppressed: list[Any] = []
        admitted = getattr(self, "admitted_scanner_findings", None)
        if isinstance(admitted, (list, tuple)):
            suppressed.extend(
                f
                for f in admitted
                if getattr(f, "state", "") == "SUPPRESSED"
                or getattr(f, "suppressed_by_change", False)
            )
        suppressed.extend(
            f
            for f in findings
            if getattr(f, "state", "") == "SUPPRESSED" or getattr(f, "suppressed_by_change", False)
        )
        if not suppressed:
            return []
        rows: list[str] = []
        seen: set[tuple[str, str, str]] = set()
        for f in suppressed:
            # Admitted findings carry path and line apart; location_display joins them, so two
            # suppressions of one rule in one file stay two rows.
            loc = (
                getattr(f, "location_display", "")
                or getattr(f, "location", "")
                or getattr(f, "path", "")
            )
            key = (loc, getattr(f, "rule_id", ""), getattr(f, "title", ""))
            if key in seen:
                continue
            seen.add(key)
            sev = getattr(f, "severity", "MEDIUM")
            reason = getattr(f, "suppression_reason", "Inline marker") or "Inline marker"
            expiry = getattr(f, "suppression_expiry", None) or "None"
            by = (
                "suppressed by this change"
                if getattr(f, "suppressed_by_change", False)
                else "review.toml/base marker"
            )
            rows.append(f"| **{sev}** | `{loc}` | {reason} | {expiry} | {by} |")
        return [
            "## Suppressed Findings",
            "| Severity | Location | Reason | Expiry | Suppressed By |",
            "|---|---|---|---|---|",
            *rows,
            "",
        ]

    def _build_complexity_section(self) -> list[str]:
        """Render before/after Complexity table for changed functions in review.md (#873)."""
        deltas = getattr(self, "complexity_deltas", [])
        if not deltas:
            return []
        rows = [
            f"| `{d['file']}` | `{d['function']}` | {d['before'] if d['before'] is not None else '—'} | {d['after'] if d['after'] is not None else '—'} |"
            for d in deltas
        ]
        return [
            "## Complexity",
            "| File | Function | Before | After |",
            "|---|---|---|---|",
            *rows,
            "",
        ]

    def _render_console_findings_table(
        self, console: Any, reportable_findings: list[SavedFinding]
    ) -> None:
        """Render the findings table and detail panels to console.

        Unless `full_output`, the table lists MEDIUM and above, panels follow for HIGH and
        above, and the rest are counted on one line naming review.md and the command that
        lists them. Each finding keeps its number in review.md.
        """
        if not reportable_findings:
            print_success("No reportable findings across reviewed files.", console=console)
            return

        tabled, panelled, minor = self._select_console_findings(reportable_findings)
        if tabled:
            print_table(
                title="Code Review Findings",
                columns=_CONSOLE_FINDING_COLUMNS,
                rows=[_format_console_finding_row(index, finding) for index, finding in tabled],
                console=console,
            )
        if minor:
            summary, command = self._format_minor_findings_line(minor)
            print_info(summary, prefix=False, console=console, safe=True)
            # Soft wrap keeps the command on one line at any width, so it copies as is.
            (console or get_console()).print(
                f"  {command}", markup=False, highlight=False, soft_wrap=True
            )
        for finding_index, finding in panelled:
            self._render_single_finding_panel(console, finding, finding_index)

    def _select_console_findings(
        self, reportable_findings: list[SavedFinding]
    ) -> tuple[list[tuple[int, SavedFinding]], list[tuple[int, SavedFinding]], list[SavedFinding]]:
        """The numbered findings for the table and for detail panels, and those only counted."""
        numbered = list(enumerate(reportable_findings, 1))
        if self.full_output:
            return numbered, numbered, []
        tabled = [
            (index, finding)
            for index, finding in numbered
            if _console_severity(finding) in CONST_REVIEW_CONSOLE_TABLE_SEVERITIES
        ]
        panelled = [
            (index, finding)
            for index, finding in tabled
            if _console_severity(finding) in CONST_REVIEW_CONSOLE_PANEL_SEVERITIES
        ]
        minor = [
            finding
            for finding in reportable_findings
            if _console_severity(finding) not in CONST_REVIEW_CONSOLE_TABLE_SEVERITIES
        ]
        return tabled, panelled, minor

    def _format_minor_findings_line(self, minor: list[SavedFinding]) -> tuple[str, str]:
        """Count the findings left out of the table by status and name review.md; return that
        line and the command that lists them."""
        severities = _in_order({_console_severity(f) for f in minor}, CONST_SEVERITY_ORDER)
        statuses = _format_counts(
            Counter(f.status.upper() for f in minor), CONST_REVIEW_STATUS_ORDER
        )
        filters = " ".join(f"--severity {severity}" for severity in severities)
        command = f"devops review findings {self.session.name} {filters} --details"
        return (
            f"Not shown: {len(minor)} {' and '.join(severities)} finding(s) ({statuses}). "
            f"They are in {self.session.report_path}; list them with:",
            command,
        )

    def _render_single_finding_panel(
        self, console: Any, finding: SavedFinding, finding_index: int
    ) -> None:
        """Render a single finding detail panel with remediation and references."""
        from devops_cli.output import SEV_COLOR_MAP

        sev_upper = (finding.severity or "INFORMATIONAL").upper()
        sev_color = SEV_COLOR_MAP.get(sev_upper, "white")
        st_badge = _get_finding_status_badge(finding.status)
        title_header = f"[{sev_color} bold]Finding #{finding_index}: [{sev_upper}] {escape_text(finding.title)}[/{sev_color} bold]  {st_badge}"
        panel_lines = [
            f"[bold]Location:[/bold] [cyan]{escape_text(finding.location)}[/cyan]  |  [bold]Producer:[/bold] [magenta]{escape_text(finding.producer)}[/magenta]",
        ]
        if finding.description:
            clean_desc = escape_text(format_clean_text_field(finding.description).strip())
            panel_lines.extend(["", "[bold]Description:[/bold]", clean_desc])
        if finding.fix:
            clean_fix = escape_text(format_clean_text_field(finding.fix).strip())
            panel_lines.extend(["", "[bold]Suggested Fix:[/bold]", clean_fix])
        if finding.invalidation_reason:
            clean_inv = escape_text(finding.invalidation_reason.strip())
            label = "Mitigation" if finding.status == "MITIGATED" else "Invalidation Reason"
            panel_lines.extend(["", f"[bold yellow]{label}:[/bold yellow] {clean_inv}"])
        if finding.references:
            refs_list = (
                finding.references
                if isinstance(finding.references, list)
                else [str(finding.references)]
            )
            panel_lines.extend(["", f"[dim]References: {escape_text(', '.join(refs_list))}[/dim]"])

        print_panel(
            "\n".join(panel_lines),
            title=title_header,
            border_style=sev_color,
            console=console,
        )

    def _render_console_dependencies_table(
        self, console: Any, all_deps: list[DependencySpec]
    ) -> None:
        """Render the dependency security audit to console.

        Unless `full_output`, one summary line and then only the vulnerable packages.
        """
        if not self.full_output:
            vulnerable = [d for d in all_deps if _is_vulnerable_dependency(d)]
            line = _format_dependency_console_line(all_deps, vulnerable)
            print_info(line, prefix=False, console=console, safe=True)
            if vulnerable:
                print_table(
                    title="Vulnerable Dependencies (OSV.dev)",
                    columns=_CONSOLE_DEPENDENCY_COLUMNS,
                    rows=[_format_dependency_table_row(d) for d in vulnerable],
                    console=console,
                )
            return
        print_table(
            title="External Dependencies Security Audit (OSV.dev)",
            columns=_CONSOLE_DEPENDENCY_COLUMNS,
            rows=[_format_dependency_table_row(d) for d in all_deps]
            or [_CONSOLE_NO_DEPENDENCIES_ROW],
            console=console,
        )

    def _render_console_network_table(self, console: Any, all_nets: list[NetworkReference]) -> None:
        """Render the network references audit to console.

        Unless `full_output`, one summary line and then only the endpoints flagged by
        reputation.
        """
        from devops_cli.security.reference_extractor import (
            deduplicate_network_references,
            is_example_or_invalid_network_target,
            sort_network_references,
        )

        filtered = [
            n
            for n in all_nets
            if not getattr(n, "is_example", False)
            and not is_example_or_invalid_network_target(getattr(n, "target", ""))
        ]
        sorted_nets = sort_network_references(deduplicate_network_references(filtered))
        if not self.full_output:
            flagged = [n for n in sorted_nets if _is_flagged_network_reference(n)]
            line = _format_network_console_line(sorted_nets, flagged)
            print_info(line, prefix=False, console=console, safe=True)
            if flagged:
                print_table(
                    title="Flagged Network References (Shodan & Cloudflare Radar)",
                    columns=_CONSOLE_NETWORK_COLUMNS,
                    rows=[_format_network_ref_table_row(n) for n in flagged],
                    console=console,
                )
            return
        print_table(
            title="Network References & Endpoints Security Audit (Shodan & Cloudflare Radar)",
            columns=_CONSOLE_NETWORK_COLUMNS,
            rows=[_format_network_ref_table_row(n) for n in sorted_nets]
            or [_CONSOLE_NO_NETWORK_ROW],
            console=console,
        )

    def _render_console_errored_files_table(self, console: Any) -> None:
        """Render table of skipped/errored files to console."""
        if not self.errored_files:
            return

        columns = [
            ("File Path", "bold red"),
            ("Stage / Error Details", "yellow"),
        ]
        rows = [[fpath, reason] for fpath, reason in sorted(self.errored_files.items())]
        print_table(
            title="Skipped / Errored Files During Review",
            columns=columns,
            rows=rows,
            border_style="yellow",
            console=console,
        )

    def _format_severity_breakdown(
        self, reportable_findings: list[SavedFinding]
    ) -> tuple[str, str]:
        """Format findings summary string and verification rate string."""
        if not reportable_findings:
            return "[bold green]0 findings (Clean)[/bold green]", "[green]✓ All clean[/green]"

        counts = {
            "CRITICAL": sum(
                1
                for finding in reportable_findings
                if (finding.severity or "").upper() == "CRITICAL"
            ),
            "HIGH": sum(
                1 for finding in reportable_findings if (finding.severity or "").upper() == "HIGH"
            ),
            "MEDIUM": sum(
                1 for finding in reportable_findings if (finding.severity or "").upper() == "MEDIUM"
            ),
            "LOW": sum(
                1 for finding in reportable_findings if (finding.severity or "").upper() == "LOW"
            ),
            "INFO": sum(
                1
                for finding in reportable_findings
                if (finding.severity or "").upper() in ("INFO", "INFORMATIONAL")
            ),
        }
        styles = {
            "CRITICAL": "[bold red]{cnt} Critical[/bold red]",
            "HIGH": "[red]{cnt} High[/red]",
            "MEDIUM": "[yellow]{cnt} Medium[/yellow]",
            "LOW": "[cyan]{cnt} Low[/cyan]",
            "INFO": "[green]{cnt} Info[/green]",
        }
        sev_parts = [styles[sev].format(cnt=cnt) for sev, cnt in counts.items() if cnt > 0]
        sev_breakdown = ", ".join(sev_parts) if sev_parts else "None"
        findings_str = f"{len(reportable_findings)} ({sev_breakdown})"

        ver_count = sum(
            1 for finding in reportable_findings if (finding.status or "").upper() == "VERIFIED"
        )
        ver_pct = ver_count / len(reportable_findings)
        ver_rate_str = f"{ver_count}/{len(reportable_findings)} verified ({ver_pct:.0%})"
        return findings_str, ver_rate_str

    def _format_dependency_summary(self, all_deps: list[DependencySpec]) -> str:
        """Format external dependency audit summary string."""
        if not all_deps:
            return "0 scanned"
        vuln_count = sum(
            1
            for dep in all_deps
            if (dep.severity or "").upper()
            not in ("CLEAN", "NONE", "INFO", "NOT_QUERIED", "NOT QUERIED", "UNCHECKED")
        )
        queried_count = sum(
            1
            for dep in all_deps
            if getattr(dep, "queried", False)
            or (dep.severity or "").upper() in ("CLEAN", "CRITICAL", "HIGH", "MEDIUM", "LOW")
        )
        if vuln_count:
            vuln_note = f" ([red]{vuln_count} vulnerable[/red])"
        elif queried_count and queried_count == len(all_deps):
            vuln_note = " ([green]clean[/green])"
        elif queried_count:
            vuln_note = f" ([green]{queried_count} clean[/green], [dim]{len(all_deps) - queried_count} unchecked[/dim])"
        else:
            vuln_note = " ([dim]unchecked[/dim])"
        return f"{len(all_deps)} audited{vuln_note}"

    def _format_network_summary(self, all_nets: list[NetworkReference]) -> str:
        """Format network endpoints audit summary string."""
        if not all_nets:
            return "0 detected"
        external_count = sum(1 for net in all_nets if not net.is_local)
        local_count = sum(1 for net in all_nets if net.is_local)
        return f"{len(all_nets)} audited ({external_count} External, {local_count} Local)"

    def _format_verdict_distributions(
        self, findings_pool: Sequence[Finding | SavedFinding]
    ) -> list[list[str]]:
        """Format verdict field distributions for console summary table."""
        if not findings_pool:
            return []
        dists = compute_verdict_distributions(findings_pool)
        status_counts = dists.get("status", {})
        status_str = (
            ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items()) if v > 0) or "0"
        )
        rep_counts = dists.get("reportable", {})
        rep_disc = is_field_discriminating(rep_counts)
        rep_str = f"{rep_counts.get('true', 0)} true, {rep_counts.get('false', 0)} false"
        if not rep_disc and sum(rep_counts.values()) > 0:
            rep_str += " [bold yellow](does not discriminate)[/bold yellow]"

        ver_counts = dists.get("verified", {})
        ver_disc = is_field_discriminating(ver_counts)
        ver_str = f"{ver_counts.get('true', 0)} true, {ver_counts.get('false', 0)} false"
        if not ver_disc and sum(ver_counts.values()) > 0:
            ver_str += " [dim](does not discriminate)[/dim]"

        return [
            ["Verdict Status", status_str],
            ["Verdict Reportable", rep_str],
            ["Verdict Verified", ver_str],
        ]

    def _render_console_summary_table(
        self,
        console: Any,
        session_id: str,
        n_files: int,
        reportable_findings: list[SavedFinding],
        all_deps: list[DependencySpec],
        all_nets: list[NetworkReference],
        all_findings: list[SavedFinding] | None = None,
        candidate_findings: list[SavedFinding] | None = None,
        symbol_delta_summary: dict[str, int] | None = None,
    ) -> None:
        """Render review summary table to console."""
        findings_str, ver_rate_str = self._format_severity_breakdown(reportable_findings)
        deps_str = self._format_dependency_summary(all_deps)
        nets_str = self._format_network_summary(all_nets)

        findings_pool = (
            candidate_findings
            if candidate_findings is not None
            else (all_findings if all_findings is not None else reportable_findings)
        )
        inval_count = sum(1 for f in findings_pool if (f.status or "").upper() == "INVALIDATED")
        total_count = len(findings_pool)
        fp_rate = (inval_count / total_count) if total_count > 0 else 0.0
        fp_rate_str = f"{inval_count}/{total_count} ({fp_rate:.1%})"

        rows = [
            ["Session ID", f"[cyan]{session_id}[/cyan]"],
            ["Files Reviewed", str(n_files)],
        ]
        if self.errored_files:
            rows.append(
                [
                    "Skipped / Errored Files",
                    f"[bold red]{len(self.errored_files)} file(s) skipped[/bold red]",
                ]
            )
        rows.extend(
            [
                ["Reportable Findings", findings_str],
                *_status_rows(reportable_findings),
                ["Verification Rate", ver_rate_str],
                ["False Positive Rate", fp_rate_str],
            ]
        )
        if symbol_delta_summary and any(symbol_delta_summary.values()):
            rows.append(
                [
                    "Symbol Delta",
                    f"+{symbol_delta_summary.get('added', 0)} / -{symbol_delta_summary.get('removed', 0)} / ={symbol_delta_summary.get('retained', 0)}",
                ]
            )
        rows.extend(self._format_verdict_distributions(findings_pool))
        rows.extend(
            [
                ["Dependencies", deps_str],
                ["Network Endpoints", nets_str],
                ["Markdown Report", str(self.session.report_path)],
                ["Findings JSON", str(self.session.findings_path)],
            ]
        )

        print_table(
            title="Review Summary",
            columns=[("Metric", "bold"), "Result"],
            rows=rows,
            border_style="cyan",
            console=console,
        )

    def _compute_symbol_delta_summary(
        self, file_payloads: list[FileReviewPayload]
    ) -> dict[str, int]:
        """Aggregate base-vs-head symbol delta counts across the reviewed files only."""
        added = sum(len(p.metadata.symbols_added) for p in file_payloads if p.metadata is not None)
        removed = sum(
            len(p.metadata.symbols_removed) for p in file_payloads if p.metadata is not None
        )
        retained = sum(
            len(p.metadata.symbols_retained) for p in file_payloads if p.metadata is not None
        )
        return {"added": added, "removed": removed, "retained": retained}

    def _persist_session_artifacts(
        self,
        payload_out: ReviewSessionPayload,
        candidates: ReviewSessionPayload,
        report_md: str,
    ) -> None:
        """Stage session findings, candidates, SARIF, and markdown report unless in dry-run.

        The run publishes the session after the profile.
        """
        from devops_cli.dry_run.state import is_dry_run

        if is_dry_run():
            return
        self.session.write_findings(payload_out)
        self.session.write_raised(candidates)
        from devops_cli.security.normalization import NormalizedFinding
        from devops_cli.security.sarif import to_sarif

        sarif_findings = [
            NormalizedFinding(
                tool=af.tool,
                tool_version=af.tool_version,
                rule_id=af.rule_id,
                severity=af.severity,
                message=af.message,
                path=af.path,
                line=af.line,
                symbol=af.symbol,
                description=af.description,
                fix=af.fix,
                partial_fingerprints=dict(af.partial_fingerprints),
                rule_properties=dict(af.properties),
                baseline_state=af.baseline_state,
                logical_locations=tuple([{"name": af.logical_location}])
                if af.logical_location
                else (),
            )
            for af in getattr(self, "admitted_scanner_findings", [])
        ]
        self.session.write_sarif(to_sarif(sarif_findings, tool_runs=self.tool_executor.runs))
        self.session.write_report(report_md)

    def generate_consolidated_report(
        self,
        file_payloads: list[FileReviewPayload],
        stage_flags: ReviewStageFlags | None = None,
        personas: list[str] | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Generate consolidated findings.json and client-facing Markdown report."""
        if stage_flags is not None and not stage_flags.reporting:
            print_info(
                "[dim]Consolidated reporting skipped (disabled via flag)[/dim]",
                prefix=False,
            )
            return {}, ""

        with trace_span(
            "review.report_generation",
            attributes={"session_id": self.session_id, "review.total_files": len(file_payloads)},
        ) as report_span:
            print_info(
                f"[dim]Generating report for session '{self.session_id}'...[/dim]",
                prefix=False,
            )
            all_findings = self._collect_and_deduplicate_findings(file_payloads)
            report_span.set_attribute("review.final_findings_count", len(all_findings))
            report_span.add_event(
                "report_findings_consolidated", {"findings_count": len(all_findings)}
            )

        all_deps, all_nets = self._collect_unique_dependencies_and_network_endpoints(file_payloads)
        symbol_delta = self._compute_symbol_delta_summary(file_payloads)

        candidate_findings = [f for payload in file_payloads for f in payload.findings]
        record_cited_code(
            [*all_findings, *candidate_findings],
            self._resolve_file_path,
            find_worktree_root(self.target_dir),
        )
        payload_out = ReviewSessionPayload(
            generated_at=datetime.now(UTC).isoformat(),
            subject=self.subject,
            findings=all_findings,
            external_dependencies=all_deps,
            network_references=all_nets,
            symbol_delta_summary=symbol_delta,
            complexity_delta=getattr(self, "complexity_deltas", []),
        )

        assert_verdict_invariants(all_findings)
        candidates = ReviewSessionPayload(
            generated_at=payload_out.generated_at,
            subject=self.subject,
            findings=candidate_findings,
        )

        if profiler := active_profiler():
            profiler.set_findings(
                candidates=len(candidate_findings),
                verified=sum(1 for f in all_findings if getattr(f, "verified", False)),
                reported=len(payload_out.findings),
            )
            profiler.set_rejections(self.rejection_counts)

        reportable_findings = [
            f for f in all_findings if f.reportable and not f.is_empty and f.location.strip()
        ]
        self._run_group_analysis_stage(stage_flags)

        report_md = self._build_consolidated_markdown_report(
            session_id=self.session_id,
            generated_at=payload_out.generated_at,
            reportable_findings=reportable_findings,
            all_deps=all_deps,
            all_nets=all_nets,
            all_findings=all_findings,
            candidate_findings=candidates.findings,
            symbol_delta_summary=symbol_delta,
        )
        self._persist_session_artifacts(payload_out, candidates, report_md)

        self._render_console_errored_files_table(None)
        self._render_console_findings_table(None, reportable_findings)
        self._render_console_dependencies_table(None, all_deps)
        self._render_console_network_table(None, all_nets)
        self._render_console_summary_table(
            console=None,
            session_id=self.session_id,
            n_files=len(file_payloads),
            reportable_findings=reportable_findings,
            all_deps=all_deps,
            all_nets=all_nets,
            all_findings=all_findings,
            candidate_findings=candidates.findings,
            symbol_delta_summary=symbol_delta,
        )

        session_path = escape_text(str(self.session.directory))
        report_path = escape_text(str(self.session.report_path))
        print_success(
            f"Consolidated review completed for session {escape_text(self.session_id)} "
            f"([bold]{len(all_findings)}[/bold] finding(s) saved to [dim]{session_path}[/dim]; "
            f"full report: [dim]{report_path}[/dim])"
        )
        return payload_out.model_dump(), report_md


format_markdown_fix = ReviewPipelineOrchestrator._format_markdown_fix
