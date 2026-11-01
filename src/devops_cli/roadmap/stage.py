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
item whose title gives no branch name, an item whose text looks like a secret, and an item whose
record holds `stage.needs_split` made with the file cap of now (`stage.file_cap`): a stop under
another measure does not count. A run takes at most `--limit`
items, highest priority first. `--item` takes the one item it names when that item is open and
Ready.

**Plan.** For each item the job asks the model for one `StageProposal` (`ai.for_task("analysis")`,
prompt `roadmap_stage_change.md`), measures each task group (`stage_change.measure_groups`) and
asks once for a split of the groups over `--step-tokens`. A group costs what its step reads: the
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
way. `plan_item` plans one item with a given client and checkout: the golden set of the job runs
it on each case (`stage_eval_run`, #3028). The plan writes nothing to git or to GitHub. A model call that fails skips its item; rejected
credentials stop the run.

**Why.** `--why` adds to the plan the open items that the filter does not name, under their own
heading, each with the family it misses (`StageFilter.mismatch`). They are not "left out": no rule
of the job judged them. `devops roadmap explain` gives the reason of one issue (#2911).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
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
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_PRIORITY_VALUES,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_TRUSTED_AUTHORS,
)
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import (
    DevOpsCLIError,
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
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import branch_authors, default_branch, git
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.planned import PlannedChanges, read_planned_changes
from devops_cli.roadmap.refine import body_dependencies, collect_context, inspect_checkout
from devops_cli.roadmap.stage_change import (
    MeasuredGroup,
    StageProposal,
    StageSplit,
    check_proposal,
    closing_keyword_in,
    measure_groups,
    pull_request_body,
    render_change,
    safe_text,
    staging_title,
    write_change_files,
)
from devops_cli.roadmap.stage_filter import split_filter_entry
from devops_cli.roadmap.stage_paths import StagedTree, path_problems
from devops_cli.roadmap.stage_validate import validate_change
from devops_cli.roadmap.store import GitHubState, Item, RoadmapStore, StageRecordKey
from devops_cli.security.sanitizer import mask_secrets, redact_text
from devops_cli.telemetry.instruments import ROADMAP_STAGE_TOTAL, emit

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
    ) -> None:
        self._store = store
        self._holder_of = holder_of
        self._planned = planned

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
            checks.append(self._recorded_split)
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
        if commit_type(item.title) is None:
            return MESSAGES.roadmap.stage_left_title_type
        return None if _slug_of(item.title) else MESSAGES.roadmap.stage_left_title_slug

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

    def _recorded_split(self, item: Item) -> str | None:
        detail = item.job_record.get(StageRecordKey.NEEDS_SPLIT)
        cap = item.job_record.get(StageRecordKey.FILE_CAP)
        if not detail or cap != str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS):
            return None
        return MESSAGES.roadmap.stage_left_recorded_split.format(detail=detail, number=item.number)


def _target_of(item: Item) -> StageTarget:
    """The target of an item whose title gives a branch name (`_Judge._title`)."""
    return StageTarget(item, commit_type(item.title) or "", _slug_of(item.title))


def priority_order(item: Item) -> tuple[int, int]:
    """The sort key of an item: highest priority first, then the lowest number."""
    values = CONST_ROADMAP_PRIORITY_VALUES
    rank = values.index(item.priority) if item.priority in values else len(values)
    return rank, item.number


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
    item_number: int | None = None,
    probe: int | None = None,
) -> StageSelection:
    """The items to stage, up to `limit`, and those the filter names that the job leaves out.

    `holder_of` tells who holds an issue and its new `branch` (`worktree_add.issue_holder`), or None. `planned` holds
    the change folders of the default branch (#2714). With `item_number` the filter and the limit
    do not apply. `probe` is the issue that `walk_named` judges also after the limit.
    """
    judge = _Judge(store, holder_of, planned)
    if item_number is not None:
        return _named_item(judge, store, item_number)

    def verdict(item: Item) -> StageTarget | str:
        why = judge.reason(item, named=False)
        return _target_of(item) if why is None else why

    walked = walk_named(named_items(store, filters), verdict, limit, probe=probe)
    return StageSelection(walked.taken, walked.left_out, walked.beyond)


# ── The plan of one item ──────────────────────────────────────────────────────

_CHANGE_TASK: Final[str] = "roadmap_stage_change.md"
_SPLIT_TASK: Final[str] = "roadmap_stage_split.md"
# The model window is shared by the reply, the body of the item and the repository context.
_WINDOW_SHARE_CONTEXT: Final[int] = 2
_WINDOW_SHARE_BODY: Final[int] = 4
_DEFAULT_WINDOW: Final[int] = 8192
# A reply that fails its schema goes back to the model once, with the violations; a second one
# stops the item.
_REPLY_RETURNS: Final[int] = 1
# The model calls of one item at most: the plan, one return of a refused reply, and one split.
CALLS_PER_ITEM_MAX: Final[int] = 3


