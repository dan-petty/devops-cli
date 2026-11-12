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
families all apply. With no filter the job takes the Ready and Planned items, one effort pass at a
time: low effort first, then medium effort when no low-effort item is selectable (#3385). The
Service sets `status/planned` once the plan is on the default branch (`status_sync.py`, #2920). An
item that the filter names, and that the job leaves out, is in the plan with its reason: its Status
is neither Ready nor Planned (an item In Progress stays while its record names a runner Job that no
round reported: that Job plans its own item), an agent or a person claimed it (#2910), it is
neither Staged nor Planned, a step stopped it
and no person cleared the stop,
its author is not the owner, a member or a collaborator, its branch is gone from `origin` or holds
a commit by anyone but the App (a clean merge by a person does not count, #3392), a worktree holds
the issue, its plan fails the stage gates of `check_proposal` or the reader cannot read it (#3393;
a branch whose change the job archived already passed them, and a retry takes it, #3645),
its pull request is not an open draft or holds the label `plan/needs-fix` of a plan with an open
finding (the job takes the item again when the label is gone, #4477), or, for a Planned item, a
branch of `origin` holds the issue, its change is archived, it has no branch name, its change has
no `tasks.md` on the default branch, or every task of its change is ticked. A run takes at most `--limit` items,
the highest priority first. `--item` takes the one item it names and does not apply the filter or
the limit.

**Why.** `--why` adds to the plan the open items that the filter does not name, under their own
heading, each with the family it misses (`StageFilter.mismatch`). `devops roadmap explain` gives the
reason of one issue for this job and for the stage job (#2911).

**Retry.** A person clears a stop with the comment `implement: retry`, made after the comment
of the job that told of the stop. Only a comment of the owner, a member or a collaborator counts
(`retry_asked`). The row `implement` of the Service reads it for an item that it set Blocked
(`stop_clear.py`); this judge reads it for an item that holds Ready or Planned and a stop on record,
such as an item that a person set back by hand. Both list the comments of an issue again only
when its `updated_at` moved since the last listing in the process (`retry_asked_on`, #4854).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
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
from devops_cli.roadmap.commit_title import commit_type, unlisted_type_reason
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    change_root,
    files_at,
    read_change,
    specs_at,
    tree_files,
)
from devops_cli.roadmap.planned import (
    PlannedChanges,
    planned_changes_at,
    read_planned_changes,
    tasks_on_default,
)
from devops_cli.roadmap.refine.refine import inspect_checkout
from devops_cli.roadmap.stage.stage import (
    LeftOut,
    StageFilter,
    Walk,
    long_title_reason,
    named_items,
    parse_filters,
    unmatched_items,
    walk_named,
)
from devops_cli.roadmap.stage.stage_change import check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ImplementRecordKey,
    IssueComment,
    Item,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.roadmap.trust import is_approved, is_trusted

GIT_OPERATION: Final[str] = "roadmap.implement"

# What the job implements without a `--filter`: the Ready and Planned items, of any type, priority
# and value (#2906, #2920). The effort of an item picks its pass, from the setting
# `roadmap.implement.effort` (#3385).
DEFAULT_IMPLEMENT_FILTERS: Final[tuple[str, ...]] = ("status=ready", "status=planned")


def parse_implement_filters(options: Iterable[str]) -> StageFilter:
    """The filter that the `family=value` options give, or `DEFAULT_IMPLEMENT_FILTERS` with none.
    A bad option raises `ValidationError`, as the stage job's parser does."""
    return parse_filters(options, DEFAULT_IMPLEMENT_FILTERS)


def implement_efforts() -> tuple[str, ...]:
    """The effort values of the passes of the job, in order: the setting
    `roadmap.implement.effort` (#3385)."""
    return tuple(load_settings().roadmap.implement.effort)


def effort_filter(filters: StageFilter, efforts: Sequence[str]) -> StageFilter:
    """The filter that names the items of the effort set: `filters` with the family `effort` of
    the values of the set. A filter that names an effort already is returned as it is (#3385)."""
    if "effort" in filters.families:
        return filters
    return StageFilter({**filters.families, "effort": frozenset(f"effort/{v}" for v in efforts)})


def effort_passes(
    filters: StageFilter, efforts: Sequence[str]
) -> tuple[tuple[str, StageFilter], ...]:
    """The passes of the job, in order, each with its effort. Each value of the set makes one pass
    with the other families of `filters`. A filter that names an effort makes one pass, as it is
    given, and the pass is named by the values that the filter names (#3385)."""
    if "effort" in filters.families:
        named = sorted(label.removeprefix("effort/") for label in filters.families["effort"])
        return ((",".join(named), filters),)
    return tuple(
        (value, StageFilter({**filters.families, "effort": frozenset({f"effort/{value}"})}))
        for value in efforts
    )


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


class NeedsFix(NamedTuple):
    """An item that the job leaves out while its draft `pull` holds the label `plan/needs-fix`
    (#4477)."""

    item: Item
    pull: int


@dataclass(frozen=True)
class ImplementPlan:
    """What a run does: the items to implement, and the items the filter names that the job leaves
    out, each with its reason. `unmatched` holds the open items that the filter does not name, only
    when the plan was asked for them (`--why`). `beyond` holds the numbers of the items that pass
    every rule but come after the limit (`walk_named`). `effort` is the effort of the pass that
    takes the run, and `fallback` is true when that pass is a later value of the set (#3385).
    `needs_fix` holds the left-out items whose draft holds the label `plan/needs-fix`. A dry run
    holds the requests of a run and nothing else."""

    repo: str
    selected: tuple[ImplementTarget, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()
    unmatched: tuple[LeftOut, ...] = ()
    beyond: tuple[int, ...] = ()
    effort: str = ""
    fallback: bool = False
    needs_fix: tuple[NeedsFix, ...] = ()


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


_retry_reads: dict[str, tuple[datetime, bool]] = {}
"""The answer of `retry_asked` for each item whose comments this process listed, by the URL of its
issue, with the `updated_at` of the item at that listing. It holds one entry for each issue at
most (#4854)."""


def reset_retry_reads() -> None:
    """Forget the answers, as a new process has listed no comments (#4854)."""
    _retry_reads.clear()


def retry_asked_on(store: RoadmapStore, item: Item) -> bool:
    """Whether a trusted commenter asked for a retry on `item`, by `retry_asked`. A new comment
    moves the `updated_at` of an issue, so the comments are listed again only when the
    `updated_at` of `item` is not the one of the last listing that the process holds. A stop that
    nothing changed costs no request after the first round of the process (#4854)."""
    held = _retry_reads.get(item.url)
    if held is not None and item.updated_at is not None and held[0] == item.updated_at:
        return held[1]
    asked = retry_asked(store.comments_on(item.number))
    if item.updated_at is not None:
        _retry_reads[item.url] = (item.updated_at, asked)
    return asked


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
        self._default_rev = f"origin/{planned.default}"
        self._pull_status = pull_status
        self._bot = load_settings().service.github_app.bot_login
        self.needs_fix: dict[int, NeedsFix] = {}

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
        if not is_trusted(item):
            return texts.implement_left_author.format(
                author=item.author_login or texts.refine_author_unknown,
                association=item.author_association or texts.refine_author_unknown,
            )
        if not is_approved(item):
            return texts.implement_left_unjudged
        stopped = item.job_record.get(ImplementRecordKey.STOPPED)
        if stopped and not retry_asked_on(self._store, item):
            return texts.implement_left_stopped.format(stopped=stopped)
        retry = bool(stopped)
        if isinstance(route, _Planned):
            return self._planned_target(item, route.folder, retry=retry)
        why = (
            self._branch_reason(item, route.branch)
            or self._plan_reason(item, f"origin/{route.branch}")
            or self._pull_reason(item, route.pull)
        )
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
            return unlisted_type_reason(item.title) or texts.stage_left_title_type
        if (too_long := long_title_reason(item.title)) is not None:
            return too_long
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
        if (problem := self._plan_reason(item, self._default_rev)) is not None:
            return problem
        return ImplementTarget(item, branch, None, retry)

    @cached_property
    def _default_files(self) -> tuple[str, ...]:
        """The paths that the default branch tracks. The judge lists them once for each run, and
        not once for each item (#3430). A read that fails is not kept, so the next item tries
        again and gets its own reason."""
        return tuple(tree_files(self._source, self._default_rev, operation=GIT_OPERATION))

    @cached_property
    def _base_facts(self) -> tuple[frozenset[str], dict[str, tuple[str, ...]]]:
        """The capabilities and the requirement names of the base specs on the default branch. The
        judge reads them once for each run, and not once for each item (#3393)."""
        return specs_at(
            self._source, self._default_rev, operation=GIT_OPERATION, files=self._default_files
        )

    def _tree(self, rev: str) -> Sequence[str]:
        """The paths that commit `rev` tracks. The default branch is the one tree that every item
        shares. The branch of a Staged item is its own, so its listing is read for each item."""
        if rev == self._default_rev:
            return self._default_files
        return tree_files(self._source, rev, operation=GIT_OPERATION)

    def _plan_reason(self, item: Item, rev: str) -> str | None:
        """The first problem that the stage gates find in the plan of `item` at `rev`, or None when
        the plan passes (#3393). A plan that the reader or git cannot read gives its reason too, so
        the item is left out and the run goes on with the other items."""
        texts = MESSAGES.roadmap
        try:
            files = self._tree(rev)
            root, folder_problems = change_root(files, item.number)
            if root is None:
                if self._archived_at(rev, item.number):
                    return None
                return folder_problems[0]
            changed = [path for path in files if path.startswith(f"{root}/")]
            proposal = read_change(files_at(self._source, rev, changed, operation=GIT_OPERATION))
            known, requirements = self._base_facts
        except PlanReadError as error:
            return texts.plan_check_read.format(path=error.path, reason=error.reason)
        except GitOperationError as error:
            return texts.implement_left_plan_git.format(reason=error)
        problems = check_proposal(
            proposal, known, StagedTree(files), requirements=requirements, issue_body=item.body
        )
        return texts.implement_left_plan.format(problem=problems[0]) if problems else None

    def _archived_at(self, rev: str, issue: int) -> bool:
        """Whether commit `rev` holds the archived change of `issue` and no active one. The job
        archives a change after the stage gates passed it, so a branch with an archived change
        has nothing left to check, and a retry after a stop in the scoped checks takes it
        (#3645)."""
        held = planned_changes_at(self._source, rev, self._planned.default, operation=GIT_OPERATION)
        return issue in held.archived and issue not in held.active

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

    def _pull_reason(self, item: Item, pull: int) -> str | None:
        """Why the job leaves out the draft `pull` of `item`, or None when it takes it. A draft
        with the label `plan/needs-fix` holds a plan with an open finding: the job leaves it out
        until the label is gone, and keeps the item in `needs_fix`."""
        texts = MESSAGES.roadmap
        try:
            status = self._pull_status(pull)
        except GitHubNotFoundError:
            return texts.implement_left_pull.format(pull=pull)
        if not status.is_open_draft:
            return texts.implement_left_pull.format(pull=pull)
        if PLAN_NEEDS_FIX_LABEL in status.labels:
            self.needs_fix[item.number] = NeedsFix(item, pull)
            return texts.implement_left_needs_fix.format(pull=pull, label=PLAN_NEEDS_FIX_LABEL)
        return None


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


def _walk_passes(
    store: RoadmapStore,
    passes: Sequence[tuple[str, StageFilter]],
    judge: _Judge,
    limit: int,
    probe: int | None,
) -> tuple[Walk[ImplementTarget], str]:
    """Walk the passes in order, and return the walk of the first pass that takes an item, with the
    effort of that pass, or `""` when no pass takes one (#3385). Until that pass takes an item, each
    pass takes up to `limit` items. A pass after it takes none, and judges only `probe`: the probe
    gets the reason that the run takes an earlier effort first."""
    texts = MESSAGES.roadmap
    walked_all: list[LeftOut] = []
    taken: tuple[ImplementTarget, ...] = ()
    beyond: tuple[int, ...] = ()
    in_use = ""
    for effort, pass_filter in passes:
        named = named_items(store, pass_filter)
        if taken:
            walked = walk_named(named, judge.judge, 0, probe=probe)
            walked_all.extend(walked.left_out)
            walked_all.extend(
                _left(item, texts.implement_job_effort_later.format(effort=in_use))
                for item in named
                if item.number in walked.beyond
            )
            continue
        walked = walk_named(named, judge.judge, limit, probe=probe)
        walked_all.extend(walked.left_out)
        if walked.taken:
            taken, beyond, in_use = walked.taken, walked.beyond, effort
    return Walk(taken, tuple(walked_all), beyond), in_use


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
        return ImplementPlan(repo, selected, left_out, needs_fix=tuple(judge.needs_fix.values()))
    efforts = implement_efforts()
    walked, in_use = _walk_passes(store, effort_passes(filters, efforts), judge, limit, probe)
    explicit = "effort" in filters.families
    return ImplementPlan(
        repo,
        walked.taken,
        walked.left_out,
        unmatched=unmatched_items(store, effort_filter(filters, efforts)) if why else (),
        beyond=walked.beyond,
        effort=in_use,
        fallback=bool(in_use) and not explicit and in_use != efforts[0],
        needs_fix=tuple(judge.needs_fix.values()),
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
    if plan.effort:
        lines.append(texts.implement_job_effort_pass.format(effort=plan.effort))
    if plan.fallback:
        lines.append(texts.implement_job_effort_fallback)
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
    "NeedsFix",
    "RecordedBranch",
    "dry_run_implement",
    "parse_implement_filters",
    "plan_implement",
    "recorded_branch",
    "render_implement_plan",
    "reset_retry_reads",
    "retry_asked",
    "retry_asked_on",
]
