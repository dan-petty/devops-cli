"""`devops roadmap implement` as a job: which Staged and Planned items it takes (#2665, #2714).

The job takes each Staged or Planned item that a label filter names and runs the task groups of
its change (`implement_run`). This module selects and plans. It makes no write to git or to GitHub.

**Staged.** An item is Staged when its record holds a branch and a draft pull request, the branch
is on `origin`, and the draft is open. The pair is `implement.branch` and `implement.pr` when the
implement job wrote both, else `stage.branch` and `stage.pr`. A draft that the Service marked
ready (the row `stage_ready`, #2865) is no longer a draft: its item is Planned once a person has
merged the plan.

**Planned.** An item is Planned when the folder `openspec/changes/<issue>-<slug>` is on
`origin/<default branch>` and no recorded branch is on `origin`: a person merged the staging pull
request, and its branch is gone. The job makes the branch `<type>/<issue>-<slug>` at the default
branch, with the slug of the folder. An item whose recorded branch is still on `origin` is Staged,
also when its plan is on the default branch.

**Selection.** `--filter family=value` is repeatable over the label families `status`,
`priority`, `type`, `value` and `effort`: the values of one family are alternatives, and the
families all apply. With no filter the job takes the Ready and Planned items of low effort. The
Service sets `status/planned` once the plan is on the default branch (`status_sync.py`, #2920). An
item that the filter names, and that the job leaves out, is in the plan with its reason: its Status
is neither Ready nor Planned (an item In Progress stays while its record names a runner Job that no
round reported: that Job plans its own item), an agent or a person claimed it (#2910), it is
neither Staged nor Planned, a step stopped it
and no person cleared the stop,
its author is not the owner, a member or a collaborator, its branch is gone from `origin` or holds
a commit by anyone but the App, a worktree holds the issue, its pull request is not an open
draft, or, for a Planned item, a branch of `origin` holds the issue, its change is archived, it
has no branch name, its change has no `tasks.md` on the default branch, or every task of its
change is ticked. A run takes at most `--limit` items,
the highest priority first. `--item` takes the one item it names and does not apply the filter or
the limit.

**Why.** `--why` adds to the plan the open items that the filter does not name, under their own
heading, each with the family it misses (`StageFilter.mismatch`). `devops roadmap explain` gives the
reason of one issue for this job and for the stage job (#2911).

**Retry.** A person clears a stop with the comment `implement: retry`, made after the comment
of the job that told of the stop. Only a comment of the owner, a member or a collaborator counts
(`retry_asked`). The row `implement` of the Service reads it for an item that it set Blocked
(`stop_clear.py`); this judge reads it for an item that holds Ready or Planned and a stop on record,
such as an item that a person set back by hand.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import GitHubNotFoundError, GitOperationError
from devops_cli.git.branch_form import BranchParts, branch_name, parse_branch
from devops_cli.git.worktree_add import (
    issue_holder,
    local_holder,
    read_remote_heads,
    remote_branches,
    stray_branch_reason,
    worktree_directory,
)
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import branch_authors
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.planned import PlannedChanges, read_planned_changes, tasks_on_default
from devops_cli.roadmap.refine import inspect_checkout
from devops_cli.roadmap.stage import (
    LeftOut,
    StageFilter,
    named_items,
    parse_filters,
    unmatched_items,
    walk_named,
)
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.store import (
    GitHubState,
    ImplementRecordKey,
    IssueComment,
    Item,
    RoadmapStore,
    StageRecordKey,
)

GIT_OPERATION: Final[str] = "roadmap.implement"

# What the job implements without a `--filter`: the Ready and Planned items of low effort, of any
# type, priority and value (#2906, #2920).
DEFAULT_IMPLEMENT_FILTERS: Final[tuple[str, ...]] = ("status=ready", "status=planned", "effort=low")


def parse_implement_filters(options: Iterable[str]) -> StageFilter:
    """The filter that the `family=value` options give, or `DEFAULT_IMPLEMENT_FILTERS` with none.
    A bad option raises `ValidationError`, as the stage job's parser does."""
    return parse_filters(options, DEFAULT_IMPLEMENT_FILTERS)


