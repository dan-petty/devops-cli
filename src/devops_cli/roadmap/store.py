"""The roadmap store: the one interface roadmap jobs read and write Items, milestones and their
fields through (ADR 0001, ADR 0016).

An Item is an issue of this repository, never a pull request, that holds a `priority/*` label:
intake placed it, or a person did. A Candidate is an open issue that holds none. A Milestone is
a GitHub milestone: a planning bucket with any title. Its number identifies it, so a rename
keeps it, and its due date orders it. Both adapters keep the same promises: reads page through
every result, and a read that cannot complete raises instead of returning an empty or partial
result. No store reads or writes a project board.

**Fields.** Each of an Item's Status, Priority, Value, Effort and Owner is one label family: the label
is the field's name and the value, lower case, with a hyphen for each space (`status/in-progress`
for In Progress). A field has the value of the family's label, or none when the issue holds no
label of the family. A family that holds more than one label has the value the job record does
not name, as the job wrote the other; with more than one such, the first in the family's order.
A job sets a field by replacing every label of the family with the value's label.

**The job record.** Every field write also records the value it set, so a job can tell a person's
change from its own (ADR 0002). The record also holds the marks of refine and of stage on an Item,
which change no field. It is a JSON object in a hidden block at the end of the issue body
(`<!-- devops-roadmap-record {...} -->`): the body every read returns holds no block, and a body
write keeps the issue's block. A block that is not a JSON object reads as an empty record, and
the next record write replaces it.

**Changes.** A write never trusts what the store read: it reads the issue first, and a job's
write of a field someone changed since the store read it raises `RoadmapItemChangedError` before
it changes anything, unless the issue already holds the value it writes, so a job never reverts
a change it did not see (ADR 0002).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol, cast, runtime_checkable

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as MalformedRecordError

from devops_cli.config.constants import (
    CONST_ROADMAP_OWNER_VALUES,
    CONST_ROADMAP_PRIORITY_VALUES,
    CONST_ROADMAP_RECORD_MARKER,
    CONST_ROADMAP_SIZE_OPTIONS,
    CONST_ROADMAP_STATUS_VALUES,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from devops_cli.roadmap.github_store import GhRunner

logger = logging.getLogger(__name__)

# ── Vocabulary ────────────────────────────────────────────────────────────────


class GitHubState(StrEnum):
    """The open or closed state GitHub gives an issue or a milestone."""

    OPEN = "open"
    CLOSED = "closed"


class ItemField(StrEnum):
    """A field of an Item that a job sets and the job record remembers, held by one label
    family.

    Each member's lower-cased name is the attribute that holds it on `Item`, and the prefix of
    its labels.
    """

    STATUS = "Status"
    PRIORITY = "Priority"
    VALUE = "Value"
    EFFORT = "Effort"
    OWNER = "Owner"


FIELD_VALUES: Mapping[ItemField, tuple[str, ...]] = {
    ItemField.STATUS: CONST_ROADMAP_STATUS_VALUES,
    ItemField.PRIORITY: CONST_ROADMAP_PRIORITY_VALUES,
    ItemField.VALUE: CONST_ROADMAP_SIZE_OPTIONS,
    ItemField.EFFORT: CONST_ROADMAP_SIZE_OPTIONS,
    ItemField.OWNER: CONST_ROADMAP_OWNER_VALUES,
}
"""Each field's values, in the order of its label family."""


class CloseReason(StrEnum):
    """Why an issue was closed, named as GitHub's `state_reason` names it."""

    COMPLETED = "completed"
    NOT_PLANNED = "not_planned"
    DUPLICATE = "duplicate"


def already_closed(number: int, details: dict[str, object]) -> GitHubOperationError:
    """The error of a close of issue `number`, which is closed now: GitHub ignores a reason
    unless the state changes, so the close is refused before any write (#1658)."""
    return GitHubOperationError(
        f"#{number} is already closed, and GitHub ignores a reason unless the state changes. "
        f"Reopen it first with `devops gh issues edit {number} --state open`.",
        operation="roadmap.issue.close",
        details=details,
    )


