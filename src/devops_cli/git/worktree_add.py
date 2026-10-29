"""Create the worktree of an issue, and refuse an issue that a worktree or a pushed branch holds
(#2337), or take over the staged branch that the App pushed (#2657).

An issue is held when a worktree of the repository has a branch of the form
`<type>/<issue>-<slug>` for it, when the standard directory of its worktree exists, or when
`origin` has such a branch. The check reads `git worktree list` and `git ls-remote` and makes no
GitHub request: a pull request of this repository always has a pushed head branch, and GitHub's
list of the pull requests that close an issue also names the open release pull request.

A pushed branch is not a hold when the App wrote every commit of it past `origin/main`: the author
of each commit, read with `git log --format=%an`, is the bot login of `service.github_app.slug`.
The run then adds the worktree on that branch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, NamedTuple

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
from devops_cli.git.branch_form import BranchParts, branch_name, issue_of_branch, parse_branch
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
    commands that a dry run lists, and is empty after a real run. `commits` is the number of commits
    by the App on a branch that the run took over. `reclaimed` and `reclaim_error`
    are the result of the reclaim of merged worktrees that comes first."""

    issue: int
    branch: str
    path: str
    status: Literal["created", "took over", "would create"]
    commits: int = 0
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


class _Pushed(NamedTuple):
    """A branch of `origin` that names an issue, with its parts."""

    name: str
    parts: BranchParts


def _pushed_branches(ls_remote: str, issue: int) -> list[_Pushed]:
    """The branches of `origin` that name `issue` in the output of `git ls-remote --heads`."""
    found: list[_Pushed] = []
    for line in ls_remote.splitlines():
        _, _, ref = line.partition("\t")
        name = ref.removeprefix(CONST_REFS_HEADS_PREFIX)
        parts = parse_branch(name)
        if parts is not None and parts.issue == issue:
            found.append(_Pushed(name, parts))
    return found


def _staged_branch(ls_remote: str, issue: int) -> _Pushed | None:
    """The one branch of `origin` for `issue`, or None; more than one holds the issue."""
    found = _pushed_branches(ls_remote, issue)
    if len(found) > 1:
        names = ", ".join(f"origin/{pushed.name}" for pushed in found)
        raise _failure(
            MESSAGES.repos.worktrees_add_held_by_branches.format(issue=issue, branches=names)
        )
    return found[0] if found else None


def _git(repo_root: Path) -> list[str]:
    return [CONST_GIT_CLI, "-C", str(repo_root)]


def _main_ref() -> str:
    return f"{CONST_GIT_REMOTE_ORIGIN}/{CONST_GIT_MAIN_BRANCH}"


def remote_branches(ls_remote: str) -> list[str]:
    """The branch names in the output of `git ls-remote --heads`, in its order."""
    refs = (line.partition("\t")[2] for line in ls_remote.splitlines())
    return [ref.removeprefix(CONST_REFS_HEADS_PREFIX) for ref in refs if ref]


