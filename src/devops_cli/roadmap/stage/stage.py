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
(`worktree_add.issue_holder`, which also counts a stray local branch of the new name with a commit that `origin` lacks), an item whose plan a person rejected until its text or a file that the reason names changes (`stage_rejected`, #3503), an item whose plan is already on the default branch or whose
change is archived there (`planned.read_planned_changes`, one read of the tree for the round), an
item whose title gives no branch name or whose summary is over `SUMMARY_MAX_CHARS` units (#3369), an item whose text looks like a secret, an item whose last plan or write failed less than
the wait of its failure class ago (`RETRY_AFTER`; its record holds `stage.failed_at`,
`stage.failed_error`, `stage.failed_step` and `stage.failed_class`, #3493, #4056), and an item whose
record holds `stage.needs_split` made with the file cap of now (`stage.file_cap`): a stop under
another measure does not count. A run takes at most `--limit`
items, highest priority first. `--item` takes the one item it names when that item is open and
Ready.

**Plan.** For each item the job plans a `StageProposal` with an agent that reads the repository
before it answers (`ai.for_task("stage")`, prompt `roadmap_stage_change.md`, and the read-only
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
plan and the files that the plan cites, and reads the repository with the read tools, on the model
of the task `verification` (#3039). A finding of the type `missing_path`, `false_premise`,
`ignores_existing_code`, `task_order` or `verify_form` that quotes its evidence sends the plan back
to the planner, up to `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` times (#3039). The planner gets
each open finding of that round. A finding of such a type, of `spec_delta_wrong` or
`criterion_dropped`, or one that reports a placeholder is open: if the last review repeats it, the
job keeps the draft with the label `plan/needs-fix` and puts the finding first in the comment
(#3264). The comment lists every other finding of each round (#3039).
The review never merges and never marks a draft ready. `plan_item` plans one item with a given client
and checkout: the golden set of the job runs
it on each case (`stage_eval_run`, #3028). The plan writes nothing to git or to GitHub. A model call
that fails skips its item; rejected credentials stop the run.

**Rejected plans.** Before it selects, the job reads the plan pull request of each staged New or
Ready item (`stage_rejected.closed_plans`). One that closed with no merge is a rejected plan. The
write deletes the staged branch when only the session identity wrote to it, posts the reason on the
issue, and records `stage.rejected`. It returns the item to New, unless the same run stages the item
again (`_reject_plan`).

**Why.** `--why` adds to the plan the open items that the filter does not name, under their own
heading, each with the family it misses (`StageFilter.mismatch`). They are not "left out": no rule
of the job judged them. `devops roadmap explain` gives the reason of one issue (#2911).
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from functools import cache, partial
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
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_PLANNED_LIMIT_PRIORITIES,
    CONST_ROADMAP_PRIORITY_VALUES,
    CONST_ROADMAP_STAGE_BODY_MAX_TOKENS,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitOperationError,
    RoadmapStageError,
    ServiceStoppingError,
    ToolExecutionError,
    ValidationError,
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
from devops_cli.roadmap.agent_run import RunTrace, TraceFacts
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import branch_authors, default_branch, git
from devops_cli.roadmap.commit_title import commit_summary, commit_type
from devops_cli.roadmap.digest_clears import has_digest_clear
from devops_cli.roadmap.failure import FailureClass, StepName, failure_class_of, retry_after
from devops_cli.roadmap.planned import (
    PlannedChanges,
    open_plan_creates,
    planned_count,
    planned_limit_priorities,
    read_planned_changes,
)
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length, title_problems
from devops_cli.roadmap.pull_labels import add_pull_labels, read_title_labels, remove_pull_labels
from devops_cli.roadmap.refine.refine import (
    NextStep,
    body_dependencies,
    collect_context,
    git_result,
    inspect_checkout,
    recorded_blockers,
    stage_comment_text,
)
from devops_cli.roadmap.refine.refine_investigation import task_window
from devops_cli.roadmap.stage.stage_change import (
    CHANGE_TASK,
    MeasuredGroup,
    StageGroup,
    StageProposal,
    check_gates,
    closing_keyword_in,
    joined_problems,
    measure_groups,
    moved_modules,
    plan_texts,
    pull_request_body,
    render_change,
    safe_text,
    shared_texts,
    staging_title,
    write_change_files,
)
from devops_cli.roadmap.stage.stage_constants import candidate_names, staged_constants
from devops_cli.roadmap.stage.stage_context_facts import collect_stage_facts_context
from devops_cli.roadmap.stage.stage_filter import split_filter_entry
from devops_cli.roadmap.stage.stage_form import (
    record_search_evidence,
)
from devops_cli.roadmap.stage.stage_github import StageGitHub
from devops_cli.roadmap.stage.stage_models import model_fields, referenced_classes
from devops_cli.roadmap.stage.stage_moved import MovedPath, moved_paths
from devops_cli.roadmap.stage.stage_overlap import (
    Overlap,
    PullReads,
    cited_instruments,
    grep_at,
    metric_senders,
    open_pulls,
    overlaps,
    session_pull_reads,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree, record_test_references
from devops_cli.roadmap.stage.stage_pending import PendingStage, orphan_mark
from devops_cli.roadmap.stage.stage_plan_record import (
    StagePlanRecord,
    delete_plan_record,
    plan_key,
    plan_record_path,
    prompt_version,
    read_plan_record,
    write_plan_record,
)
from devops_cli.roadmap.stage.stage_probe import blocked_by, probe_premise
from devops_cli.roadmap.stage.stage_references import reference_files
from devops_cli.roadmap.stage.stage_registry import matches, registry_table
from devops_cli.roadmap.stage.stage_rejected import (
    ReadFailure,
    RejectedPlan,
    closed_plans,
    hold_reason,
    reasons_of,
    recorded_rejection,
    staged_plans,
)
from devops_cli.roadmap.stage.stage_removal_references import scan_removal_references
from devops_cli.roadmap.stage.stage_request import StageRequest, gate_arguments
from devops_cli.roadmap.stage.stage_specs import BaseSpec, read_base_specs
from devops_cli.roadmap.stage.stage_split import ask_split
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, ToolboxModel, review
from devops_cli.roadmap.stage.stage_validate import validate_change
from devops_cli.roadmap.stage.stage_verify import (
    PLAN_NEEDS_FIX_LABEL,
    Finding,
    VerificationInput,
    findings_section,
    open_findings,
    open_findings_section,
    return_problem,
    returning,
)
from devops_cli.roadmap.step_files import code_spans
from devops_cli.roadmap.step_metrics import observe_step
from devops_cli.roadmap.stores.store import (
    GitHubState,
    Item,
    ItemField,
    RefineRecordKey,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.roadmap.trust import is_approved, is_trusted
from devops_cli.security.sanitizer import mask_secrets, redact_text
from devops_cli.telemetry.instruments import (
    ROADMAP_STAGE_GATE_REFUSALS_TOTAL,
    ROADMAP_STAGE_PLAN_RECORD_TOTAL,
    ROADMAP_STAGE_TOTAL,
    emit,
)

logger = logging.getLogger(__name__)

# The row of the step seconds that this job sends (#4066).
_ROW = "stage"

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
    which the job plans only a P0 or P1 item."""

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
        rejected: Mapping[int, RejectedPlan],
    ) -> None:
        self._store = store
        self._holder_of = holder_of
        self._planned = planned
        self._queue = queue
        self._now = now
        self._rejected_now = rejected

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
            self._recorded_blocker,
            self._planned_on_default,
            *([] if named else [self._rejected]),
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
        """An account that the jobs do not trust opened the item, or a bot opened it and no
        review of refine approved it (#3502)."""
        texts = MESSAGES.roadmap
        if not is_trusted(item):
            return texts.stage_left_author.format(
                author=item.author_login or texts.refine_author_unknown,
                association=item.author_association or texts.refine_author_unknown,
            )
        return None if is_approved(item) else texts.stage_left_unjudged

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

    def _recorded_blocker(self, item: Item) -> str | None:
        """An open item that the record of a refine round or of the stage job names as the blocker
        of `item` (#3418). A closed blocker holds nothing back, so it is no reason to leave out."""
        open_blockers = [
            f"#{number}"
            for number in recorded_blockers(item)
            if (found := self._store.item(number)) is not None and found.state is GitHubState.OPEN
        ]
        if not open_blockers:
            return None
        return MESSAGES.roadmap.stage_left_blocked.format(issues=", ".join(open_blockers))

    def _planned_on_default(self, item: Item) -> str | None:
        """The plan is on the default branch, or its change is archived there (#2714). The folder
        matches by the issue number, so a slug that differs from the title does not matter."""
        texts = MESSAGES.roadmap
        if (folder := self._planned.active.get(item.number)) is not None:
            return texts.stage_left_planned.format(branch=self._planned.default, folder=folder)
        if (folder := self._planned.archived.get(item.number)) is not None:
            return texts.stage_left_archived.format(branch=self._planned.default, folder=folder)
        return None

    def _rejected(self, item: Item) -> str | None:
        """A person closed the plan pull request of the item with no merge, and neither the text
        of the item nor a file that the reason names changed since (#3503). The rejections that
        the same run found count, as the job has not written their record yet."""
        rejected = self._rejected_now.get(item.number) or recorded_rejection(item)
        return None if rejected is None else hold_reason(self._store, item, rejected)

    def _held(self, item: Item) -> str | None:
        return self._holder_of(item.number, _target_of(item).branch)

    def _secret(self, item: Item) -> str | None:
        looks_secret = any(redact_text(text) != text for text in (item.title, item.body))
        return MESSAGES.roadmap.stage_left_secret if looks_secret else None

    def _queue_full(self, item: Item) -> str | None:
        """The queue of Planned items is at its limit (#3487): the job plans only a P0 or P1 item
        (#3692). `--item` overrules it, as it overrules a recorded split."""
        if not self._queue.full or item.priority in CONST_ROADMAP_PLANNED_LIMIT_PRIORITIES:
            return None
        return MESSAGES.roadmap.stage_left_planned_limit.format(
            count=self._queue.count,
            limit=self._queue.limit,
            priorities=planned_limit_priorities(),
        )

    def _failed_lately(self, item: Item) -> str | None:
        """The last plan or write of the item failed less than the wait of its failure class ago (#3493). The
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
        until = failed_at + retry_after(item.job_record.get(StageRecordKey.FAILED_CLASS))
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
    rejected: Mapping[int, RejectedPlan] | None = None,
) -> StageSelection:
    """The items to stage, up to `limit`, and those the filter names that the job leaves out.

    `holder_of` tells who holds an issue and its new `branch` (`worktree_add.issue_holder`), or None. `planned` holds
    the change folders of the default branch (#2714). With `item_number` the filter and the limit
    do not apply. `probe` is the issue that `walk_named` judges also after the limit. With
    `planned_limit` Planned items or more, the job takes only a P0 or P1 item (#3487, #3692). An
    item that failed less than the wait of its failure class before `now` waits (#3493, #4060). An
    item whose plan a person rejected waits for a change of its text or of a file that the reason
    names; `rejected` holds the rejections of this run that the record does not hold yet (#3503).
    """
    opened = _open_items(store)
    judge = _Judge(
        store,
        holder_of,
        planned,
        PlannedQueue(planned_count(opened), planned_limit),
        now or datetime.now(UTC),
        rejected or {},
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
    what the plan runs and the review runs of the toolbox did (#3037, #3039). The trace is empty
    for an item planned with one call and no review. `proposal` is the plan that the files render. `findings` are the points that each model
    review of the plan raised in each repair round (#3153, #3039): the comment lists them.
    `open_findings` are the findings of the last review that keep the draft with the label
    `plan/needs-fix` (#3264); they are a part of `findings`."""

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
    warnings: tuple[str, ...] = ()


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
class Blocked:
    """An item whose premise cites a path that an open plan creates (#3418). The job returns it
    to New with `blockers` in its record, and plans no change for it. `paths` are the cited paths
    that those plans create."""

    target: StageTarget
    blockers: tuple[int, ...]
    paths: tuple[str, ...]


@dataclass(frozen=True)
class StageFailure:
    """An item the job could not plan or write: the class of the error and why, never the model's
    text. `item` is the item itself, when the job read it, so that the job records the failure in
    the job record of the item (#3493). `failure_class` comes from the type of the error, and
    `step` names the step that failed (#4056)."""

    number: int
    title: str
    error: str
    reason: str = ""
    item: Item | None = field(default=None, compare=False, repr=False)
    failure_class: FailureClass = field(kw_only=True)
    step: StepName = field(kw_only=True)


@dataclass(frozen=True)
class Removal:
    """The staged branch of a closed item that only the session's identity wrote to: the job
    closes its draft pull request and deletes it, or, when `gone`, only clears the record. With
    `orphan`, the item is open and holds the intent mark of the job and no pull request (#4051):
    the writer finds the draft by its branch."""

    item: Item
    branch: str
    pull: int | None
    gone: bool = False
    orphan: bool = False

    @property
    def number(self) -> int:
        """The number of the closed item."""
        return self.item.number


@dataclass(frozen=True)
class Rejection:
    """The plan pull request of an item that a person closed with no merge (#3503): the record to
    write, the comment that holds the reason, and the staged `branch` to delete with the commit
    `branch_sha` that the job judged, or None when the branch is gone or another author wrote to
    it."""

    item: Item
    plan: RejectedPlan
    comment: str
    branch: str | None = None
    branch_sha: str = ""

    @property
    def number(self) -> int:
        """The number of the item."""
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
    failed: tuple[StageFailure, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    removals: tuple[Removal, ...] = ()
    kept: tuple[KeptBranch, ...] = ()
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()
    planned: PlannedChanges | None = None
    unmatched: tuple[LeftOut, ...] = ()
    blocked: tuple[Blocked, ...] = ()
    rejections: tuple[Rejection, ...] = ()


def _stage_error(message: str, target: StageTarget) -> RoadmapStageError:
    return RoadmapStageError(message, failed_items=[target.item.number])


def _check_removal_references(
    source: Path, target: StageTarget, files: Mapping[str, str]
) -> tuple[str, ...]:
    """Scan `source` for removed entity references, raise on test references, return source warnings."""
    scan = scan_removal_references(source, files)
    if scan.has_test_failures:
        lines = [
            MESSAGES.roadmap.stage_problem_unhandled_test_reference.format(path=p, name=name)
            for name, paths in sorted(scan.unhandled_tests.items())
            for p in sorted(paths)
        ]
        raise _stage_error(" ".join(lines), target)
    return tuple(
        MESSAGES.roadmap.stage_problem_unhandled_test_reference.format(path=p, name=name)
        for name, paths in sorted(scan.unhandled_sources.items())
        for p in sorted(paths)
    )


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


@dataclass(frozen=True)
class PlanFiles:
    """Where the planner keeps the plan of each item, and what the key of a plan names (#4064): the
    repository (the folder of the files), the model name and the toolset name. The prompt version
    is the hash of the prompt texts."""

    repo: str
    model: str
    toolset: str

    def path(self, number: int) -> Path:
        return plan_record_path(self.repo, number)

    def key(self, item: Item) -> str:
        return plan_key(
            number=item.number,
            title=item.title,
            body=item.body,
            model=self.model,
            toolset=self.toolset,
            prompt_version=prompt_version(self.toolset),
        )


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
        verifier: ToolboxClient | None = None,
        verify_window: int | None = None,
        pull_reads: Callable[[], PullReads] | None = None,
        pull_repo: str = "",
        grep: Callable[[str], Sequence[str]] | None = None,
        open_creates: Callable[[], Mapping[str, int]] | None = None,
        traces: list[RunTrace] | None = None,
        rejected: Mapping[int, str] | None = None,
        plan_files: PlanFiles | None = None,
    ) -> None:
        self._client = client
        self._plan_files = plan_files
        self._toolbox = toolbox or (client if isinstance(client, ToolboxClient) else None)
        self._verifier = verifier
        self._verify_window = verify_window
        # The runs of the planner and of the verifier, in order, for the comment (#3039).
        self._traces: list[RunTrace] = [] if traces is None else traces
        self._source = source
        self._sha = sha
        self._specs = specs
        self._known = frozenset(specs)
        self._requirements = {name: spec.requirements for name, spec in specs.items()}
        # The statement of each base requirement, by capability and name: an added requirement
        # that removes a command needs a `modified` requirement for each base requirement that
        # names it (#3287).
        self._requirement_texts = {name: dict(spec.statements) for name, spec in specs.items()}
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
        # The read of the open plans that create a path (#3418), and the dependency that the
        # probe of the item in hand found, which the run returns without a model call.
        self._open_creates = open_creates
        # The reason of a rejected plan, by issue number, for the request (#3503).
        self._rejected = rejected or {}
        self._dependency: Blocked | None = None
        # The number of GraphQL requests that read the open pull requests of the item in hand.
        self._pull_requests = 0

    def plan(self, target: StageTarget) -> StagedChange | OverBudget | Blocked:
        """The change of `target`, or the group that stops it. A reply the checks refuse goes back
        to the model once, with the problem. The model splits the groups at most once. With a
        verifier, the model review of the plan (#3153) follows the checks and may return the plan
        up to `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` times (#3039). So an item costs three
        planner calls at most without a verifier, five with one, and three calls of the verifier."""
        self._split_asked = False
        self._traces.clear()
        kept, key = self._kept(target)
        if kept is None:
            request = self._request(target)
            if self._dependency is not None:
                return self._dependency
        else:
            # The kept request holds what the gates read; the gates run again on the current
            # commit (#4064).
            request = kept.request
            self._dependency = None
        outcome = self._gated(target, request, first=None if kept is None else kept.proposal)
        if isinstance(outcome, StagedChange) and key is not None:
            self._keep(target, key, request, outcome.proposal, kept)
        verifier = self._verifier
        if isinstance(outcome, StagedChange) and verifier is not None:
            outcome = self._verified(target, request, outcome, verifier)
        if isinstance(outcome, StagedChange) and self._traces:
            return replace(outcome, trace=RunTrace.combined(self._traces))
        return outcome

    def _trace_facts(self) -> TraceFacts | None:
        """The facts of the last agent run, or None when no toolbox client ran."""
        if not isinstance(self._client, ToolboxClient):
            return None
        traces = getattr(self._toolbox, "traces", None)
        return TraceFacts.of(traces[-1]) if traces else None

    def _kept(self, target: StageTarget) -> tuple[StagePlanRecord | None, str | None]:
        """The kept plan of the item and its key, (None, None) for a run that keeps no file. A
        file of another key goes at once, so a plan that then fails leaves no stale file. The
        counter tells a hit from a miss (#4064)."""
        files = self._plan_files
        if files is None:
            return None, None
        path, key = files.path(target.item.number), files.key(target.item)
        kept = read_plan_record(path, key)
        if kept is None:
            delete_plan_record(path)
        emit(ROADMAP_STAGE_PLAN_RECORD_TOTAL, 1, {"result": "miss" if kept is None else "hit"})
        return kept, key

    def _keep(
        self,
        target: StageTarget,
        key: str,
        request: StageRequest,
        proposal: StageProposal,
        kept: StagePlanRecord | None,
    ) -> None:
        """Write the plan that passed the checks, before the review: a failed review leaves the
        file, and the rerun asks the planner nothing. A hit whose plan the checks did not change
        leaves the file as it is."""
        files = self._plan_files
        if files is None or (kept is not None and kept.proposal == proposal):
            return
        write_plan_record(
            files.path(target.item.number),
            StagePlanRecord(key=key, proposal=proposal, request=request),
        )
        emit(ROADMAP_STAGE_PLAN_RECORD_TOTAL, 1, {"result": "written"})

    def _gated(
        self, target: StageTarget, request: StageRequest, *, first: StageProposal | None = None
    ) -> StagedChange | OverBudget:
        """The change that passes the checks, with one return of a refused reply. `first` is a kept
        plan that stands for the first reply of the model."""
        proposal = first or self._ask(StageProposal, CHANGE_TASK, request.for_model())
        outcome = self._settle(target, proposal, request, trace=self._trace_facts())
        if isinstance(outcome, _Refused):
            again = {
                **request.for_model(),
                "previous": outcome.reply.model_dump(),
                "problem": outcome.problem,
            }
            proposal = self._ask(StageProposal, CHANGE_TASK, again)
            outcome = self._settle(target, proposal, request, trace=self._trace_facts())
        if isinstance(outcome, _Refused):
            message = MESSAGES.roadmap.stage_invalid.format(problem=outcome.problem)
            raise _stage_error(message, target)
        return outcome

    def _verified(
        self,
        target: StageTarget,
        request: StageRequest,
        change: StagedChange,
        verifier: ToolboxClient,
    ) -> StagedChange | OverBudget:
        """The change after the model review. A finding of a type that returns the plan, with a
        quote that is in the input, sends the plan back to the planner with each open finding of
        the round. The revised plan passes the checks and the review again, up to
        `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` times (#3039), and a refused revision stops the
        item. Every finding of each round stays on the change for the comment (#3039). The last
        review judges the last plan, so only its open findings keep the draft with
        `plan/needs-fix` (#3264)."""
        seen, returned, open_ = self._review(target, change, verifier)
        for _ in range(CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS):
            if not returned:
                break
            revised = self._repaired(target, request, change, open_)
            if isinstance(revised, OverBudget):
                return revised
            change = revised
            findings, returned, open_ = self._review(target, change, verifier)
            seen = [*seen, *findings]
        return replace(change, findings=tuple(dict.fromkeys(seen)), open_findings=tuple(open_))

    def _repaired(
        self,
        target: StageTarget,
        request: StageRequest,
        change: StagedChange,
        open_: Sequence[Finding],
    ) -> StagedChange | OverBudget:
        """The plan of one repair round: the planner gets the plan and each open finding of the
        review, and its revision passes the checks or stops the item."""
        again = {
            **request.for_model(),
            "previous": change.proposal.model_dump(),
            "problem": return_problem(open_),
        }
        revised = self._ask(StageProposal, CHANGE_TASK, again)
        outcome = self._settle(target, revised, request, trace=self._trace_facts())
        if isinstance(outcome, _Refused):
            message = MESSAGES.roadmap.stage_invalid.format(problem=outcome.problem)
            raise _stage_error(message, target)
        return outcome

    def _input_of(self, target: StageTarget, change: StagedChange) -> VerificationInput:
        """The input that the pass reads for `change`."""
        item = target.item
        return VerificationInput.of(
            number=item.number,
            title=item.title,
            body=item.body,
            plan=change.proposal.model_dump(mode="json"),
            source=self._source,
            window=self._verify_window,
        )

    def _review(
        self, target: StageTarget, change: StagedChange, verifier: ToolboxClient
    ) -> tuple[list[Finding], list[Finding], list[Finding]]:
        """The findings of the model review of `change`, those that return the plan, and those
        that are open."""
        with observe_step(self._pull_repo, _ROW, StepName.REVIEW):
            findings, given = review(verifier, self._input_of(target, change))
        return findings, returning(findings, given), open_findings(findings, given)

    def _request(self, target: StageTarget) -> StageRequest:
        """The request for one item: what the model reads and what the gates need. The open plans
        that create a path are read here, once for the run (#4046)."""
        item = target.item
        context = collect_context(
            self._source,
            self._sha,
            item.body,
            max_tokens=min(
                CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS, self._window // _WINDOW_SHARE_CONTEXT
            ),
        )
        registry = registry_table(self._source)
        matched = matches(registry, (item.title, item.body), tuple(self._tree.paths_in(item.body)))
        if matched:
            lines = [f"- {entry.path} ({entry.declaring_path}:{entry.line})" for entry in matched]
            context = f"{context}\n\n### Registry places\n\n" + "\n".join(lines)
        facts_context = collect_stage_facts_context(
            f"{item.title}\n{item.body}",
            lambda path: _read_staged_file(self._source, self._sha, path),
        )
        if facts_context:
            context = f"{context}\n\n{facts_context}"
        pulls, senders = self._read_overlaps(item.body)
        probe = probe_premise(self._source, self._sha, item.body)
        self._dependency = self._dependency_of(target, probe.missing)
        return StageRequest(
            number=item.number,
            title=item.title,
            body=truncate_to_token_limit(
                item.body,
                min(CONST_ROADMAP_STAGE_BODY_MAX_TOKENS, self._window // _WINDOW_SHARE_BODY),
            ),
            context=context,
            capabilities=self._capabilities(),
            budget=self._budget,
            rejected_plan=self._rejected.get(item.number),
            overlaps=[overlap.entry() for overlap in pulls] or None,
            metric_senders={name: list(files) for name, files in senders.items()} or None,
            probes=probe.text or None,
            issue_body=item.body,
            # The checks of the reply read the same lines as the model (#3200): `feasibility`
            # quotes one.
            probe_lines=probe.lines,
            overlap_pulls=pulls,
            creators=dict(self._creators()),
        )

    def _dependency_of(self, target: StageTarget, missing: Sequence[str]) -> Blocked | None:
        """The open item whose plan creates a cited path that the staging commit lacks, or None
        (#3418). The open plans are read once for the run, and only when a path is missing."""
        if not missing or self._open_creates is None:
            return None
        creators = self._open_creates()
        paths = tuple(path for path in missing if path in creators)
        blockers = blocked_by(paths, creators)
        return Blocked(target, blockers, paths) if blockers else None

    def _capabilities(self) -> list[Any]:
        """The capabilities for the request. A run with `read_spec` gets the names, and reads the
        purpose and the requirements of a capability on demand: the entries of 170 capabilities
        count about 28,000 tokens, as much as the window leaves for the whole first request
        (#3477). A run with no tool gets the entries."""
        names = sorted(self._specs)
        if self._specs_on_demand:
            return names
        return [self._specs[name].request_entry(name) for name in names]

    def _read_overlaps(self, body: str) -> tuple[tuple[Overlap, ...], Mapping[str, Sequence[str]]]:
        """Read the open pull requests whose files meet the paths that `body` cites, and the files
        that hold each metric name that `body` cites (#3252). A failed read adds no entry and
        never stops the item."""
        pulls: tuple[Overlap, ...] = ()
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
                pulls = overlaps(read.pulls, cited)
        senders = (
            metric_senders(cited_instruments(body), self._grep) if self._grep is not None else {}
        )
        return pulls, senders

    def _ask[M: BaseModel](self, schema: type[M], task: str, request: Mapping[str, Any]) -> M:
        with observe_step(self._pull_repo, _ROW, StepName.PLAN):
            return self._client.chat_structured(
                load_task_prompt(task),
                json.dumps(request, ensure_ascii=False, indent=1),
                schema,
                max_retries=_REPLY_RETURNS,
            )

    def _plan_body(
        self, target: StageTarget, title: str, proposal: StageProposal
    ) -> str | _Refused:
        """The body of the draft, built and checked by `build_plan_body`. A text with a closing
        keyword stops the item. A body that breaks the plan form goes back to the model."""
        keyword = closing_keyword_in(f"{title}\n{safe_text(proposal.pull_request_body)}")
        if keyword is not None:
            raise _stage_error(MESSAGES.roadmap.stage_closing.format(keyword=keyword), target)
        try:
            return pull_request_body(target.item.number, target.change, proposal)
        except ValidationError as exc:
            lines = (line.removeprefix("- ") for line in str(exc).splitlines())
            return _Refused(" ".join(lines), proposal)

    def _settle(
        self,
        target: StageTarget,
        proposal: StageProposal,
        request: StageRequest,
        *,
        trace: TraceFacts | None = None,
    ) -> StagedChange | OverBudget | _Refused:
        """The outcome for one reply: a change, a stop on the budget, or the problem that sends
        the reply back."""
        texts = [
            *plan_texts(proposal),
            *(
                t
                for g in proposal.groups
                for t in (g.title, g.test, g.implementation, g.documentation, g.verify)
                if t
            ),
        ]
        referenced = referenced_classes(texts)
        models = model_fields(self._source, self._sha, referenced)
        problems = self._problems(
            proposal,
            self._tree_of(target, proposal),
            request,
            change=target.change,
            models=models,
            trace=trace,
        )
        if problems:
            return _Refused(" ".join(problems), proposal)
        title = staging_title(target.item.number, proposal.summary)
        if problems := title_problems(title):
            return _Refused(" ".join(problems), proposal)
        body = self._plan_body(target, title, proposal)
        if isinstance(body, _Refused):
            return body
        asked, files, measured = self._fit(target, proposal)
        if asked is not proposal:
            # The split gave new groups, and the model can bring back a fault that only one gate
            # refuses. Every gate of the first reply judges the split too.
            problems = self._problems(
                asked,
                self._tree.with_files(files),
                request,
                change=target.change,
                models=models,
                trace=trace,
            )
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
        warnings = _check_removal_references(self._source, target, files)
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
            warnings=warnings,
        )

    def _problems(
        self,
        proposal: StageProposal,
        tree: StagedTree,
        request: StageRequest,
        *,
        change: str = "",
        models: Mapping[str, tuple[str, Sequence[str]]] | None = None,
        trace: TraceFacts | None = None,
    ) -> list[str]:
        """The problems that every gate finds in one reply: the first one and a split of it. Each
        gate with a problem adds 1 to the refusal counter of the job (#4066)."""
        with observe_step(self._pull_repo, _ROW, StepName.GATE):
            return self._gate_problems(
                proposal, tree, request, change=change, models=models, trace=trace
            )

    def _gate_problems(
        self,
        proposal: StageProposal,
        tree: StagedTree,
        request: StageRequest,
        *,
        change: str,
        models: Mapping[str, tuple[str, Sequence[str]]] | None,
        trace: TraceFacts | None,
    ) -> list[str]:
        evidence = (
            record_search_evidence(proposal.groups, self._grep) if self._grep is not None else None
        )
        # The tests that each changed manifest reaches, from the same staged search (#3972).
        manifest_references = (
            record_test_references(proposal.groups, self._grep) if self._grep is not None else None
        )
        constants = staged_constants(self._source, self._sha, candidate_names(plan_texts(proposal)))
        references = self._probe_references(proposal.groups)
        found = check_gates(
            proposal,
            change=change,
            **gate_arguments(
                request,
                tree,
                known=self._known,
                requirements=self._requirements,
                requirement_texts=self._requirement_texts,
                search_evidence=evidence,
                manifest_references=manifest_references,
                # The citation rule reads the staged commit, the one the probe and the model read
                # (#3422), and never the working tree.
                read_text=partial(_read_staged_file, self._source, self._sha),
                registry=registry_table(self._source),
                constants=constants,
                references=references,
                models=models,
                trace=trace,
            ),
        )
        if self._pull_repo:
            for gate, problems in found.items():
                if problems:
                    emit(
                        ROADMAP_STAGE_GATE_REFUSALS_TOTAL,
                        1,
                        {"repo": self._pull_repo, "gate": gate.value},
                    )
        return joined_problems(found)

    def _probe_references(self, groups: Sequence[StageGroup]) -> list[str]:
        """The files of the staged commit that hold the old path or the dotted name of each moved
        module (#3373)."""
        moved = moved_modules(groups)
        if not moved:
            return []
        hits: list[str] = []
        seen: set[str] = set()
        for old_path, dotted_name in moved:
            for term in (old_path, dotted_name):
                for path in _probe_reference_files(self._source, self._sha, term):
                    if path not in seen:
                        seen.add(path)
                        hits.append(path)
        return hits

    def _creators(self) -> Mapping[str, int]:
        """The paths that the plans of open items create, each with its item (#3418). The job
        reads them once for the run, with the premise probe, and a plan run without them has none."""
        return {} if self._open_creates is None else self._open_creates()

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
        shared = shared_texts(item.title, item.body, files)
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
        target.item.number,
        target.item.title,
        type(exc).__name__,
        reason,
        target.item,
        failure_class=failure_class_of(exc),
        step=StepName.PLAN,
    )


def _plan_each(
    planner: _Planner, targets: Iterable[StageTarget], writer: StageWriter | None = None
) -> tuple[list[StagedChange], list[OverBudget], list[StageFailure], list[Blocked]]:
    """Plan each target in order. With a `writer`, the result of a target is written as soon as the
    target is done, before the next target is planned (#4034)."""
    ready: list[StagedChange] = []
    stopped: list[OverBudget] = []
    failed: list[StageFailure] = []
    blocked: list[Blocked] = []
    for target in targets:
        result: StagedChange | OverBudget | Blocked | StageFailure
        try:
            result = planner.plan(target)
        except AICredentialsError:
            raise
        except (AIClientError, RoadmapStageError, ToolExecutionError) as exc:
            result = _failure_of(target, exc)
        if writer is not None:
            writer.settle(target, result)
        if isinstance(result, StageFailure):
            failed.append(result)
        elif isinstance(result, OverBudget):
            stopped.append(result)
        elif isinstance(result, Blocked):
            blocked.append(result)
        else:
            ready.append(result)
    return ready, stopped, failed, blocked


def _pull_of(item: Item) -> int | None:
    """The number of the draft pull request that the item's record holds, if it is a number."""
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    return int(recorded) if recorded.isdigit() else None


def _foreign_commits(source: Path, branch: str) -> int:
    """How many commits `origin/<branch>` holds past the default branch whose author is not the
    identity the clone commits as. A clean merge by a person is not counted (#3392)."""
    own = _git(source, "config", "user.name")
    authors = branch_authors(source, branch, operation=_GIT_OPERATION)
    return sum(1 for author in authors if author != own)


def _reconcile(
    store: RoadmapStore, source: Path, remote_heads: str
) -> tuple[tuple[Removal, ...], tuple[KeptBranch, ...]]:
    """Judge the staged branch of each closed item whose record holds one: removed when the
    branch is gone or every commit past the default branch is the clone identity's or a clean
    merge by a person, else kept."""
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


def _orphans(
    store: RoadmapStore, source: Path, remote_heads: str, now: datetime
) -> tuple[tuple[Removal, ...], tuple[KeptBranch, ...]]:
    """Judge the orphan of each open item that holds the intent mark `stage.pending` and no
    pull request, when the mark is old enough (#4051). The branch is the one the mark names. It is
    removed when it is gone or every commit past the default branch is the clone identity's, else
    kept. A pushed branch with no mark is never judged."""
    pushed = set(remote_branches(remote_heads))
    removals: list[Removal] = []
    kept: list[KeptBranch] = []
    for item in store.items():
        if (pending := orphan_mark(item, now)) is None:
            continue
        branch = pending.branch
        if branch not in pushed:
            removals.append(Removal(item, branch, None, gone=True, orphan=True))
        elif (foreign := _foreign_commits(source, branch)) == 0:
            removals.append(Removal(item, branch, None, orphan=True))
        else:
            reason = MESSAGES.roadmap.stage_kept_reason.format(count=foreign)
            kept.append(KeptBranch(item.number, branch, reason))
    return tuple(removals), tuple(kept)


class Rejections(NamedTuple):
    """The plans that a person closed with no merge, the staged branches that the job keeps for
    them, and the items whose plan pull request could not be read."""

    found: tuple[Rejection, ...] = ()
    kept: tuple[KeptBranch, ...] = ()
    failures: tuple[ReadFailure, ...] = ()


def _rejections(
    store: RoadmapStore,
    repo: str,
    source: Path,
    heads: str,
    planned: PlannedChanges,
    item_number: int | None,
) -> Rejections:
    """Find the staged plans that a person closed with no merge (#3503). The staged branch goes
    with the rule of a closed item: it is deleted when every commit past the default branch is the
    identity of the session's or a clean merge by a person, and kept when another author wrote to
    it. The job deletes it only while it ends at the commit judged here. The read writes nothing."""
    pushed = set(remote_branches(heads))
    staged = staged_plans(store.items(), planned, item_number)
    read = closed_plans(store, repo, staged, stop=(*_STOP_THE_RUN, GitHubRateLimitError))
    found: list[Rejection] = []
    kept: list[KeptBranch] = []
    for closed in read.closed:
        plan, comment = closed.rejection()
        branch = closed.item.job_record.get(StageRecordKey.BRANCH) or ""
        delete, tip = None, ""
        if branch in pushed:
            if (foreign := _foreign_commits(source, branch)) == 0:
                delete, tip = branch, _git(source, "rev-parse", f"origin/{branch}")
            else:
                reason = MESSAGES.roadmap.stage_kept_reason.format(count=foreign)
                kept.append(KeptBranch(closed.item.number, branch, reason))
        found.append(Rejection(closed.item, plan, comment, delete, tip))
    return Rejections(tuple(found), tuple(kept), read.failures)


def _heads_after(heads: str, rejections: Iterable[Rejection]) -> str:
    """The heads of `origin` (`git ls-remote --heads`) without the branches that the writes of
    `rejections` delete. An item whose branch the run deletes is no more held by it, so a run can
    stage the item at once."""
    deleted = {found.branch for found in rejections if found.branch is not None}
    return "\n".join(
        line for line in heads.splitlines() if not deleted.intersection(remote_branches(line))
    )


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
    rejected: Mapping[int, RejectedPlan] | None = None,
) -> StageRead:
    """Select the items to stage in the clone `source`, with no model call and no write to git or
    to GitHub. `plan_stage` and `devops roadmap explain` read the selection through this one
    function. A caller that read the heads of `origin` or the plans already passes them in, so
    that a command that judges both jobs reads each once. The staged commit is the default branch
    of `origin` after the fetch, not the HEAD of the clone (#3301)."""
    inspect_checkout(source, repo)  # refuses a clone whose origin is not `repo`
    heads = read_remote_heads(source) if heads is None else heads
    planned = read_planned_changes(source, operation=_GIT_OPERATION) if planned is None else planned
    sha = _git(source, "rev-parse", f"origin/{planned.default}")
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
        rejected=rejected,
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
    verifier: ToolboxModel | None = None,
    why: bool = False,
    now: datetime | None = None,
    writer: StageWriter | None = None,
) -> StagePlan:
    """Plans the stage of up to `limit` items. It writes nothing unless the caller gives a
    `writer`: the writer then gets the removals and the rejections of the items the round does not
    select before the first plan call, and the result of each selected item as soon as that item
    is done, so a stop of the Service loses at most the item in progress (#4034). When an item is
    selected, the clone moves to the staged commit, the default branch of `origin` after the fetch
    (#3301).

    `source` is the clone of the repository, at the default branch. `limit` and `step_tokens`
    override `roadmap.stage.limit` and `roadmap.stage.step_tokens`. At `roadmap.stage.planned_limit`
    Planned items the plan holds only P0 and P1 items (#3487, #3692). A client as `model` replaces
    the client of the `analysis` task and plans with the one call and no tool. A `ToolboxModel`
    plans with the read-only tools (#3037), and the client of the `analysis` task answers the call
    that splits the groups. A `verifier`, the model of the `verification` task, makes an agent with
    the read-only tools review each plan after the checks (#3153, #3039); without one, the job makes
    no review call, as the golden-set run of the planner does. With `why`, the plan also lists the
    open items that the filter does not name (#2911). An item that failed less than
    the wait of its failure class before `now` is left out, unless `item_number` names it
    (#3493).
    """
    checkout = Path(source)
    settings = load_settings()
    inspect_checkout(checkout, repo)  # refuses a clone whose origin is not `repo`
    heads = read_remote_heads(checkout)
    planned = read_planned_changes(checkout, operation=_GIT_OPERATION)
    rejections = _rejections(store, repo, checkout, heads, planned, item_number)
    with observe_step(repo, _ROW, StepName.SELECT):
        sha, heads, planned, selection = read_stage_selection(
            store,
            repo=repo,
            source=checkout,
            filters=filters,
            limit=limit or settings.roadmap.stage.limit,
            planned_limit=settings.roadmap.stage.planned_limit,
            item_number=item_number,
            heads=_heads_after(heads, rejections.found),
            planned=planned,
            now=now,
            rejected={found.number: found.plan for found in rejections.found},
        )
    budget = step_tokens or settings.roadmap.stage.step_tokens
    removals, kept = _reconcile(store, checkout, heads)
    orphans, orphans_kept = _orphans(store, checkout, heads, now or datetime.now(UTC))
    unmatched = unmatched_items(store, filters) if why and item_number is None else ()
    plan = StagePlan(
        repo,
        sha,
        budget,
        left_out=selection.left_out,
        removals=(*removals, *orphans),
        kept=(*kept, *orphans_kept, *rejections.kept),
        planned=planned,
        unmatched=unmatched,
        failed=tuple(_write_failure(f.item, f.error) for f in rejections.failures),
        rejections=rejections.found,
    )
    if writer is not None:
        writer.begin(plan, {target.item.number for target in selection.selected})
    if not selection.selected:
        return plan
    _move_clone(checkout, sha)
    toolbox = model if isinstance(model, ToolboxModel) else None
    client: StageClient
    if isinstance(model, ToolboxModel) or model is None:
        client = get_llm_client(task="stage", settings=settings)
    else:
        client = model
    creators = cache(partial(open_plan_creates, store, checkout, planned, operation=_GIT_OPERATION))
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
            plan_files=PlanFiles(
                repo, settings.ai.for_task("stage").model, settings.roadmap.stage.toolset
            ),
            open_creates=creators,
            rejected={
                **{found.number: stage_comment_text(found.comment) for found in rejections.found},
                **reasons_of(store, (target.item for target in selection.selected)),
            },
        )
        ready, stopped, failed, blocked = _plan_each(planner, selection.selected, writer)
    return replace(
        plan,
        ready=tuple(ready),
        over_budget=tuple(stopped),
        failed=(*plan.failed, *failed),
        blocked=tuple(blocked),
    )


def _planner_of(
    client: StageClient,
    checkout: Path,
    sha: str,
    *,
    budget: int,
    tool: OpenSpecTool | None,
    toolbox: ToolboxModel | None = None,
    verifier: ToolboxModel | None = None,
    repo: str | None = None,
    open_creates: Callable[[], Mapping[str, int]] | None = None,
    rejected: Mapping[int, str] | None = None,
    plan_files: PlanFiles | None = None,
) -> _Planner:
    """The planner for the checkout at `sha`: it reads the tracked files, the capabilities and the
    context window of the `stage` task once. With a `toolbox` model, a plan run calls the
    read-only tools on the checkout, and `client` answers the other calls. The toolset
    `roadmap.stage.toolset` chooses the tools; with `repo`, `read_issue` and `find_issues` of the
    toolset `extended` read that repository on GitHub with the client of the session (#3238). A
    `verifier` makes the model review of each plan (#3153): an agent of the task `verification`
    with the same tools, and with the window of that task, because the two tasks can resolve to
    different windows (#3039). `rejected` holds the reason of each rejected plan by issue number,
    for the request of an item that a person rejected (#3503)."""
    window = task_window("stage")
    verify_window = task_window("verification")
    traces: list[RunTrace] = []

    def runner_of(model: ToolboxModel, tokens: int) -> ToolboxClient:
        return ToolboxClient(
            model.model,
            client,
            checkout,
            sha,
            window=tokens,
            openspec=tool,
            github=None if repo is None else StageGitHub(repo),
            traces=traces,
        )

    runner = None if toolbox is None else runner_of(toolbox, window)
    # A review makes only agent runs, so the client of the job as its inner client gets no call.
    reviewer = None if verifier is None else runner_of(verifier, verify_window)
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
        verifier=reviewer,
        verify_window=verify_window,
        pull_reads=None if repo is None else session_pull_reads,
        pull_repo=repo or "",
        grep=partial(grep_at, checkout, sha, operation=_GIT_OPERATION),
        open_creates=open_creates,
        traces=traces,
        rejected=rejected,
        plan_files=plan_files,
    )


def plan_item(
    item: Item,
    *,
    client: StageClient,
    checkout: Path,
    sha: str,
    step_tokens: int | None = None,
) -> StagedChange | OverBudget:
    """Plans `item` as the job does, in the checkout at `sha`, and writes nothing (#3028).

    The golden set of the stage job runs this on each case. A reply the checks refuse goes back to
    the model once, as in a run, and a second one raises `RoadmapStageError`. `step_tokens`
    overrides `roadmap.stage.step_tokens`. A `client` that is a `ToolboxClient` plans with the
    read-only tools (#3037); the golden set builds it for the case checkout. This planner reads no
    open plan, so it finds no dependency. A dependency that the type still allows raises
    `RoadmapStageError`, which the golden set counts as refused (#3418).
    """
    budget = step_tokens or load_settings().roadmap.stage.step_tokens
    target = _target_of(item)
    with openspec_tool() as tool:
        planner = _planner_of(client, checkout, sha, budget=budget, tool=tool)
        outcome = planner.plan(target)
    if isinstance(outcome, Blocked):
        issues = ", ".join(f"#{number}" for number in outcome.blockers)
        raise _stage_error(MESSAGES.roadmap.stage_left_blocked.format(issues=issues), target)
    return outcome


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
    """What a run wrote: the items it staged, the items it stopped on a group over the budget, and
    the items whose writes failed."""

    staged: tuple[int, ...] = ()
    stopped: tuple[int, ...] = ()
    failed: tuple[StageFailure, ...] = ()
    removed: tuple[int, ...] = ()
    returned: tuple[int, ...] = ()
    rejected: tuple[int, ...] = ()


def _git(cwd: Path, *args: str) -> str:
    """The output of `git <args>` in `cwd` for the stage job."""
    return git(cwd, *args, operation=_GIT_OPERATION)


def _read_staged_file(source: Path, sha: str, path: str) -> str | None:
    """The text of `path` at the staged commit `sha`, or None when that commit holds no such file
    (#3422). The citation check reads the commit that the job plans on, and not the working tree,
    whose lines can differ from that commit."""
    shown, content = git_result(source, "show", f"{sha}:{path}")
    return content if shown == 0 else None


def _probe_reference_files(source: Path, sha: str, name: str) -> list[str]:
    """The files of the staged commit that hold `name` from `git grep` with no cap (#3373)."""
    try:
        output = git(
            source, "grep", "-n", "-I", "-F", "-e", name, sha, "--", operation=_GIT_OPERATION
        )
    except GitOperationError:
        return []
    return reference_files(output, sha)


def _move_clone(checkout: Path, sha: str) -> None:
    """Move the clone to the staged commit with a fast-forward, so that its HEAD, its index and
    its files are that commit. The toolbox refuses any other HEAD (#3301). A clone that has
    diverged from `origin` fails with the reason of git. Git merges a clone that is ahead of `sha`
    as up to date and keeps its HEAD, so the job also checks HEAD and fails there. The job never
    plans on a commit it did not read.
    """
    _git(checkout, "merge", "--ff-only", "-q", sha)
    if _git(checkout, "rev-parse", "HEAD") != sha:
        raise GitOperationError(
            MESSAGES.roadmap.stage_clone_ahead.format(sha=sha), operation=_GIT_OPERATION
        )


@contextmanager
def _worktree(source: Path, target: StageTarget, base: str) -> Iterator[Path]:
    """The worktree of the item's branch, which starts at the staged commit `base`. The worktree
    and the local branch go when the block ends, so the clone keeps its HEAD and holds no issue."""
    report = add_worktree(
        source, issue=target.item.number, type_=target.type_, slug=target.slug, base=base
    )
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
    """The report of the plan runs of an item: the counts, each tool call in order, and one line
    of the calls and the empty answers of each tool (#3240). It is empty for an item that was
    planned with one call, which made no run of the toolbox."""
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
    else:
        listed = texts.stage_comment_no_calls.format(
            offered=sum(1 for tools in trace.offered if tools), requests=len(trace.offered)
        )
    counts = ", ".join(
        texts.stage_comment_tool_count.format(name=name, calls=made, empty=empty)
        for name, (made, empty) in trace.tool_counts().items()
    )
    return texts.stage_comment_run.format(
        requests=trace.requests,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        calls=listed,
    ) + (texts.stage_comment_tool_counts.format(counts=counts) if counts else "")


def _named_paths(change: StagedChange) -> list[str]:
    """The paths that the plan of `change` names: the reads and the changes of each group, once
    each, in the order of the groups (#3309)."""
    return list(
        dict.fromkeys(
            path
            for measured in change.groups
            for path in (*measured.group.reads, *measured.group.changes)
        )
    )


def _moved_section(moved: Sequence[MovedPath]) -> str:
    """The section of the comment that lists the named paths that the default branch changed after
    the base commit of the plan, each with its commits (#3309). It is empty when no path moved."""
    if not moved:
        return ""
    texts = MESSAGES.roadmap
    lines = "\n".join(
        texts.stage_comment_moved_path.format(
            path=entry.path, commits="; ".join(safe_text(commit) for commit in entry.commits)
        )
        for entry in moved
    )
    return f"{texts.stage_comment_moved}{lines}"


def _moved_for(checkout: Path, sha: str, change: StagedChange) -> tuple[MovedPath, ...]:
    """The named paths of `change` that the default branch changed after the base commit `sha`
    (#3309). The default branch is fetched for each item, just before its publish, so the
    comparison holds a commit that landed during the plans of the earlier items. A run with no
    base commit to compare reads no git."""
    if not sha:
        return ()
    default = default_branch(checkout, operation=_GIT_OPERATION)
    _git(checkout, "fetch", "-q", "origin", default)
    return tuple(moved_paths(checkout, sha, f"origin/{default}", _named_paths(change)))


def _warnings_section(warnings: Sequence[str]) -> str:
    """The section of the comment that lists warnings, or empty text for none (#3324)."""
    if not warnings:
        return ""
    lines = "\n".join(f"- {w}" for w in warnings)
    return MESSAGES.roadmap.stage_comment_warnings.format(warnings=lines)


def _notes(change: StagedChange, moved: Sequence[MovedPath] = ()) -> str:
    """The notes that end the comment of a staged item: the named paths that moved first, then the
    open findings, the other findings, the report of the plan runs, the read of the open pull
    requests, and a validation that did not run (#3309, #3264, #3252)."""
    unvalidated = "" if change.validated else MESSAGES.roadmap.stage_comment_not_validated
    read = (
        MESSAGES.roadmap.stage_comment_overlaps.format(requests=change.pulls_requests)
        if change.pulls_requests
        else ""
    )
    advisory = tuple(finding for finding in change.findings if finding not in change.open_findings)
    warnings = _warnings_section(change.warnings)
    return (
        _moved_section(moved)
        + open_findings_section(change.open_findings)
        + findings_section(advisory)
        + _run_report(change.trace)
        + read
        + unvalidated
        + warnings
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


def _stage_one(
    store: RoadmapStore,
    repo: str,
    source: Path,
    base: str,
    change: StagedChange,
    moved: Sequence[MovedPath],
    now: datetime,
) -> None:
    """Make the branch, the commit, the push and the draft of one item, then record them and
    post the one comment. The branch starts at the staged commit `base` (#3301). The Status of the
    item stays as it is. `moved` is the named paths that the default branch changed after `base`
    (#3309). The intent mark `stage.pending` goes first, before the push, so that a later round
    finds the branch if the record write fails or the worker dies (#4051); the record clears it."""
    target = change.target
    source_warnings = _check_removal_references(source, target, change.files)
    if source_warnings and not change.warnings:
        change = replace(change, warnings=source_warnings)
    with _worktree(source, target, base) as path:
        store.set_marks(
            target.item,
            {StageRecordKey.PENDING: PendingStage(branch=target.branch, time=now).record},
        )
        sha = _commit_and_push(path, change)
        pull = _open_pull(repo, source, change)
    store.set_marks(
        target.item,
        {
            StageRecordKey.BRANCH: target.branch,
            StageRecordKey.PR: str(pull.number),
            StageRecordKey.SHA: sha,
            StageRecordKey.GROUPS: _groups_recorded(change.groups),
            StageRecordKey.TEXT_HASH: body_hashes(target.item.body)[0],
            StageRecordKey.NEEDS_SPLIT: None,
            StageRecordKey.FILE_CAP: None,
            StageRecordKey.FAILED_AT: None,
            StageRecordKey.FAILED_ERROR: None,
            StageRecordKey.FAILED_STEP: None,
            StageRecordKey.FAILED_CLASS: None,
            StageRecordKey.REJECTED: None,
            StageRecordKey.PENDING: None,
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
            notes=f"{_notes(change, moved)}{label_note}",
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
            StageRecordKey.FAILED_STEP: None,
            StageRecordKey.FAILED_CLASS: None,
        },
    )


def _write_failure(item: Item, exc: DevOpsCLIError) -> StageFailure:
    """The failure of a write: the error's class and its message, credentials masked."""
    return StageFailure(
        item.number,
        item.title,
        type(exc).__name__,
        mask_secrets(str(exc)),
        item,
        failure_class=failure_class_of(exc),
        step=StepName.APPLY,
    )


def _remove_staged(store: RoadmapStore, repo: str, source: Path, removal: Removal) -> None:
    """Close the draft of a closed item and delete its branch, then clear the item's stage
    record. A branch that is gone needs only the record cleared."""
    if not removal.gone:
        if removal.pull is not None:
            get_github_session().client.close_pull(repo, removal.pull)
        _git(source, "push", "origin", "--delete", removal.branch)
    store.set_marks(removal.item, {key: None for key in StageRecordKey})


def _delete_rejected_branch(source: Path, branch: str, tip: str) -> None:
    """Delete `branch` of `origin` while it ends at `tip`, the commit that the plan judged. A
    commit that someone pushed since keeps the branch: the lease refuses the delete, and the job
    goes on with the rest of the rejection (#3503). A refused delete with the branch at `tip` is a
    real failure and stops the item."""
    try:
        ref = f"refs/heads/{branch}"
        _git(source, "push", f"--force-with-lease={ref}:{tip}", "origin", f":{ref}")
    except GitOperationError:
        remote = _git(source, "ls-remote", "--heads", "origin", f"refs/heads/{branch}").split()
        if remote and remote[0] == tip:
            raise
        if remote:
            logger.warning("The branch %s changed after the plan judged it, so it stays.", branch)


def _reject_plan(store: RoadmapStore, source: Path, rejection: Rejection, *, staged: bool) -> None:
    """Write a rejected plan (#3503): delete the staged branch, post the comment with the reason,
    then record the rejection and clear every other stage key. The branch goes first and the
    comment second, so a failed write never leaves a record that no one was told about, and the
    next run tries the whole rejection again. The item returns to New, unless the same run stages
    it (`staged`): then its Status stays as it is."""
    if rejection.branch is not None:
        _delete_rejected_branch(source, rejection.branch, rejection.branch_sha)
    store.comment(rejection.number, rejection.comment)
    marks = {key: None for key in StageRecordKey} | {StageRecordKey.REJECTED: rejection.plan.record}
    if staged or rejection.item.status == CONST_ROADMAP_STATUS_NEW:
        store.set_marks(rejection.item, marks)
    else:
        store.set_field(rejection.item, ItemField.STATUS, CONST_ROADMAP_STATUS_NEW, marks=marks)


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


def _return_blocked(store: RoadmapStore, blocked: Blocked) -> None:
    """Return the item to New with its open blockers in `refine.blocked_by`, and say why in a
    comment (#3418). Refine waits on that record until each blocker closes, and the stage
    selection leaves the item out meanwhile."""
    texts = MESSAGES.roadmap
    item = blocked.target.item
    issues = ", ".join(f"#{number}" for number in blocked.blockers)
    paths = ", ".join(f"`{path}`" for path in blocked.paths)
    store.comment(
        item.number,
        f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n\n"
        f"{texts.stage_returned_blocked.format(issues=issues, paths=paths)}",
    )
    marks = {
        RefineRecordKey.BLOCKED_BY: ",".join(str(number) for number in blocked.blockers),
        RefineRecordKey.NEXT_STEP: NextStep.BLOCKED.value,
    }
    store.set_field(item, ItemField.STATUS, CONST_ROADMAP_STATUS_NEW, marks=marks)


def _record_failures(store: RoadmapStore, failures: Sequence[StageFailure], now: datetime) -> None:
    """Record each failure in the job record of its item: the time, the type of the error (#3493),
    the step and the failure class (#4056), in one write. The item waits for the wait of its class, and the job goes on with the others. A
    write that fails here is no failure of an item: it ends the run, and the round counts it."""
    for failure in failures:
        if failure.item is not None:
            store.set_marks(
                failure.item,
                {
                    StageRecordKey.FAILED_AT: now.isoformat(),
                    StageRecordKey.FAILED_ERROR: failure.error,
                    StageRecordKey.FAILED_STEP: failure.step.value,
                    StageRecordKey.FAILED_CLASS: failure.failure_class.value,
                },
            )


class StageWriter:
    """The writes of one stage round, made when each item is done (#4034).

    `plan_stage` calls `begin` once, and `settle` for each selected item as soon as the item is
    planned. A stop of the Service then ends the round and loses at most the item in progress.
    `begin` removes the staged branches of closed items and writes the rejected plans of the items
    the round does not select (#3503): these need no model. `settle` writes the rejection of a
    selected item between its plan and its publish, then the result of the item, and reads the
    moved paths of the item just before its publish. A write that fails stops its item, and the
    others go on; rejected GitHub credentials stop the run. Each item that failed, in the plan or
    in a write, gets the time and the error class in its job record, and the job leaves it for
    the wait of its failure class (#3493, #4060). The stop of the Service stops the run too, but it is
    no failed item: the failures before it are recorded, and the run ends with the stop (#2753).
    """

    def __init__(self, store: RoadmapStore, source: Path | str, *, now: datetime | None = None):
        self._store = store
        self._source = Path(source)
        self._now = now
        self._repo = ""
        self._sha = ""
        self._rejections: dict[int, Rejection] = {}
        self._removed: list[int] = []
        self._rejected: list[int] = []
        self._returned: list[int] = []
        self._staged: list[int] = []
        self._stopped: list[int] = []
        self._failed: list[StageFailure] = []

    def applied(self) -> StageApplied:
        """What the round wrote so far."""
        return StageApplied(
            tuple(self._staged),
            tuple(self._stopped),
            tuple(self._failed),
            tuple(self._removed),
            tuple(self._returned),
            tuple(self._rejected),
        )

    def begin(self, plan: StagePlan, selected: Collection[int]) -> None:
        """Write what needs no model: the removals, the rejections of the items outside `selected`
        and the failures that `plan` holds. A rejection of a selected item waits for its plan."""
        self._repo, self._sha = plan.repo, plan.sha
        self._rejections = {r.number: r for r in plan.rejections if r.number in selected}
        drafts = cache(self._draft_heads)
        with self._recording(plan.failed):
            write_each(
                [(r.item, partial(self._remove, plan.repo, r, drafts)) for r in plan.removals],
                self._removed,
                self._failed,
            )
            write_each(
                [
                    (
                        r.item,
                        partial(_reject_plan, self._store, self._source, r, staged=False),
                    )
                    for r in plan.rejections
                    if r.number not in selected
                ],
                self._rejected,
                self._failed,
            )

    def _draft_heads(self) -> dict[str, int]:
        """The number of the open pull request of each head branch: one read for the round."""
        drafts: dict[str, int] = {}
        for pull in self._store.open_pulls():
            drafts.setdefault(pull.head_ref, pull.number)
        return drafts

    def _remove(self, repo: str, removal: Removal, drafts: Callable[[], Mapping[str, int]]) -> None:
        """Remove a staged branch. The draft of an orphan is not in the record, so it is found by
        its head branch in the one read of the open pull requests (#4051)."""
        if removal.orphan and not removal.gone:
            removal = replace(removal, pull=drafts().get(removal.branch))
        _remove_staged(self._store, repo, self._source, removal)

    def settle(
        self, target: StageTarget, result: StagedChange | OverBudget | Blocked | StageFailure
    ) -> None:
        """Write the result of one selected item: its rejection, if a person rejected its plan,
        then the branch and the draft pull request of a change, the stop on the budget, the return
        for open blockers, or the record of a failure."""
        with self._recording((result,) if isinstance(result, StageFailure) else ()):
            self._settle(target.item, result)

    def _settle(
        self, item: Item, result: StagedChange | OverBudget | Blocked | StageFailure
    ) -> None:
        store, source = self._store, self._source
        if (rejection := self._rejections.pop(item.number, None)) is not None:
            staged = isinstance(result, StagedChange)
            write_each(
                [(item, partial(_reject_plan, store, source, rejection, staged=staged))],
                self._rejected,
                self._failed,
            )
        if isinstance(result, StagedChange):
            write_each([(item, partial(self._stage, result))], self._staged, self._failed)
        elif isinstance(result, OverBudget):
            write_each(
                [(item, partial(_stop_on_budget, store, result))], self._stopped, self._failed
            )
        elif isinstance(result, Blocked):
            write_each(
                [(item, partial(_return_blocked, store, result))], self._returned, self._failed
            )

    def _stage(self, change: StagedChange) -> None:
        with observe_step(self._repo, _ROW, StepName.APPLY):
            moved = _moved_for(self._source, self._sha, change)
            now = self._now or datetime.now(UTC)
            _stage_one(self._store, self._repo, self._source, self._sha, change, moved, now)
        # The item is staged, so its plan has no more use. A failed write raised above and kept it.
        delete_plan_record(plan_record_path(self._repo, change.target.item.number))

    @contextmanager
    def _recording(self, planned: Iterable[StageFailure]) -> Iterator[None]:
        """Record the failures of the plan and the failures of the writes made in the block. The
        stop of the Service leaves its own write undone, so the failures that came before are
        recorded first and the stop goes on (#2753). Rejected credentials record nothing."""
        mark = len(self._failed)
        try:
            yield
        except ServiceStoppingError:
            self._record(planned, mark)
            raise
        self._record(planned, mark)

    def _record(self, planned: Iterable[StageFailure], mark: int) -> None:
        _record_failures(
            self._store, [*planned, *self._failed[mark:]], self._now or datetime.now(UTC)
        )


class StageResult(StrEnum):
    """How a run handled an item, as `devops_cli_roadmap_stage_total` labels it."""

    STAGED = "staged"
    NEEDS_SPLIT = "needs_split"
    FAILED = "failed"
    SKIPPED = "skipped"


def stage_results(plan: StagePlan, applied: StageApplied) -> dict[int, StageResult]:
    """The result of each item a run handled, by issue number. A write that failed moves its item
    from staged or needs_split to failed, so an item has one result (#2659). An item staged with
    an open finding is a failed attempt, so the round counts no staged plan (#3264)."""
    results = dict.fromkeys((left.number for left in plan.left_out), StageResult.SKIPPED)
    results |= dict.fromkeys(applied.staged, StageResult.STAGED)
    results |= dict.fromkeys(applied.stopped, StageResult.NEEDS_SPLIT)
    results |= dict.fromkeys(applied.returned, StageResult.SKIPPED)
    results |= dict.fromkeys(applied.rejected, StageResult.SKIPPED)
    results |= dict.fromkeys(
        (failure.number for failure in (*plan.failed, *applied.failed)), StageResult.FAILED
    )
    open_items = {change.target.item.number for change in plan.ready if change.open_findings}
    results |= dict.fromkeys(
        (number for number in applied.staged if number in open_items), StageResult.FAILED
    )
    return results


def emit_stage_results(plan: StagePlan, applied: StageApplied, repo: str = "") -> None:
    """Add 1 to `devops_cli_roadmap_stage_total` for each item of a run that wrote, by repository
    and result (#2659, #3069). A plan with no write counts nothing."""
    for result in stage_results(plan, applied).values():
        emit(ROADMAP_STAGE_TOTAL, 1, {"result": result.value, "repo": repo})


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
    if plan.sha:
        lines.append(texts.stage_staged_commit.format(sha=plan.sha))
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
    rejected = [
        texts.stage_rejected_line.format(
            number=r.number,
            pull=r.plan.pull,
            note=texts.stage_rejected_deletes.format(branch=r.branch) if r.branch else "",
        )
        for r in plan.rejections
    ]
    lines += _section(texts.stage_heading_ready, ready)
    lines += _section(texts.stage_heading_over, over)
    lines += _section(texts.stage_heading_left, left)
    lines += _section(
        texts.item_heading_unmatched,
        [
            texts.stage_left_line.format(number=x.number, title=x.title, reason=x.reason)
            for x in plan.unmatched
        ],
    )
    returned = [
        texts.stage_returned_line.format(
            number=b.target.item.number,
            title=b.target.item.title,
            issues=", ".join(f"#{number}" for number in b.blockers),
        )
        for b in plan.blocked
    ]
    lines += _section(texts.stage_heading_returned, returned)
    lines += _section(texts.stage_heading_rejected, rejected)
    lines += _section(texts.stage_heading_failed, failed)
    lines += _section(texts.stage_heading_removals, removals)
    lines += _section(texts.stage_heading_kept, kept)
    if not (ready or over or left or failed or removals or kept or returned or rejected):
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
    on the budget (#3493). An item that failed while another was handled is
    recorded in its own job record and waits for the wait of its failure class, so it does not
    count against the repository. A round that tried no item does not fail."""
    if applied.staged or applied.stopped:
        return
    raise_for_failed([*plan.failed, *applied.failed])


__all__ = [
    "KeptBranch",
    "LeftOut",
    "OverBudget",
    "PlannedQueue",
    "Rejection",
    "Removal",
    "StageApplied",
    "StageFailure",
    "StageFilter",
    "StagePlan",
    "StageRead",
    "StageResult",
    "StageSelection",
    "StageTarget",
    "StageWriter",
    "StagedChange",
    "Walk",
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
    "task_window",
    "unmatched_items",
    "walk_named",
    "write_each",
]