class EvidenceKind(StrEnum):
    """What a piece of evidence for a P0 is (#742): a GitHub security advisory, a failed Actions
    run of this repository, or the commit of this repository that introduced a regression."""

    ADVISORY = "advisory"
    FAILED_RUN = "failed_run"
    REGRESSION_COMMIT = "regression_commit"


class ChangeKind(StrEnum):
    """What happened to an issue, as the repository's issue events report it. A field change
    is a `labeled` or `unlabeled` event of its family's label (ADR 0003)."""

    LABELED = "labeled"
    UNLABELED = "unlabeled"
    CLOSED = "closed"
    REOPENED = "reopened"


class RefineRecordKey(StrEnum):
    """What refine records in an Item's job record (#744): the body hash outside the section,
    the section hash, whether the proposal needs splitting, the body hash a reply that never
    validated was about (#1539), the next step the item waits on with the open items that
    block it (#1758), the repository paths whose code the proposal cites as the cause of
    the block (#2005), and the creation time of the newest comment that the cap on refine's
    comments last left with no answer (#2475), and the URL of the covering tool that the
    alternatives check found and refine put to a person (#2652)."""

    BODY_HASH = "refine.body_hash"
    SECTION_HASH = "refine.section_hash"
    NEEDS_SPLIT = "refine.needs_split"
    FAILED_BODY_HASH = "refine.failed_body_hash"
    NEXT_STEP = "refine.next_step"
    BLOCKED_BY = "refine.blocked_by"
    BLOCK_PATHS = "refine.block_paths"
    CAPPED_AFTER = "refine.capped_after"
    ALTERNATIVES_ASKED = "refine.alternatives_asked"


class Verdict(StrEnum):
    """What an alternatives check found (#2650): `COVERS` one tool covers the whole need,
    `PARTLY` one covers a part, `NONE` the search found no tool, `NOT_APPLICABLE` the item asks
    for no tool. The job records it, and refine reads it (#2652)."""

    COVERS = "covers"
    PARTLY = "partly"
    NONE = "none"
    NOT_APPLICABLE = "not-applicable"


class AlternativesRecordKey(StrEnum):
    """What `devops roadmap alternatives` records in an Item's job record (#2650): when the check
    ran, the hash of the body it read outside its own block and the refine section, its verdict,
    and the URL of the tool it found, if any."""

    CHECKED_AT = "alternatives.checked_at"
    BODY_HASH = "alternatives.body_hash"
    VERDICT = "alternatives.verdict"
    TOOL = "alternatives.tool"


class StageRecordKey(StrEnum):
    """What the stage job records in an Item's job record (#2654): the staged branch, the number
    of its draft pull request, the commit it ends on, the task groups with their measures in
    tokens, the task group over the budget that stopped the item, which a person decides, and the
    file cap in tokens of the measure that made the stop: a stop under another cap is stale. The
    Service records `stage.ready`, the number of the draft pull request that it has seen leave the
    draft state (#2865)."""

    BRANCH = "stage.branch"
    PR = "stage.pr"
    SHA = "stage.sha"
    GROUPS = "stage.groups"
    NEEDS_SPLIT = "stage.needs_split"
    FILE_CAP = "stage.file_cap"
    READY = "stage.ready"


class ImplementRecordKey(StrEnum):
    """What the implement job records in an Item's job record (#2665): the last task group that
    passed, the commit the job ended on, the branch and the pull request it works on (#2714), the
    step that stopped the item, and the spend of its steps as JSON. A person clears
    `implement.stopped` with a comment. The Service records the runner Job it made for the item
    and, once the Job ended, its state (#2667), and the digest of the runner image that the template
    named when it made the Job (#2912): the digest of the stop that the Job leaves."""

    GROUP = "implement.group"
    SHA = "implement.sha"
    BRANCH = "implement.branch"
    PR = "implement.pr"
    STOPPED = "implement.stopped"
    SPEND = "implement.spend"
    JOB = "implement.job"
    JOB_STATE = "implement.job_state"
    JOB_DIGEST = "implement.job_digest"


JobRecord = dict[
    ItemField | RefineRecordKey | AlternativesRecordKey | StageRecordKey | ImplementRecordKey,
    str | None,
]

