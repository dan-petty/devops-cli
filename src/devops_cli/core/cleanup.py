"""Workspace and Data Tier Housekeeping and Retention Engine."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GIT_DIR_NAME
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import (
    _linked_worktree_common_dir,
    _own_common_dir,
    _stale_worktree_common_dir,
    find_worktree_root,
    main_worktree_root,
    resolve_data_path,
)
from devops_cli.exceptions import SecurityError
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

PRUNED_SUBDIRECTORIES = ("reviews", "analysis", "logs", "traces", "benchmarks", "cache")
"""The data directory's subdirectories whose stale entries cleanup removes."""


class CleanupSummary(BaseModel):
    """Summary of cleaned files and directories."""

    pruned_files: list[str] = Field(default_factory=list)
    pruned_dirs: list[str] = Field(default_factory=list)
    freed_bytes: int = 0
    dry_run: bool = False


def _prune_single_item(
    item: Path,
    data_dir: Path,
    cutoff_time: float,
    dry_run: bool,
    summary: CleanupSummary,
) -> None:
    """Helper to evaluate and prune a single expired file or directory."""
    try:
        if item.is_symlink() or not item.resolve().is_relative_to(data_dir):
            return

        mtime = item.stat().st_mtime
        if mtime >= cutoff_time:
            return

        rel_path = str(item.relative_to(data_dir))
        if item.is_file():
            size = item.stat().st_size
            if not dry_run:
                item.unlink(missing_ok=True)
            summary.pruned_files.append(rel_path)
            summary.freed_bytes += size
        elif item.is_dir():
            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            if not dry_run:
                shutil.rmtree(item, ignore_errors=True)
            summary.pruned_dirs.append(rel_path)
            summary.freed_bytes += size
    except Exception as exc:
        logger.warning("Failed to prune cleanup candidate %s: %s", item, exc)


def _listed_worktrees(main_root: Path) -> list[Path]:
    """Every worktree of the repository whose main worktree is `main_root`, as git lists them;
    none when `main_root` is not in a repository."""
    listing = run_subprocess(
        ["git", "worktree", "list", "--porcelain"], cwd=main_root, check=False, quiet=True
    )
    if listing.returncode != 0:
        return []
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in listing.stdout.splitlines()
        if line.startswith("worktree ")
    ]


def _is_git_directory(path: Path) -> bool:
    """Whether `path` is a git directory: a `.git`, or a bare repository's layout."""
    return path.name == CONST_GIT_DIR_NAME or (
        (path / "HEAD").is_file() and (path / "objects").is_dir() and (path / "refs").is_dir()
    )


def _holds_a_repository(data_dir: Path) -> bool:
    """Whether `data_dir` is in a git directory, is a repository or worktree, or holds one in a
    subdirectory cleanup prunes, which git's index of the enclosing checkout does not list: a
    checkout or worktree (a `.git` entry), or a bare or separate git directory (its layout)."""
    if any(_is_git_directory(path) for path in (data_dir, *data_dir.parents)):
        return True
    if (data_dir / CONST_GIT_DIR_NAME).exists():
        return True
    for subdir_name in PRUNED_SUBDIRECTORIES:
        for top, dirs, files in os.walk(data_dir / subdir_name):
            if (
                CONST_GIT_DIR_NAME in dirs
                or CONST_GIT_DIR_NAME in files
                or _is_git_directory(Path(top))
            ):
                logger.debug("A repository is under %s", top)
                return True
    return False


def _holds_more_than_data(data_dir: Path, main_root: Path, current_root: Path) -> bool:
    """Whether `data_dir` is the filesystem root or a directory directly under it (`/opt`,
    `/tmp`, `/home`), a system directory, the home directory or a parent of it, a git directory
    or inside one, a repository or holds one where cleanup prunes, or a worktree (the main one,
    the one the command runs in, or any other the repository lists) or a parent of one, whose
    `logs/`, `cache/` or `benchmarks/` hold more than the tool's data."""
    worktrees = [main_root, current_root, *_listed_worktrees(main_root)]
    return (
        len(data_dir.parts) <= 2
        or is_forbidden_system_path(data_dir)
        or Path.home().resolve().is_relative_to(data_dir)
        or _holds_a_repository(data_dir)
        or any(worktree.is_relative_to(data_dir) for worktree in worktrees)
    )


def _holds_tracked_files(data_dir: Path) -> bool:
    """Whether `data_dir` holds files git tracks, or is in a checkout and git cannot tell: a data
    directory inside a checkout must be one the checkout does not track, such as `.data/`.

    Git is asked from the checkout, not from `data_dir`, which may be a mounted volume that git
    does not search across.
    """
    checkout = next(
        (path for path in data_dir.parents if (path / CONST_GIT_DIR_NAME).exists()), None
    )
    if checkout is None or not data_dir.is_dir():
        return False
    pathspec = f":(literal){data_dir.relative_to(checkout)}"
    listing = run_subprocess(
        ["git", "ls-files", "-z", "--", pathspec], cwd=checkout, check=False, quiet=True
    )
    return listing.returncode != 0 or bool(listing.stdout)


