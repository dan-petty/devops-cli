"""Detached git worktree management for review isolation (#1047).

Branch and pull request reviews run static scanners and pre-analysis against
isolated detached worktrees created under the user data root, outside the repository,
preventing uncommitted checkout edits from corrupting review findings and metadata.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.config.constants import CONST_USER_DATA_ROOT
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)

_WORKTREE_DIR_NAME: Final[str] = "worktrees"


def get_user_worktrees_dir() -> Path:
    """The directory under user data root where review worktrees live."""
    env_root = os.environ.get("DEVOPS_CLI_USER_DATA_ROOT")
    root = Path(env_root).resolve() if env_root else CONST_USER_DATA_ROOT
    worktrees_dir = root / _WORKTREE_DIR_NAME
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    return worktrees_dir


def add_detached_worktree(repo_dir: Path, commit_ish: str, dest_dir: Path) -> bool:
    """Create a detached git worktree at dest_dir for commit_ish."""
    if dest_dir.exists():
        remove_worktree(repo_dir, dest_dir)

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "-C", str(repo_dir), "worktree", "add", "--detach", str(dest_dir), commit_ish]
    try:
        proc = run_subprocess(cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
        if proc.returncode == 0:
            return True
        logger.debug("git worktree add failed (%s): %s", proc.returncode, proc.stderr)
    except Exception as exc:
        logger.debug("Failed adding worktree at %s for %s: %s", dest_dir, commit_ish, exc)
    return False


def remove_worktree(repo_dir: Path, dest_dir: Path) -> None:
    """Remove a git worktree and prune worktree records."""
    try:
        run_subprocess(
            ["git", "-C", str(repo_dir), "worktree", "remove", "--force", str(dest_dir)],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.debug("git worktree remove failed for %s: %s", dest_dir, exc)

    try:
        run_subprocess(
            ["git", "-C", str(repo_dir), "worktree", "prune"],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.debug("git worktree prune failed: %s", exc)

    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)


def fetch_pr_head(repo_dir: Path, pr_number: int, remote: str = "origin") -> str | None:
    """Fetch refs/pull/N/head from remote, returning commit ref or None."""
    ref_spec = f"refs/pull/{pr_number}/head"
    cmd = ["git", "-C", str(repo_dir), "fetch", remote, ref_spec]
    try:
        proc = run_subprocess(cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
        if proc.returncode == 0:
            rev_proc = run_subprocess(
                ["git", "-C", str(repo_dir), "rev-parse", "FETCH_HEAD"],
                quiet=True,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if rev_proc.returncode == 0 and rev_proc.stdout.strip():
                return rev_proc.stdout.strip()
            return "FETCH_HEAD"
        logger.debug("Fetching %s failed (%s): %s", ref_spec, proc.returncode, proc.stderr)
    except Exception as exc:
        logger.debug("Failed fetching %s: %s", ref_spec, exc)
    return None


@dataclass(frozen=True)
class ReviewWorktrees:
    """Detached worktrees for a review session."""

    commit_worktree: Path | None
    base_worktree: Path | None
    partial_context: bool = False


@contextmanager
def review_worktrees_context(
    repo_dir: Path,
    commit_rev: str | None,
    base_rev: str | None,
    session_id: str,
) -> Iterator[ReviewWorktrees]:
    """Context manager creating detached worktrees for commit and base, cleaned up on exit."""
    base_worktrees_root = get_user_worktrees_dir()
    created: list[Path] = []

    commit_tree: Path | None = None
    if commit_rev:
        commit_dest = base_worktrees_root / f"review-{session_id}-commit"
        if add_detached_worktree(repo_dir, commit_rev, commit_dest):
            commit_tree = commit_dest
            created.append(commit_dest)

    base_tree: Path | None = None
    if base_rev:
        base_dest = base_worktrees_root / f"review-{session_id}-base"
        if add_detached_worktree(repo_dir, base_rev, base_dest):
            base_tree = base_dest
            created.append(base_dest)

    try:
        yield ReviewWorktrees(
            commit_worktree=commit_tree,
            base_worktree=base_tree,
            partial_context=commit_tree is None,
        )
    finally:
        for wt in created:
            remove_worktree(repo_dir, wt)