# ── Models ────────────────────────────────────────────────────────────────────


class Milestone(BaseModel):
    """A GitHub milestone, a planning bucket: its number identifies it and its due date orders
    it. The title is any text. `closed_at` is when it last closed."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    description: str = ""
    state: GitHubState = GitHubState.OPEN
    due_on: date | None = None
    open_issues: int = 0
    closed_issues: int = 0
    closed_at: datetime | None = None


class Candidate(BaseModel):
    """An open issue of this repository that holds no `priority/*` label."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    labels: tuple[str, ...] = ()
    milestone: str | None = None


class Item(BaseModel):
    """An issue of this repository with its fields and job record.

    State, labels and the milestone title come from the issue; Status, Priority, Value, Effort
    and Owner from its label families (`field_values`). The job record holds the last value the
    store set for each field; a field missing from it was never set by a job. `body` is the
    issue's body, with no record block, as the read the Item came from gave it, so a job can
    judge an Item by its text without a read of each issue. `author_association` is the
    author's relation to the repository, as on `IssueRecord`: a refine round refines only an
    Item that the owner, a member or a collaborator opened (#2478). `sub_issues` is how many
    sub-issues the issue has, as on `IssueRecord`: an Item with some is a tracker.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    body: str = ""
    state: GitHubState = GitHubState.OPEN
    state_reason: str | None = None
    labels: tuple[str, ...] = ()
    milestone: str | None = None
    author_association: str | None = None
    sub_issues: int = 0
    status: str | None = None
    priority: str | None = None
    value: str | None = None
    effort: str | None = None
    owner: str | None = None
    job_record: JobRecord = Field(default_factory=dict)

    def field_value(self, field: ItemField) -> str | None:
        """The Item's current value for `field`, to compare with its job record."""
        return cast(str | None, getattr(self, field.name.lower()))


class Change(BaseModel):
    """One change to an issue, with who made it and when; `label` names the label a `labeled`
    or `unlabeled` change added or removed."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    number: int
    actor: str | None
    at: datetime
    label: str | None = None


class IssueRecord(BaseModel):
    """What the repository's issue listing says about one issue or pull request.

    `body` holds no record block: `job_record` is what the block held. `milestone` is the title
    of the issue's milestone. `author_association` is GitHub's word for the author's relation
    to the repository, such as `OWNER`, `COLLABORATOR` or `NONE`. `updated_at` is when the issue
    last changed: any write to it, a comment included, moves it. `sub_issues` is how many
    sub-issues GitHub records for the issue, open or closed. `parent` is the number of the issue
    of the same repository that has the issue as a sub-issue.
    """

    model_config = ConfigDict(frozen=True)

    id: int = 0
    number: int
    title: str
    url: str
    body: str = ""
    state: GitHubState = GitHubState.OPEN
    state_reason: str | None = None
    labels: tuple[str, ...] = ()
    milestone: str | None = None
    pull_request: bool = False
    author_association: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    sub_issues: int = 0
    parent: int | None = None
    job_record: JobRecord = Field(default_factory=dict)


class IssueComment(BaseModel):
    """One comment on an issue: its body, when it was made, and the commenter's relation to the
    repository as GitHub gives it (`OWNER`, `MEMBER`, `COLLABORATOR`, `NONE` and others), None
    when the store does not know it."""

    model_config = ConfigDict(frozen=True)

    body: str
    created_at: datetime
    author_association: str | None = None


class Closure(BaseModel):
    """One close or reopen of an issue, as its timeline records it: a close carries its state
    reason, and the issue it duplicates when it was closed as a duplicate."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    at: datetime
    reason: str | None = None
    duplicate_of: int | None = None


def is_name_segment(text: str) -> bool:
    """Whether `text` is one name as GitHub and PyPI spell one: ASCII letters, digits, `-`, `_`
    and `.`, and not `.` or `..`. Such a text is one safe segment of a URL path (#2650)."""
    return text not in {"", ".", ".."} and all(
        char.isascii() and (char.isalnum() or char in "-_.") for char in text
    )


