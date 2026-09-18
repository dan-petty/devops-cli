"""High-performance execution caching and pre-commit file change tracking for CI gates.

Computes deterministic codebase fingerprints from Git state, working tree diffs,
configuration files, and target file hashes. Bypasses redundant CI execution when the
codebase is unchanged since the last passing run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import (
    CONST_CACHE_DIR_NAME,
    CONST_CI_CACHE_FILENAME,
    CONST_PRE_COMMIT_CONFIG_FILENAME,
    CONST_PYPROJECT_FILENAME,
    CONST_UV_LOCK_FILENAME,
)
from devops_cli.config.defaults import DEFAULT_DATA_DIR, DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)

_CRITICAL_CONFIG_FILES: tuple[str, ...] = (
    CONST_PYPROJECT_FILENAME,
    CONST_UV_LOCK_FILENAME,
    CONST_PRE_COMMIT_CONFIG_FILENAME,
)


class CICachedCheck(BaseModel):
    """Cached execution result for an individual CI quality gate check."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_title: str
    passed: bool
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""


class CICacheEntry(BaseModel):
    """Complete cached CI run state and verified file hashes."""

    fingerprint: str
    head_sha: str
    timestamp: float
    passed: bool
    options: dict[str, Any] = Field(default_factory=dict)
    checks: list[CICachedCheck]
    file_hashes: dict[str, str] = Field(default_factory=dict)


def resolve_ci_cache_path() -> Path:
    """Resolve CI cache JSON file path honoring configuration and data directory."""
    from devops_cli.config.settings import load_settings

    try:
        settings = load_settings()
        cache_dir = settings.data.cache_dir
    except Exception:
        env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
        base_dir = Path(env_dir) if env_dir else DEFAULT_DATA_DIR
        cache_dir = base_dir / CONST_CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / CONST_CI_CACHE_FILENAME


def _hash_file(path: Path) -> str:
    """Compute SHA-256 digest of a file safely."""
    if not path.is_file():
        return ""
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except OSError:
        return ""


