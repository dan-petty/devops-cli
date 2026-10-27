"""Create the worktree of an issue, and refuse an issue that a worktree or a pushed branch holds
(#2337).

An issue is held when a worktree of the repository has a branch of the form
`<type>/<issue>-<slug>` for it, when the standard directory of its worktree exists, or when
`origin` has such a branch. The check reads `git worktree list` and `git ls-remote` and makes no
GitHub request: a pull request of this repository always has a pushed head branch, and GitHub's
list of the pull requests that close an issue also names the open release pull request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_AGENT_WORKTREE_PREFIX,
    CONST_AGENT_WORKTREES_SUBPATH,
    CONST_GIT_CLI,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_REMOTE_ORIGIN,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name, resolve_data_path
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitOperationError
from devops_cli.git.branch_form import branch_name, issue_of_branch
from devops_cli.git.worktree_inventory import (
    CONST_REFS_HEADS_PREFIX,
    WorktreePruneItem,
    git_message,
    inventory_worktrees,
    list_worktree_infos,
    plan_prune,
    prune_worktrees,
)
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "worktrees add"


class ReclaimResult(BaseModel):
    """What the reclaim of merged worktrees did: the worktrees it removed, the GitHub reads that
    a dry run lists, and the reason it removed nothing when it could not run."""

    removed: list[WorktreePruneItem] = Field(default_factory=list)
    requests: list[str] = Field(default_factory=list)
    error: str | None = None


class WorktreeAddReport(BaseModel):
    """What `add` did, or with `dry_run` what it would do. `requests` holds the requests and
    commands that a dry run lists, and is empty after a real run. `reclaimed` and `reclaim_error`
    are the result of the reclaim of merged worktrees that comes first."""

    issue: int
    branch: str
    path: str
    status: Literal["created", "would create"]
    requests: list[str] = Field(default_factory=list)
    reclaimed: list[WorktreePruneItem] = Field(default_factory=list)
    reclaim_error: str | None = None


def worktree_directory(issue: int, repo_root: Path) -> Path:
    """The standard directory of the worktree of `issue`: `w-<issue>` under the agent worktrees
    directory of the data directory, which every worktree of the repository shares."""
    return resolve_data_path(
        load_settings().data.dir
        / CONST_AGENT_WORKTREES_SUBPATH
        / f"{CONST_AGENT_WORKTREE_PREFIX}{issue}",
        repo_root,
    )


def _failure(message: str) -> GitOperationError:
    return GitOperationError(message, operation=_OPERATION)


def _require_origin(repo_root: Path) -> None:
    """Refuse a repository that has no remote named `origin`."""
    proc = run_subprocess(
        [CONST_GIT_CLI, "-C", str(repo_root), "remote", "get-url", CONST_GIT_REMOTE_ORIGIN],
        check=False,
        quiet=True,
        local_read=True,
    )
    if proc.returncode != 0:
        raise _failure(MESSAGES.repos.worktrees_add_no_origin)


def _local_holder(repo_root: Path, issue: int, directory: Path) -> str | None:
    """Who holds `issue` in this repository, as a sentence: a worktree on a branch for it, or the
    standard directory of its worktree; None when nobody does. A local branch with no worktree
    holds nothing, since `prune` leaves such a branch after a merge."""
    for info in list_worktree_infos(repo_root):
        branch = info.branch.removeprefix(CONST_REFS_HEADS_PREFIX) if info.branch else None
        if issue_of_branch(branch) == issue:
            return MESSAGES.repos.worktrees_add_held_by_worktree.format(
                issue=issue, path=info.path, branch=branch
            )
    if directory.exists():
        return MESSAGES.repos.worktrees_add_held_by_directory.format(issue=issue, path=directory)
    return None


def _remote_holder(ls_remote: str, issue: int) -> str | None:
    """The branch of `origin` that names `issue` in the output of `git ls-remote --heads`."""
    for line in ls_remote.splitlines():
        _, _, ref = line.partition("\t")
        branch = ref.removeprefix(CONST_REFS_HEADS_PREFIX)
        if issue_of_branch(branch) == issue:
            return branch
    return None


def _commands(repo_root: Path, branch: str, directory: Path) -> list[list[str]]:
    """The three git commands of a run, in order: read the branches of `origin`, fetch the main
    branch, and create the worktree. `--no-track` leaves the branch with no upstream, so that a
    plain `git push` cannot aim at `main`."""
    git = [CONST_GIT_CLI, "-C", str(repo_root)]
    base = f"{CONST_GIT_REMOTE_ORIGIN}/{CONST_GIT_MAIN_BRANCH}"
    return [
        [*git, "ls-remote", "--heads", CONST_GIT_REMOTE_ORIGIN],
        [*git, "fetch", CONST_GIT_REMOTE_ORIGIN, CONST_GIT_MAIN_BRANCH],
        [*git, "worktree", "add", "--no-track", "-b", branch, str(directory), base],
    ]


def _run(argv: list[str]) -> str:
    """Run one git command; its output, or the error that names the command and what git said."""
    proc = run_subprocess(argv, check=False, quiet=True)
    if proc.returncode != 0:
        raise _failure(
            MESSAGES.repos.worktrees_add_git_failed.format(
                command=" ".join(argv[3:]), reason=mask_secrets(git_message(proc))
            )
        )
    return proc.stdout


def reclaim_merged_worktrees(repo_root: Path, *, dry_run: bool = False) -> ReclaimResult:
    """Remove the worktrees that `prune --confirm` removes: clean, not locked, not the current
    directory, and at the head of a merged pull request (#2338).

    A merged worktree still holds its issue, so `add` runs this before it looks for a holder. The
    reclaim is housekeeping and never stops the work after it: when the pull requests cannot be
    read, nothing is removed (`prune_worktrees` decides every worktree before it removes one) and
    the reason comes back in `error`. A dry run lists the GitHub reads and removes nothing.
    """
    _require_origin(repo_root)
    repo = get_repo_origin_name(repo_root)
    entries = inventory_worktrees(repo_root)
    if dry_run:
        return ReclaimResult(requests=plan_prune(entries, repo=repo).requests)
    try:
        report = prune_worktrees(repo_root, entries, repo=repo, confirm=True)
    except DevOpsCLIError as exc:
        return ReclaimResult(error=str(exc))
    failed = [f"{item.path}: {item.reason}" for item in report.items if item.status == "failed"]
    return ReclaimResult(
        removed=[item for item in report.items if item.status == "removed"],
        error="; ".join(failed) or None,
    )


def add_worktree(
    repo_root: Path,
    *,
    issue: int,
    type_: str,
    slug: str,
    dry_run: bool = False,
    reclaim: ReclaimResult | None = None,
) -> WorktreeAddReport:
    """Create the worktree of `issue` on `<type>/<issue>-<slug>` at the fetched `origin/main`.

    The run refuses an issue that a local worktree holds before it reads `origin`, and one that a
    branch of `origin` holds before it fetches, so a refused run changes nothing. A dry run reads
    the local worktrees only and lists the three commands. `reclaim` is the result of
    `reclaim_merged_worktrees`, which the caller ran first; it goes into the report.
    """
    reclaim = reclaim or ReclaimResult()
    branch = branch_name(issue, type_, slug)
    directory = worktree_directory(issue, repo_root)
    _require_origin(repo_root)
    if (held := _local_holder(repo_root, issue, directory)) is not None:
        raise _failure(held)
    ls_remote, fetch, create = commands = _commands(repo_root, branch, directory)
    if dry_run:
        planned = [PlannedRequest("git", " ".join(argv[1:]), argv=tuple(argv)) for argv in commands]
        return WorktreeAddReport(
            issue=issue,
            branch=branch,
            path=str(directory),
            status="would create",
            requests=[*reclaim.requests, *(request.line() for request in planned)],
            reclaimed=reclaim.removed,
            reclaim_error=reclaim.error,
        )
    if (pushed := _remote_holder(_run(ls_remote), issue)) is not None:
        raise _failure(
            MESSAGES.repos.worktrees_add_held_by_branch.format(issue=issue, branch=pushed)
        )
    _run(fetch)
    _run(create)
    return WorktreeAddReport(
        issue=issue,
        branch=branch,
        path=str(directory),
        status="created",
        reclaimed=reclaim.removed,
        reclaim_error=reclaim.error,
    )