def is_repository_name(text: str) -> bool:
    """Whether `text` is `owner/name`, each part a name (`is_name_segment`)."""
    parts = text.split("/")
    return len(parts) == 2 and all(is_name_segment(part) for part in parts)


class RepositoryFacts(BaseModel):
    """What GitHub says of a repository that an item might use as a tool (#2650): its license,
    when it was last pushed to, whether it is archived, its stars, and its latest release."""

    model_config = ConfigDict(frozen=True)

    full_name: str
    url: str
    license: str | None = None
    archived: bool = False
    pushed_at: datetime | None = None
    stars: int = 0
    latest_release: str | None = None
    released_at: datetime | None = None


class Evidence(BaseModel):
    """A piece of evidence for a P0: its kind and the value that names it."""

    model_config = ConfigDict(frozen=True)

    kind: EvidenceKind
    value: str = Field(min_length=1, max_length=128)


# ── Label families ────────────────────────────────────────────────────────────


def family_prefix(field: ItemField) -> str:
    """The prefix every label of `field`'s family starts with, such as `status/`."""
    return f"{field.value.lower()}/"


def field_label(field: ItemField, value: str) -> str:
    """The label that holds `value` of `field`: `priority/p1-high` for P1-High."""
    return family_prefix(field) + value.lower().replace(" ", "-")


def _held_values(labels: Iterable[str], field: ItemField) -> list[str]:
    """The values of `field` whose labels `labels` holds, in the family's order."""
    held = {label.lower() for label in labels}
    return [value for value in FIELD_VALUES[field] if field_label(field, value) in held]


def field_values(labels: Iterable[str], record: Mapping[Any, str | None]) -> dict[str, str | None]:
    """Each field's value that `labels` give, keyed as `Item` holds it. A family with more than
    one label has the value the job record does not name: the job wrote the other, so a person
    added it; with more than one such, the first in the family's order."""
    listed = tuple(labels)
    values: dict[str, str | None] = {}
    for field in ItemField:
        held = _held_values(listed, field)
        newer = [value for value in held if value != record.get(field)] or held
        values[field.name.lower()] = newer[0] if newer else None
    return values


def relabeled(labels: Iterable[str], field: ItemField, value: str | None) -> tuple[str, ...]:
    """`labels` with every label of `field`'s family replaced by the label of `value`, or by none
    when `value` is None; the other labels keep their order."""
    prefix = family_prefix(field)
    kept = tuple(label for label in labels if not label.lower().startswith(prefix))
    return kept if value is None else (*kept, field_label(field, value))


def require_value(field: ItemField, value: str | None, operation: str) -> None:
    """Refuse a value that is not one of the field's values. Clearing is always allowed."""
    choices = FIELD_VALUES[field]
    if value is not None and value not in choices:
        raise GitHubOperationError(
            MESSAGES.roadmap.field_value_unknown.format(
                field=field.value, value=value[:256], values=", ".join(choices)
            ),
            operation=operation,
            details={"field": field.value, "value": value[:256]},
        )


# ── The record block ──────────────────────────────────────────────────────────

_RECORD_BLOCK = re.compile(
    rf"<!-- {re.escape(CONST_ROADMAP_RECORD_MARKER)} (?P<record>.*?) -->", re.DOTALL
)
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
# GitHub's Markdown is CommonMark: `html_block` is a real comment, `code_inline`, `fence` and
# `code_block` are text that only shows one.
_BODY_MARKDOWN: Final = MarkdownIt("commonmark")
_RECORD_SEPARATORS = ("\r\n\r\n", "\n\n")
_JOB_RECORD = TypeAdapter(JobRecord)
# The job record keys this version reads; the others are another version's, kept as they are.
_JOB_RECORD_KEYS = frozenset(
    key.value
    for key in (
        *ItemField,
        *RefineRecordKey,
        *AlternativesRecordKey,
        *StageRecordKey,
        *ImplementRecordKey,
    )
)


