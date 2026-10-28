"""Worktree inventory, status inspection, and safe worktree reclamation (#700, #2341).

Provides NUL-separated porcelain parsing for `git worktree list -z`, ahead-of-main calculation,
dirty-path counting, and pruning. A worktree is removable only when GitHub reports a merged pull
request whose head is the tip of the worktree: the repository squash-merges, so no ref that
contains a tip shows that its work is merged.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_GIT_BARE_TOKEN,
    CONST_GIT_BRANCH_PREFIX,
    CONST_GIT_DETACHED_TOKEN,
    CONST_GIT_HEAD_PREFIX,
    CONST_GIT_LOCKED_TOKEN,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS,
    CONST_GIT_NOT_A_WORKTREE_TOKEN,
    CONST_GIT_PRUNABLE_TOKEN,
    CONST_GIT_WORKTREE_PREFIX,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_repo_root
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitOperationError
from devops_cli.git.branch_form import issue_of_branch

if TYPE_CHECKING:
    from collections.abc import Callable

CONST_REFS_HEADS_PREFIX: Final[str] = "refs/heads/"


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
    """Enriched worktree record with ahead and dirty metrics. `dirty` is None when `git status`
    failed in the worktree, which is not the same as clean. `issue` is the issue that the branch
    names, as `<type>/<issue>-<slug>`, and None for any other branch."""

    path: str
    head: str
    branch: str | None = None
    issue: int | None = None
    ahead: int
    dirty: int | None
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
    size_bytes: int | None = None


class WorktreePruneReport(BaseModel):
    """Summary report of worktree prune execution. `requests` lists the GitHub requests that a
    dry run would make, and is empty for a run that made them. `total_bytes` is the size of the
    directories of the worktrees removed, or that a run without `confirm` would remove."""

    removed_count: int = 0
    refused_count: int = 0
    failed_count: int = 0
    total_bytes: int = 0
    items: list[WorktreePruneItem] = Field(default_factory=list)
    requests: list[str] = Field(default_factory=list)


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


def count_dirty_paths(worktree_dir: Path) -> int | None:
    """Count uncommitted, modified, and untracked paths via git status --porcelain -z.

    A directory that is gone has nothing uncommitted, so it counts 0. None means `git status`
    failed, so nothing is known about the directory.
    """
    if not worktree_dir.is_dir():
        return 0
    proc = run_subprocess(
        ["git", "-C", str(worktree_dir), "status", "--porcelain", "-z"],
        check=False,
        quiet=True,
        local_read=True,
    )
    if proc.returncode != 0:
        return None
    if not proc.stdout:
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
            check=False,
            quiet=True,
            local_read=True,
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
        check=False,
        quiet=True,
        local_read=True,
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


def list_worktree_infos(repo_root: Path) -> list[WorktreeInfo]:
    """Execute git worktree list --porcelain -z and parse records."""
    proc = run_subprocess(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain", "-z"],
        check=False,
        quiet=True,
        local_read=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return []
    return parse_worktree_porcelain_z(proc.stdout)


def enrich_worktree_entry(
    repo_root: Path,
    info: WorktreeInfo,
    base_ref: str = CONST_GIT_MAIN_BRANCH,
) -> WorktreeEntry:
    """Enrich a WorktreeInfo record with ahead and dirty metrics."""
    dirty = count_dirty_paths(info.path)
    ahead = count_commits_ahead_of_main(repo_root, info.head, main_ref=base_ref)
    branch_display = (
        info.branch.removeprefix(CONST_REFS_HEADS_PREFIX)
        if info.branch
        else ("HEAD detached" if info.detached else None)
    )
    return WorktreeEntry(
        path=str(info.path),
        head=info.head,
        branch=branch_display,
        issue=issue_of_branch(branch_display),
        ahead=ahead,
        dirty=dirty,
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
    """Collect all repository worktrees with ahead, dirty, and lock states."""
    effective_root = repo_root or find_repo_root()
    infos = list_worktree_infos(effective_root)
    return [enrich_worktree_entry(effective_root, info, base_ref=base_ref) for info in infos]


def _file_size(path: str) -> int:
    """The size of one file in bytes, or 0 when the file is gone."""
    try:
        return os.lstat(path).st_size
    except FileNotFoundError:
        return 0


def directory_size(path: Path) -> int:
    """The bytes of every file under `path`, links counted as links and not followed."""
    return sum(
        _file_size(os.path.join(top, name)) for top, _dirs, names in os.walk(path) for name in names
    )


def _size_of(path: str) -> int | None:
    """The size of a worktree's directory, or None when the directory is gone."""
    directory = Path(path)
    return directory_size(directory) if directory.is_dir() else None


def _total(items: list[WorktreePruneItem], *statuses: str) -> int:
    """The bytes of the items whose status is one of `statuses`."""
    return sum(item.size_bytes or 0 for item in items if item.status in statuses)


@dataclass(frozen=True)
class _Decision:
    """Whether one worktree is removable, and why or why not."""

    entry: WorktreeEntry
    removable: bool
    reason: str