@dataclass(frozen=True)
class ImplementTarget:
    """An item to implement: its branch, its draft pull request, and whether a person's retry
    comment clears a stop on its record before the first step.

    A Staged item has the branch and the open draft that the stage job or an earlier run made. A
    Planned item has `pull` None: its plan is on the default branch, and the job makes `branch`
    and opens the draft when the branch first holds a commit (#2714)."""

    item: Item
    branch: str
    pull: int | None
    retry: bool = False

    @property
    def planned(self) -> bool:
        """Whether the item is Planned: the job makes its branch and its pull request."""
        return self.pull is None

    @property
    def new_branch(self) -> BranchParts | None:
        """The parts of the branch that the job makes, or None for a Staged item."""
        return parse_branch(self.branch) if self.planned else None


@dataclass(frozen=True)
class ImplementPlan:
    """What a run does: the items to implement, and the items the filter names that the job leaves
    out, each with its reason. `unmatched` holds the open items that the filter does not name, only
    when the plan was asked for them (`--why`). `beyond` holds the numbers of the items that pass
    every rule but come after the limit (`walk_named`). A dry run holds the requests of a run and
    nothing else."""

    repo: str
    selected: tuple[ImplementTarget, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()
    unmatched: tuple[LeftOut, ...] = ()
    beyond: tuple[int, ...] = ()


class RecordedBranch(NamedTuple):
    """The branch and the draft pull request that a record names."""

    branch: str
    pull: int


def _pull_number(recorded: str | None) -> int | None:
    return int(recorded) if recorded is not None and recorded.isdigit() else None


def recorded_branch(item: Item) -> RecordedBranch | None:
    """The branch and the pull request in the item's record, or None. The pair that the implement
    job wrote comes first: after a Planned run opened its draft, a retry finds that draft, not the
    merged pull request of the stage job (#2714). The two keys of a pair go together."""
    record = item.job_record
    for branch_key, pull_key in (
        (ImplementRecordKey.BRANCH, ImplementRecordKey.PR),
        (StageRecordKey.BRANCH, StageRecordKey.PR),
    ):
        branch, pull = record.get(branch_key), _pull_number(record.get(pull_key))
        if branch and pull is not None:
            return RecordedBranch(branch, pull)
    return None


class _Planned(NamedTuple):
    """The change folder, `<issue>-<slug>`, of a Planned item."""

    folder: str


def retry_asked(comments: Sequence[IssueComment]) -> bool:
    """Whether a trusted commenter asked for a retry after the last comment of the job."""
    marked = [
        index
        for index, comment in enumerate(comments)
        if comment.body.startswith(CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER)
    ]
    after = comments[marked[-1] + 1 :] if marked else comments
    return any(
        comment.author_association in CONST_ROADMAP_TRUSTED_AUTHORS
        and comment.body.strip().casefold() == CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT
        for comment in after
    )


def _takeable_status(item: Item) -> bool:
    """Whether the Status of `item` lets the job take it: Ready or Planned, or In Progress while
    the record names a runner Job that no round reported, which is the Job that plans its own item
    (#2920)."""
    if item.status in {CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED}:
        return True
    return item.status == CONST_ROADMAP_STATUS_IN_PROGRESS and job_holds(item)


class _Judge:
    """Decides, for one item, whether the job may implement it. The checks run from the cheapest
    to the dearest: the record and the labels first, then git, then the pull request."""

    def __init__(
        self,
        store: RoadmapStore,
        *,
        repo: str,
        source: Path,
        remote_heads: str,
        planned: PlannedChanges,
        pull_status: Callable[[int], PullStatus],
    ) -> None:
        self._store = store
        self._source = source
        self._heads = remote_heads
        self._pushed = frozenset(remote_branches(remote_heads))
        self._planned = planned
        self._pull_status = pull_status
        self._bot = load_settings().service.github_app.bot_login

    def judge(self, item: Item) -> ImplementTarget | str:
        """The target for `item`, or the reason the job leaves it out."""
        texts = MESSAGES.roadmap
        if not _takeable_status(item):
            return texts.implement_left_not_ready.format(status=item.status or "none")
        if (owner := claimed_by(item)) is not None:
            return texts.item_left_claimed.format(owner=owner)
        route = self._route(item)
        if route is None:
            return self._not_taken(item)
        if item.author_association not in CONST_ROADMAP_TRUSTED_AUTHORS:
            return texts.implement_left_author.format(association=item.author_association)
        stopped = item.job_record.get(ImplementRecordKey.STOPPED)
        if stopped and not retry_asked(self._store.comments_on(item.number)):
            return texts.implement_left_stopped.format(stopped=stopped)
        retry = bool(stopped)
        if isinstance(route, _Planned):
            return self._planned_target(item, route.folder, retry=retry)
        why = self._branch_reason(item, route.branch) or self._pull_reason(route.pull)
        return why if why is not None else ImplementTarget(item, route.branch, route.pull, retry)

    def _route(self, item: Item) -> RecordedBranch | _Planned | None:
        """A Staged item keeps its branch while the branch is on `origin`, or while no plan is on
        the default branch. Else the plan on the default branch makes a Planned item."""
        recorded = recorded_branch(item)
        folder = self._planned.active.get(item.number)
        if recorded is not None and (folder is None or recorded.branch in self._pushed):
            return recorded
        return _Planned(folder) if folder is not None else None

    def _not_taken(self, item: Item) -> str:
        texts = MESSAGES.roadmap
        if (folder := self._planned.archived.get(item.number)) is not None:
            return texts.stage_left_archived.format(branch=self._planned.default, folder=folder)
        return texts.implement_left_not_staged.format(branch=self._planned.default)

    def _planned_target(self, item: Item, folder: str, *, retry: bool) -> ImplementTarget | str:
        """The new branch of a Planned item, or the reason the job leaves it out. The slug of the
        branch is the slug of the folder, whatever the title says."""
        texts = MESSAGES.roadmap
        type_ = commit_type(item.title)
        if type_ is None:
            return texts.stage_left_title_type
        branch = branch_name(item.number, type_, folder.partition("-")[2])
        if parse_branch(branch) is None:
            return texts.implement_left_planned_branch.format(folder=folder, branch=branch)
        held = issue_holder(self._source, item.number, self._heads, branch)
        if held is not None:
            return held
        try:
            tasks = tasks_on_default(self._source, self._planned, folder, operation=GIT_OPERATION)
        except GitOperationError as error:
            return texts.implement_left_no_tasks.format(
                folder=folder, branch=self._planned.default, reason=error
            )
        if all(task.ticked for group in parse_task_groups(tasks) for task in group.tasks):
            return texts.implement_left_all_ticked.format(folder=folder)
        return ImplementTarget(item, branch, None, retry)

    def _branch_reason(self, item: Item, branch: str) -> str | None:
        texts = MESSAGES.roadmap
        if self._bot is None:
            return texts.implement_left_no_app
        if branch not in self._pushed:
            return texts.implement_left_no_branch.format(branch=branch)
        held = local_holder(
            self._source, item.number, worktree_directory(item.number, self._source)
        )
        if held is not None:
            return held
        authors = branch_authors(self._source, branch, operation=GIT_OPERATION)
        other = next((author for author in authors if author != self._bot), None)
        if other is not None:
            return texts.implement_left_foreign.format(author=other, bot=self._bot)
        return stray_branch_reason(self._source, branch, self._heads)

    def _pull_reason(self, pull: int) -> str | None:
        try:
            status = self._pull_status(pull)
        except GitHubNotFoundError:
            return MESSAGES.roadmap.implement_left_pull.format(pull=pull)
        return (
            None if status.is_open_draft else MESSAGES.roadmap.implement_left_pull.format(pull=pull)
        )


def _left(item: Item, why: str) -> LeftOut:
    return LeftOut(item.number, why, item.title)


ImplementPlanPart = tuple[tuple[ImplementTarget, ...], tuple[LeftOut, ...]]


def _named(judge: _Judge, store: RoadmapStore, number: int) -> ImplementPlanPart:
    """The selection of `--item`: the item when the job may take it, else why not."""
    item = store.item(number)
    if item is None:
        return (), (LeftOut(number, MESSAGES.roadmap.item_left_not_item),)
    if item.state is not GitHubState.OPEN:
        return (), (_left(item, MESSAGES.roadmap.item_left_closed),)
    verdict = judge.judge(item)
    if isinstance(verdict, str):
        return (), (_left(item, verdict),)
    return (verdict,), ()


def plan_implement(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path | str,
    filters: StageFilter,
    item_number: int | None = None,
    limit: int = DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
    planned: PlannedChanges | None = None,
    why: bool = False,
    probe: int | None = None,
    remote_heads: str | None = None,
) -> ImplementPlan:
    """Plans a run without a write to git or to GitHub: up to `limit` Staged or Planned items that
    `filters` name, and the named items that the job leaves out. `source` is the clone of the
    repository. `planned` is the plans on the default branch when the caller read them already
    (the Service reads them once for a round, #2920). With `why`, the plan also lists the open
    items that the filter does not name. `probe` is the issue that `walk_named` judges also after
    the limit (#2911). `remote_heads` is the heads of `origin` when the caller read them already."""
    checkout = Path(source)
    inspect_checkout(checkout, repo)
    client = get_github_session().client
    judge = _Judge(
        store,
        repo=repo,
        source=checkout,
        remote_heads=read_remote_heads(checkout) if remote_heads is None else remote_heads,
        planned=(
            read_planned_changes(checkout, operation=GIT_OPERATION) if planned is None else planned
        ),
        pull_status=lambda pull: client.get_pull_status(repo, pull),
    )
    if item_number is not None:
        selected, left_out = _named(judge, store, item_number)
        return ImplementPlan(repo, selected, left_out)
    walked = walk_named(named_items(store, filters), judge.judge, limit, probe=probe)
    return ImplementPlan(
        repo,
        walked.taken,
        walked.left_out,
        unmatched=unmatched_items(store, filters) if why else (),
        beyond=walked.beyond,
    )


def dry_run_implement(
    repo: str, *, item: int | None = None, limit: int | None = None
) -> ImplementPlan:
    """The plan a dry run returns, having made no request: the requests and the git commands that a
    run makes, in order, and the writes that `--confirm` adds."""
    from devops_cli.roadmap.request_plan import implement_requests

    reads, writes = implement_requests(repo, item=item, limit=limit)
    return ImplementPlan(repo, dry_run=True, requests=reads, write_requests=writes)


def render_implement_plan(plan: ImplementPlan) -> str:
    """The plan as the report of the command: the items to implement, and those left out."""
    texts = MESSAGES.roadmap
    lines = [texts.implement_job_title.format(repo=plan.repo)]
    ready = [
        (texts.implement_job_planned_line if t.planned else texts.implement_job_ready_line).format(
            number=t.item.number,
            title=t.item.title,
            branch=t.branch,
            pull=t.pull,
            retry=texts.implement_job_retry_note if t.retry else "",
        )
        for t in plan.selected
    ]
    left = [
        texts.implement_job_left_line.format(number=x.number, title=x.title, reason=x.reason)
        for x in plan.left_out
    ]
    unmatched = [
        texts.implement_job_left_line.format(number=x.number, title=x.title, reason=x.reason)
        for x in plan.unmatched
    ]
    for heading, rows in (
        (texts.implement_job_heading_ready, ready),
        (texts.implement_job_heading_left, left),
        (texts.item_heading_unmatched, unmatched),
    ):
        if rows:
            lines += ["", heading, *rows]
    if not (ready or left):
        lines += ["", texts.implement_job_nothing]
    return "\n".join(lines)


__all__ = [
    "DEFAULT_IMPLEMENT_FILTERS",
    "GIT_OPERATION",
    "ImplementPlan",
    "ImplementTarget",
    "RecordedBranch",
    "dry_run_implement",
    "parse_implement_filters",
    "plan_implement",
    "recorded_branch",
    "render_implement_plan",
]
