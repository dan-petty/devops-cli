"""`devops roadmap implement` as a job: which Staged items it takes (#2665).

The job takes each Staged item that a label filter names and runs the task groups of its change
(`implement_run`). This module selects and plans. It makes no write to git or to GitHub.

**Staged.** An item is Staged when the stage job's record holds its branch (`stage.branch`) and
its draft pull request (`stage.pr`), the branch is on `origin`, and the draft is open.

**Selection.** `--filter family=value` is repeatable over the label families `status`,
`priority`, `type`, `value` and `effort`: the values of one family are alternatives, and the
families all apply. With no filter the job takes the Ready P0 and P1 bugs of low effort. An item
that the filter names, and that the job leaves out, is in the plan with its reason: its Status
is not Ready, it is not Staged, a step stopped it and no person cleared the stop, its author is
not the owner, a member or a collaborator, its branch is gone from `origin` or holds a commit by
anyone but the App, a worktree holds the issue, or its pull request is not an open draft. A run
takes at most `--limit` items, the highest priority first. `--item` takes the one item it names
and does not apply the filter or the limit.

**Retry.** A person clears a stop with the comment `implement: retry`, made after the comment
of the job that told of the stop. Only a comment of the owner, a member or a collaborator counts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import GitHubNotFoundError
from devops_cli.git.worktree_add import (
    local_holder,
    read_remote_heads,
    remote_branches,
    worktree_directory,
)
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import branch_authors
from devops_cli.roadmap.refine import inspect_checkout
from devops_cli.roadmap.stage import LeftOut, StageFilter, parse_filters, priority_order
from devops_cli.roadmap.store import (
    GitHubState,
    ImplementRecordKey,
    IssueComment,
    Item,
    RoadmapStore,
    StageRecordKey,
)

GIT_OPERATION: Final[str] = "roadmap.implement"

# What the job implements without a `--filter`: the Ready P0 and P1 bugs of low effort.
DEFAULT_IMPLEMENT_FILTERS: Final[tuple[str, ...]] = (
    "status=ready",
    "priority=p0-critical",
    "priority=p1-high",
    "type=bug",
    "effort=low",
)


def parse_implement_filters(options: Iterable[str]) -> StageFilter:
    """The filter that the `family=value` options give, or `DEFAULT_IMPLEMENT_FILTERS` with none.
    A bad option raises `ValidationError`, as the stage job's parser does."""
    return parse_filters(options, DEFAULT_IMPLEMENT_FILTERS)


@dataclass(frozen=True)
class ImplementTarget:
    """A Staged item to implement: its staged branch, its draft pull request, and whether a
    person's retry comment clears a stop on its record before the first step."""

    item: Item
    branch: str
    pull: int
    retry: bool = False


@dataclass(frozen=True)
class ImplementPlan:
    """What a run does: the items to implement, and the items the filter names that the job leaves
    out, each with its reason. A dry run holds the requests of a run and nothing else."""

    repo: str
    selected: tuple[ImplementTarget, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()


def recorded_pull(item: Item) -> int | None:
    """The number of the draft pull request in the item's stage record, or None."""
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    return int(recorded) if recorded.isdigit() else None


def _retry_asked(comments: Sequence[IssueComment]) -> bool:
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
        pull_status: Callable[[int], PullStatus],
    ) -> None:
        self._store = store
        self._source = source
        self._pushed = frozenset(remote_branches(remote_heads))
        self._pull_status = pull_status
        self._bot = load_settings().service.github_app.bot_login

    def judge(self, item: Item) -> ImplementTarget | str:
        """The target for `item`, or the reason the job leaves it out."""
        texts = MESSAGES.roadmap
        record = item.job_record
        branch, pull = record.get(StageRecordKey.BRANCH), recorded_pull(item)
        if item.status != CONST_ROADMAP_STATUS_READY:
            return texts.implement_left_not_ready.format(status=item.status or "none")
        if not branch or pull is None:
            return texts.implement_left_not_staged
        if item.author_association not in CONST_ROADMAP_TRUSTED_AUTHORS:
            return texts.implement_left_author.format(association=item.author_association)
        stopped = record.get(ImplementRecordKey.STOPPED)
        if stopped and not _retry_asked(self._store.comments_on(item.number)):
            return texts.implement_left_stopped.format(stopped=stopped)
        why = self._branch_reason(item, branch) or self._pull_reason(pull)
        return why if why is not None else ImplementTarget(item, branch, pull, bool(stopped))

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
        return None

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
        return (), (LeftOut(number, MESSAGES.roadmap.implement_left_not_item),)
    if item.state is not GitHubState.OPEN:
        return (), (_left(item, MESSAGES.roadmap.implement_left_closed),)
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
) -> ImplementPlan:
    """Plans a run without a write to git or to GitHub: up to `limit` Staged items that `filters`
    name, and the named items that the job leaves out. `source` is the clone of the repository."""
    checkout = Path(source)
    inspect_checkout(checkout, repo)
    client = get_github_session().client
    judge = _Judge(
        store,
        repo=repo,
        source=checkout,
        remote_heads=read_remote_heads(checkout),
        pull_status=lambda pull: client.get_pull_status(repo, pull),
    )
    if item_number is not None:
        selected, left_out = _named(judge, store, item_number)
        return ImplementPlan(repo, selected, left_out)
    named = sorted(
        (
            item
            for item in store.items()
            if item.state is GitHubState.OPEN and filters.matches(item)
        ),
        key=priority_order,
    )
    selected_list: list[ImplementTarget] = []
    left_list: list[LeftOut] = []
    for item in named:
        if len(selected_list) >= limit:
            break
        verdict = judge.judge(item)
        if isinstance(verdict, str):
            left_list.append(_left(item, verdict))
        else:
            selected_list.append(verdict)
    return ImplementPlan(repo, tuple(selected_list), tuple(left_list))


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
        texts.implement_job_ready_line.format(
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
    for heading, rows in (
        (texts.implement_job_heading_ready, ready),
        (texts.implement_job_heading_left, left),
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
    "dry_run_implement",
    "parse_implement_filters",
    "plan_implement",
    "recorded_pull",
    "render_implement_plan",
]