def _spellings(path: Path) -> list[Path]:
    """`path` (absolute) with each of its leading parts resolved in turn: the first leaves it as
    written, the last resolves every link. A data directory linked to another volume from inside
    a workspace is in that workspace under one of them, though its target is not."""
    parts = Path(os.path.abspath(path)).parts
    return [
        Path(*parts[:index]).resolve().joinpath(*parts[index:])
        for index in range(1, len(parts) + 1)
    ]


def _belongs_to_an_outer_workspace(main_root: Path, current_root: Path) -> bool:
    """Whether `main_root`, where shared data resolves, is another workspace around the linked
    worktree the command runs in, `current_root`, rather than that worktree's repository.

    A worktree placed inside a different repository or project resolves shared data to that
    outer directory (a known limit of `main_worktree_root`), whose data is not the worktree's
    repository's to prune. A nested worktree of the checkout, a worktree of a repository cloned
    inside it, and a bare-repository layout's worktree all belong to it.
    """
    if current_root == main_root or not current_root.is_relative_to(main_root):
        return False
    common_dir = _linked_worktree_common_dir(current_root) or _stale_worktree_common_dir(
        current_root
    )
    if common_dir is None or common_dir == _own_common_dir(main_root):
        return False
    owner = common_dir.parent if common_dir.name == CONST_GIT_DIR_NAME else common_dir
    return not owner.is_relative_to(main_root)


def cleanup_data_directory(repo_root: Path = Path(".")) -> Path:
    """The directory cleanup prunes: the configured data directory (`data.dir`,
    `DEVOPS_CLI_DATA_DIR`), resolved as the data writers resolve it.

    A relative directory resolves with `resolve_data_path`, under the main worktree of the
    top-most workspace root, where the review, run and analysis writers put their data: every
    worktree of the checkout, nested, outside or pruned, and every repository cloned under
    `repos/`, its worktrees and submodules share the workspace's data directory.

    Cleanup prunes only the data directory's `PRUNED_SUBDIRECTORIES` (`reviews/`, `analysis/`,
    `logs/`, `traces/`, `benchmarks/`, `cache/`), where the writers put their data by default.
    A child directory configured on its own (`data.reviews_dir`, `DEVOPS_CLI_DATA_REVIEWS_DIR`
    and the like) lies elsewhere and is left alone.

    Known limit: a checkout below another directory holding `.git` or `pyproject.toml`, such as
    a project in a home directory kept in git, shares that outer directory's data, as its
    writers do; cleanup cannot tell it from a `repos/` clone and prunes that directory. A linked
    worktree placed inside another repository or project is recognised and refused instead,
    also when that workspace's data directory links to another volume.

    Raises:
        SecurityError: The configured directory climbs with `..`; is the filesystem root or a
            directory directly under it, a system directory, the home directory or a parent of
            it, a git directory or inside one, or a repository; holds a repository in a
            subdirectory cleanup prunes; is a worktree of `repo_root`'s repository (the main
            one, the one `repo_root` is in, or another it lists) or a parent of one; holds files
            git tracks, or lies in a checkout git cannot be asked about; or lies, as written or
            through a link, in another workspace around the linked worktree `repo_root` is in.
    """
    configured = validate_no_path_traversal(load_settings().data.dir, label="data directory")
    data_dir = resolve_data_path(configured, repo_root).resolve()
    main_root = main_worktree_root(repo_root)
    current_root = find_worktree_root(repo_root)
    written = configured if configured.is_absolute() else main_root / configured
    if any(
        spelling.is_relative_to(main_root) for spelling in _spellings(written)
    ) and _belongs_to_an_outer_workspace(main_root, current_root):
        raise SecurityError(
            f"Refusing to prune {data_dir}: it is the data of {main_root}, another workspace"
            f" around the worktree at {current_root}."
        )
    if _holds_more_than_data(data_dir, main_root, current_root):
        raise SecurityError(f"Refusing to prune {data_dir}: it is not a dedicated data directory.")
    if _holds_tracked_files(data_dir):
        raise SecurityError(
            f"Refusing to prune {data_dir}: it holds tracked files, or git cannot tell."
        )
    return data_dir


@trace_span("workspace.cleanup")
def cleanup_data_tier(
    repo_root: Path = Path("."),
    older_than_seconds: float = 7 * 86400,  # 7 days default
    dry_run: bool = False,
) -> CleanupSummary:
    """Prune stale review runs, temporary metadata, and cached traces in the data directory
    `cleanup_data_directory` names; pruned paths are reported relative to it."""
    data_dir = cleanup_data_directory(repo_root)
    summary = CleanupSummary(dry_run=dry_run)

    if not data_dir.is_dir():
        return summary

    cutoff_time = time.time() - older_than_seconds
    for subdir_name in PRUNED_SUBDIRECTORIES:
        target_sub = data_dir / subdir_name
        if not target_sub.exists() or not target_sub.is_dir():
            continue
        for item in target_sub.iterdir():
            _prune_single_item(item, data_dir, cutoff_time, dry_run, summary)

    return summary