@dataclass(frozen=True)
class StagedChange:
    """A change ready to write: the target, the title and the body of its draft pull request, the
    files by path from the repository root, the measure of each task group, whether
    `openspec validate` ran on it (it does not without the binary), and the budget of the run."""

    target: StageTarget
    title: str
    body: str
    files: Mapping[str, str]
    groups: tuple[MeasuredGroup, ...]
    validated: bool
    budget: int


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
class StageFailure:
    """An item the job could not plan: the class of the error and why, never the model's text."""

    number: int
    title: str
    error: str
    reason: str = ""


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
        known: frozenset[str],
        tree: StagedTree,
        budget: int,
        window: int,
        tool: OpenSpecTool | None,
    ) -> None:
        self._client = client
        self._source = source
        self._sha = sha
        self._known = known
        self._tree = tree
        self._budget = budget
        self._window = window
        self._tool = tool
        self._today: date = datetime.now(UTC).date()
        # Whether the model split the groups of the item in hand: it does so once for each item.
        self._split_asked = False

    def plan(self, target: StageTarget) -> StagedChange | OverBudget:
        """The change of `target`, or the group that stops it. A reply the checks refuse goes
        back to the model once, with the problem. The model splits the groups at most once, so an
        item costs three model calls at most."""
        self._split_asked = False
        request = self._request(target)
        proposal = self._ask(StageProposal, _CHANGE_TASK, request)
        outcome = self._settle(target, proposal)
        if isinstance(outcome, _Refused):
            again = {
                **request,
                "previous": outcome.reply.model_dump(),
                "problem": outcome.problem,
            }
            proposal = self._ask(StageProposal, _CHANGE_TASK, again)
            outcome = self._settle(target, proposal)
        if isinstance(outcome, _Refused):
            message = MESSAGES.roadmap.stage_invalid.format(problem=outcome.problem)
            raise _stage_error(message, target)
        return outcome

    def _request(self, target: StageTarget) -> dict[str, Any]:
        item = target.item
        return {
            "number": item.number,
            "title": item.title,
            "body": truncate_to_token_limit(item.body, self._window // _WINDOW_SHARE_BODY),
            "context": collect_context(
                self._source, self._sha, item.body, max_tokens=self._window // _WINDOW_SHARE_CONTEXT
            ),
            "capabilities": sorted(self._known),
            "budget": self._budget,
        }

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
        problems = check_proposal(proposal, self._known, self._tree_of(target, proposal))
        if problems:
            return _Refused(" ".join(problems), proposal)
        title = staging_title(target.item.number, proposal.summary)
        body = pull_request_body(target.item.number, target.change, proposal)
        keyword = closing_keyword_in(f"{title}\n{body}")
        if keyword is not None:
            raise _stage_error(MESSAGES.roadmap.stage_closing.format(keyword=keyword), target)
        asked, files, measured = self._fit(target, proposal)
        if asked is not proposal:
            # The split gave new groups, and the model can bring old paths back with them.
            problems = path_problems(asked.groups, self._tree.with_files(files))
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
        }
        split = self._ask(StageSplit, _SPLIT_TASK, asked)
        proposal = proposal.model_copy(update={"groups": split.groups})
        files, measured = self._build(target, proposal)
        return proposal, files, measured

    def _validate(self, change: str, files: Mapping[str, str]) -> str | None:
        """The problems that `openspec validate` finds in `files`, or None when it finds none or
        the tool is not installed."""
        if self._tool is None:
            return None
        return validate_change(self._tool, self._source, change, files)


def capabilities_of(source: Path) -> frozenset[str]:
    """The names of the specs under `openspec/specs/` of the checkout."""
    specs = source / "openspec" / "specs"
    return (
        frozenset(p.name for p in specs.iterdir() if p.is_dir()) if specs.is_dir() else frozenset()
    )


@contextmanager
def _openspec_tool() -> Iterator[OpenSpecTool | None]:
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
    return StageFailure(target.item.number, target.item.title, type(exc).__name__, reason)


