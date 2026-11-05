"""`devops roadmap stage`: a Ready item becomes Staged (#2654).

The job turns each item that a label filter names into a branch `<type>/<issue>-<slug>` at the
fetched default branch, with the OpenSpec change `openspec/changes/<issue>-<slug>/` written from
the refined body, one commit by the identity of the session, and a draft pull request whose title
is `docs(openspec): plan #<issue> <summary>` (a plan is no fix: #2714) and whose body starts with
`Plans #<issue>`. It never changes the item's Status. The staged branch and the draft are the
record. The job does not mark the draft ready: the row `stage_ready` of the Service does, when the
checks of the draft have passed (`stage_ready`).

**Selection.** `--filter family=value` is repeatable over the label families `status`,
`priority`, `type`, `value` and `effort`. The values of one family are alternatives, and the
families all apply. With no `--filter` the job takes the filter of the setting
`roadmap.stage.filter`, by default every Ready item. It leaves out an item
that is not Ready, whatever the filter says: a `status` filter can only narrow the Ready items.
It also leaves out an item that an agent or a person claimed with an `owner/*` label (#2910), an item with the label `needs-split`, a tracker (sub-issues or the label `type/epic`), an item whose author has no write access
(the model reads the body), an item whose "Dependencies" section names an open issue, a held item
(`worktree_add.issue_holder`, which also counts a stray local branch of the new name with a commit that `origin` lacks), an item whose plan is already on the default branch or whose
change is archived there (`planned.read_planned_changes`, one read of the tree for the round), an
item whose title gives no branch name or whose summary is over `SUMMARY_MAX_CHARS` units (#3369), an item whose text looks like a secret, an item whose last plan or write failed less than
`roadmap.stage.retry_hours` hours ago (its record holds `stage.failed_at` and
`stage.failed_error`, #3493), and an item whose
record holds `stage.needs_split` made with the file cap of now (`stage.file_cap`): a stop under
another measure does not count. A run takes at most `--limit`
items, highest priority first. `--item` takes the one item it names when that item is open and
Ready.

**Plan.** For each item the job plans a `StageProposal` with an agent that reads the repository
before it answers (`ai.for_task("analysis")`, prompt `roadmap_stage_change.md`, and the read-only
tools of `stage_tools`, with the prompt `roadmap_stage_tools.md`, #3037). A plan run has a budget
of tool calls and requests (`stage_toolbox`), and its tools end when its messages fill the context
window; a run that passes the budget fails the item. Without a
`ToolboxModel` the planner makes the one call with no tool, as the tests and the option
`--no-toolbox` of the golden-set run do. The job measures each task group
(`stage_change.measure_groups`) and asks once for a split of the groups over `--step-tokens`. A group costs what its step reads: the
files that its tasks name, each packed to at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens
(`step_files`). A group still over the budget stops the item (`OverBudget`). The job validates the
change with `openspec validate --strict` in a scratch directory when the binary is on `PATH`; a
failure goes back to the model once, and a second one stops the item. A reply the rules refuse
(`check_proposal`) takes the same one return. A group that changes no file, has a blank text, or
breaks the rules of its kind (`GroupKind`: a `behavior` group has a test and changes a path under
`src/`, and an `other` group has no test and one of `verify` and `process`) fails the schema of
the reply, and `chat_structured` sends it back once (`_REPLY_RETURNS`). A reply that names a path
that is no file of the staged commit, and that no group up to its own creates (`stage_paths`), is
sent back in the same way: the problem lists the files with the same name, and a second reply with
a missing path stops the item, so no draft opens. The groups of a split are checked in the same
way. After the checks, the model review of the plan (`stage_verify`, #3153) reads the issue, the
plan and the files that the plan cites with the client of the task `verification`. A finding of
the type `missing_path`, `false_premise` or `ignores_existing_code` that quotes its evidence sends
the plan back to the planner once. A finding of such a type, of `spec_delta_wrong`, or one that
reports a placeholder is open: the job keeps the draft with the label `plan/needs-fix` and puts
the finding first in the comment (#3264). Every other finding goes into the comment of the item.
The review never merges and never marks a draft ready. `plan_item` plans one item with a given client
and checkout: the golden set of the job runs
it on each case (`stage_eval_run`, #3028). The plan writes nothing to git or to GitHub. A model call
that fails skips its item; rejected credentials stop the run.

**Why.** `--why` adds to the plan the open items that the filter does not name, under their own
heading, each with the family it misses (`StageFilter.mismatch`). They are not "left out": no rule
of the job judged them. `devops roadmap explain` gives the reason of one issue (#2911).
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import Any, Final, NamedTuple, Protocol

from pydantic import BaseModel

from devops_cli.ai.client import LLMClient, get_llm_client
from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    StructuredOutputValidationError,
)
from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.commands import BIN_OPENSPEC
from devops_cli.config.constants import (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_PRIORITY_VALUES,
    CONST_ROADMAP_STAGE_BODY_MAX_TOKENS,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubOperationError,
    GitHubUnauthenticatedError,
    RoadmapStageError,
    ServiceStoppingError,
    ToolExecutionError,
)
from devops_cli.git.branch_form import branch_name
from devops_cli.git.worktree_add import (
    add_worktree,
    issue_holder,
    read_remote_heads,
    remote_branches,
)
from devops_cli.github.client import CreatedPull
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool, isolated_openspec
from devops_cli.roadmap.agent_run import RunTrace
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import branch_authors, default_branch, git
from devops_cli.roadmap.commit_title import commit_summary, commit_type
from devops_cli.roadmap.digest_clears import has_digest_clear
from devops_cli.roadmap.planned import PlannedChanges, planned_count, read_planned_changes
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length, title_problems
from devops_cli.roadmap.pull_labels import add_pull_labels, read_title_labels, remove_pull_labels
from devops_cli.roadmap.refine import body_dependencies, collect_context, inspect_checkout
from devops_cli.roadmap.refine_investigation import analysis_window
from devops_cli.roadmap.return_item import apply_return, plan_return
from devops_cli.roadmap.stage_change import (
    MeasuredGroup,
    StageProposal,
    check_proposal,
    closing_keyword_in,
    measure_groups,
    pull_request_body,
    render_change,
    safe_text,
    staging_title,
    write_change_files,
)
from devops_cli.roadmap.stage_criteria import criterion_problems
from devops_cli.roadmap.stage_filter import split_filter_entry
from devops_cli.roadmap.stage_form import form_problems, record_search_evidence, search_problems
from devops_cli.roadmap.stage_github import StageGitHub
from devops_cli.roadmap.stage_overlap import (
    Overlap,
    PullReads,
    cited_instruments,
    grep_at,
    metric_senders,
    open_pulls,
    overlaps,
    session_pull_reads,
)
from devops_cli.roadmap.stage_paths import StagedTree, path_problems
from devops_cli.roadmap.stage_probe import probe_premise
from devops_cli.roadmap.stage_specs import BaseSpec, read_base_specs
from devops_cli.roadmap.stage_split import ask_split
from devops_cli.roadmap.stage_toolbox import ToolboxClient, ToolboxModel
from devops_cli.roadmap.stage_validate import validate_change
from devops_cli.roadmap.stage_verify import (
    PLAN_NEEDS_FIX_LABEL,
    Finding,
    VerificationInput,
    findings_section,
    open_findings,
    open_findings_section,
    return_problem,
    returning,
    verify,
)
from devops_cli.roadmap.step_files import code_spans
from devops_cli.roadmap.store import GitHubState, Item, RoadmapStore, StageRecordKey
from devops_cli.security.sanitizer import mask_secrets, redact_text
from devops_cli.telemetry.instruments import ROADMAP_STAGE_TOTAL, emit

logger = logging.getLogger(__name__)

# ── The filter ────────────────────────────────────────────────────────────────

_NEEDS_SPLIT_LABEL: Final[str] = "needs-split"
# The words of a title's summary that make the slug of the branch.
_SLUG_WORDS: Final[int] = 6


@dataclass(frozen=True)
class StageFilter:
    """The labels an item must hold: for each family, one of the labels of its alternatives."""

    families: Mapping[str, frozenset[str]]

    def _missed(self, item: Item) -> tuple[str, frozenset[str]] | None:
        """The first family, in the order of the filter, of which `item` holds no label."""
        return next(
            (
                (family, wanted)
                for family, wanted in self.families.items()
                if wanted.isdisjoint(item.labels)
            ),
            None,
        )

    def matches(self, item: Item) -> bool:
        """Whether `item` holds a label of every family of the filter."""
        return self._missed(item) is None

    def mismatch(self, item: Item) -> str | None:
        """The reason the filter does not name `item`: the family it misses, the values the filter
        takes and the value the item has. None when the filter names the item (#2911)."""
        missed = self._missed(item)
        if missed is None:
            return None
        family, wanted = missed
        prefix = f"{family}/"
        have = [label.removeprefix(prefix) for label in item.labels if label.startswith(prefix)]
        return MESSAGES.roadmap.item_left_filter.format(
            family=family,
            wanted=" or ".join(sorted(label.removeprefix(prefix) for label in wanted)),
            have=", ".join(have) or MESSAGES.roadmap.stage_status_none,
        )


def parse_filters(options: Iterable[str], defaults: Sequence[str] | None = None) -> StageFilter:
    """The filter that the `family=value` options give. With none, the `defaults` when the caller
    gives them (the job that implements the items gives its own), else the filter of the setting
    `roadmap.stage.filter`.

    A value is the label's name after the family: `priority=p1-high` is the label
    `priority/p1-high`. A family outside the label families, and an option that is not
    `family=value`, raise `ValidationError`.
    """
    families: dict[str, set[str]] = {}
    wanted = tuple(options) or tuple(
        load_settings().roadmap.stage.filter if defaults is None else defaults
    )
    for option in wanted:
        family, value = split_filter_entry(option)
        families.setdefault(family, set()).add(f"{family}/{value}")
    return StageFilter({family: frozenset(labels) for family, labels in families.items()})


# ── The branch of an item ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageTarget:
    """An item to stage with the type and the slug of its branch."""

    item: Item
    type_: str
    slug: str

    @property
    def change(self) -> str:
        """The name of the change folder: `<issue>-<slug>`."""
        return f"{self.item.number}-{self.slug}"

    @property
    def branch(self) -> str:
        """The branch: `<type>/<issue>-<slug>`."""
        return branch_name(self.item.number, self.type_, self.slug)


def _slug_of(title: str) -> str:
    """The slug of `title`'s summary: its first words of ASCII letters and digits, lower case,
    joined by hyphens. It is empty when the summary holds no such word."""
    summary = title.partition(":")[2].lower()
    words = "".join(ch if ch.isascii() and ch.isalnum() else " " for ch in summary).split()
    return "-".join(words[:_SLUG_WORDS])


# ── The selection ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LeftOut:
    """An issue the job did not stage, and why. `title` is empty for an issue that is no item."""

    number: int
    reason: str
    title: str = ""


@dataclass(frozen=True)
class Walk[T]:
    """What a walk over the items that a filter names found: the items taken, the items left out
    with their reasons, and the numbers of the items that pass every rule but come after the
    limit."""

    taken: tuple[T, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    beyond: tuple[int, ...] = ()


def walk_named[T](
    named: Iterable[Item],
    judge: Callable[[Item], T | str],
    limit: int,
    *,
    probe: int | None = None,
) -> Walk[T]:
    """Judge `named`, in order, until `limit` items are taken; both jobs select this way. A judge
    gives the target of an item it takes, or the reason it leaves the item out. After the limit the
    walk judges no item, except the item numbered `probe` (`devops roadmap explain`, #2911): that
    item is left out with its reason, or is `beyond` when it passes every rule."""
    taken: list[T] = []
    left_out: list[LeftOut] = []
    beyond: list[int] = []
    for item in named:
        full = len(taken) >= limit
        if full and item.number != probe:
            if probe is None:
                break
            continue
        verdict = judge(item)
        if isinstance(verdict, str):
            left_out.append(LeftOut(item.number, verdict, item.title))
        elif full:
            beyond.append(item.number)
        else:
            taken.append(verdict)
    return Walk(tuple(taken), tuple(left_out), tuple(beyond))


def _open_items(store: RoadmapStore) -> list[Item]:
    """The open items, highest priority first."""
    return sorted(
        (item for item in store.items() if item.state is GitHubState.OPEN), key=priority_order
    )


def named_items(store: RoadmapStore, filters: StageFilter) -> list[Item]:
    """The open items that `filters` names, highest priority first."""
    return [item for item in _open_items(store) if filters.matches(item)]


@dataclass(frozen=True)
class PlannedQueue:
    """The Planned items that wait for a delivery (#3487): how many there are, and the count at
    which the job plans no new item."""

    count: int
    limit: int

    @property
    def full(self) -> bool:
        return self.count >= self.limit


def unmatched_items(store: RoadmapStore, filters: StageFilter) -> tuple[LeftOut, ...]:
    """The open items that `filters` does not name, each with the family it misses (`--why`)."""
    return tuple(
        LeftOut(item.number, why, item.title)
        for item in _open_items(store)
        if (why := filters.mismatch(item)) is not None
    )


@dataclass(frozen=True)
class StageSelection:
    """The items one run stages, and those it leaves out with their reasons. `beyond` holds the
    numbers of the items that pass every rule but come after the limit (see `walk_named`)."""

    selected: tuple[StageTarget, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    beyond: tuple[int, ...] = ()


class _Judge:
    """Decides, for one item, whether the job may stage it. The checks run from the cheapest to
    the dearest: the labels and the text first, then the issues it depends on, then the git
    holders."""

    def __init__(
        self,
        store: RoadmapStore,
        holder_of: Callable[[int, str], str | None],
        planned: PlannedChanges,
        queue: PlannedQueue,
        now: datetime,
        retry: timedelta,
    ) -> None:
        self._store = store
        self._holder_of = holder_of
        self._planned = planned
        self._queue = queue
        self._now = now
        self._retry = retry

    def reason(self, item: Item, *, named: bool) -> str | None:
        """Why the job leaves `item` out, or None when it may stage it. A person who names the
        item (`--item`) overrules the record of an earlier split."""
        checks = [
            self._not_ready,
            self._claimed,
            self._needs_split,
            self._tracker,
            self._author,
            self._title,
            self._dependency,
            self._planned_on_default,
            self._held,
            self._secret,
        ]
        if not named:
            checks += [self._recorded_split, self._failed_lately, self._queue_full]
        return next((why for check in checks if (why := check(item)) is not None), None)

    def _not_ready(self, item: Item) -> str | None:
        if item.status == CONST_ROADMAP_STATUS_READY:
            return None
        texts = MESSAGES.roadmap
        return texts.stage_left_not_ready.format(status=item.status or texts.stage_status_none)

    def _claimed(self, item: Item) -> str | None:
        """An agent or a person holds the item (#2910): the Service takes no claimed item."""
        owner = claimed_by(item)
        return None if owner is None else MESSAGES.roadmap.item_left_claimed.format(owner=owner)

    def _needs_split(self, item: Item) -> str | None:
        return (
            MESSAGES.roadmap.stage_left_needs_split if _NEEDS_SPLIT_LABEL in item.labels else None
        )

    def _tracker(self, item: Item) -> str | None:
        """A tracker has sub-issues or the label `type/epic`: its sub-issues deliver it, so no
        plan of its own makes sense (#1985)."""
        is_tracker = item.sub_issues > 0 or CONST_ROADMAP_EPIC_LABEL in item.labels
        return MESSAGES.roadmap.stage_left_tracker if is_tracker else None

    def _author(self, item: Item) -> str | None:
        if item.author_association in CONST_ROADMAP_TRUSTED_AUTHORS:
            return None
        texts = MESSAGES.roadmap
        return texts.stage_left_author.format(
            association=item.author_association or texts.refine_author_unknown
        )

    def _title(self, item: Item) -> str | None:
        texts = MESSAGES.roadmap
        if commit_type(item.title) is None:
            return texts.stage_left_title_type
        if (too_long := long_title_reason(item.title)) is not None:
            return too_long
        return None if _slug_of(item.title) else texts.stage_left_title_slug

    def _dependency(self, item: Item) -> str | None:
        open_issues = [
            f"#{number}"
            for number in body_dependencies(item.body)
            if (found := self._store.item(number)) is not None and found.state is GitHubState.OPEN
        ]
        if not open_issues:
            return None
        return MESSAGES.roadmap.stage_left_dependency.format(issues=", ".join(open_issues))

    def _planned_on_default(self, item: Item) -> str | None:
        """The plan is on the default branch, or its change is archived there (#2714). The folder
        matches by the issue number, so a slug that differs from the title does not matter."""
        texts = MESSAGES.roadmap
        if (folder := self._planned.active.get(item.number)) is not None:
            return texts.stage_left_planned.format(branch=self._planned.default, folder=folder)
        if (folder := self._planned.archived.get(item.number)) is not None:
            return texts.stage_left_archived.format(branch=self._planned.default, folder=folder)
        return None

    def _held(self, item: Item) -> str | None:
        return self._holder_of(item.number, _target_of(item).branch)

    def _secret(self, item: Item) -> str | None:
        looks_secret = any(redact_text(text) != text for text in (item.title, item.body))
        return MESSAGES.roadmap.stage_left_secret if looks_secret else None

    def _queue_full(self, item: Item) -> str | None:
        """The queue of Planned items is at its limit (#3487): the job plans no new item, except one
        of the highest priority. `--item` overrules it, as it overrules a recorded split."""
        if not self._queue.full or item.priority == CONST_ROADMAP_CRITICAL_PRIORITY:
            return None
        return MESSAGES.roadmap.stage_left_planned_limit.format(
            count=self._queue.count,
            limit=self._queue.limit,
            priority=CONST_ROADMAP_CRITICAL_PRIORITY,
        )

    def _failed_lately(self, item: Item) -> str | None:
        """The last plan or write of the item failed less than the retry delay ago (#3493). The
        job takes the other items and takes this one again when the delay has passed. A record
        whose time is no time holds the item for no time."""
        recorded = item.job_record.get(StageRecordKey.FAILED_AT)
        if not recorded:
            return None
        try:
            failed_at = datetime.fromisoformat(recorded)
        except ValueError:
            logger.warning("The failure time recorded on #%d is not a time.", item.number)
            return None
        until = failed_at + self._retry
        if until <= self._now:
            return None
        return MESSAGES.roadmap.stage_left_failed_lately.format(
            error=item.job_record.get(StageRecordKey.FAILED_ERROR) or "unknown",
            until=until.astimezone(UTC).strftime("%Y-%m-%d %H:%M"),
        )

    def _recorded_split(self, item: Item) -> str | None:
        detail = item.job_record.get(StageRecordKey.NEEDS_SPLIT)
        cap = item.job_record.get(StageRecordKey.FILE_CAP)
        if not detail or cap != str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS):
            return None
        return MESSAGES.roadmap.stage_left_recorded_split.format(detail=detail, number=item.number)


def long_title_reason(title: str) -> str | None:
    """The reason a job leaves out an item whose `title` has a summary over `SUMMARY_MAX_CHARS`
    (#3486), or None. The stage job and the implement job both judge a title with it, before they
    make a model request; `devops roadmap retitle` shortens such a title."""
    length = summary_length(commit_summary(title))
    if length <= SUMMARY_MAX_CHARS:
        return None
    return MESSAGES.roadmap.stage_left_title_long.format(length=length, limit=SUMMARY_MAX_CHARS)


def _target_of(item: Item) -> StageTarget:
    """The target of an item whose title gives a branch name (`_Judge._title`)."""
    return StageTarget(item, commit_type(item.title) or "", _slug_of(item.title))


def priority_order(item: Item) -> tuple[int, bool, int]:
    """The sort key of an item: highest priority first, then an item with no digest clear before
    an item with one (#3481), then the lowest number. Priority comes first, so a retried item of a
    higher priority still goes before a new item of a lower priority."""
    values = CONST_ROADMAP_PRIORITY_VALUES
    rank = values.index(item.priority) if item.priority in values else len(values)
    return rank, has_digest_clear(item), item.number


def _named_item(judge: _Judge, store: RoadmapStore, number: int) -> StageSelection:
    """The selection of `--item`: the item when it is open and Ready, else why not."""
    texts = MESSAGES.roadmap
    item = store.item(number)
    why: str | None
    if item is None:
        why = texts.item_left_not_item
    elif item.state is not GitHubState.OPEN:
        why = texts.item_left_closed
    else:
        why = judge.reason(item, named=True)
    if item is not None and why is None:
        return StageSelection(selected=(_target_of(item),))
    return StageSelection(left_out=(LeftOut(number, why or "", item.title if item else ""),))


def select_stageable(
    store: RoadmapStore,
    *,
    filters: StageFilter,
    holder_of: Callable[[int, str], str | None],
    planned: PlannedChanges,
    limit: int,
    planned_limit: int,
    item_number: int | None = None,
    probe: int | None = None,
    now: datetime | None = None,
) -> StageSelection:
    """The items to stage, up to `limit`, and those the filter names that the job leaves out.

    `holder_of` tells who holds an issue and its new `branch` (`worktree_add.issue_holder`), or None. `planned` holds
    the change folders of the default branch (#2714). With `item_number` the filter and the limit
    do not apply. `probe` is the issue that `walk_named` judges also after the limit. With
    `planned_limit` Planned items or more, the job takes only an item of the highest priority
    (#3487). An item that failed less than `roadmap.stage.retry_hours` hours before `now` waits
    (#3493).
    """
    opened = _open_items(store)
    retry = timedelta(hours=load_settings().roadmap.stage.retry_hours)
    judge = _Judge(
        store,
        holder_of,
        planned,
        PlannedQueue(planned_count(opened), planned_limit),
        now or datetime.now(UTC),
        retry,
    )
    if item_number is not None:
        return _named_item(judge, store, item_number)

    def verdict(item: Item) -> StageTarget | str:
        why = judge.reason(item, named=False)
        return _target_of(item) if why is None else why

    named = [item for item in opened if filters.matches(item)]
    walked = walk_named(named, verdict, limit, probe=probe)
    return StageSelection(walked.taken, walked.left_out, walked.beyond)


# ── The plan of one item ──────────────────────────────────────────────────────

_CHANGE_TASK: Final[str] = "roadmap_stage_change.md"
# The model window is shared by the reply, the body of the item and the repository context. A cap
# is the smaller of its fixed size and this share of the window: a larger window gives no larger
# cap, so the first plan request leaves room below the limit of the tools (#3477).
_WINDOW_SHARE_CONTEXT: Final[int] = 2
_WINDOW_SHARE_BODY: Final[int] = 4
# A reply that fails its schema goes back to the model once, with the violations; a second one
# stops the item.
_REPLY_RETURNS: Final[int] = 1
# The model calls of one item at most: the plan, one return of a refused reply, and one split.
CALLS_PER_ITEM_MAX: Final[int] = 3


@dataclass(frozen=True)
class StagedChange:
    """A change ready to write: the target, the title and the body of its draft pull request, the
    files by path from the repository root, the measure of each task group, whether
    `openspec validate` ran on it (it does not without the binary), the budget of the run, and
    what the plan runs of the toolbox did (#3037). The trace is empty for an item planned with one
    call. `proposal` is the plan that the files render, and `findings` are the points that the
    model review of the plan raised and that returned no plan (#3153): the comment lists them.
    `open_findings` are the findings that keep the draft with the label `plan/needs-fix`
    (#3264); they are a part of `findings`."""

    target: StageTarget
    title: str
    body: str
    files: Mapping[str, str]
    groups: tuple[MeasuredGroup, ...]
    validated: bool
    budget: int
    proposal: StageProposal
    trace: RunTrace = field(default_factory=RunTrace)
    findings: tuple[Finding, ...] = ()
    open_findings: tuple[Finding, ...] = ()
    pulls_requests: int = 0


@dataclass(frozen=True)
class OverBudget:
    """An item with a task group over the budget after the split: a person decides."""

    target: StageTarget
    groups: tuple[MeasuredGroup, ...]
    budget: int

    @property
    def worst(self) -> MeasuredGroup:
        """The first group over the budget."""
        return next(group for group in self.groups if group.tokens > self.budget)


@dataclass(frozen=True)
class PremiseFailed:
    """An item whose premise is false: the model's evidence, on one line. The job returns the item
    to New and plans no change (#3011)."""

    target: StageTarget
    evidence: str


@dataclass(frozen=True)
class StageFailure:
    """An item the job could not plan or write: the class of the error and why, never the model's
    text. `item` is the item itself, when the job read it, so that the job records the failure in
    the job record of the item (#3493)."""

    number: int
    title: str
    error: str
    reason: str = ""
    item: Item | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class Removal:
    """The staged branch of a closed item that only the session's identity wrote to: the job
    closes its draft pull request and deletes it, or, when `gone`, only clears the record."""

    item: Item
    branch: str
    pull: int | None
    gone: bool = False

    @property
    def number(self) -> int:
        """The number of the closed item."""
        return self.item.number


@dataclass(frozen=True)
class KeptBranch:
    """The staged branch of a closed item that the job keeps, and why."""

    number: int
    branch: str
    reason: str


@dataclass(frozen=True)
class StagePlan:
    """What a run does: the changes ready to write, the items stopped on a group over the budget,
    the items that failed, and the issues left out with their reasons."""

    repo: str
    sha: str = ""
    budget: int = 0
    ready: tuple[StagedChange, ...] = ()
    over_budget: tuple[OverBudget, ...] = ()
    returned: tuple[PremiseFailed, ...] = ()
    failed: tuple[StageFailure, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    removals: tuple[Removal, ...] = ()
    kept: tuple[KeptBranch, ...] = ()
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()
    planned: PlannedChanges | None = None
    unmatched: tuple[LeftOut, ...] = ()


def _stage_error(message: str, target: StageTarget) -> RoadmapStageError:
    return RoadmapStageError(message, failed_items=[target.item.number])


class _Refused(NamedTuple):
    """A reply that fails a check: the problem that goes back to the model, and the reply that has
    it (after a split, the reply with the split groups)."""

    problem: str
    reply: StageProposal


class StageClient(Protocol):
    """What the stage job needs of `LLMClient`: one structured call."""

    def chat_structured[M: BaseModel](
        self, system: str, prompt: str, schema: type[M], *, max_retries: int
    ) -> M: ...


class _Planner:
    """Plans the change of each item with one model client, one checkout and one budget."""

    def __init__(
        self,
        *,
        client: StageClient,
        source: Path,
        sha: str,
        specs: Mapping[str, BaseSpec],
        tree: StagedTree,
        budget: int,
        window: int,
        tool: OpenSpecTool | None,
        toolbox: ToolboxClient | None = None,
        verifier: StageClient | None = None,
        pull_reads: Callable[[], PullReads] | None = None,
        pull_repo: str = "",
        grep: Callable[[str], Sequence[str]] | None = None,
    ) -> None:
        self._client = client
        self._toolbox = toolbox
        self._verifier = verifier
        self._source = source
        self._sha = sha
        self._specs = specs
        self._known = frozenset(specs)
        self._requirements = {name: spec.requirements for name, spec in specs.items()}
        self._tree = tree
        self._budget = budget
        self._window = window
        self._tool = tool
        self._pull_reads = pull_reads
        self._pull_repo = pull_repo
        self._grep = grep
        self._today: date = datetime.now(UTC).date()
        # Whether the run reads the capabilities with `read_spec`: then the request names them. A
        # client that wraps the toolbox client (the recorder of the golden set) forwards the flag.
        self._specs_on_demand = bool(getattr(client, "reads_specs", False))
        # Whether the model split the groups of the item in hand: it does so once for each item.
        self._split_asked = False
        # The lines of the premise probe of the item in hand, for the quote rule of `feasibility`.
        self._probe_lines: tuple[str, ...] = ()
        # The open pull requests that overlap the paths of the item in hand, and the files that
        # hold a cited metric (#3252). The gate reads the overlaps.
        self._overlaps: tuple[Overlap, ...] = ()
        self._pull_requests = 0
        self._metric_senders: dict[str, tuple[str, ...]] = {}

    def plan(self, target: StageTarget) -> StagedChange | OverBudget | PremiseFailed:
        """The change of `target`, the group that stops it, or the evidence that its premise is
        false. A reply the checks refuse goes back to the model once, with the problem. The model
        splits the groups at most once. With a verifier, the model review of the plan (#3153)
        follows the checks and may return the plan once more. So an item costs three planner calls
        at most without a verifier, four with one, and two calls of the verifier. A reply that
        sets `premise_failed` ends the item at once, with no review."""
        self._split_asked = False
        if self._toolbox is not None:
            self._toolbox.traces.clear()
        request = self._request(target)
        outcome = self._gated(target, request)
        verifier = self._verifier
        if isinstance(outcome, StagedChange) and verifier is not None:
            outcome = self._verified(target, request, outcome, verifier)
        if isinstance(outcome, StagedChange) and self._toolbox is not None:
            return replace(outcome, trace=RunTrace.combined(self._toolbox.traces))
        return outcome

    def _gated(
        self, target: StageTarget, request: Mapping[str, Any]
    ) -> StagedChange | OverBudget | PremiseFailed:
        """The change that passes the checks, with one return of a refused reply, or the evidence
        that the premise is false."""
        proposal = self._ask(StageProposal, _CHANGE_TASK, request)
        if proposal.premise_failed is not None:
            return self._premise_failed(target, proposal.premise_failed)
        outcome = self._settle(target, proposal)
        if isinstance(outcome, _Refused):
            again = {
                **request,
                "previous": outcome.reply.model_dump(),
                "problem": outcome.problem,
            }
            proposal = self._ask(StageProposal, _CHANGE_TASK, again)
            if proposal.premise_failed is not None:
                return self._premise_failed(target, proposal.premise_failed)
            outcome = self._settle(target, proposal)
        if isinstance(outcome, _Refused):
            message = MESSAGES.roadmap.stage_invalid.format(problem=outcome.problem)
            raise _stage_error(message, target)
        return outcome

    @staticmethod
    def _premise_failed(target: StageTarget, evidence: str) -> PremiseFailed:
        """The outcome for a reply that says the premise is false: the evidence on one line, a
        secret masked, with no handle or link that pings anyone."""
        return PremiseFailed(target, safe_text(mask_secrets(evidence)))

    def _verified(
        self,
        target: StageTarget,
        request: Mapping[str, Any],
        change: StagedChange,
        verifier: StageClient,
    ) -> StagedChange | OverBudget | PremiseFailed:
        """The change after the model review. A finding of a type that returns the plan, with a
        quote that is in the input, sends the plan back to the planner once: the revised plan
        passes the checks and the review again, a refused revision stops the item, and a reply
        that sets `premise_failed` returns the item. Every
        other finding, and every finding of the revised plan, stays on the change for the
        comment. An open finding keeps the draft with `plan/needs-fix` (#3264)."""
        findings, returned, _ = self._review(target, change, verifier)
        if returned:
            again = {
                **request,
                "previous": change.proposal.model_dump(),
                "problem": return_problem(returned),
            }
            revised = self._ask(StageProposal, _CHANGE_TASK, again)
            if revised.premise_failed is not None:
                return self._premise_failed(target, revised.premise_failed)
            outcome = self._settle(target, revised)
            if isinstance(outcome, _Refused):
                message = MESSAGES.roadmap.stage_invalid.format(problem=outcome.problem)
                raise _stage_error(message, target)
            if isinstance(outcome, OverBudget):
                return outcome
            change = outcome
            findings, _, open_ = self._review(target, change, verifier)
        else:
            given = self._input_of(target, change)
            open_ = open_findings(findings, given)
        return replace(change, findings=tuple(findings), open_findings=tuple(open_))

    def _input_of(self, target: StageTarget, change: StagedChange) -> VerificationInput:
        """The input that the pass reads for `change`."""
        item = target.item
        return VerificationInput.of(
            number=item.number,
            title=item.title,
            body=item.body,
            plan=change.proposal.model_dump(mode="json"),
            source=self._source,
        )

    def _review(
        self, target: StageTarget, change: StagedChange, verifier: StageClient
    ) -> tuple[list[Finding], list[Finding], list[Finding]]:
        """The findings of the model review of `change`, those that return the plan, and those
        that are open."""
        given = self._input_of(target, change)
        findings = verify(verifier, given)
        return findings, returning(findings, given), open_findings(findings, given)

    def _request(self, target: StageTarget) -> dict[str, Any]:
        item = target.item
        request: dict[str, Any] = {
            "number": item.number,
            "title": item.title,
            "body": truncate_to_token_limit(
                item.body,
                min(CONST_ROADMAP_STAGE_BODY_MAX_TOKENS, self._window // _WINDOW_SHARE_BODY),
            ),
            "context": collect_context(
                self._source,
                self._sha,
                item.body,
                max_tokens=min(
                    CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS, self._window // _WINDOW_SHARE_CONTEXT
                ),
            ),
            "capabilities": self._capabilities(),
            "budget": self._budget,
        }
        self._read_overlaps(item.body)
        if self._overlaps:
            request["overlaps"] = [overlap.entry() for overlap in self._overlaps]
        if self._metric_senders:
            request["metric_senders"] = {
                name: list(files) for name, files in self._metric_senders.items()
            }
        probe = probe_premise(self._source, self._sha, item.body)
        # The checks of the reply read the same lines as the model (#3200): `feasibility` quotes one.
        self._probe_lines = probe.lines
        if probe.text:
            request["probes"] = probe.text
        return request

    def _capabilities(self) -> list[Any]:
        """The capabilities for the request. A run with `read_spec` gets the names, and reads the
        purpose and the requirements of a capability on demand: the entries of 170 capabilities
        count about 28,000 tokens, as much as the window leaves for the whole first request
        (#3477). A run with no tool gets the entries."""
        names = sorted(self._specs)
        if self._specs_on_demand:
            return names
        return [self._specs[name].request_entry(name) for name in names]

    def _read_overlaps(self, body: str) -> None:
        """Read the open pull requests whose files meet the paths that `body` cites, and the files
        that hold each metric name that `body` cites (#3252). A failed read adds no entry and
        never stops the item."""
        self._overlaps = ()
        self._pull_requests = 0
        cited = set(self._tree.paths_in(body))
        for span in code_spans(body):
            cited.update(self._tree.paths_in(span))
        if cited and self._pull_reads is not None:
            try:
                read = open_pulls(self._pull_reads(), self._pull_repo)
            except GitHubOperationError:
                read = None
            if read is not None:
                self._pull_requests = read.requests
                self._overlaps = overlaps(read.pulls, cited)
        self._metric_senders = (
            metric_senders(cited_instruments(body), self._grep) if self._grep is not None else {}
        )

    def _ask[M: BaseModel](self, schema: type[M], task: str, request: Mapping[str, Any]) -> M:
        return self._client.chat_structured(
            load_task_prompt(task),
            json.dumps(request, ensure_ascii=False, indent=1),
            schema,
            max_retries=_REPLY_RETURNS,
        )

    def _settle(
        self, target: StageTarget, proposal: StageProposal
    ) -> StagedChange | OverBudget | _Refused:
        """The outcome for one reply: a change, a stop on the budget, or the problem that sends
        the reply back."""
        evidence = (
            record_search_evidence(proposal.groups, self._grep) if self._grep is not None else None
        )
        problems = check_proposal(
            proposal,
            self._known,
            self._tree_of(target, proposal),
            requirements=self._requirements,
            issue_body=target.item.body,
            probes=self._probe_lines,
            overlaps=self._overlaps,
            search_evidence=evidence,
        )
        if problems:
            return _Refused(" ".join(problems), proposal)
        title = staging_title(target.item.number, proposal.summary)
        if problems := title_problems(title):
            return _Refused(" ".join(problems), proposal)
        body = pull_request_body(target.item.number, target.change, proposal)
        keyword = closing_keyword_in(f"{title}\n{body}")
        if keyword is not None:
            raise _stage_error(MESSAGES.roadmap.stage_closing.format(keyword=keyword), target)
        asked, files, measured = self._fit(target, proposal)
        if asked is not proposal:
            # The split gave new groups, and the model can bring old paths back with them.
            problems = form_problems(asked.groups)
            problems.extend(path_problems(asked.groups, self._tree.with_files(files)))
            problems.extend(
                search_problems(
                    asked.groups,
                    record_search_evidence(asked.groups, self._grep)
                    if self._grep is not None
                    else None,
                )
            )
            problems.extend(criterion_problems(asked.criteria, target.item.body, len(asked.groups)))
            if problems:
                return _Refused(" ".join(problems), asked)
        proposal = asked
        if any(m.tokens > self._budget for m in measured):
            return OverBudget(target, tuple(measured), self._budget)
        for path, text in files.items():
            if redact_text(text) != text:
                raise _stage_error(MESSAGES.roadmap.stage_secret.format(path=path), target)
        problem = self._validate(target.change, files)
        if problem is not None:
            return _Refused(problem, proposal)
        return StagedChange(
            target,
            title,
            body,
            files,
            tuple(measured),
            self._tool is not None,
            self._budget,
            proposal,
            pulls_requests=self._pull_requests,
        )

    def _tree_of(self, target: StageTarget, proposal: StageProposal) -> StagedTree:
        """The files that exist when the change is written: the tracked files of the commit and
        the files of the change folder, which the job writes in the same commit."""
        files = render_change(target.change, proposal, self._known, created=self._today)
        return self._tree.with_files(files)

    def _build(
        self, target: StageTarget, proposal: StageProposal
    ) -> tuple[dict[str, str], list[MeasuredGroup]]:
        files = render_change(target.change, proposal, self._known, created=self._today)
        item = target.item
        shared = [f"{item.title}\n{item.body}", *files.values()]
        measured = measure_groups(self._source, proposal.groups, shared=shared)
        return files, measured

    def _fit(
        self, target: StageTarget, proposal: StageProposal
    ) -> tuple[StageProposal, dict[str, str], list[MeasuredGroup]]:
        """The proposal with its groups measured. When a group is over the budget, the model
        splits the groups once for the item and the new groups are measured. After that split, a
        group over the budget stays over it."""
        files, measured = self._build(target, proposal)
        if self._split_asked or all(m.tokens <= self._budget for m in measured):
            return proposal, files, measured
        self._split_asked = True
        asked = {
            "number": target.item.number,
            "title": target.item.title,
            "budget": self._budget,
            "groups": [
                {**m.group.model_dump(), "tokens": m.tokens, "over_budget": m.tokens > self._budget}
                for m in measured
            ],
            "criteria": [entry.model_dump() for entry in proposal.criteria],
        }
        split = ask_split(self._client, asked)
        proposal = proposal.model_copy(update={"groups": split.groups, "criteria": split.criteria})
        files, measured = self._build(target, proposal)
        return proposal, files, measured

    def _validate(self, change: str, files: Mapping[str, str]) -> str | None:
        """The problems that `openspec validate` finds in `files`, or None when it finds none or
        the tool is not installed."""
        if self._tool is None:
            return None
        return validate_change(self._tool, self._source, change, files)


@contextmanager
def openspec_tool() -> Iterator[OpenSpecTool | None]:
    """The pinned OpenSpec under its own configuration, or None when `openspec` is not on PATH."""
    if shutil.which(BIN_OPENSPEC) is None:
        yield None
        return
    with isolated_openspec() as tool:
        yield tool


def _failure_of(
    target: StageTarget, exc: AIClientError | RoadmapStageError | ToolExecutionError
) -> StageFailure:
    """The failure that `exc` made of the item. A model's error says its class and the count of
    schema violations, never the reply."""
    if isinstance(exc, StructuredOutputValidationError):
        reason = MESSAGES.roadmap.stage_violations.format(count=exc.violations)
    elif isinstance(exc, AIClientError):
        reason = ""
    else:
        reason = mask_secrets(str(exc))
    return StageFailure(
        target.item.number, target.item.title, type(exc).__name__, reason, target.item
    )


def _plan_each(
    planner: _Planner, targets: Iterable[StageTarget]
) -> tuple[list[StagedChange], list[OverBudget], list[PremiseFailed], list[StageFailure]]:
    ready: list[StagedChange] = []
    stopped: list[OverBudget] = []
    returned: list[PremiseFailed] = []
    failed: list[StageFailure] = []
    for target in targets:
        try:
            outcome = planner.plan(target)
        except AICredentialsError:
            raise
        except (AIClientError, RoadmapStageError, ToolExecutionError) as exc:
            failed.append(_failure_of(target, exc))
            continue
        if isinstance(outcome, OverBudget):
            stopped.append(outcome)
        elif isinstance(outcome, PremiseFailed):
            returned.append(outcome)
        else:
            ready.append(outcome)
    return ready, stopped, returned, failed


def _pull_of(item: Item) -> int | None:
    """The number of the draft pull request that the item's record holds, if it is a number."""
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    return int(recorded) if recorded.isdigit() else None


def _foreign_commits(source: Path, branch: str) -> int:
    """How many commits `origin/<branch>` holds past the default branch whose author is not the
    identity the clone commits as."""
    own = _git(source, "config", "user.name")
    authors = branch_authors(source, branch, operation=_GIT_OPERATION)
    return sum(1 for author in authors if author != own)


def _reconcile(
    store: RoadmapStore, source: Path, remote_heads: str
) -> tuple[tuple[Removal, ...], tuple[KeptBranch, ...]]:
    """Judge the staged branch of each closed item whose record holds one: removed when the
    branch is gone or every commit past the default branch is the clone identity's, else kept."""
    pushed = set(remote_branches(remote_heads))
    removals: list[Removal] = []
    kept: list[KeptBranch] = []
    for item in store.items():
        branch = item.job_record.get(StageRecordKey.BRANCH)
        if item.state is not GitHubState.CLOSED or not branch:
            continue
        pull = _pull_of(item)
        if branch not in pushed:
            removals.append(Removal(item, branch, pull, gone=True))
        elif (foreign := _foreign_commits(source, branch)) == 0:
            removals.append(Removal(item, branch, pull))
        else:
            reason = MESSAGES.roadmap.stage_kept_reason.format(count=foreign)
            kept.append(KeptBranch(item.number, branch, reason))
    return tuple(removals), tuple(kept)


class StageRead(NamedTuple):
    """What the stage job reads before it asks the model: the commit of the default branch, the
    heads of `origin`, the plans on the default branch, and the selection."""

    sha: str
    heads: str
    planned: PlannedChanges
    selection: StageSelection


def read_stage_selection(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    filters: StageFilter,
    limit: int,
    planned_limit: int,
    item_number: int | None = None,
    probe: int | None = None,
    heads: str | None = None,
    planned: PlannedChanges | None = None,
    now: datetime | None = None,
) -> StageRead:
    """Select the items to stage in the clone `source`, with no model call and no write to git or
    to GitHub. `plan_stage` and `devops roadmap explain` read the selection through this one
    function. A caller that read the heads of `origin` or the plans already passes them in, so
    that a command that judges both jobs reads each once."""
    sha = inspect_checkout(source, repo)
    heads = read_remote_heads(source) if heads is None else heads
    planned = read_planned_changes(source, operation=_GIT_OPERATION) if planned is None else planned
    selection = select_stageable(
        store,
        filters=filters,
        holder_of=lambda issue, branch: issue_holder(source, issue, heads, branch),
        planned=planned,
        item_number=item_number,
        limit=limit,
        planned_limit=planned_limit,
        probe=probe,
        now=now,
    )
    return StageRead(sha, heads, planned, selection)


def plan_stage(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path | str,
    filters: StageFilter,
    item_number: int | None = None,
    limit: int | None = None,
    step_tokens: int | None = None,
    model: LLMClient | ToolboxModel | None = None,
    verifier: StageClient | None = None,
    why: bool = False,
    now: datetime | None = None,
) -> StagePlan:
    """Plans the stage of up to `limit` items without a write to git or to GitHub.

    `source` is the clone of the repository, at the default branch. `limit` and `step_tokens`
    override `roadmap.stage.limit` and `roadmap.stage.step_tokens`. At `roadmap.stage.planned_limit`
    Planned items the plan holds only items of the highest priority (#3487). A client as `model` replaces
    the client of the `analysis` task and plans with the one call and no tool. A `ToolboxModel`
    plans with the read-only tools (#3037), and the client of the `analysis` task answers the call
    that splits the groups. A `verifier`, the client of the `verification` task, makes the model
    review each plan after the checks (#3153); without one, the job makes no review call, as the
    golden-set run of the planner does. With `why`, the plan also lists the open items that the
    filter does not name (#2911). An item that failed less than `roadmap.stage.retry_hours` hours
    before `now` is left out, unless `item_number` names it (#3493).
    """
    checkout = Path(source)
    settings = load_settings()
    sha, heads, planned, selection = read_stage_selection(
        store,
        repo=repo,
        source=checkout,
        filters=filters,
        limit=limit or settings.roadmap.stage.limit,
        planned_limit=settings.roadmap.stage.planned_limit,
        item_number=item_number,
        now=now,
    )
    budget = step_tokens or settings.roadmap.stage.step_tokens
    removals, kept = _reconcile(store, checkout, heads)
    unmatched = unmatched_items(store, filters) if why and item_number is None else ()
    plan = StagePlan(
        repo,
        sha,
        budget,
        left_out=selection.left_out,
        removals=removals,
        kept=kept,
        planned=planned,
        unmatched=unmatched,
    )
    if not selection.selected:
        return plan
    toolbox = model if isinstance(model, ToolboxModel) else None
    client: StageClient
    if isinstance(model, ToolboxModel) or model is None:
        client = get_llm_client(task="analysis", settings=settings)
    else:
        client = model
    with openspec_tool() as tool:
        planner = _planner_of(
            client,
            checkout,
            sha,
            budget=budget,
            tool=tool,
            toolbox=toolbox,
            verifier=verifier,
            repo=repo,
        )
        ready, stopped, returned, failed = _plan_each(planner, selection.selected)
    return replace(
        plan,
        ready=tuple(ready),
        over_budget=tuple(stopped),
        returned=tuple(returned),
        failed=tuple(failed),
    )


def _planner_of(
    client: StageClient,
    checkout: Path,
    sha: str,
    *,
    budget: int,
    tool: OpenSpecTool | None,
    toolbox: ToolboxModel | None = None,
    verifier: StageClient | None = None,
    repo: str | None = None,
) -> _Planner:
    """The planner for the checkout at `sha`: it reads the tracked files, the capabilities and the
    context window of the `analysis` task once. With a `toolbox` model, a plan run calls the
    read-only tools on the checkout, and `client` answers the other calls. The toolset
    `roadmap.stage.toolset` chooses the tools; with `repo`, `read_issue` and `find_issues` of the
    toolset `extended` read that repository on GitHub with the client of the session (#3238). A
    `verifier` makes the model review of each plan (#3153)."""
    window = analysis_window()
    runner = (
        None
        if toolbox is None
        else ToolboxClient(
            toolbox.model,
            client,
            checkout,
            sha,
            window=window,
            openspec=tool,
            github=None if repo is None else StageGitHub(repo),
        )
    )
    return _Planner(
        client=runner or client,
        toolbox=runner,
        source=checkout,
        sha=sha,
        specs=read_base_specs(checkout),
        tree=StagedTree.read(checkout, operation=_GIT_OPERATION),
        budget=budget,
        window=window,
        tool=tool,
        verifier=verifier,
        pull_reads=None if repo is None else session_pull_reads,
        pull_repo=repo or "",
        grep=partial(grep_at, checkout, sha, operation=_GIT_OPERATION),
    )


def plan_item(
    item: Item,
    *,
    client: StageClient,
    checkout: Path,
    sha: str,
    step_tokens: int | None = None,
) -> StagedChange | OverBudget | PremiseFailed:
    """Plans `item` as the job does, in the checkout at `sha`, and writes nothing (#3028).

    The golden set of the stage job runs this on each case. A reply the checks refuse goes back to
    the model once, as in a run, and a second one raises `RoadmapStageError`. `step_tokens`
    overrides `roadmap.stage.step_tokens`. A `client` that is a `ToolboxClient` plans with the
    read-only tools (#3037); the golden set builds it for the case checkout.
    """
    budget = step_tokens or load_settings().roadmap.stage.step_tokens
    with openspec_tool() as tool:
        planner = _planner_of(client, checkout, sha, budget=budget, tool=tool)
        return planner.plan(_target_of(item))


def dry_run_stage(repo: str, *, item: int | None = None, limit: int | None = None) -> StagePlan:
    """The plan a dry run returns, having made no request: the requests and the git commands that
    a run makes, in order, and the writes that `--confirm` adds."""
    from devops_cli.roadmap.request_plan import stage_requests

    reads, writes = stage_requests(repo, item=item, limit=limit)
    return StagePlan(repo, dry_run=True, requests=reads, write_requests=writes)


# ── The writes ────────────────────────────────────────────────────────────────

_CHANGES_DIRECTORY: Final[str] = "openspec/changes"
_GIT_OPERATION: Final[str] = "roadmap.stage"


@dataclass(frozen=True)
class StageApplied:
    """What a run wrote: the items it staged, the items it stopped on a group over the budget, the
    items it returned to New on a false premise, and the items whose writes failed."""

    staged: tuple[int, ...] = ()
    stopped: tuple[int, ...] = ()
    failed: tuple[StageFailure, ...] = ()
    removed: tuple[int, ...] = ()
    returned: tuple[int, ...] = ()


def _git(cwd: Path, *args: str) -> str:
    """The output of `git <args>` in `cwd` for the stage job."""
    return git(cwd, *args, operation=_GIT_OPERATION)


@contextmanager
def _worktree(source: Path, target: StageTarget) -> Iterator[Path]:
    """The worktree of the item's branch at the fetched default branch. The worktree and the
    local branch go when the block ends, so the clone keeps its HEAD and holds no issue."""
    report = add_worktree(source, issue=target.item.number, type_=target.type_, slug=target.slug)
    path = Path(report.path)
    try:
        yield path
    finally:
        _git(source, "worktree", "remove", "--force", str(path))
        _git(source, "branch", "-D", target.branch)


def _commit_and_push(path: Path, change: StagedChange) -> str:
    """Write the files, make the one commit and push the branch with `-u origin`; the commit's
    SHA."""
    target = change.target
    write_change_files(path, change.files)
    _git(path, "add", "--", f"{_CHANGES_DIRECTORY}/{target.change}")
    _git(path, "commit", "-q", "-m", change.title, "-m", f"Plans #{target.item.number}.")
    sha = _git(path, "rev-parse", "HEAD")
    _git(path, "push", "-q", "-u", "origin", target.branch)
    return sha


def _open_pull(repo: str, source: Path, change: StagedChange) -> CreatedPull:
    """The draft pull request of the pushed branch. When GitHub does not make it, the branch
    goes from `origin`, so no remote branch stays without an open pull request."""
    branch = change.target.branch
    try:
        return get_github_session().client.create_draft_pull(
            repo,
            title=change.title,
            body=change.body,
            head=branch,
            base=default_branch(source, operation=_GIT_OPERATION),
        )
    except DevOpsCLIError:
        _git(source, "push", "origin", "--delete", branch)
        raise


def _groups_listed(groups: Sequence[MeasuredGroup]) -> str:
    return "\n".join(
        MESSAGES.roadmap.stage_comment_group.format(
            index=index, title=safe_text(measured.group.title), tokens=measured.tokens
        )
        for index, measured in enumerate(groups, start=1)
    )


def _groups_recorded(groups: Sequence[MeasuredGroup]) -> str:
    """The groups as `stage.groups` holds them: a JSON list of [title, tokens]."""
    return json.dumps([[m.group.title, m.tokens] for m in groups], ensure_ascii=False)


def _run_report(trace: RunTrace) -> str:
    """The report of the plan runs of an item: the counts and each tool call, in order. It is
    empty for an item that was planned with one call, which made no run of the toolbox."""
    if not trace.requests:
        return ""
    texts = MESSAGES.roadmap
    calls = [
        texts.stage_comment_call.format(
            index=index, name=call.name, argument=call.argument.replace("`", "'")
        )
        for index, call in enumerate(trace.tool_calls, start=1)
    ]
    if calls:
        listed = texts.stage_comment_calls.format(calls="\n".join(calls))
    elif any(trace.offered):
        listed = texts.stage_comment_no_calls.format(
            offered=sum(1 for tools in trace.offered if tools), requests=len(trace.offered)
        )
    else:
        listed = texts.stage_comment_no_tools_offered
    return texts.stage_comment_run.format(
        requests=trace.requests,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        calls=listed,
    )


def _notes(change: StagedChange) -> str:
    """The notes that end the comment of a staged item: the open findings first, then the other
    findings, the report of the plan runs, the read of the open pull requests, and a validation
    that did not run (#3264, #3252)."""
    unvalidated = "" if change.validated else MESSAGES.roadmap.stage_comment_not_validated
    read = (
        MESSAGES.roadmap.stage_comment_overlaps.format(requests=change.pulls_requests)
        if change.pulls_requests
        else ""
    )
    advisory = tuple(finding for finding in change.findings if finding not in change.open_findings)
    return (
        open_findings_section(change.open_findings)
        + findings_section(advisory)
        + _run_report(change.trace)
        + read
        + unvalidated
    )


def _label_pull(store: RoadmapStore, pull_number: int, title: str) -> str:
    """Add the labels of `title` to draft pull request `pull_number`. A refused label gives a
    failure note for the comment. Rejected credentials stop the run."""
    try:
        given = read_title_labels(store, title, ref=None)
        add_pull_labels(store, pull_number, given.labels)
    except GitHubUnauthenticatedError:
        raise
    except GitHubOperationError as exc:
        return MESSAGES.roadmap.stage_comment_labels_failed.format(pull=pull_number, error=exc)
    return ""


def _label_needs_fix(store: RoadmapStore, pull: CreatedPull, change: StagedChange) -> str:
    """Apply `plan/needs-fix` when `change` has an open finding, and remove it when it has none
    (#3264). A refused label gives a failure note for the comment; rejected credentials stop the
    run."""
    try:
        if change.open_findings:
            add_pull_labels(store, pull.number, (PLAN_NEEDS_FIX_LABEL,))
        elif PLAN_NEEDS_FIX_LABEL in pull.labels:
            remove_pull_labels(store, pull.number, (PLAN_NEEDS_FIX_LABEL,))
    except GitHubUnauthenticatedError:
        raise
    except GitHubOperationError as exc:
        return MESSAGES.roadmap.stage_comment_labels_failed.format(pull=pull.number, error=exc)
    return ""


def _stage_one(store: RoadmapStore, repo: str, source: Path, change: StagedChange) -> None:
    """Make the branch, the commit, the push and the draft of one item, then record them and
    post the one comment. The Status of the item stays as it is."""
    target = change.target
    with _worktree(source, target) as path:
        sha = _commit_and_push(path, change)
        pull = _open_pull(repo, source, change)
    store.set_marks(
        target.item,
        {
            StageRecordKey.BRANCH: target.branch,
            StageRecordKey.PR: str(pull.number),
            StageRecordKey.SHA: sha,
            StageRecordKey.GROUPS: _groups_recorded(change.groups),
            StageRecordKey.NEEDS_SPLIT: None,
            StageRecordKey.FILE_CAP: None,
            StageRecordKey.FAILED_AT: None,
            StageRecordKey.FAILED_ERROR: None,
        },
    )
    label_note = _label_pull(store, pull.number, change.title)
    label_note += _label_needs_fix(store, pull, change)
    texts = MESSAGES.roadmap
    store.comment(
        target.item.number,
        texts.stage_comment_staged.format(
            marker=CONST_ROADMAP_STAGE_COMMENT_MARKER,
            branch=target.branch,
            pull=pull.number,
            budget=change.budget,
            groups=_groups_listed(change.groups),
            notes=f"{_notes(change)}{label_note}",
        ),
    )


def _stop_on_budget(store: RoadmapStore, stopped: OverBudget) -> None:
    """Tell a person that a group is still over the budget, then record it: the job leaves the
    item alone until a person decides. The comment goes first, so a failed write never leaves a
    record that no one was told about."""
    worst = stopped.worst
    texts = MESSAGES.roadmap
    number = stopped.target.item.number
    store.comment(
        number,
        texts.stage_comment_over_budget.format(
            marker=CONST_ROADMAP_STAGE_COMMENT_MARKER,
            title=safe_text(worst.group.title),
            tokens=worst.tokens,
            budget=stopped.budget,
            number=number,
            groups=_groups_listed(stopped.groups),
        ),
    )
    store.set_marks(
        stopped.target.item,
        {
            StageRecordKey.NEEDS_SPLIT: texts.stage_split_record.format(
                title=worst.group.title, tokens=worst.tokens
            ),
            StageRecordKey.FILE_CAP: str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS),
            StageRecordKey.GROUPS: _groups_recorded(stopped.groups),
            StageRecordKey.FAILED_AT: None,
            StageRecordKey.FAILED_ERROR: None,
        },
    )


def _return_item(store: RoadmapStore, repo: str, returned: PremiseFailed) -> None:
    """Return the item to New with the evidence, as `devops roadmap return` does: the comment goes
    first, then the Status. The item gets no branch and no pull request."""
    number = returned.target.item.number
    comment = MESSAGES.roadmap.stage_comment_premise_failed.format(
        marker=CONST_ROADMAP_STAGE_COMMENT_MARKER, evidence=returned.evidence
    )
    apply_return(store, plan_return(store, number, comment, repo))


def _write_failure(item: Item, exc: DevOpsCLIError) -> StageFailure:
    """The failure of a write: the error's class and its message, credentials masked."""
    return StageFailure(item.number, item.title, type(exc).__name__, mask_secrets(str(exc)), item)


def _remove_staged(store: RoadmapStore, repo: str, source: Path, removal: Removal) -> None:
    """Close the draft of a closed item and delete its branch, then clear the item's stage
    record. A branch that is gone needs only the record cleared."""
    if not removal.gone:
        if removal.pull is not None:
            get_github_session().client.close_pull(repo, removal.pull)
        _git(source, "push", "origin", "--delete", removal.branch)
    store.set_marks(removal.item, {key: None for key in StageRecordKey})


_STOP_THE_RUN: tuple[type[DevOpsCLIError], ...] = (GitHubUnauthenticatedError, ServiceStoppingError)


def write_each(
    writes: Iterable[tuple[Item, Callable[[], None]]],
    done: list[int],
    failed: list[StageFailure],
    *,
    also_stop: tuple[type[DevOpsCLIError], ...] = (),
) -> None:
    """Run each write. A write that fails adds a `StageFailure` and the next write still runs.
    Rejected GitHub credentials and the stop of the Service stop the run (#2753), and so does
    each class in `also_stop`. The row `stage_ready` runs its pull requests the same way (#2865)."""
    stop = (*_STOP_THE_RUN, *also_stop)
    for item, write in writes:
        try:
            write()
        except stop:
            raise
        except DevOpsCLIError as exc:
            failed.append(_write_failure(item, exc))
        else:
            done.append(item.number)


def _record_failures(store: RoadmapStore, failures: Sequence[StageFailure], now: datetime) -> None:
    """Record each failure in the job record of its item: the time and the class of the error
    (#3493). The item waits for the retry delay, and the job goes on with the others. A write
    that fails here is no failure of an item: it ends the run, and the round counts it."""
    for failure in failures:
        if failure.item is not None:
            store.set_marks(
                failure.item,
                {
                    StageRecordKey.FAILED_AT: now.isoformat(),
                    StageRecordKey.FAILED_ERROR: failure.error,
                },
            )


def apply_stage(
    store: RoadmapStore, plan: StagePlan, *, source: Path | str, now: datetime | None = None
) -> StageApplied:
    """Writes the plan: removes the staged branches of closed items, stages each ready change,
    and stops each item whose group is over the budget. A write that fails stops its item, and
    the others go on; rejected GitHub credentials stop the run. Each item that failed, in the plan
    or in a write, gets the time and the error class in its job record, and the job leaves it for
    `roadmap.stage.retry_hours` hours (#3493). The stop of the Service stops the run too, but it
    is no failed item: the failures before it are recorded, and the run ends with the stop
    (#2753)."""
    checkout = Path(source)
    removed: list[int] = []
    staged: list[int] = []
    stopped: list[int] = []
    returned: list[int] = []
    failed: list[StageFailure] = []
    phases = (
        (
            [
                (r.item, partial(_remove_staged, store, plan.repo, checkout, r))
                for r in plan.removals
            ],
            removed,
        ),
        (
            [
                (c.target.item, partial(_stage_one, store, plan.repo, checkout, c))
                for c in plan.ready
            ],
            staged,
        ),
        ([(o.target.item, partial(_stop_on_budget, store, o)) for o in plan.over_budget], stopped),
        (
            [(r.target.item, partial(_return_item, store, plan.repo, r)) for r in plan.returned],
            returned,
        ),
    )
    stopped_by: ServiceStoppingError | None = None
    try:
        for writes, done in phases:
            write_each(writes, done, failed)
    except ServiceStoppingError as stop:
        stopped_by = stop
    _record_failures(store, [*plan.failed, *failed], now or datetime.now(UTC))
    if stopped_by is not None:
        raise stopped_by
    return StageApplied(
        tuple(staged), tuple(stopped), tuple(failed), tuple(removed), tuple(returned)
    )


class StageResult(StrEnum):
    """How a run handled an item, as `devops_cli_roadmap_stage_total` labels it."""

    STAGED = "staged"
    NEEDS_SPLIT = "needs_split"
    RETURNED = "returned"
    FAILED = "failed"
    SKIPPED = "skipped"


def stage_results(plan: StagePlan, applied: StageApplied) -> dict[int, StageResult]:
    """The result of each item a run handled, by issue number. A write that failed moves its item
    from staged or needs_split to failed, so an item has one result (#2659). An item staged with
    an open finding is a failed attempt, so the round counts no staged plan (#3264)."""
    results = dict.fromkeys((left.number for left in plan.left_out), StageResult.SKIPPED)
    results |= dict.fromkeys(applied.staged, StageResult.STAGED)
    results |= dict.fromkeys(applied.stopped, StageResult.NEEDS_SPLIT)
    results |= dict.fromkeys(applied.returned, StageResult.RETURNED)
    results |= dict.fromkeys(
        (failure.number for failure in (*plan.failed, *applied.failed)), StageResult.FAILED
    )
    open_items = {change.target.item.number for change in plan.ready if change.open_findings}
    results |= dict.fromkeys(
        (number for number in applied.staged if number in open_items), StageResult.FAILED
    )
    return results


def emit_stage_results(plan: StagePlan, applied: StageApplied) -> None:
    """Add 1 to `devops_cli_roadmap_stage_total` for each item of a run that wrote, by its result
    (#2659). A plan with no write counts nothing."""
    for result in stage_results(plan, applied).values():
        emit(ROADMAP_STAGE_TOTAL, 1, {"result": result.value})


# ── The report ────────────────────────────────────────────────────────────────


def _section(heading: str, lines: Sequence[str]) -> list[str]:
    return ["", heading, *lines] if lines else []


def render_stage_plan(plan: StagePlan) -> str:
    """The plan as the report of the command: the items to stage with their groups, the items
    stopped on the budget, those left out and those that failed, and the staged branches to
    remove or to keep."""
    texts = MESSAGES.roadmap
    lines = [
        texts.stage_title.format(repo=plan.repo),
        texts.stage_budget.format(budget=plan.budget),
    ]
    ready = [
        texts.stage_ready_line.format(
            number=c.target.item.number,
            title=c.target.item.title,
            branch=c.target.branch,
            count=len(c.groups),
            largest=max(g.tokens for g in c.groups),
            note="" if c.validated else texts.stage_unvalidated,
        )
        for c in plan.ready
    ]
    over = [
        texts.stage_over_line.format(
            number=o.target.item.number,
            title=o.target.item.title,
            group=o.worst.group.title,
            tokens=o.worst.tokens,
        )
        for o in plan.over_budget
    ]
    returned = [
        texts.stage_returned_line.format(
            number=r.target.item.number, title=r.target.item.title, evidence=r.evidence
        )
        for r in plan.returned
    ]
    left = [
        texts.stage_left_line.format(number=x.number, title=x.title, reason=x.reason)
        for x in plan.left_out
    ]
    failed = [
        texts.stage_failed_line.format(
            number=f.number,
            title=f.title,
            error=f.error,
            reason=f": {f.reason}" if f.reason else "",
        )
        for f in plan.failed
    ]
    removals = [
        texts.stage_removal_line.format(
            number=r.number, branch=r.branch, note=texts.stage_removal_gone if r.gone else ""
        )
        for r in plan.removals
    ]
    kept = [
        texts.stage_kept_line.format(number=k.number, branch=k.branch, reason=k.reason)
        for k in plan.kept
    ]
    lines += _section(texts.stage_heading_ready, ready)
    lines += _section(texts.stage_heading_over, over)
    lines += _section(texts.stage_heading_returned, returned)
    lines += _section(texts.stage_heading_left, left)
    lines += _section(
        texts.item_heading_unmatched,
        [
            texts.stage_left_line.format(number=x.number, title=x.title, reason=x.reason)
            for x in plan.unmatched
        ],
    )
    lines += _section(texts.stage_heading_failed, failed)
    lines += _section(texts.stage_heading_removals, removals)
    lines += _section(texts.stage_heading_kept, kept)
    if not (ready or over or returned or left or failed or removals or kept):
        lines += ["", texts.stage_nothing]
    return "\n".join(lines)


def raise_for_failed(failures: Sequence[StageFailure], *, summary: str | None = None) -> None:
    """Fail the run after the other items are written, naming each item that failed with the
    class of its error. The message holds no text of the model. `summary` is the message with
    `{count}` and `{items}`; the stage job's own by default."""
    if not failures:
        return
    texts = MESSAGES.roadmap
    items = ", ".join(
        texts.stage_failed_item.format(
            number=f.number, error=f.error, reason=f": {f.reason}" if f.reason else ""
        )
        for f in failures
    )
    raise RoadmapStageError(
        (summary or texts.stage_failed).format(count=len(failures), items=items),
        failed_items=[f.number for f in failures],
    )


def raise_for_failed_round(plan: StagePlan, applied: StageApplied) -> None:
    """Fail the row's round only when it tried items and handled none: no item was staged, stopped
    on the budget or returned to New (#3493). An item that failed while another was handled is
    recorded in its own job record and waits for `roadmap.stage.retry_hours` hours, so it does not
    count against the repository. A round that tried no item does not fail."""
    if applied.staged or applied.stopped or applied.returned:
        return
    raise_for_failed([*plan.failed, *applied.failed])


__all__ = [
    "KeptBranch",
    "LeftOut",
    "OverBudget",
    "PlannedQueue",
    "PremiseFailed",
    "Removal",
    "StageApplied",
    "StageFailure",
    "StageFilter",
    "StagePlan",
    "StageRead",
    "StageResult",
    "StageSelection",
    "StageTarget",
    "StagedChange",
    "Walk",
    "analysis_window",
    "apply_stage",
    "dry_run_stage",
    "emit_stage_results",
    "named_items",
    "openspec_tool",
    "parse_filters",
    "plan_stage",
    "priority_order",
    "raise_for_failed",
    "raise_for_failed_round",
    "read_stage_selection",
    "render_stage_plan",
    "select_stageable",
    "stage_results",
    "unmatched_items",
    "walk_named",
    "write_each",
]
