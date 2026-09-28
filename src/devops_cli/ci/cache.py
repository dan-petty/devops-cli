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
from devops_cli.core.repo import find_worktree_root, resolve_data_path

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


def resolve_ci_cache_path(root: Path = Path(".")) -> Path:
    """The CI cache file of the worktree at `root`.

    It is in the configured cache directory (`data.cache_dir`), resolved as every data path is
    (`resolve_data_path`): under the main worktree when relative, whichever worktree or
    subdirectory the gate runs from. `devops workspace clean` prunes it there while
    `data.cache_dir` is the default child of `data.dir`. Each worktree
    has its own file there, named after the worktree's root, so a gate never trusts a result
    recorded for another worktree's files and parallel worktrees do not evict each other's.
    """
    from devops_cli.config.settings import load_settings

    try:
        settings = load_settings()
        cache_dir = settings.data.cache_dir
    except Exception:
        env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
        base_dir = Path(env_dir) if env_dir else DEFAULT_DATA_DIR
        cache_dir = base_dir / CONST_CACHE_DIR_NAME
    cache_dir = resolve_data_path(cache_dir, root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    worktree = hashlib.sha256(str(find_worktree_root(root)).encode()).hexdigest()[:16]
    cache_file = Path(CONST_CI_CACHE_FILENAME)
    return cache_dir / f"{cache_file.stem}-{worktree}{cache_file.suffix}"


def _hash_file(path: Path) -> str:
    """Compute SHA-256 digest of a file safely."""
    if not path.is_file():
        return ""
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except OSError:
        return ""


def _get_git_output(args: list[str], root: Path, strip: bool = True) -> str | None:
    """Execute git command within root directory, returning stdout or None.

    `strip` must be disabled for porcelain output: its first two columns are status codes
    and an unmodified index is reported as a leading space, so stripping shifts every
    column by one and a file modified in the working tree reads as one modified in the
    index -- inverting exactly the distinction the caller needs.
    """
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
        if result.returncode != 0:
            return None
        return result.stdout.strip() if strip else result.stdout
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


def _index_blob_hashes(root: Path) -> dict[str, str]:
    """Map every tracked path to the content hash git holds for it in the index."""
    output = _get_git_output(["ls-files", "-s"], root)
    if not output:
        return {}
    hashes: dict[str, str] = {}
    for line in output.splitlines():
        # Format: <mode> <object> <stage>\t<path>
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if path and len(fields) >= 2:
            hashes[path] = fields[1]
    return hashes


def _worktree_divergent_paths(root: Path) -> tuple[list[str], list[str]]:
    """Return paths whose working copy differs from the index, and paths that are gone."""
    output = _get_git_output(
        ["status", "--porcelain=v1", "--untracked-files=all"], root, strip=False
    )
    if not output:
        return [], []

    changed: list[str] = []
    deleted: list[str] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        index_state, worktree_state, path = line[0], line[1], line[3:].strip().strip('"')
        # A rename is reported as "old -> new"; only the new path exists on disk.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if worktree_state == "D" or index_state == "D":
            deleted.append(path)
        elif worktree_state != " " or index_state == "?":
            changed.append(path)
    return changed, deleted


def _git_blob_hashes(root: Path, paths: list[str]) -> dict[str, str]:
    """Hash working-copy files the way git hashes them, in one invocation.

    `git hash-object --stdin-paths` takes the whole list at once; hashing per file would
    spawn a process per changed file on every fingerprint.
    """
    if not paths:
        return {}
    try:
        result = run_subprocess(
            ["git", "hash-object", "--stdin-paths"],
            cwd=root,
            input="\n".join(paths) + "\n",
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.debug("Failed hashing worktree files: %s", exc)
        return {}
    if result.returncode != 0:
        return {}

    digests = result.stdout.split()
    if len(digests) != len(paths):
        # A mismatch means some path could not be read; falling back to no cache is safer
        # than pairing hashes with the wrong files and calling a stale tree verified.
        logger.debug("git hash-object returned %d digests for %d paths", len(digests), len(paths))
        return {}
    return dict(zip(paths, digests, strict=True))


def compute_workspace_fingerprint(
    root: Path = Path("."),
    options: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, str]] | None:
    """Compute a fingerprint of what the checks will actually read.

    The fingerprint describes **content**, not git state. It previously hashed `HEAD`, the
    written tree, and the staged and unstaged diffs separately, which meant staging a file
    changed it and committing changed it again -- even though no file content differed.
    Since committing is precisely what happens between running `devops ci` and pushing, the
    pre-push hook could never hit the cache and re-ran the whole suite on every push.

    Content addressing makes the fingerprint invariant across `git add` and `git commit`,
    so a verified tree stays verified until something in it actually changes.
    """
    head_sha = _get_git_output(["rev-parse", "HEAD"], root) or ""

    index_hashes = _index_blob_hashes(root)
    if not index_hashes and head_sha == "":
        return None

    changed, deleted = _worktree_divergent_paths(root)

    # The working copy wins over the index: it is what the checks read. Worktree content is
    # hashed by git rather than directly, because a git blob hash covers a header as well as
    # the bytes -- mixing the two hash spaces would make a staged file look different from
    # the identical unstaged one, which is the invariance this exists to provide.
    content: dict[str, str] = dict(index_hashes)
    content.update(_git_blob_hashes(root, [p for p in changed if (root / p).is_file()]))
    for rel_path in deleted:
        content.pop(rel_path, None)

    config_hash = _compute_config_hashes(root)
    opt_str = json.dumps(options or {}, sort_keys=True)

    hasher = hashlib.sha256()
    hasher.update(config_hash.encode())
    hasher.update(opt_str.encode())
    for f_path, f_sha in sorted(content.items()):
        hasher.update(f"{f_path}:{f_sha}".encode())

    # The per-file hashes retained for the pre-commit subset check cover the paths that
    # differ from the index, which are the ones a partial run is asked about.
    file_hashes = _compute_file_hashes(root, sorted(set(changed) | set(_CRITICAL_CONFIG_FILES)))
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
    cache_path = resolve_ci_cache_path(root)
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
    root: Path = Path("."),
) -> None:
    """Persist successful CI quality gate run of the worktree at `root` to its cache atomically."""
    if not passed:
        clear_ci_cache(root)
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

    cache_path = resolve_ci_cache_path(root)
    tmp_path = cache_path.with_suffix(f".tmp-{os.getpid()}")
    try:
        tmp_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(cache_path)
    except OSError as exc:
        logger.warning("Failed writing CI cache to %s: %s", cache_path, exc)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def clear_ci_cache(root: Path = Path(".")) -> None:
    """Invalidate and remove the CI cache file of the worktree at `root`."""
    cache_path = resolve_ci_cache_path(root)
    if cache_path.is_file():
        try:
            cache_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("Failed unlinking CI cache: %s", exc)