def _plan_each(
    planner: _Planner, targets: Iterable[StageTarget]
) -> tuple[list[StagedChange], list[OverBudget], list[StageFailure]]:
    ready: list[StagedChange] = []
    stopped: list[OverBudget] = []
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
        else:
            ready.append(outcome)
    return ready, stopped, failed


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
    item_number: int | None = None,
    probe: int | None = None,
    heads: str | None = None,
    planned: PlannedChanges | None = None,
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
        probe=probe,
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
    model: LLMClient | None = None,
    why: bool = False,
) -> StagePlan:
    """Plans the stage of up to `limit` items without a write to git or to GitHub.

    `source` is the clone of the repository, at the default branch. `limit` and `step_tokens`
    override `roadmap.stage.limit` and `roadmap.stage.step_tokens`; `model` overrides the client
    of the `analysis` task. With `why`, the plan also lists the open items that the filter does
    not name (#2911).
    """
    checkout = Path(source)
    settings = load_settings()
    sha, heads, planned, selection = read_stage_selection(
        store,
        repo=repo,
        source=checkout,
        filters=filters,
        limit=limit or settings.roadmap.stage.limit,
        item_number=item_number,
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
    client = model or get_llm_client(task="analysis", settings=settings)
    with _openspec_tool() as tool:
        planner = _planner_of(client, checkout, sha, budget=budget, tool=tool)
        ready, stopped, failed = _plan_each(planner, selection.selected)
    return replace(plan, ready=tuple(ready), over_budget=tuple(stopped), failed=tuple(failed))


def _planner_of(
    client: StageClient, checkout: Path, sha: str, *, budget: int, tool: OpenSpecTool | None
) -> _Planner:
    """The planner for the checkout at `sha`: it reads the tracked files, the capabilities and the
    context window of the `analysis` task once."""
    window = load_settings().ai.for_task("analysis").context_window or _DEFAULT_WINDOW
    return _Planner(
        client=client,
        source=checkout,
        sha=sha,
        known=capabilities_of(checkout),
        tree=StagedTree.read(checkout, operation=_GIT_OPERATION),
        budget=budget,
        window=window,
        tool=tool,
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
    overrides `roadmap.stage.step_tokens`.
    """
    budget = step_tokens or load_settings().roadmap.stage.step_tokens
    with _openspec_tool() as tool:
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
    """What a run wrote: the items it staged, the items it stopped on a group over the budget, and
    the items whose writes failed."""

    staged: tuple[int, ...] = ()
    stopped: tuple[int, ...] = ()
    failed: tuple[StageFailure, ...] = ()
    removed: tuple[int, ...] = ()


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


def _notes(change: StagedChange) -> str:
    """The note that ends the comment of a staged item: a validation that did not run."""
    return "" if change.validated else MESSAGES.roadmap.stage_comment_not_validated


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
        },
    )
    texts = MESSAGES.roadmap
    store.comment(
        target.item.number,
        texts.stage_comment_staged.format(
            marker=CONST_ROADMAP_STAGE_COMMENT_MARKER,
            branch=target.branch,
            pull=pull.number,
            budget=change.budget,
            groups=_groups_listed(change.groups),
            notes=_notes(change),
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
        },
    )


def _write_failure(item: Item, exc: DevOpsCLIError) -> StageFailure:
    """The failure of a write: the error's class and its message, credentials masked."""
    return StageFailure(item.number, item.title, type(exc).__name__, mask_secrets(str(exc)))


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


def apply_stage(store: RoadmapStore, plan: StagePlan, *, source: Path | str) -> StageApplied:
    """Writes the plan: removes the staged branches of closed items, stages each ready change,
    and stops each item whose group is over the budget. A write that fails stops its item, and
    the others go on; rejected GitHub credentials stop the run. The stop of the Service stops
    the run too, but it is no failed item: when an item failed before it, the run fails with
    that item (#2753)."""
    checkout = Path(source)
    removed: list[int] = []
    staged: list[int] = []
    stopped: list[int] = []
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
    )
    try:
        for writes, done in phases:
            write_each(writes, done, failed)
    except ServiceStoppingError:
        raise_for_failed([*plan.failed, *failed])
        raise
    return StageApplied(tuple(staged), tuple(stopped), tuple(failed), tuple(removed))


class StageResult(StrEnum):
    """How a run handled an item, as `devops_cli_roadmap_stage_total` labels it."""

    STAGED = "staged"
    NEEDS_SPLIT = "needs_split"
    FAILED = "failed"
    SKIPPED = "skipped"


def stage_results(plan: StagePlan, applied: StageApplied) -> dict[int, StageResult]:
    """The result of each item a run handled, by issue number. A write that failed moves its item
    from staged or needs_split to failed, so an item has one result (#2659)."""
    results = dict.fromkeys((left.number for left in plan.left_out), StageResult.SKIPPED)
    results |= dict.fromkeys(applied.staged, StageResult.STAGED)
    results |= dict.fromkeys(applied.stopped, StageResult.NEEDS_SPLIT)
    results |= dict.fromkeys(
        (failure.number for failure in (*plan.failed, *applied.failed)), StageResult.FAILED
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
    if not (ready or over or left or failed or removals or kept):
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


__all__ = [
    "KeptBranch",
    "LeftOut",
    "OverBudget",
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
    "apply_stage",
    "dry_run_stage",
    "emit_stage_results",
    "named_items",
    "parse_filters",
    "plan_stage",
    "priority_order",
    "raise_for_failed",
    "read_stage_selection",
    "render_stage_plan",
    "select_stageable",
    "stage_results",
    "unmatched_items",
    "walk_named",
    "write_each",
]
