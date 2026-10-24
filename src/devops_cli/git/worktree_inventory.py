"""Worktree inventory, status inspection, and safe orphan reclamation (#700).

Provides NUL-separated porcelain parsing for `git worktree list -z`,
ahead-of-main calculation, dirty-path counting, contained ref detection,
and safe orphan worktree pruning.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_GIT_BARE_TOKEN,
    CONST_GIT_BRANCH_PREFIX,
    CONST_GIT_DETACHED_TOKEN,
    CONST_GIT_HEAD_PREFIX,
    CONST_GIT_LOCKED_TOKEN,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS,
    CONST_GIT_PRUNABLE_TOKEN,
    CONST_GIT_WORKTREE_PREFIX,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_repo_root

logger = logging.getLogger(__name__)

CONST_REFS_HEADS_PREFIX: Final[str] = "refs/heads/"
CONST_REFS_REMOTES_PREFIX: Final[str] = "refs/remotes/"


class WorktreeInfo(BaseModel):
    """Raw worktree record parsed from git worktree list --porcelain -z."""

    path: Path
    head: str
    branch: str | None = None
    detached: bool = False
    bare: bool = False
    locked: bool = False
    lock_reason: str | None = None
    prunable: bool = False
    prunable_reason: str | None = None
    is_main: bool = False


class WorktreeEntry(BaseModel):
    """Enriched worktree record with ahead, dirty, and contained metrics."""

    path: str
    head: str
    branch: str | None = None
    ahead: int
    dirty: int
    contained: bool
    locked: bool = False
    lock_reason: str | None = None
    prunable: bool = False
    prunable_reason: str | None = None
    is_main: bool = False


class WorktreePruneItem(BaseModel):
    """Individual worktree prune outcome."""

    path: str
    status: str
    reason: str | None = None


class WorktreePruneReport(BaseModel):
    """Summary report of worktree prune execution."""

    removed_count: int = 0
    refused_count: int = 0
    items: list[WorktreePruneItem] = Field(default_factory=list)


def _parse_single_record(record: list[str], *, is_main: bool) -> WorktreeInfo | None:
    """Extract worktree properties from a single record's tokens."""
    path: Path | None = None
    head: str = ""
    branch: str | None = None
    detached = False
    bare = False
    locked = False
    lock_reason: str | None = None
    prunable = False
    prunable_reason: str | None = None

    for token in record:
        if token.startswith(CONST_GIT_WORKTREE_PREFIX):
            path = Path(token.removeprefix(CONST_GIT_WORKTREE_PREFIX))
            continue
        if token.startswith(CONST_GIT_HEAD_PREFIX):
            head = token.removeprefix(CONST_GIT_HEAD_PREFIX)
            continue
        if token.startswith(CONST_GIT_BRANCH_PREFIX):
            branch = token.removeprefix(CONST_GIT_BRANCH_PREFIX)
            continue
        if token == CONST_GIT_DETACHED_TOKEN:
            detached = True
            continue
        if token == CONST_GIT_BARE_TOKEN:
            bare = True
            continue
        if token.startswith(CONST_GIT_LOCKED_TOKEN):
            locked = True
            rem = token.removeprefix(CONST_GIT_LOCKED_TOKEN).strip()
            lock_reason = rem or None
            continue
        if token.startswith(CONST_GIT_PRUNABLE_TOKEN):
            prunable = True
            rem = token.removeprefix(CONST_GIT_PRUNABLE_TOKEN).strip()
            prunable_reason = rem or None
            continue

    if path is None:
        return None

    return WorktreeInfo(
        path=path,
        head=head,
        branch=branch,
        detached=detached,
        bare=bare,
        locked=locked,
        lock_reason=lock_reason,
        prunable=prunable,
        prunable_reason=prunable_reason,
        is_main=is_main,
    )