def _get_git_output(args: list[str], root: Path) -> str | None:
    """Execute git command within root directory, returning stdout or None."""
    try:
        result = run_subprocess(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as exc:
        logger.debug("Git command git %s failed: %s", " ".join(args), exc)
        return None


def _compute_config_hashes(root: Path) -> str:
    """Compute consolidated hash of critical toolchain configuration files."""
    hasher = hashlib.sha256()
    for cfg_name in _CRITICAL_CONFIG_FILES:
        cfg_path = root / cfg_name
        hasher.update(f"{cfg_name}:{_hash_file(cfg_path)}".encode())
    return hasher.hexdigest()


def _compute_file_hashes(root: Path, file_list: list[str]) -> dict[str, str]:
    """Compute map of relative file path to SHA-256 content digest."""
    hashes: dict[str, str] = {}
    for rel_str in file_list:
        clean_rel = rel_str.strip()
        if not clean_rel:
            continue
        file_path = root / clean_rel
        if file_path.is_file():
            hashes[clean_rel] = _hash_file(file_path)
    return hashes


def _collect_modified_git_files(root: Path) -> list[str]:
    """Gather list of modified, staged, untracked, recent, and critical files to hash."""
    target_files: list[str] = list(_CRITICAL_CONFIG_FILES)
    for args in (
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
        ["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
    ):
        output = _get_git_output(args, root)
        if output:
            target_files.extend(output.splitlines())
    return sorted(set(target_files))


def compute_workspace_fingerprint(
    root: Path = Path("."),
    options: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, str]] | None:
    """Compute deterministic codebase fingerprint from git state and file hashes.

    Returns (fingerprint, head_sha, file_hashes) or None if git repository cannot be queried.
    """
    _get_git_output(["update-index", "--refresh", "-q"], root)
    head_sha = _get_git_output(["rev-parse", "HEAD"], root)
    if not head_sha:
        return None

    tree_sha = _get_git_output(["write-tree"], root) or ""
    diff_files = _get_git_output(["diff", "-p"], root) or ""
    diff_cached = _get_git_output(["diff", "--cached"], root) or ""
    untracked = _get_git_output(["ls-files", "--others", "--exclude-standard"], root) or ""

    config_hash = _compute_config_hashes(root)
    opt_str = json.dumps(options or {}, sort_keys=True)

    target_files = _collect_modified_git_files(root)
    file_hashes = _compute_file_hashes(root, target_files)

    hasher = hashlib.sha256()
    hasher.update(head_sha.encode())
    hasher.update(tree_sha.encode())
    hasher.update(hashlib.sha256(diff_files.encode()).hexdigest().encode())
    hasher.update(hashlib.sha256(diff_cached.encode()).hexdigest().encode())
    hasher.update(hashlib.sha256(untracked.encode()).hexdigest().encode())
    hasher.update(config_hash.encode())
    hasher.update(opt_str.encode())
    for f_path, f_sha in sorted(file_hashes.items()):
        hasher.update(f"{f_path}:{f_sha}".encode())

    return hasher.hexdigest(), head_sha, file_hashes


def _is_subset_file_matching(rel_path: str, entry: CICacheEntry, root: Path) -> bool:
    """Check if an individual file in pre-commit subset matches verified state."""
    file_path = root / rel_path
    if not file_path.is_file():
        return False
    cached_sha = entry.file_hashes.get(rel_path)
    if cached_sha is not None:
        return bool(cached_sha == _hash_file(file_path))
    diff_output = _get_git_output(["diff", entry.head_sha, "--", rel_path], root)
    return diff_output == ""


def _check_pre_commit_subset_match(
    entry: CICacheEntry,
    files: list[str],
    root: Path,
) -> bool:
    """Predicate verifying all files specified by pre-commit match cached state."""
    if not files:
        return False
    return all(_is_subset_file_matching(rel_path, entry, root) for rel_path in files)


def get_ci_cache(
    fingerprint: str,
    files: list[str] | None = None,
    options: dict[str, Any] | None = None,
    root: Path = Path("."),
) -> CICacheEntry | None:
    """Retrieve valid passing CI cache entry if fingerprint or file hashes match."""
    cache_path = resolve_ci_cache_path()
    if not cache_path.is_file():
        return None

    try:
        raw_json = cache_path.read_text(encoding="utf-8")
        entry = CICacheEntry.model_validate_json(raw_json)
    except Exception as exc:
        logger.debug("Failed reading CI cache from %s: %s", cache_path, exc)
        return None

    if not entry.passed:
        return None

    if entry.options != (options or {}):
        return None

    # Exact global workspace fingerprint match
    if entry.fingerprint == fingerprint:
        return entry

    # Pre-commit file change tracking match for passed file subset
    if files and _check_pre_commit_subset_match(entry, files, root):
        return entry

    return None


def save_ci_cache(
    fingerprint: str,
    head_sha: str,
    checks: list[CICachedCheck],
    file_hashes: dict[str, str],
    options: dict[str, Any] | None = None,
    passed: bool = True,
) -> None:
    """Persist successful CI quality gate run to disk cache atomically."""
    if not passed:
        clear_ci_cache()
        return

    entry = CICacheEntry(
        fingerprint=fingerprint,
        head_sha=head_sha,
        timestamp=time.time(),
        passed=passed,
        options=options or {},
        checks=checks,
        file_hashes=file_hashes,
    )

    cache_path = resolve_ci_cache_path()
    tmp_path = cache_path.with_suffix(f".tmp-{os.getpid()}")
    try:
        tmp_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(cache_path)
    except OSError as exc:
        logger.warning("Failed writing CI cache to %s: %s", cache_path, exc)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def clear_ci_cache() -> None:
    """Invalidate and remove CI cache file."""
    cache_path = resolve_ci_cache_path()
    if cache_path.is_file():
        try:
            cache_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("Failed unlinking CI cache: %s", exc)