def _record_block_span(body: str) -> tuple[int, int] | None:
    """The start and end of the last block of `body`, when it is a comment: the only place
    `with_record` writes the record block. A quote of the block in a code span or a code block,
    or a comment that more text follows, is not it."""
    last = next((token for token in reversed(_BODY_MARKDOWN.parse(body)) if token.level == 0), None)
    if last is None or last.type != "html_block" or last.map is None:
        return None
    starts = [0, *(found.end() for found in _LINE_BREAK.finditer(body))]
    first, after = last.map
    return starts[first], starts[after] if after < len(starts) else len(body)


def split_record(body: str, *, issue: str = "an issue") -> tuple[str, dict[str, Any]]:
    """The body with its record block taken out, and the JSON object the block holds: empty
    when the body has no block, or when the block holds no JSON object, which a warning names.

    The record block is the comment at the end of the body. The writer's separator before it
    goes with it, so a body read back after `with_record` is the body written.
    """
    span = _record_block_span(body)
    found = _RECORD_BLOCK.fullmatch(body[span[0] : span[1]].strip()) if span else None
    if span is None or found is None:
        return body, {}
    rest = body[: span[0]]
    rest = next(
        (rest.removesuffix(sep) for sep in _RECORD_SEPARATORS if rest.endswith(sep)),
        rest,
    )
    try:
        held = json.loads(found.group("record"))
    except json.JSONDecodeError:
        held = None
    if not isinstance(held, dict):
        logger.warning(MESSAGES.roadmap.record_unreadable.format(issue=issue))
        return rest, {}
    return rest, held


def decode_job_record(held: Mapping[str, Any], *, issue: str = "an issue") -> JobRecord:
    """The keys of a record block this version knows. A key another version writes is left out
    here and kept by every write (`encode_job_record`); a known key whose value is not text or
    null is left out, with a warning."""
    known = {key: value for key, value in held.items() if key in _JOB_RECORD_KEYS}
    try:
        return _JOB_RECORD.validate_python(known)
    except MalformedRecordError:
        logger.warning(MESSAGES.roadmap.record_unreadable.format(issue=issue))
        return _JOB_RECORD.validate_python(
            {key: value for key, value in known.items() if value is None or isinstance(value, str)}
        )


def encode_job_record(held: Mapping[str, Any], changes: Mapping[Any, str | None]) -> str:
    """The record block for `held`, the JSON object the issue's block holds now, with `changes`
    made. Each `>` is escaped, so no value ends the comment."""
    merged = dict(held) | {str(key): value for key, value in changes.items()}
    text = json.dumps(merged, sort_keys=True).replace(">", "\\u003e")
    return f"<!-- {CONST_ROADMAP_RECORD_MARKER} {text} -->"


def with_record(body: str, block: str | None) -> str:
    """`body`, which holds no record block, with `block` at its end; `body` itself when there
    is no block."""
    if block is None:
        return body
    return f"{body}\n\n{block}" if body else block


# ── Rules both adapters apply ─────────────────────────────────────────────────