def parse_worktree_porcelain_z(raw_output: str | bytes) -> list[WorktreeInfo]:
    """Parse NUL-separated porcelain records from git worktree list --porcelain -z."""
    raw_str = (
        raw_output.decode("utf-8", errors="surrogateescape")
        if isinstance(raw_output, bytes)
        else raw_output
    )
    tokens = raw_str.split("\0")
    records: list[list[str]] = []
    current: list[str] = []

    for token in tokens:
        if not token:
            if current:
                records.append(current)
                current = []
        else:
            current.append(token)
    if current:
        records.append(current)

    worktrees: list[WorktreeInfo] = []
    for idx, rec in enumerate(records):
        entry = _parse_single_record(rec, is_main=(idx == 0))
        if entry is not None:
            worktrees.append(entry)
    return worktrees


def count_dirty_paths(worktree_dir: Path) -> int:
    """Count uncommitted, modified, and untracked paths via git status --porcelain -z."""
    if not worktree_dir.is_dir():
        return 0
    proc = run_subprocess(
        ["git", "-C", str(worktree_dir), "status", "--porcelain", "-z"],
        quiet=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return 0
    raw_str = (
        proc.stdout.decode("utf-8", errors="surrogateescape")
        if isinstance(proc.stdout, bytes)
        else proc.stdout
    )
    tokens = raw_str.split("\0")
    count = 0
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if not token:
            idx += 1
            continue
        count += 1
        if len(token) >= 2 and (
            token[0] in CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS
            or token[1] in CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS
        ):
            idx += 2
        else:
            idx += 1
    return count


def _resolve_base_ref(repo_root: Path, preferred: str) -> str | None:
    """Resolve an existing base ref for rev-list comparisons."""
    candidates = [preferred, f"origin/{preferred}", "master", "origin/master"]
    for candidate in candidates:
        proc = run_subprocess(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", candidate],
            quiet=True,
        )
        if proc.returncode == 0:
            return candidate
    return None


def count_commits_ahead_of_main(
    repo_root: Path,
    head_or_ref: str,
    main_ref: str = CONST_GIT_MAIN_BRANCH,
) -> int:
    """Count how many commits head_or_ref is ahead of main (or resolved base branch)."""
    if not head_or_ref:
        return 0

    base_ref = _resolve_base_ref(repo_root, main_ref)
    if not base_ref:
        return 0

    rev_range = f"{base_ref}..{head_or_ref}"
    proc = run_subprocess(
        ["git", "-C", str(repo_root), "rev-list", "--count", rev_range],
        quiet=True,
    )
    if proc.returncode != 0:
        return 0
    raw = (
        proc.stdout.decode("utf-8", errors="surrogateescape")
        if isinstance(proc.stdout, bytes)
        else proc.stdout
    )
    try:
        return int(raw.strip())
    except ValueError:
        return 0


def is_tip_contained_in_other_ref(
    repo_root: Path,
    head: str,
    own_branch: str | None = None,
) -> bool:
    """Determine whether any local or remote ref other than own_branch contains the tip commit."""
    if not head:
        return False

    proc = run_subprocess(
        [
            "git",
            "-C",
            str(repo_root),
            "for-each-ref",
            "--format=%(refname)%00",
            "--contains",
            head,
            "refs/heads",
            "refs/remotes",
        ],
        quiet=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return False

    raw_str = (
        proc.stdout.decode("utf-8", errors="surrogateescape")
        if isinstance(proc.stdout, bytes)
        else proc.stdout
    )
    refs = [r.strip() for r in raw_str.split("\0") if r.strip()]
    if own_branch:
        other_refs = [r for r in refs if r != own_branch]
    else:
        other_refs = refs
    return len(other_refs) > 0


def list_worktree_infos(repo_root: Path) -> list[WorktreeInfo]:
    """Execute git worktree list --porcelain -z and parse records."""
    proc = run_subprocess(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain", "-z"],
        quiet=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return []
    return parse_worktree_porcelain_z(proc.stdout)


def enrich_worktree_entry(
    repo_root: Path,
    info: WorktreeInfo,
    base_ref: str = CONST_GIT_MAIN_BRANCH,
) -> WorktreeEntry:
    """Enrich a WorktreeInfo record with ahead, dirty, and contained metrics."""
    dirty = count_dirty_paths(info.path)
    ahead = count_commits_ahead_of_main(repo_root, info.head, main_ref=base_ref)
    contained = is_tip_contained_in_other_ref(repo_root, info.head, own_branch=info.branch)
    branch_display = (
        info.branch.removeprefix(CONST_REFS_HEADS_PREFIX)
        if info.branch
        else ("HEAD detached" if info.detached else None)
    )
    return WorktreeEntry(
        path=str(info.path),
        head=info.head,
        branch=branch_display,
        ahead=ahead,
        dirty=dirty,
        contained=contained,
        locked=info.locked,
        lock_reason=info.lock_reason,
        prunable=info.prunable,
        prunable_reason=info.prunable_reason,
        is_main=info.is_main,
    )


def inventory_worktrees(
    repo_root: Path | None = None,
    base_ref: str = CONST_GIT_MAIN_BRANCH,
) -> list[WorktreeEntry]:
    """Collect all repository worktrees with ahead, dirty, contained, and lock states."""
    effective_root = repo_root or find_repo_root()
    infos = list_worktree_infos(effective_root)
    return [enrich_worktree_entry(effective_root, info, base_ref=base_ref) for info in infos]


def _evaluate_single_prune_candidate(
    entry: WorktreeEntry,
    *,
    force: bool,
) -> tuple[bool, str]:
    """Evaluate whether an individual entry is removable and provide the decision reason."""
    if entry.is_main:
        return False, "main worktree"
    if force:
        return True, "forced"
    if entry.locked:
        reason = f"locked ({entry.lock_reason})" if entry.lock_reason else "locked"
        return False, reason
    if entry.dirty > 0:
        plural = "s" if entry.dirty != 1 else ""
        return False, f"dirty ({entry.dirty} uncommitted path{plural})"
    if not entry.contained:
        return False, "unmerged (tip not contained in any other ref)"
    return True, "clean and contained"


def evaluate_prune_candidates(
    entries: list[WorktreeEntry],
    *,
    force: bool = False,
) -> list[tuple[WorktreeEntry, bool, str]]:
    """Determine for each entry whether it is removable and the reason if refused."""
    return [
        (entry, is_rem, reason)
        for entry in entries
        for is_rem, reason in [_evaluate_single_prune_candidate(entry, force=force)]
    ]


def prune_worktrees(
    repo_root: Path,
    entries: list[WorktreeEntry],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> WorktreePruneReport:
    """Safely prune worktrees, requiring clean and contained status unless forced."""
    evaluated = evaluate_prune_candidates(entries, force=force)
    items: list[WorktreePruneItem] = []
    removed_count = 0
    refused_count = 0

    for entry, is_removable, reason in evaluated:
        if not is_removable:
            refused_count += 1
            items.append(WorktreePruneItem(path=entry.path, status="refused", reason=reason))
            continue

        if dry_run:
            items.append(WorktreePruneItem(path=entry.path, status="would remove", reason=reason))
            continue

        dest_dir = Path(entry.path)
        cmd = ["git", "-C", str(repo_root), "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(str(dest_dir))
        proc = run_subprocess(cmd, quiet=True)
        if proc.returncode == 0:
            removed_count += 1
            items.append(WorktreePruneItem(path=entry.path, status="removed", reason=None))
        else:
            if dest_dir.exists():
                shutil.rmtree(dest_dir, ignore_errors=True)
            removed_count += 1
            items.append(WorktreePruneItem(path=entry.path, status="removed", reason=None))

    if not dry_run:
        prune_proc = run_subprocess(
            ["git", "-C", str(repo_root), "worktree", "prune"],
            quiet=True,
        )
        if prune_proc.returncode != 0:
            logger.debug(
                "git worktree prune failed (%s): %s", prune_proc.returncode, prune_proc.stderr
            )

    return WorktreePruneReport(
        removed_count=removed_count,
        refused_count=refused_count,
        items=items,
    )
