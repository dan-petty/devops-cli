"""Repository path resolution, dynamic gitignore reading, and workspace utilities."""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pathspec

from devops_cli.config.constants import CONST_BINARY_EXTENSIONS, CONST_GIT_DIR_NAME
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import SecurityError

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=32)
def _get_pathspec_for_repo(repo_root_str: str) -> pathspec.PathSpec[Any] | None:
    """Compile and cache PathSpec instance for a repository root."""
    patterns = read_gitignore_patterns(Path(repo_root_str))
    if not patterns:
        return None
    import pathspec

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def find_repo_root(start_path: Path | str | None = None) -> Path:
    """Find the root directory of the repository containing .git or pyproject.toml."""
    current = Path(start_path or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for parent in [current, *current.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent

    return current


def _repo_root_candidates(start_path: Path | str | None) -> list[Path]:
    """Directories holding .git or pyproject.toml from `start_path` upward, nearest first; the
    start directory alone when there are none."""
    current = Path(start_path or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    found = [
        p
        for p in [current, *current.parents]
        if (p / ".git").exists() or (p / "pyproject.toml").exists()
    ]
    return found or [current]


def find_top_level_repo_root(start_path: Path | str | None = None) -> Path:
    """Find the top-most workspace root directory containing .git or pyproject.toml."""
    return _repo_root_candidates(start_path)[-1]


def _read_git_path_file(path: Path) -> str:
    """The stripped text of a git-written path file, such as `.git` or `commondir`.

    Git writes path bytes unchanged, so bytes that are not UTF-8 are kept as surrogate escapes
    and turn back into the same file-system path.
    """
    return path.read_text(encoding="utf-8", errors="surrogateescape").strip()


def _gitdir_named_by(root: Path) -> Path | None:
    """The git directory a `gitdir:` file at `root/.git` names, or None for any other `.git`."""
    marker = root / CONST_GIT_DIR_NAME
    try:
        text = _read_git_path_file(marker) if marker.is_file() else ""
    except OSError:
        return None
    if not text.startswith("gitdir:"):
        return None
    return (root / text.removeprefix("gitdir:").strip()).resolve()


def _linked_worktree_common_dir(worktree_root: Path) -> Path | None:
    """The shared git directory of the linked worktree rooted at `worktree_root`, or None.

    A linked worktree's `.git` is a `gitdir:` file whose git directory holds a `commondir`
    file. A submodule's git directory has none, and a `.git` directory is a repository's own.
    """
    gitdir = _gitdir_named_by(worktree_root)
    if gitdir is None:
        return None
    try:
        return (gitdir / _read_git_path_file(gitdir / "commondir")).resolve()
    except OSError:
        return None


def _stale_worktree_common_dir(root: Path) -> Path | None:
    """The shared git directory a stale linked worktree at `root` still names, or None.

    A linked worktree's git directory is `<common dir>/worktrees/<name>`. When it is gone,
    because the worktree was pruned or its main checkout moved, the path its `.git` file names
    still shows whose worktree it was. A submodule's git directory lies elsewhere.
    """
    gitdir = _gitdir_named_by(root)
    if gitdir is None or gitdir.exists() or gitdir.parent.name != "worktrees":
        return None
    return gitdir.parent.parent


def is_stale_linked_worktree(root: Path) -> bool:
    """Whether `root` is a linked git worktree whose git directory is missing.

    Git commands fail there. When its main checkout moved, `git worktree repair <root>` run
    from the main checkout reconnects it; a pruned worktree cannot be repaired and must be
    moved aside and re-created with `git worktree add`.
    """
    return _stale_worktree_common_dir(root) is not None


def _own_common_dir(root: Path) -> Path:
    """The shared git directory of the repository checked out at `root`.

    A `.git` directory is its own; a `gitdir:` file names another, such as the `.bare` clone
    of a bare-repository layout, and a linked worktree's leads on to its `commondir`.
    """
    gitdir = _gitdir_named_by(root)
    if gitdir is None:
        return (root / CONST_GIT_DIR_NAME).resolve()
    return _linked_worktree_common_dir(root) or gitdir


def _checks_as_its_own_tree(root: Path, workspace_root: Path) -> bool:
    """Whether a verifying command stops its climb at `root`, a candidate below `workspace_root`.

    It stops at a linked worktree, live or stale, of the workspace's own repository, however
    that repository is laid out, or of a repository outside the workspace. A worktree of a
    repository nested in the workspace, such as a `repos/` clone, resolves with that
    repository, to the workspace.
    """
    common_dir = _linked_worktree_common_dir(root) or _stale_worktree_common_dir(root)
    if common_dir is None:
        return False
    owner = common_dir.parent if common_dir.name == CONST_GIT_DIR_NAME else common_dir
    return common_dir == _own_common_dir(workspace_root) or not owner.is_relative_to(workspace_root)


def find_worktree_root(start_path: Path | str | None = None) -> Path:
    """The root of the working tree a verifying command checks.

    This is the nearest enclosing linked git worktree, so a worktree nested inside a checkout
    (for example under `.claude/worktrees/`) is checked instead of the checkout around it.
    Otherwise it is the top-level workspace root, as `find_top_level_repo_root` gives it, so
    repositories cloned under `repos/`, their own worktrees and submodules resolve to the
    workspace. A stale worktree, whose git directory is missing, still resolves to itself
    rather than to the checkout around it; `is_stale_linked_worktree` tells callers to warn.

    Known limit: a checkout below another directory holding `.git` or `pyproject.toml`, such as
    a dotfiles repository at `$HOME`, resolves to that outer directory, and its worktrees resolve
    with it as a `repos/` clone's do; the `devops ci` header names the root it checks.
    """
    candidates = _repo_root_candidates(start_path)
    workspace_root = candidates[-1]
    return next(
        (root for root in candidates if _checks_as_its_own_tree(root, workspace_root)),
        workspace_root,
    )


def main_worktree_root(start_path: Path | str | None = None) -> Path:
    """The main worktree of the repository at `start_path`; a linked worktree resolves to it.

    A linked worktree's `.git` is a file naming its git directory, whose `commondir` leads to
    the repository's shared git directory, inside the main worktree. A submodule's git
    directory has no `commondir` and stays its own repository.

    It starts from the top-most root on purpose: a worktree nested in a checkout reaches that
    checkout directly, and a `repos/` clone shares the workspace data. Only a worktree that
    is itself the top-most root needs the `commondir` step. A stale one, whose git directory
    was pruned, reaches the shared git directory its `.git` file still names, while that
    directory exists.
    """
    root = find_top_level_repo_root(start_path)
    common_dir = _linked_worktree_common_dir(root) or _stale_worktree_common_dir(root)
    return (
        common_dir.parent
        if common_dir is not None and common_dir.name == CONST_GIT_DIR_NAME and common_dir.is_dir()
        else root
    )


def resolve_data_path(path: Path, start_path: Path | str | None = None) -> Path:
    """A configured data path: as given when absolute, else under the main worktree.

    Every worktree of a repository shares one data directory, so removing a worktree keeps the
    reviews, benchmarks and evaluations recorded in it.
    """
    return path if path.is_absolute() else (main_worktree_root(start_path) / path).resolve()


def read_gitignore_patterns(repo_root: Path) -> list[str]:
    """Dynamically read .gitignore patterns from the repository root at runtime."""
    gitignore_file = repo_root / ".gitignore"
    if not gitignore_file.is_file():
        return []

    try:
        return [
            line.strip()
            for line in gitignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except OSError as err:
        logger.warning("Failed to read .gitignore at %s: %s", gitignore_file, err)
        return []


def is_ignored_by_git(repo_root: Path, target_path: Path, is_dir: bool | None = None) -> bool:
    """Report whether a path should be skipped when walking a repository.

    Ignore rules are evaluated in-process. This previously consulted only the repository
    root's `.gitignore` and, on a miss, spawned `git check-ignore` for the file -- and a
    miss is the common case, since most files are not ignored, so the slow path ran per
    file. Measured over this repository's sources: 39.5 ms per tracked file, almost all of
    it process spawn.

    Binary files report as skipped even though git does not ignore them. Callers use this
    to decide what is worth reading, and a binary never is.

    `is_dir` lets a caller that already knows avoid a `stat`. Directory-only patterns
    (`build/`) need to know, and on a slow filesystem that one call is most of what remains
    of the cost -- a walk that has just listed a directory has the answer already.
    """
    if target_path.suffix.lower() in CONST_BINARY_EXTENSIONS:
        return True

    from devops_cli.core.gitignore import get_index

    if CONST_GIT_DIR_NAME in target_path.parts:
        return True

    try:
        return get_index(repo_root).is_ignored(target_path, is_dir=is_dir)
    except Exception as exc:
        # An unreadable repository is not an ignored path; failing open keeps a walk
        # going rather than silently skipping everything it could not evaluate.
        logger.debug("Ignore evaluation failed for %s: %s", target_path, exc)
        return False


def _list_git_tracked_files(repo_root: Path, resolved_target: Path) -> list[Path] | None:
    """List files using git ls-files if inside a git repository."""
    if not (repo_root / ".git").exists():
        return None
    try:
        cmd = [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ]
        if resolved_target != repo_root:
            rel_to_repo = resolved_target.relative_to(repo_root)
            cmd.extend(["--", str(rel_to_repo)])

        proc = run_subprocess(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        files: list[Path] = []
        repo_root_resolved = repo_root.resolve()
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            p = repo_root / line_str
            try:
                p_res = p.resolve()
                if not p_res.is_relative_to(repo_root_resolved):
                    continue
            except OSError, RuntimeError:
                continue
            if p.is_file() and p.suffix.lower() not in CONST_BINARY_EXTENSIONS:
                files.append(p)
        return sorted(files)
    except Exception as err:
        logger.warning("git ls-files failed in %s: %s", repo_root, err)
        return None


def list_repo_files(target: Path | str = ".") -> list[Path]:
    """Return all reviewable files under target directory respecting .gitignore rules."""
    resolved_target = Path(target).resolve()
    if not resolved_target.exists():
        return []

    repo_root = find_repo_root(resolved_target)

    if resolved_target.is_file():
        return [resolved_target] if not is_ignored_by_git(repo_root, resolved_target) else []

    # 1. Try git ls-files if inside a git repository
    git_files = _list_git_tracked_files(repo_root, resolved_target)
    if git_files is not None:
        return git_files

    # 2. Directory walk with dynamic .gitignore rules fallback
    walked_files: list[Path] = []
    repo_root_resolved = repo_root.resolve()
    for p in resolved_target.rglob("*"):
        try:
            resolved_p = p.resolve()
            if not resolved_p.is_relative_to(repo_root_resolved):
                continue
        except OSError, RuntimeError:
            continue
        if p.is_file() and not is_ignored_by_git(repo_root, p):
            walked_files.append(p)
    return sorted(walked_files)


@functools.lru_cache(maxsize=32)
def _cached_repo_origin(resolved_root: Path) -> str | None:
    """Execute git remote query and parse origin owner/repo with bounded caching."""
    import re

    if (resolved_root / ".git").exists():
        proc = run_subprocess(["git", "remote", "get-url", "origin"], cwd=resolved_root, quiet=True)
        if proc.returncode == 0 and proc.stdout.strip():
            raw = proc.stdout.strip()
            match = re.search(r"[:/]([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+?)(?:\.git)?$", raw)
            if match:
                return match.group(1)
    return None


def get_repo_origin_name(repo_root: Path | None = None) -> str | None:
    """Extract owner/repo string from git remote origin URL (e.g. 'org/repo')."""
    root = (repo_root or find_repo_root()).resolve()
    origin = _cached_repo_origin(root)
    if origin is not None:
        return origin

    if repo_root is None:
        import os

        env_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        if env_repo and "/" in env_repo:
            return env_repo

    return None


get_repo_origin_name.cache_clear = _cached_repo_origin.cache_clear  # type: ignore[attr-defined]


def is_safe_subpath(root: Path | str, target: Path | str) -> bool:
    """Return True if *target* strictly resides within *root* directory hierarchy."""
    try:
        resolved_root = Path(root).resolve()
        target_p = Path(target)
        resolved_target = (
            (resolved_root / target_p).resolve()
            if not target_p.is_absolute()
            else target_p.resolve()
        )
        return resolved_target.is_relative_to(resolved_root)
    except Exception:
        return False


def resolve_safe_subpath(root: Path | str, target: Path | str) -> Path:
    """Resolve *target* relative to *root* and verify it strictly resides within *root*.

    Raises ValueError if path traversal outside *root* is detected.
    """
    resolved_root = Path(root).resolve()
    target_p = Path(target)
    resolved_target = (
        (resolved_root / target_p).resolve() if not target_p.is_absolute() else target_p.resolve()
    )
    if not resolved_target.is_relative_to(resolved_root):
        raise SecurityError(
            f"Path traversal detected: target '{resolved_target}' "
            f"resolves outside root '{resolved_root}'"
        )
    return resolved_target
