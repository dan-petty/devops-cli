"""The stage job replaces its own draft plan that fails the plan check (#3387).

The stage job leaves an item out while its branch is on origin, so a draft plan that fails a check
has no way back: a person must edit or close the draft by hand. `may_replace` decides, from the
facts of the one draft pull request of a held item (`DraftRead`), whether the job stages the item
again on the branch of that draft. The plan must fail `check_proposal`, the draft must hold no
unresolved review thread, its branch must end at the commit that `stage.sha` records with commits of
the App alone, it must change no path outside the change folder of the item, and the job must not
have re-staged the plan of the same text (`Restage`, `stage.restage`). Every other draft holds the
item as it did before.

The module holds the rule, the record of one re-stage, and the read of the facts that the rule
takes (`held_draft`). The rule itself reads no GitHub and runs no git: its caller gives it the
facts, so a test passes them as data.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from devops_cli.config.settings import load_settings
from devops_cli.git.worktree_add import read_remote_heads, remote_branches
from devops_cli.github.client import GitHubClient
from devops_cli.github.pr_threads import ReviewThread, list_pr_review_threads
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.clone_git import branch_authors, checkout_at, default_branch
from devops_cli.roadmap.plan_check import PlanFolder, PlanProblem, folder_problems
from devops_cli.roadmap.plan_read import change_root, tree_files
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_registry import registry_table
from devops_cli.roadmap.stage.stage_specs import read_base_specs
from devops_cli.roadmap.stores.store import Item, StageRecordKey

if TYPE_CHECKING:
    from devops_cli.openspec.tool import OpenSpecTool

logger = logging.getLogger(__name__)

_GIT_OPERATION: Final[str] = "roadmap.stage.held"
"""The operation that a failed git command of the read names."""

ThreadsRead = Callable[[str, str, int], Sequence[ReviewThread]]
"""The read of the unresolved review threads of one pull request: the owner, the repository and the
number of the pull request."""


class Restage(BaseModel):
    """The record `stage.restage`: the draft pull request that the job replaced, and the hash of the
    text of the item that the replaced plan came from. The job re-stages the plan of one text once,
    so a plan that fails the check again holds the item until a person edits its text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pull: int
    text_hash: str

    @property
    def record(self) -> str:
        """The value of `stage.restage`."""
        return self.model_dump_json()


def restage_record(item: Item, pull: int) -> str:
    """The value of `stage.restage` for a re-stage of the draft pull request `pull` of `item`."""
    return Restage(pull=pull, text_hash=body_hashes(item.body)[0]).record


def recorded_restage(item: Item) -> Restage | None:
    """The re-stage that the job record of `item` holds, or None when it holds none. A record that
    is no re-stage is logged and read as none, so it never stops a round."""
    recorded = item.job_record.get(StageRecordKey.RESTAGE)
    if not recorded:
        return None
    try:
        return Restage.model_validate_json(recorded)
    except ValueError:
        logger.warning("The re-stage recorded on #%d is not a re-stage.", item.number)
        return None


def restaged_now(item: Item) -> bool:
    """Whether the job already re-staged the draft plan of the text that `item` holds now. A body
    edit is a new text, and its plan gets the one re-stage that the record bounds."""
    recorded = recorded_restage(item)
    return recorded is not None and recorded.text_hash == body_hashes(item.body)[0]


@dataclass(frozen=True)
class DraftRead:
    """The facts of the one draft pull request of a held item that decide whether the job replaces
    its plan (#3387).

    `pull` is the number of the draft, `draft` whether the pull request is still a draft,
    `at_recorded_commit` whether the tip of its branch is the commit that `stage.sha` records,
    `app_authored` whether each commit of the branch past the default branch has the App as its
    author, `unresolved_threads` the count of its review threads that no person resolved,
    `problems` what the plan check finds in its change files, `outside_paths` the paths that its
    branch changes outside the change folder of the item, and `restaged` whether the job already
    re-staged the plan of the text that the item holds now (`restaged_now`).
    """

    pull: int
    draft: bool
    at_recorded_commit: bool
    app_authored: bool
    unresolved_threads: int
    problems: tuple[PlanProblem, ...]
    outside_paths: tuple[str, ...]
    restaged: bool


def may_replace(read: DraftRead | None) -> bool:
    """Whether the stage job stages the item again on the branch of the draft that `read` gives,
    and updates that draft: the plan fails the plan check, and no other rule holds the item. `read`
    is None when the item has no draft that the job may read, and the job replaces nothing then."""
    if read is None:
        return False
    return (
        read.draft
        and read.at_recorded_commit
        and read.app_authored
        and read.unresolved_threads == 0
        and not read.outside_paths
        and bool(read.problems)
        and not read.restaged
    )