def _decided_by_local_state(
    entry: WorktreeEntry, *, force: bool, current_dir: Path
) -> _Decision | None:
    """What git shows of the worktree decides, or None when the pull request of its tip must.

    The main worktree and the worktree that holds the current directory stay under `--force` too:
    removing the second would take the directory away from the shell that runs the command
    (#2338). A worktree whose directory is gone is removable: it holds nothing, and removing it
    drops only git's record.
    """
    if entry.is_main:
        return _Decision(entry, removable=False, reason="main worktree")
    if current_dir.is_relative_to(Path(entry.path).resolve()):
        return _Decision(entry, removable=False, reason="current directory")
    if force:
        return _Decision(entry, removable=True, reason="forced")
    if entry.locked:
        reason = f"locked ({entry.lock_reason})" if entry.lock_reason else "locked"
        return _Decision(entry, removable=False, reason=reason)
    if entry.prunable:
        return _Decision(entry, removable=True, reason="directory is missing")
    if entry.dirty is None:
        return _Decision(entry, removable=False, reason="dirty state unknown (git status failed)")
    if entry.dirty > 0:
        plural = "s" if entry.dirty != 1 else ""
        return _Decision(
            entry, removable=False, reason=f"dirty ({entry.dirty} uncommitted path{plural})"
        )
    return None


def _decide(
    entry: WorktreeEntry,
    *,
    force: bool,
    current_dir: Path,
    merged_pull: Callable[[str], int | None],
) -> _Decision:
    """Decide one worktree: local state first, then the merged pull request of its tip."""
    local = _decided_by_local_state(entry, force=force, current_dir=current_dir)
    if local is not None:
        return local
    number = merged_pull(entry.head)
    if number is None:
        return _Decision(
            entry, removable=False, reason="no merged pull request has this commit as its head"
        )
    return _Decision(entry, removable=True, reason=f"head of merged pull request #{number}")


def _require_repo(repo: str | None) -> str:
    """The GitHub repository whose pull requests are read, or the error that names why none is."""
    if repo is None:
        raise GitOperationError(
            "The checkout has no GitHub origin, so the merged pull requests of its worktrees "
            "cannot be read; add an origin remote, or use --force",
            operation="worktrees prune",
        )
    return repo


def plan_prune(
    entries: list[WorktreeEntry],
    *,
    repo: str | None,
    force: bool = False,
) -> WorktreePruneReport:
    """The dry run of `prune_worktrees`: what local state decides, and the GitHub requests that
    the other worktrees would need. It makes no request."""
    items: list[WorktreePruneItem] = []
    requests: list[str] = []
    current_dir = Path.cwd().resolve()
    for entry in entries:
        local = _decided_by_local_state(entry, force=force, current_dir=current_dir)
        if local is None:
            requests.append(
                PlannedRequest("GET", f"/repos/{repo}/commits/{entry.head}/pulls").line()
            )
            item = WorktreePruneItem(
                path=entry.path,
                status="would check",
                reason="the merged pull request of its tip is read",
            )
        else:
            status = "would remove" if local.removable else "refused"
            size = _size_of(entry.path) if local.removable else None
            item = WorktreePruneItem(
                path=entry.path, status=status, reason=local.reason, size_bytes=size
            )
        items.append(item)
    return WorktreePruneReport(
        refused_count=sum(1 for item in items if item.status == "refused"),
        total_bytes=_total(items, "would remove"),
        items=items,
        requests=requests,
    )


def git_message(proc: subprocess.CompletedProcess[str]) -> str:
    """What a failed git command said, or its exit status when it said nothing."""
    said = " ".join(str(proc.stderr or "").split())
    return said[:CONST_MAX_ERROR_DETAIL_LENGTH] or f"git exited with status {proc.returncode}"


def prune_worktrees(
    repo_root: Path,
    entries: list[WorktreeEntry],
    *,
    repo: str | None,
    force: bool = False,
    confirm: bool = False,
) -> WorktreePruneReport:
    """Prune worktrees whose tip heads a merged pull request, or all of them under `force`.

    Every worktree is decided before any is removed, so a failed GitHub read ends the run with
    nothing removed. Without `confirm` the run removes nothing and reports `would remove`. A
    removal that git refuses is reported as `failed`, with git's message, and its directory stays.
    A worktree that a parallel run already removed cannot be removed again: git reports `is not a
    working tree`, and the run reports the worktree as `removed`, so it counts as done, not failed.
    """

    def merged_pull(tip: str) -> int | None:
        from devops_cli.github.session import get_github_session

        client = get_github_session().client
        for pull in client.get_commit_pulls(_require_repo(repo), tip):
            if pull.merged_at is not None and pull.head_sha == tip:
                return pull.number
        return None

    current_dir = Path.cwd().resolve()
    decisions = [
        _decide(entry, force=force, current_dir=current_dir, merged_pull=merged_pull)
        for entry in entries
    ]
    items: list[WorktreePruneItem] = []
    for decision in decisions:
        path = decision.entry.path
        if not decision.removable:
            items.append(WorktreePruneItem(path=path, status="refused", reason=decision.reason))
            continue
        size = _size_of(path)
        if not confirm:
            items.append(
                WorktreePruneItem(
                    path=path, status="would remove", reason=decision.reason, size_bytes=size
                )
            )
        else:
            cmd = ["git", "-C", str(repo_root), "worktree", "remove"]
            if force:
                cmd.append("--force")
            proc = run_subprocess([*cmd, path], check=False, quiet=True)
            if proc.returncode == 0 or CONST_GIT_NOT_A_WORKTREE_TOKEN in git_message(proc):
                items.append(WorktreePruneItem(path=path, status="removed", size_bytes=size))
            else:
                items.append(
                    WorktreePruneItem(path=path, status="failed", reason=git_message(proc))
                )
    return WorktreePruneReport(
        removed_count=sum(1 for item in items if item.status == "removed"),
        refused_count=sum(1 for item in items if item.status == "refused"),
        failed_count=sum(1 for item in items if item.status == "failed"),
        total_bytes=_total(items, "removed", "would remove"),
        items=items,
    )