def as_utc(moment: datetime) -> datetime:
    """Read a naive time as UTC, so it compares with GitHub's timestamps."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def milestone_order(milestone: Milestone) -> tuple[bool, date, int]:
    """The one order of milestones: by due date, then by number, with no due date last."""
    return (milestone.due_on is None, milestone.due_on or date.min, milestone.number)


def find_milestone(milestones: Iterable[Milestone], name: str) -> Milestone | None:
    """The milestone `name` names: the one with that exact title, else the one with that number
    when `name` is a number. No title is read as a version."""
    listed = list(milestones)
    titled = next((milestone for milestone in listed if milestone.title == name), None)
    if titled is not None or not name.isdecimal():
        return titled
    return next((milestone for milestone in listed if milestone.number == int(name)), None)


def require_milestone(milestones: Iterable[Milestone], name: str, operation: str) -> Milestone:
    """The milestone `name` names, raising when there is none."""
    found = find_milestone(milestones, name)
    if found is None:
        raise GitHubOperationError(
            MESSAGES.roadmap.milestone_missing.format(name=name[:256]),
            operation=operation,
            details={"milestone": name[:256]},
        )
    return found


def milestone_edits(
    milestones: Sequence[Milestone],
    current: Milestone,
    *,
    title: str | None,
    description: str | None,
    due_on: date | None,
    state: GitHubState | None,
) -> dict[str, str | date]:
    """The fields an edit of `current` changes: only those it was given.

    A new title must differ from the title of every other milestone, as GitHub requires. An
    edit that names no state changes no state.
    """
    taken = {milestone.title for milestone in milestones if milestone.number != current.number}
    if title is not None and title in taken:
        raise GitHubOperationError(
            MESSAGES.roadmap.milestone_title_taken.format(title=title[:256]),
            operation="roadmap.milestone.edit",
            details={"title": title[:256]},
        )
    requested: dict[str, str | date | None] = {
        "title": title,
        "description": description,
        "due_on": due_on,
        "state": state,
    }
    return {name: change for name, change in requested.items() if change is not None}


def with_marks(record: JobRecord, marks: Mapping[Any, str | None]) -> JobRecord:
    """A copy of the job record with `marks` set or cleared in it."""
    merged: JobRecord = dict(record)
    for mark, value in marks.items():
        merged[mark] = value
    return merged


def require_unchanged(
    name: str,
    field: ItemField,
    read: str | None,
    now: str | None,
    value: str | None,
    operation: str,
) -> None:
    """Refuse a job's write of `value` to `field` of issue `name` when the issue holds `now` but
    the store read `read`: the job planned without that change, so the write would revert it
    (ADR 0002). Writing the value the issue holds now reverts nothing."""
    if read == now or value == now:
        return
    texts = MESSAGES.roadmap
    raise RoadmapItemChangedError(
        texts.item_changed.format(
            item=name,
            field=field.value,
            now=now or texts.item_value_unset,
            read=read or texts.item_value_unset,
        ),
        operation=operation,
        details={
            "item": name[:256],
            "field": field.value,
            "read": read and read[:256],
            "now": now and now[:256],
        },
    )


def item_of(issue: IssueRecord) -> Item:
    """The issue as an Item, its fields read from its labels and its job record, whether or not
    it holds a Priority: intake writes to a Candidate through it."""
    held = issue.model_dump(exclude={"pull_request", "created_at"})
    held = {key: value for key, value in held.items() if key in Item.model_fields}
    return Item.model_validate(held | field_values(issue.labels, issue.job_record))


def select_items(issues: Iterable[IssueRecord]) -> list[Item]:
    """The Items among `issues`: the issues, never pull requests, that hold a Priority."""
    items = (item_of(issue) for issue in issues if not issue.pull_request)
    return sorted((item for item in items if item.priority is not None), key=lambda i: i.number)


def select_candidates(issues: Iterable[IssueRecord]) -> list[Candidate]:
    """The Candidates among `issues`: open issues, never pull requests, with no Priority."""
    return sorted(
        (
            Candidate.model_validate(issue.model_dump(include=set(Candidate.model_fields)))
            for issue in issues
            if issue.state is GitHubState.OPEN
            and not issue.pull_request
            and item_of(issue).priority is None
        ),
        key=lambda candidate: candidate.number,
    )


# ── Interface ─────────────────────────────────────────────────────────────────


@runtime_checkable
class RoadmapStore(Protocol):
    """Reads and writes the roadmap: its milestones, its Items and their fields."""

    def milestones(self) -> list[Milestone]:
        """Every milestone, open and closed, by due date and then by number (`milestone_order`)."""

    def milestone(self, name: str) -> Milestone | None:
        """The milestone with the exact title `name`, else the one numbered `name`, or None."""

    def edit_milestone(
        self,
        name: str,
        *,
        title: str | None = None,
        description: str | None = None,
        due_on: date | None = None,
        state: GitHubState | None = None,
    ) -> Milestone:
        """Change only the given fields of the milestone `name` names, raising if there is none."""

    def close_milestone(self, name: str) -> Milestone:
        """Close the milestone `name` names, raising if there is none."""

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is no Item: it holds no
        Priority, is a pull request or does not exist."""

    def items(self, *, milestone: int | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the milestone numbered `milestone`."""

    def backlog(self) -> list[Item]:
        """The open Items in no milestone."""

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that hold no Priority."""

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The issue changes made at or after `since`, oldest first, without those
        `except_actor` made."""

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Set or clear the field's label family on the Item's issue, and record the value, with
        `marks` set or cleared, in its job record, in one write.

        A value that is not one of the field's values, an issue that is not this repository's,
        or a field someone changed since the store read the Item, unless the issue already
        holds `value`, raises before the store changes anything. The record keeps what the
        store set for the Item's other fields, even when `item` was read before an earlier
        write.
        """

    def set_marks(self, item: Item, marks: Mapping[Any, str | None]) -> None:
        """Set or clear a job's marks in the Item's job record in one write, changing none of
        its fields. It raises like `set_field` before the store changes anything."""

    def issues(self) -> list[IssueRecord]:
        """Every issue of the repository, open and closed, Item or not; never pull requests."""

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""

    def add_sub_issue(self, parent: int, child: int) -> None:
        """Add issue `child` as a sub-issue of issue `parent`."""

    def read_issue_body(self, number: int) -> str:
        """The body of issue `number`, with no record block, raising if it is not an issue of
        this repository."""

    def write_issue_body(self, number: int, body: str) -> None:
        """Write `body` as the body of issue `number`, keeping its record block, raising if it is
        not an issue of this repository."""

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The text of the repository file at `path` on `ref` (the default branch when None),
        raising `GitHubFileNotFoundError` when there is no such file."""

    def repository_is_private(self) -> bool:
        """Whether the repository is private."""

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""

    def close(self, number: int, reason: CloseReason, *, comment: str | None = None) -> None:
        """Close the open issue `number` for `reason`, after `comment` is posted on it when
        given, so a failed close leaves the comment. It raises before any write when `number` is
        no open issue of this repository: GitHub ignores a reason unless the state changes, so
        a closed issue is refused (#1658)."""

    def comments_on(self, number: int) -> list[IssueComment]:
        """Every comment on issue `number`, oldest first."""

    def path_changed_at(self, path: str) -> datetime | None:
        """When the newest commit on the default branch that changed `path` was made, or None
        when no commit changed it (#2005)."""

    # ── What intake reads and writes (#742) ──

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number`, oldest first, from its timeline."""

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue or pull request `number`, keeping its other labels."""

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether GitHub confirms the evidence: the advisory exists, the run of this repository
        failed, or the commit exists in this repository."""

    def repository_facts(self, full_name: str) -> RepositoryFacts | None:
        """The facts of the repository `full_name` (`owner/name`), which need not be this one,
        or None when GitHub has no such repository (#2650). A read that cannot complete raises."""


def get_roadmap_store(repo: str, *, runner: GhRunner | None = None) -> RoadmapStore:
    """Open the roadmap store for `repo`, its `gh` commands through `runner` when one is given.

    Every caller builds its store here, so a test replaces this one function with a fixture
    that returns the in-memory adapter.
    """
    from devops_cli.roadmap.github_store import GitHubRoadmapStore

    if runner is None:
        return GitHubRoadmapStore(repo)
    return GitHubRoadmapStore(repo, runner=runner)


__all__ = [
    "FIELD_VALUES",
    "AlternativesRecordKey",
    "Candidate",
    "Change",
    "ChangeKind",
    "CloseReason",
    "Closure",
    "Evidence",
    "EvidenceKind",
    "GitHubState",
    "ImplementRecordKey",
    "IssueComment",
    "IssueRecord",
    "Item",
    "ItemField",
    "JobRecord",
    "Milestone",
    "RefineRecordKey",
    "RepositoryFacts",
    "RoadmapStore",
    "StageRecordKey",
    "Verdict",
    "as_utc",
    "decode_job_record",
    "encode_job_record",
    "family_prefix",
    "field_label",
    "field_values",
    "find_milestone",
    "get_roadmap_store",
    "is_name_segment",
    "is_repository_name",
    "item_of",
    "milestone_edits",
    "milestone_order",
    "relabeled",
    "require_milestone",
    "require_unchanged",
    "require_value",
    "select_candidates",
    "select_items",
    "split_record",
    "with_marks",
    "with_record",
]