def _commands(repo_root: Path, branch: str, directory: Path) -> list[list[str]]:
    """The four git commands that a run can make, in order: read the branches of `origin`, fetch
    the main branch, read the authors of the pushed branch past main, and create the worktree.
    A run makes the third only when `origin` holds the branch, and then it takes the branch over
    instead of the fourth (`_take_over`). `--no-track` leaves a new branch with no upstream, so
    that a plain `git push` cannot aim at `main`."""
    git = _git(repo_root)
    return [
        [*git, "ls-remote", "--heads", CONST_GIT_REMOTE_ORIGIN],
        [*git, "fetch", CONST_GIT_REMOTE_ORIGIN, CONST_GIT_MAIN_BRANCH],
        [*git, "log", "--format=%an", f"{_main_ref()}..{CONST_GIT_REMOTE_ORIGIN}/{branch}"],
        [*git, "worktree", "add", "--no-track", "-b", branch, str(directory), _main_ref()],
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


def _check_authors(issue: int, branch: str, authors: list[str]) -> None:
    """Refuse the branch unless it has a commit and the App wrote every one."""
    bot = load_settings().service.github_app.bot_login
    messages = MESSAGES.repos
    if not authors:
        raise _failure(messages.worktrees_add_held_no_commits.format(issue=issue, branch=branch))
    if bot is None:
        raise _failure(messages.worktrees_add_held_no_app.format(issue=issue, branch=branch))
    if (other := next((author for author in authors if author != bot), None)) is not None:
        raise _failure(
            messages.worktrees_add_held_by_author.format(
                issue=issue, branch=branch, author=other, bot=bot
            )
        )


def _check_names(issue: int, pushed: _Pushed, type_: str | None, slug: str | None) -> None:
    """Refuse a `--type` or `--slug` that differs from the pushed branch."""
    for option, given, staged in (
        ("type", type_, pushed.parts.type),
        ("slug", slug, pushed.parts.slug),
    ):
        if given is not None and given != staged:
            raise _failure(
                MESSAGES.repos.worktrees_add_staged_differs.format(
                    issue=issue, branch=pushed.name, option=option, staged=staged, given=given
                )
            )


def _take_over(
    repo_root: Path, issue: int, pushed: _Pushed, directory: Path, reclaim: ReclaimResult
) -> WorktreeAddReport:
    """Add the worktree on the pushed branch when the App wrote every commit past main.

    The fetch names the branch, so `origin/<branch>` exists whatever the fetch refspec of the
    clone. The worktree tracks the pushed branch, so a plain `git push` goes to it.
    """
    git, branch = _git(repo_root), pushed.name
    remote_branch = f"{CONST_GIT_REMOTE_ORIGIN}/{branch}"
    _run(
        [
            *git,
            "fetch",
            CONST_GIT_REMOTE_ORIGIN,
            CONST_GIT_MAIN_BRANCH,
            f"+{CONST_REFS_HEADS_PREFIX}{branch}:refs/remotes/{remote_branch}",
        ]
    )
    authors = _run([*git, "log", "--format=%an", f"{_main_ref()}..{remote_branch}"]).splitlines()
    _check_authors(issue, branch, authors)
    _run([*git, "worktree", "add", "--track", "-b", branch, str(directory), remote_branch])
    return WorktreeAddReport(
        issue=issue,
        branch=branch,
        path=str(directory),
        status="took over",
        commits=len(authors),
        reclaimed=reclaim.removed,
        reclaim_error=reclaim.error,
    )


def _create(
    repo_root: Path,
    issue: int,
    branch: str,
    directory: Path,
    reclaim: ReclaimResult,
) -> WorktreeAddReport:
    """Add the worktree on the new `branch` at the fetched `origin/main`."""
    _, fetch, _, create = _commands(repo_root, branch, directory)
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


def _new_branch(issue: int, type_: str | None, slug: str | None) -> str:
    """The name of the new branch; both parts are required when `origin` holds no branch."""
    if type_ is None or slug is None:
        raise _failure(MESSAGES.repos.worktrees_add_needs_branch_options.format(issue=issue))
    return branch_name(issue, type_, slug)


def add_worktree(
    repo_root: Path,
    *,
    issue: int,
    type_: str | None,
    slug: str | None,
    dry_run: bool = False,
    reclaim: ReclaimResult | None = None,
) -> WorktreeAddReport:
    """Create the worktree of `issue`, or take over the staged branch that `origin` holds for it.

    With no branch of `origin` for the issue, the worktree is on the new branch
    `<type>/<issue>-<slug>` at the fetched `origin/main`, and `type_` and `slug` are required.
    With a pushed branch, the App must have written every commit of it past main: the run takes
    the branch over (`took over`), takes `type_` and `slug` from it, and refuses a value that
    differs. The run refuses an issue that a local worktree holds before it reads `origin`, and
    one that a branch of `origin` holds before it adds the worktree, so a refused run leaves no
    worktree and no local branch. A dry run reads the local worktrees only and lists the four
    commands. `reclaim` is the result of `reclaim_merged_worktrees`, which the caller ran first;
    it goes into the report.
    """
    reclaim = reclaim or ReclaimResult()
    directory = worktree_directory(issue, repo_root)
    _require_origin(repo_root)
    if (held := _local_holder(repo_root, issue, directory)) is not None:
        raise _failure(held)
    if dry_run:
        branch = _new_branch(issue, type_, slug)
        planned = [
            PlannedRequest("git", " ".join(argv[1:]), argv=tuple(argv))
            for argv in _commands(repo_root, branch, directory)
        ]
        return WorktreeAddReport(
            issue=issue,
            branch=branch,
            path=str(directory),
            status="would create",
            requests=[*reclaim.requests, *(request.line() for request in planned)],
            reclaimed=reclaim.removed,
            reclaim_error=reclaim.error,
        )
    ls_remote = [*_git(repo_root), "ls-remote", "--heads", CONST_GIT_REMOTE_ORIGIN]
    if (pushed := _staged_branch(_run(ls_remote), issue)) is None:
        return _create(repo_root, issue, _new_branch(issue, type_, slug), directory, reclaim)
    _check_names(issue, pushed, type_, slug)
    return _take_over(repo_root, issue, pushed, directory, reclaim)


def read_remote_heads(repo_root: Path) -> str:
    """The output of `git ls-remote --heads origin` for the clone at `repo_root`: one read of the
    branches of `origin`, for `issue_holder` to judge many issues with."""
    _require_origin(repo_root)
    return _run([*_git(repo_root), "ls-remote", "--heads", CONST_GIT_REMOTE_ORIGIN])


def issue_holder(repo_root: Path, issue: int, remote_heads: str) -> str | None:
    """Who holds `issue`, as a sentence: a worktree of the clone, the standard directory of its
    worktree, or a branch of `origin` that `remote_heads` lists; None when nobody does. A caller
    that judges an issue before it adds a worktree leaves a held issue alone (#2654); `add_worktree`
    itself takes over a staged branch."""
    held = _local_holder(repo_root, issue, worktree_directory(issue, repo_root))
    if held is not None:
        return held
    pushed = _pushed_branches(remote_heads, issue)
    if not pushed:
        return None
    names = ", ".join(f"origin/{branch.name}" for branch in pushed)
    return MESSAGES.repos.worktrees_add_held_by_pushed.format(issue=issue, branches=names)