def _unresolved_threads(owner: str, name: str, pull: int) -> list[ReviewThread]:
    """The review threads of the pull request `pull` that no person resolved."""
    return list_pr_review_threads(owner, name, pull, unresolved_only=True)


def _recorded_draft(item: Item) -> tuple[int, str, str | None] | None:
    """The draft pull request, the branch and the commit that the record of `item` holds, or None
    when the record holds no draft of a branch."""
    recorded = item.job_record.get(StageRecordKey.PR)
    branch = item.job_record.get(StageRecordKey.BRANCH)
    if not recorded or not branch:
        return None
    try:
        pull = int(recorded)
    except ValueError:
        logger.warning("The draft pull request recorded on #%d is no number.", item.number)
        return None
    return pull, branch, item.job_record.get(StageRecordKey.SHA)


def _app_authored(source: Path, branch: str) -> bool:
    """Whether every commit of `origin/<branch>` past the default branch has the App as its author.
    A branch with no such commit, and a run with no App slug, is no branch of the App."""
    bot = load_settings().service.github_app.bot_login
    if bot is None:
        return False
    authors = branch_authors(source, branch, operation=_GIT_OPERATION)
    return bool(authors) and all(author == bot for author in authors)


def _inside(root: str, path: str) -> bool:
    """Whether `path` is the change folder `root` or a file of it."""
    return path == root or path.startswith(f"{root}/")


def _plan_problems(
    item: Item,
    *,
    repo: str,
    source: Path,
    head: str,
    root: str | None,
    tree: Sequence[str],
    client: GitHubClient,
    tool: OpenSpecTool | None,
) -> tuple[PlanProblem, ...]:
    """What the plan check finds in the change files of `item` at `head` (#3387): the reader of the
    folder `root`, the stage gates and the size of each group, on the full tracked tree of the
    commit, so that a path of the tree reads as present."""
    if root is None:
        return ()
    files = {
        path: client.get_file_at(repo, path, head) or "" for path in tree if _inside(root, path)
    }
    specs = read_base_specs(source, tool)
    with checkout_at(source, head, operation=_GIT_OPERATION) as worktree:
        folder = PlanFolder(
            root=root,
            files=files,
            checkout=worktree,
            tree=StagedTree(tree),
            known=frozenset(specs),
            requirements={name: spec.requirements for name, spec in specs.items()},
            base_scenarios={name: spec.scenarios for name, spec in specs.items()},
            item_title=item.title,
            item_body=item.body,
            budget=load_settings().roadmap.stage.step_tokens,
            registry=registry_table(worktree),
        )
        _, problems = folder_problems(folder)
    return tuple(problems)


def held_draft(
    item: Item,
    *,
    repo: str,
    source: Path,
    client: GitHubClient | None = None,
    threads: ThreadsRead = _unresolved_threads,
    tool: OpenSpecTool | None = None,
    default: str | None = None,
) -> DraftRead | None:
    """The facts of the one draft pull request of the held `item`, read in the clone `source`
    (#3387), or None when the item has no draft that the job may read: the record holds no
    `stage.pr` or no `stage.branch`, the pull request is no open draft with a head commit, or
    `origin` holds no branch of the record.

    `client` is the client of the GitHub session unless the caller gives one, `threads` reads the
    unresolved review threads, `tool` names the capabilities of the base specs, and `default` is the
    default branch of the repository, which the compare of the branch reads when the caller gives
    none.
    """
    recorded = _recorded_draft(item)
    if recorded is None:
        return None
    pull, branch, sha = recorded
    client = client or get_github_session().client
    status = client.get_pull_status(repo, pull)
    if not status.is_open_draft or not status.head_sha:
        return None
    if branch not in remote_branches(read_remote_heads(source)):
        return None
    # The fetch of the branch brings its commit into the clone, so the tree of the head is read
    # after it.
    app_authored = _app_authored(source, branch)
    head = status.head_sha
    compared = client.get_compare_files(
        repo, default or default_branch(source, operation=_GIT_OPERATION), head
    )
    tree = tree_files(source, head, operation=_GIT_OPERATION)
    root, _ = change_root(tree, item.number)
    outside = tuple(
        changed.filename
        for changed in compared.files
        if root is None or not _inside(root, changed.filename)
    )
    owner, name = repo.split("/", 1)
    return DraftRead(
        pull=pull,
        draft=status.draft,
        at_recorded_commit=bool(sha) and head == sha,
        app_authored=app_authored,
        unresolved_threads=len(threads(owner, name, pull)),
        problems=_plan_problems(
            item,
            repo=repo,
            source=source,
            head=head,
            root=root,
            tree=tree,
            client=client,
            tool=tool,
        ),
        outside_paths=outside,
        restaged=restaged_now(item),
    )
