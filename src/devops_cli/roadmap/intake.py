"""`devops roadmap intake`: the single way new work becomes an item (#742).

A candidate is an open issue not on the board (an archived card is not on it), a board item intake
left without a Priority (an unfinished item), or a candidate that is not an issue yet
(`NewCandidate`), which `--title` and `--body-file` and the Python entry point `intake_candidate`
take. Intake plans every candidate before it writes anything, model calls included, so a model
gateway that does not answer (`ModelGatewayUnreachableError`) leaves GitHub as it was.

**Possible duplicates.** A candidate is compared with every item on the board, open or closed,
and every issue closed as not planned, plus the candidates this run placed before it; a new
candidate is also compared with the open agent issues off the board. An issue that has
sub-issues is compared with no candidate. Its sub-issues deliver it, one pull request each (ADR
0012), so no candidate asks for its change. A new candidate is not compared with the issue its
source links, such as the issue it splits (#1985). Each text is embedded once, and the model
judges the candidate against its nearest `DEFAULT_ROADMAP_INTAKE_SHORTLIST` items, by cosine
similarity. A duplicate asks for the same change as its original: the same result and
acceptance criteria, so that the delivery of one delivers the other. A shared theme, goal,
umbrella or file does not make a duplicate (#1755). The model names an original only with the
change both ask for (`shared_change`). An original named with no shared change is not a
possible duplicate: intake names it as related. The model can also name a related item that
asks for a different change, such as an umbrella, a sibling or a neighbour (`related_to`).

The model's verdict is a flag, never an action (#2218). Intake places a possible duplicate as
it places any candidate, files a new one, and closes no issue. The report and the reason
comment name the possible original and the change the model says both ask for, and the comment
links it, so that a person, or refine, closes a real duplicate. A related item is named the
same way. An issue whose timeline shows a duplicate close that a person reversed by reopening
it skips the check, and so does an unfinished item. A new candidate whose title and body are
those of an open issue that is not finished, which a run that stopped after filing leaves, is
that issue: intake places it and files nothing. A new candidate whose text holds what looks
like a secret is refused before it reaches a model or GitHub.

**The proposal.** The model returns a type, a Priority from P1 to P3, Value and Effort, each
with a one-line reason, and optionally one piece of evidence. The types it may pick are the
`type/*` labels `.github/labels.yml` declares, `type/epic` aside; a run reads the file at its
first candidate, before any timeline read or model call, and stops with a `ConfigurationError`
naming the repository when the file is missing or declares none (#1358). The candidate's text
is untrusted: code checks every value against its list, a `duplicate_of` outside the shortlist
is rejected, and a proposal with a value off its list, or an answer that never fits the
schema, is skipped.
P0 needs evidence whose value is a whole word of the candidate's text or was attached by the
entry point's caller, that GitHub confirms (`RoadmapStore.evidence_holds`), from a trusted
source: an author with write access, on an issue no agent filed, or the caller that attached it.
Otherwise the model's priority stands, and the comment says why and that a person can set P0.
The comment shows each of the model's reasons as inline code, so no `#N` or `@name` in it links
or notifies.

**Placement.** Intake puts every new item in the backlog and sets no milestone. A person
plans the milestones on the board. A milestone the issue already has stands, and an unfinished
item keeps its milestone.

**Writes**, in order, with Priority last, which marks the item finished: file the issue (a new
candidate only), add a `type/*` label when it has none, put it on the board, set the empty ones
of Status (New), Value and Effort, leave one reason comment carrying
`CONST_ROADMAP_INTAKE_REASON_MARKER` unless one is there, then set Priority. Each field write goes to the card the item has, or the card the add returned: no
placement looks for its card in the board listing, which can show a new card minutes after the
add (#1361).

**A card planning did not see** (#1403). The listing leaves out an archived card, which the add
restores (`AddedItem.restored`), and a card it has not shown yet, so intake plans such an issue as
one off the board and the writes follow the card the add returns. A card that holds a Priority is
an item intake would not take, and gets nothing more (`IntakeApplied.finished`). Otherwise intake
writes only the fields the card holds no value for, besides the Status New the board's add
workflow sets on a card the add did not restore; a restored card keeps its milestone, as an item
does; and the reason comment gives that placement and those values. A value a person set stays,
and the job record never claims it (ADR 0002).

A run that stops part-way leaves an open issue off the board, or an item with no Priority, and
the next run finishes it. Intake writes to no issue but the candidate, and closes none.

**Dry run, plan, confirm** (the dry-run rule of #412). `dry_run_intake` makes no request, to
GitHub or a model: it returns an `IntakePlan` marked `dry_run`, with no decision, that holds
the requests a run makes, in order, with placeholders for what a read gives
(`intake_requests`). `plan_intake` makes the reads and the model calls and writes nothing; the
command reports what it spent. `apply_intake` makes the writes.

**A limit** (#1360). With `limit`, a run decides at most that many candidates and leaves the
rest for a later run, so a burst of new issues never holds back the jobs after it. The fresh
candidates come first, oldest (lowest number) first: those never decided, and those edited
since a run left them undecided. The others follow, longest waiting first. `waiting` says which
candidates were decided before, and when: the Service keeps it between rounds as an
`IntakeRecord`, beside `schedule.json`; `devops roadmap intake --limit` keeps none, so it takes
the oldest candidates first.

**Agent candidates.** A new candidate comes from an agent unless its caller says a person
filed it (`Filer`). An agent's is filed with the `source/agent` label, a person's with none.
Intake files every new candidate, a possible duplicate too.
"""

from __future__ import annotations

import logging
import string
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from functools import cached_property
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as InvalidLabelsError

from devops_cli.ai.vector_similarity import cosine_similarity
from devops_cli.config.constants import (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_EVIDENCE_PATTERNS,
    CONST_ROADMAP_INTAKE_REASON_MARKER,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_MODEL_PRIORITIES,
    CONST_ROADMAP_P0_PRIORITIES,
    CONST_ROADMAP_SIZE_OPTIONS,
    CONST_ROADMAP_SOURCE_AGENT_LABEL,
    CONST_ROADMAP_STATUS_DONE,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_TRUSTED_AUTHORS,
    CONST_ROADMAP_TYPE_LABEL_PREFIX,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_INTAKE_EXCERPT_CHARS,
    DEFAULT_ROADMAP_INTAKE_REASON_CHARS,
    DEFAULT_ROADMAP_INTAKE_SHORTLIST,
    DEFAULT_ROADMAP_INTAKE_TEXT_CHARS,
)
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
)
from devops_cli.exceptions.roadmap import RoadmapIntakeError
from devops_cli.exceptions.security import SecurityError
from devops_cli.github.labels import LabelSpec
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake_model import (
    IntakeModel,
    ModelEvidence,
    ModelProposal,
    Neighbour,
    ProposalRequest,
    UnusableProposalError,
)
from devops_cli.roadmap.intake_requests import Spend, planned_requests
from devops_cli.roadmap.store import (
    AddedItem,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    EvidenceKind,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    RoadmapStore,
)
from devops_cli.security.sanitizer import redact_text

_LABEL_SPECS = TypeAdapter(list[LabelSpec])
logger = logging.getLogger(__name__)


class Filer(StrEnum):
    """Who files a new candidate: an agent's is labeled `source/agent`, a person's is not."""

    AGENT = "agent"
    PERSON = "person"


class Outcome(StrEnum):
    """What intake does with a candidate."""

    PLACE = "place"
    SKIP = "skip"


@dataclass(frozen=True)
class NewCandidate:
    """A candidate that is not an issue yet: its title and body, the link it came from, the
    evidence its caller attaches, and who files it."""

    title: str
    body: str
    source: str | None = None
    evidence: tuple[Evidence, ...] = ()
    filed_by: Filer = Filer.AGENT

    def filed_body(self) -> str:
        """The body the issue is filed with: the candidate's, then its source link."""
        return f"{self.body}\n\nSource: {self.source}" if self.source else self.body

    def refuse_secrets(self) -> None:
        """Raise when the title, body or source holds what looks like a secret: the text would
        reach the model and a public issue."""
        for part, text in (("title", self.title), ("body", self.body), ("source", self.source)):
            if text and redact_text(text) != text:
                raise SecurityError(MESSAGES.roadmap.intake_secret.format(part=part))


@dataclass(frozen=True)
class Subject:
    """One candidate intake decides about; an unfinished item carries its `item`, a new
    candidate its `new`."""

    title: str
    body: str
    number: int | None = None
    labels: tuple[str, ...] = ()
    milestone: str | None = None
    author_association: str | None = None
    updated_at: datetime | None = None
    item: Item | None = None
    new: NewCandidate | None = None
    sub_issues: int = 0

    @property
    def name(self) -> str:
        if self.number is None:
            return MESSAGES.roadmap.intake_new.format(title=self.title)
        return MESSAGES.roadmap.intake_issue.format(number=self.number, title=self.title)

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.body}"[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS]

    @property
    def type_label(self) -> str | None:
        return next(
            (lb for lb in self.labels if lb.startswith(CONST_ROADMAP_TYPE_LABEL_PREFIX)), None
        )

    @property
    def agent(self) -> bool:
        """Whether an agent filed it: a new candidate its caller did not mark as a person's, or
        an issue labeled `source/agent`."""
        if self.new is not None:
            return self.new.filed_by is Filer.AGENT
        return CONST_ROADMAP_SOURCE_AGENT_LABEL in self.labels

    def cites(self, value: str) -> bool:
        """Whether `value` is a whole word of the title or the whole body, a link's path
        segments included."""
        words = f"{self.title}\n{self.body}".split()
        return value in {
            part.strip(string.punctuation) for word in words for part in word.split("/")
        }

    @property
    def trusted(self) -> bool:
        """Whether the author has write access and the text is theirs, not an agent's."""
        return (
            self.author_association in CONST_ROADMAP_TRUSTED_AUTHORS
            and CONST_ROADMAP_SOURCE_AGENT_LABEL not in self.labels
        )


@dataclass(frozen=True)
class Proposal:
    """The model's proposal once code has checked it."""

    type: str
    type_reason: str
    priority: str
    priority_reason: str
    value: str
    value_reason: str
    effort: str
    effort_reason: str
    evidence: Evidence | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Placement:
    """The milestone a candidate stays in (None for the backlog), and the comment's words for it."""

    milestone: str | None
    text: str


@dataclass(frozen=True)
class IntakeDecision:
    """What intake does with one candidate, and every write it makes for it.

    `shown` is the type, Priority, Value and Effort the item ends with, for the report.
    `reasons` holds the reason comment's lines, each value intake sets with its reason, so the
    comment can be written for the placement and fields the writes make. `possible_duplicate`
    is the item the model names as asking for the same change, with `duplicate_reason`, for a
    person to judge (#2218). `related` is the item a placed candidate is related to but does not
    duplicate, with `related_reason` (#1755).
    """

    subject: Subject
    outcome: Outcome
    reason: str = ""
    possible_duplicate: int | None = None
    duplicate_reason: str = ""
    related: int | None = None
    related_reason: str = ""
    labels: tuple[str, ...] = ()
    placement: Placement | None = None
    fields: tuple[tuple[ItemField, str], ...] = ()
    priority: str | None = None
    comment: str | None = None
    filing_labels: tuple[str, ...] = ()
    shown: tuple[str, str, str, str] = ("", "", "", "")
    notes: tuple[str, ...] = ()
    reasons: tuple[tuple[str, str, str], ...] = ()

    @property
    def has_writes(self) -> bool:
        return self.outcome is Outcome.PLACE

    def writes(self) -> list[str]:
        """Each write, in the order intake makes it."""
        texts = MESSAGES.roadmap
        filing = ", ".join(self.filing_labels) or texts.intake_no_labels
        planned = [texts.intake_write_file.format(labels=filing)]
        planned = planned if self.subject.number is None else []
        planned += [texts.intake_write_label.format(label=label) for label in self.labels]
        planned += [texts.intake_write_add] if self.subject.item is None else []
        planned += [texts.intake_write_field.format(field=f.value, value=v) for f, v in self.fields]
        planned += [texts.intake_write_comment] if self.comment else []
        planned.append(
            texts.intake_write_field.format(field=ItemField.PRIORITY.value, value=self.priority)
        )
        return planned


@dataclass(frozen=True)
class IntakePlan:
    """A decision for each candidate, and the asked-for issues that are not candidates; with
    `spend`, the requests the planning run made.

    With a `limit`, `left` holds the candidates the run left for a later one, in the order a
    later run takes them, and `fresh_left` whether a fresh one is among them: never decided, or
    edited since it was.

    A dry run (`dry_run`) made no request, so it has no decision: `requests` holds the reads
    and model calls a run makes, in order, and `writes` those `--confirm` adds.
    """

    decisions: tuple[IntakeDecision, ...]
    missing: tuple[int, ...] = ()
    limit: int | None = None
    left: tuple[int, ...] = ()
    fresh_left: bool = False
    spend: Spend | None = None
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    writes: tuple[PlannedRequest, ...] = ()

    @property
    def has_writes(self) -> bool:
        return any(decision.has_writes for decision in self.decisions)


@dataclass(frozen=True)
class PlacementFailure:
    """A candidate intake skipped because one of its writes failed: its issue number, None for
    a new candidate never filed, its title and the error's class (#1443)."""

    number: int | None
    title: str
    error: str

    @property
    def name(self) -> str:
        """How messages name the candidate: its number, or its title when it has none."""
        if self.number is not None:
            return f"#{self.number}"
        return MESSAGES.roadmap.intake_failed_new.format(title=self.title[:80])


@dataclass(frozen=True)
class IntakeApplied:
    """What a run wrote: items placed, and the issues it filed. `finished` names each candidate
    whose card the add returned holding a Priority, a card a person archived that the add
    restored or one a lagging listing left out: intake wrote nothing else to it (#1403).
    `failed` names each candidate a failed write made it skip (#1443)."""

    placed: int = 0
    filed: tuple[int, ...] = ()
    finished: tuple[int, ...] = ()
    failed: tuple[PlacementFailure, ...] = ()


@dataclass(frozen=True)
class CandidateOutcome:
    """The entry point's answer: the plan, the candidate's decision, and the issue filed for it
    or, when a run that stopped after filing left that issue, the issue intake placed."""

    plan: IntakePlan
    decision: IntakeDecision
    number: int | None


class Waiting(BaseModel):
    """A candidate a run decided that is still a candidate: the issue's `updated_at` then, and
    when it was decided."""

    model_config = ConfigDict(frozen=True)

    updated_at: datetime | None
    decided_at: datetime


class IntakeRecord(BaseModel):
    """What the Service's intake keeps between rounds (#1360): each candidate it decided that is
    still one, by number, and whether a fresh candidate is left, which makes intake due at the
    next poll."""

    model_config = ConfigDict(frozen=True)

    pending: bool = False
    waiting: dict[int, Waiting] = Field(default_factory=dict)

    def after(self, plan: IntakePlan, now: datetime) -> IntakeRecord:
        """The record once `plan`'s candidates are decided, at `now`: those it decided, placed
        or not, and those it left that waited before. A candidate that is one no more drops out
        at the next run, which no longer lists it; one whose placement raised is decided again
        after the fresh ones, unless that placement had already written to it, which makes it
        fresh once."""
        decided = {
            decision.subject.number: Waiting(updated_at=decision.subject.updated_at, decided_at=now)
            for decision in plan.decisions
            if decision.subject.number is not None
        }
        kept = {number: self.waiting[number] for number in plan.left if number in self.waiting}
        return IntakeRecord(pending=plan.fresh_left, waiting=kept | decided)


class _InvalidProposal(ValueError):
    """A proposal with a value off its list."""

    def __init__(self, message: str, problems: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.problems = problems


# ── Reading the roadmap ───────────────────────────────────────────────────────


@dataclass
class _Run:
    """What one run reads once, from `repo`'s `store`."""

    store: RoadmapStore
    repo: str
    model: IntakeModel
    ref: str | None
    issues: list[IssueRecord]
    board: dict[int, Item]

    @cached_property
    def types(self) -> tuple[str, ...]:
        """The `type/*` labels `.github/labels.yml` declares, `type/epic` aside. A file that is
        missing, is no label specs or declares none is a configuration error naming the
        repository; any other failed read stays GitHub's error (#1358)."""
        path, texts = CONST_ROADMAP_LABELS_PATH, MESSAGES.roadmap
        where = {
            "repo": self.repo,
            "path": path,
            "ref": self.ref or texts.intake_placeholder_default_branch,
        }
        try:
            text = self.store.repository_file(path, ref=self.ref)
            specs = _LABEL_SPECS.validate_python(yaml.safe_load(text))
        except GitHubFileNotFoundError as exc:
            missing = texts.intake_labels_missing.format(**where)
            raise ConfigurationError(missing, details={"path": path}) from exc
        except (yaml.YAMLError, InvalidLabelsError) as exc:
            unreadable = texts.intake_labels_unreadable.format(**where, error=str(exc)[:200])
            raise ConfigurationError(unreadable, details={"path": path}) from exc
        types = tuple(
            spec.name
            for spec in specs
            if spec.name.startswith(CONST_ROADMAP_TYPE_LABEL_PREFIX)
            and spec.name != CONST_ROADMAP_EPIC_LABEL
        )
        if not types:
            untyped = texts.intake_labels_untyped.format(**where)
            raise ConfigurationError(untyped, details={"path": path})
        return types


def _subject(issue: IssueRecord, item: Item | None = None) -> Subject:
    return Subject(
        title=issue.title,
        body=issue.body,
        number=issue.number,
        labels=issue.labels,
        milestone=issue.milestone,
        author_association=issue.author_association,
        updated_at=issue.updated_at,
        item=item,
        sub_issues=issue.sub_issues,
    )


def _new_subject(run: _Run, new: NewCandidate) -> Subject:
    """The subject of a new candidate: the open issue that is not finished and holds the title
    and body that intake files for it, which a run that stopped after filing leaves, or else the
    candidate itself, to file (#2218)."""
    body = new.filed_body()
    for issue in run.issues:
        item = run.board.get(issue.number)
        unfinished = item is None or item.priority is None
        if (
            issue.state is GitHubState.OPEN
            and unfinished
            and (issue.title, issue.body)
            == (
                new.title,
                body,
            )
        ):
            return replace(_subject(issue, item), new=new)
    return Subject(title=new.title, body=body, new=new)


def _subjects(
    run: _Run, issues: Collection[int], new: NewCandidate | None
) -> tuple[list[Subject], tuple[int, ...]]:
    """The candidates this run decides, by number, and the asked-for numbers that are none."""
    if new is not None:
        return [_new_subject(run, new)], ()
    found = [
        _subject(issue, run.board.get(issue.number))
        for issue in run.issues
        if issue.state is GitHubState.OPEN
        and (issue.number not in run.board or run.board[issue.number].priority is None)
    ]
    if not issues:
        return found, ()
    chosen = [subject for subject in found if subject.number in issues]
    return chosen, tuple(sorted(set(issues) - {subject.number for subject in chosen}))


@dataclass(frozen=True)
class _Queue:
    """The candidates a limited run decides, those it leaves, and whether a fresh one is left."""

    decided: list[Subject]
    left: tuple[int, ...]
    fresh_left: bool


def _queue(subjects: Sequence[Subject], waiting: Mapping[int, Waiting], limit: int) -> _Queue:
    """The first `limit` candidates: the fresh ones, never decided or edited since they were,
    oldest (lowest number) first, then the others, longest waiting first."""

    def fresh(subject: Subject) -> bool:
        before = waiting.get(subject.number or 0)
        return before is None or before.updated_at != subject.updated_at

    renewed = sorted((s for s in subjects if fresh(s)), key=lambda s: s.number or 0)
    waited = sorted(
        (s for s in subjects if not fresh(s)), key=lambda s: waiting[s.number or 0].decided_at
    )
    ordered = renewed + waited
    left = tuple(subject.number for subject in ordered[limit:] if subject.number is not None)
    return _Queue(ordered[:limit], left, len(renewed) > limit)


# ── The duplicate check ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Entry:
    """An item, a not-planned issue or an open agent issue off the board, that a candidate is
    compared with; `done` when it is a completed item."""

    number: int | None
    title: str
    body: str
    state: str
    done: bool = False

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.body}"[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS]

    def neighbour(self) -> Neighbour:
        assert self.number is not None
        excerpt = self.body[:DEFAULT_ROADMAP_INTAKE_EXCERPT_CHARS]
        return Neighbour(number=self.number, title=self.title, state=self.state, excerpt=excerpt)


def _is_done(issue: IssueRecord, run: _Run) -> bool:
    """Whether `issue` is a completed/Done item on the board or in GitHub."""
    if issue.state is GitHubState.CLOSED and issue.state_reason != CloseReason.NOT_PLANNED:
        return True
    card = run.board.get(issue.number)
    return card is not None and card.status == CONST_ROADMAP_STATUS_DONE


def _compared(issue: IssueRecord, run: _Run, *, off_board: bool) -> bool:
    """Whether a candidate is compared with `issue`: an item, an issue closed as not planned,
    and with `off_board` an open agent issue that is not on the board. An issue that has
    sub-issues is none of them: its sub-issues deliver it (#1985)."""
    if issue.sub_issues:
        return False
    if issue.number in run.board:
        return True
    if issue.state is GitHubState.CLOSED:
        return issue.state_reason == CloseReason.NOT_PLANNED
    return off_board and CONST_ROADMAP_SOURCE_AGENT_LABEL in issue.labels


def _comparison(run: _Run, *, off_board: bool) -> list[_Entry]:
    """Every item, open or closed, and every issue closed as not planned; with `off_board`, for
    a new candidate, also the open agent issues off the board."""
    return [
        _Entry(issue.number, issue.title, issue.body, issue.state.value, done=_is_done(issue, run))
        for issue in run.issues
        if _compared(issue, run, off_board=off_board)
    ]


def _source_issue(run: _Run, subject: Subject) -> int | None:
    """The issue of the repository that a new candidate's source links, such as the issue it
    splits: the issue whose GitHub link is the source with no query or fragment, so a link to
    one of its comments names it too (#1985)."""
    source = subject.new.source if subject.new is not None else None
    if not source:
        return None
    link = urlsplit(source.strip())._replace(query="", fragment="").geturl()
    return next((issue.number for issue in run.issues if issue.url == link), None)


def _with_regression_reference(subject: Subject, entry: _Entry) -> Subject:
    """Add a regression reference to the candidate's body when it matches a Done item."""
    ref = f"regression of #{entry.number}"
    if ref in subject.body:
        return subject
    body = f"{subject.body}\n\n{ref}" if subject.body else ref
    return replace(subject, body=body)


def _reopened_after_duplicate(closures: Sequence[Closure]) -> bool:
    """Whether a person reopened the issue after a duplicate close, which their decision overrules."""
    closed_as_duplicate = False
    for closure in closures:
        if closure.kind is ChangeKind.CLOSED and closure.reason == CloseReason.DUPLICATE:
            closed_as_duplicate = True
        elif closure.kind is ChangeKind.REOPENED and closed_as_duplicate:
            return True
    return False


def _checked(run: _Run, subject: Subject) -> bool:
    """Whether the candidate goes through the duplicate check."""
    if subject.item is not None:
        return False
    return subject.number is None or not _reopened_after_duplicate(
        run.store.closures(subject.number)
    )


def _line(text: str) -> str:
    """A model's reason as one short line of inline code, so a `#N` in it links no issue and an
    `@name` notifies no one; its own backticks become quotes so it can't leave the code."""
    line = " ".join(text.replace("`", "'").split())[:DEFAULT_ROADMAP_INTAKE_REASON_CHARS]
    return f"`{line}`" if line else ""


def _named_number(value: int | str | None) -> int | None:
    """The issue number the model named, as a number or as text such as `#740`."""
    if isinstance(value, int):
        return value
    digits = (value or "").strip().removeprefix("#")
    return int(digits) if digits.isdecimal() else None


# ── Checking the proposal ─────────────────────────────────────────────────────


def _choice(name: str, value: str, choices: Sequence[str], problems: list[str]) -> str:
    if value not in choices:
        problems.append(
            MESSAGES.roadmap.intake_invalid_value.format(
                field=name, value=value[:64], choices=", ".join(choices)
            )
        )
    return value


def _priority_choice(value: str, problems: list[str], notes: list[str]) -> str:
    """The model's priority; a P0 is capped at P1, as only verified evidence sets P0."""
    if value in CONST_ROADMAP_P0_PRIORITIES:
        capped = CONST_ROADMAP_MODEL_PRIORITIES[0]
        notes.append(
            MESSAGES.roadmap.intake_note_priority_capped.format(priority=value, capped=capped)
        )
        return capped
    return _choice("priority", value, CONST_ROADMAP_MODEL_PRIORITIES, problems)


def _evidence(raw: ModelEvidence | None, notes: list[str]) -> Evidence | None:
    """The model's evidence, when its kind is known and its value has that kind's shape."""
    if raw is None or not (raw.kind or raw.value):
        return None
    pattern = CONST_ROADMAP_EVIDENCE_PATTERNS.get(raw.kind)
    if pattern is None or pattern.fullmatch(raw.value) is None:
        notes.append(
            MESSAGES.roadmap.intake_note_evidence_dropped.format(
                kind=raw.kind[:32], value=raw.value[:64]
            )
        )
        return None
    return Evidence(kind=EvidenceKind(raw.kind), value=raw.value)


def validate_proposal(raw: ModelProposal, types: Sequence[str], *, needs_type: bool) -> Proposal:
    """The proposal once every value is on its list; raises `_InvalidProposal` otherwise."""
    problems: list[str] = []
    notes: list[str] = []
    proposal = Proposal(
        type=_choice("type", raw.type, types, problems) if needs_type else raw.type,
        type_reason=_line(raw.type_reason),
        priority=_priority_choice(raw.priority, problems, notes),
        priority_reason=_line(raw.priority_reason),
        value=_choice("value", raw.value, CONST_ROADMAP_SIZE_OPTIONS, problems),
        value_reason=_line(raw.value_reason),
        effort=_choice("effort", raw.effort, CONST_ROADMAP_SIZE_OPTIONS, problems),
        effort_reason=_line(raw.effort_reason),
        evidence=_evidence(raw.evidence, notes),
        notes=tuple(notes),
    )
    if problems:
        raise _InvalidProposal(
            MESSAGES.roadmap.intake_invalid.format(problems="; ".join(problems)),
            problems=tuple(problems),
        )
    return proposal


@dataclass(frozen=True)
class _Judgement:
    """What the model's reply says of the shortlist once code has read it: the possible original
    of a duplicate, or the item a candidate is related to, with its reason, and a note for each
    number code did not take (#1755, #2218)."""

    possible_duplicate: int | None = None
    related: int | None = None
    reason: str = ""
    notes: tuple[str, ...] = ()


def _related(
    raw: ModelProposal, shortlist: Mapping[int, _Entry], notes: tuple[str, ...] = ()
) -> _Judgement:
    """The item the model named as related, when it is on the shortlist."""
    named = _named_number(raw.related_to)
    if named is None:
        return _Judgement(notes=notes)
    if named not in shortlist:
        rejected = MESSAGES.roadmap.intake_note_related_rejected.format(number=named)
        return _Judgement(notes=(*notes, rejected))
    return _Judgement(related=named, reason=_line(raw.related_reason), notes=notes)


def _judge(
    raw: ModelProposal, shortlist: Mapping[int, _Entry], subject: Subject
) -> tuple[_Judgement, Subject]:
    """The possible original or related item the reply names, and the candidate, with a
    reference to the Done item it names as the original. An original named with no change both
    items ask for is a related item, not a possible original."""
    named = _named_number(raw.duplicate_of)
    if named is None or named not in shortlist:
        return _related(raw, shortlist, _rejected(named)), subject
    entry = shortlist[named]
    if entry.done:
        return _related(raw, shortlist), _with_regression_reference(subject, entry)
    change, said = _line(raw.shared_change), _line(raw.duplicate_reason)
    if not change:
        unnamed = MESSAGES.roadmap.intake_note_no_shared_change.format(number=named)
        related = _Judgement(related=named, reason=said, notes=(unnamed,))
        return related, subject
    reason = MESSAGES.roadmap.intake_duplicate_reason.format(change=change, reason=said)
    return _Judgement(possible_duplicate=named, reason=reason.strip()), subject


def _resolve_raw(
    raw: ModelProposal,
    types: Sequence[str],
    shortlist: Mapping[int, _Entry],
    subject: Subject,
    *,
    needs_type: bool,
) -> tuple[_Judgement, Proposal, Subject]:
    """The reply's judgement, and its proposal once checked."""
    judgement, subject = _judge(raw, shortlist, subject)
    return judgement, validate_proposal(raw, types, needs_type=needs_type), subject


def _kind_name(evidence: Evidence) -> str:
    return evidence.kind.value.replace("_", " ")


def _p0_refusal(store: RoadmapStore, subject: Subject, evidence: Evidence) -> str | None:
    """Why the evidence does not set P0, or None when it does."""
    attached = subject.new is not None and evidence in subject.new.evidence
    if not attached and not subject.cites(evidence.value):
        return MESSAGES.roadmap.intake_why_not_verbatim
    if not (attached or subject.trusted):
        return MESSAGES.roadmap.intake_why_untrusted
    if not store.evidence_holds(evidence):
        return MESSAGES.roadmap.intake_why_unconfirmed[evidence.kind.value]
    return None


def _priority(store: RoadmapStore, subject: Subject, proposal: Proposal) -> tuple[str, str]:
    """The Priority intake sets, and its reason."""
    evidence = proposal.evidence
    if evidence is None:
        return proposal.priority, proposal.priority_reason
    why = _p0_refusal(store, subject, evidence)
    named = {"kind": _kind_name(evidence), "value": evidence.value}
    if why is None:
        return CONST_ROADMAP_CRITICAL_PRIORITY, MESSAGES.roadmap.intake_p0_granted.format(**named)
    refused = MESSAGES.roadmap.intake_p0_refused.format(why=why, **named)
    return proposal.priority, f"{proposal.priority_reason} {refused}".strip()


# ── Placement ─────────────────────────────────────────────────────────────────


def _to_backlog(reason: str) -> Placement:
    return Placement(None, MESSAGES.roadmap.intake_placement_backlog.format(reason=reason))


def _kept(milestone: str, reason: str) -> Placement:
    return Placement(
        milestone,
        MESSAGES.roadmap.intake_placement_kept.format(milestone=milestone, reason=reason),
    )


def _resumed(milestone: str) -> Placement:
    """An item's milestone, which it keeps."""
    return _kept(milestone, MESSAGES.roadmap.intake_reason_resumed.format(milestone=milestone))


def _placement(subject: Subject) -> Placement:
    """Where the candidate stays: the milestone it has, or the backlog. Intake sets none."""
    if subject.milestone is None:
        return _to_backlog(MESSAGES.roadmap.intake_reason_backlog)
    if subject.item is not None:
        return _resumed(subject.milestone)
    reason = MESSAGES.roadmap.intake_reason_person.format(milestone=subject.milestone)
    return _kept(subject.milestone, reason)


# ── Deciding ──────────────────────────────────────────────────────────────────


def _filing_labels(subject: Subject) -> tuple[str, ...]:
    """The labels a new candidate is filed with: `source/agent` when an agent files it."""
    if subject.new is None or not subject.agent:
        return ()
    return (CONST_ROADMAP_SOURCE_AGENT_LABEL,)


def _reason_lines(
    proposal: Proposal,
    type_label: str | None,
    fields: Sequence[tuple[ItemField, str]],
    priority: tuple[str, str],
    judgement: _Judgement,
) -> tuple[tuple[str, str, str], ...]:
    """Each value intake sets that the reason comment gives, with its name and reason, then
    the possible original or the related item, whose number the comment links."""
    reasons = {ItemField.VALUE: proposal.value_reason, ItemField.EFFORT: proposal.effort_reason}
    lines = [("Type", type_label, proposal.type_reason)] if type_label else []
    lines.append((ItemField.PRIORITY.value, priority[0], priority[1]))
    lines += [(f.value, value, reasons[f]) for f, value in fields if f in reasons]
    texts = MESSAGES.roadmap
    if judgement.possible_duplicate is not None:
        original = texts.intake_possible_duplicate_value.format(number=judgement.possible_duplicate)
        why = texts.intake_possible_duplicate_reason.format(reason=judgement.reason)
        lines.append((texts.intake_possible_duplicate_field, original, why))
    if judgement.related is not None:
        related = texts.intake_related_value.format(number=judgement.related)
        lines.append((texts.intake_related_field, related, judgement.reason))
    return tuple(lines)


def _comment(placement: Placement, lines: Sequence[tuple[str, str, str]]) -> str:
    """The reason comment: where the item went, and each value intake set with its reason. A
    line with no reason ends at its value."""
    rendered = "\n".join(
        MESSAGES.roadmap.intake_comment_field.format(
            field=name, value=value, reason=reason
        ).rstrip()
        for name, value, reason in lines
    )
    return MESSAGES.roadmap.intake_comment.format(
        marker=CONST_ROADMAP_INTAKE_REASON_MARKER, placement=placement.text, fields=rendered
    )


def _has_comment(store: RoadmapStore, subject: Subject, marker: str) -> bool:
    """Whether intake already left the comment `marker` marks on the candidate."""
    return subject.number is not None and any(
        marker in comment.body for comment in store.comments_on(subject.number)
    )


def _fields(subject: Subject, proposal: Proposal) -> tuple[tuple[ItemField, str], ...]:
    """Status, Value and Effort, those the item has no value for."""
    wanted = (
        (ItemField.STATUS, CONST_ROADMAP_STATUS_NEW),
        (ItemField.VALUE, proposal.value),
        (ItemField.EFFORT, proposal.effort),
    )
    item = subject.item
    return tuple((f, v) for f, v in wanted if item is None or item.field_value(f) is None)


def _shown(
    subject: Subject, type_label: str, priority: str, proposal: Proposal
) -> tuple[str, str, str, str]:
    item = subject.item
    value = (item.value if item else None) or proposal.value
    effort = (item.effort if item else None) or proposal.effort
    return (type_label, priority, value, effort)


def _rejected(named: int | None) -> tuple[str, ...]:
    """The note for an original the model named outside the shortlist."""
    if named is None:
        return ()
    return (MESSAGES.roadmap.intake_note_duplicate_rejected.format(number=named),)


@dataclass
class _Planner:
    """Decides each candidate in turn; one it places joins the comparison set. With
    `off_board`, for a new candidate, the open agent issues off the board join it too."""

    run: _Run
    off_board: bool = False
    entries: list[_Entry] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)

    def decide_all(self, subjects: Sequence[Subject]) -> Iterator[IntakeDecision]:
        """Each candidate's decision, in turn. A run with a candidate reads `.github/labels.yml`
        first, so a file it can't use stops it before any timeline read or model call (#1358).
        A placed candidate that has sub-issues does not join the comparison set (#1985)."""
        if not subjects:
            return
        _ = self.run.types
        checked = [_checked(self.run, subject) for subject in subjects]
        own = self._embed(subjects, checked)
        for subject, vector in zip(subjects, own, strict=True):
            decision = self._decide(subject, vector)
            joins = decision.outcome is Outcome.PLACE and not subject.sub_issues
            if joins and vector is not None:
                self.entries.append(_Entry(subject.number, subject.title, subject.body, "open"))
                self.vectors.append(vector)
            yield decision

    def _embed(
        self, subjects: Sequence[Subject], checked: Sequence[bool]
    ) -> list[list[float] | None]:
        """Embed the comparison set and the checked candidates in one call, or nothing at all."""
        if not any(checked):
            return [None] * len(subjects)
        self.entries = _comparison(self.run, off_board=self.off_board)
        texts = [entry.text for entry in self.entries]
        texts += [subject.text for subject, check in zip(subjects, checked, strict=True) if check]
        vectors = self.run.model.embed(texts)
        self.vectors = vectors[: len(self.entries)]
        own = iter(vectors[len(self.entries) :])
        return [next(own) if check else None for check in checked]

    def _shortlist(self, vector: list[float] | None, apart: Collection[int]) -> list[_Entry]:
        """The comparison entries other than those `apart` names, nearest first, at most
        `DEFAULT_ROADMAP_INTAKE_SHORTLIST` of them."""
        if vector is None:
            return []
        indexes = [
            index
            for index, entry in enumerate(self.entries)
            if entry.number is not None and entry.number not in apart
        ]
        nearest = sorted(
            indexes,
            key=lambda index: cosine_similarity(self.vectors[index], vector),
            reverse=True,
        )
        return [self.entries[index] for index in nearest[:DEFAULT_ROADMAP_INTAKE_SHORTLIST]]

    def _decide(self, subject: Subject, vector: list[float] | None) -> IntakeDecision:
        """The candidate's decision, compared with neither itself nor the issue its source
        links (#1985)."""
        own = (subject.number, _source_issue(self.run, subject))
        apart = {number for number in own if number is not None}
        shortlist = self._shortlist(vector, apart)
        request = ProposalRequest(
            title=subject.title,
            body=subject.body[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS],
            shortlist=tuple(entry.neighbour() for entry in shortlist),
            types=self.run.types,
        )
        return self._propose(subject, request, vector, shortlist)

    def _propose(
        self,
        subject: Subject,
        request: ProposalRequest,
        vector: list[float] | None,
        shortlist: list[_Entry],
    ) -> IntakeDecision:
        shortlist_entries = {entry.number: entry for entry in shortlist if entry.number is not None}
        needs_type = subject.type_label is None
        try:
            raw = self.run.model.propose(request)
            judgement, proposal, subject = _resolve_raw(
                raw, self.run.types, shortlist_entries, subject, needs_type=needs_type
            )
        except UnusableProposalError as exc:
            return self._skipped(subject, str(exc), ())
        except _InvalidProposal as first_exc:
            return self._retry_proposal(
                subject, request, vector, shortlist_entries, first_exc, needs_type=needs_type
            )
        return self._place(subject, proposal, judgement)

    def _retry_proposal(
        self,
        subject: Subject,
        request: ProposalRequest,
        vector: list[float] | None,
        shortlist_entries: dict[int, _Entry],
        first_exc: _InvalidProposal,
        *,
        needs_type: bool,
    ) -> IntakeDecision:
        retry_request = replace(request, problem="; ".join(first_exc.problems))
        try:
            raw = self.run.model.propose(retry_request)
            judgement, proposal, subject = _resolve_raw(
                raw, self.run.types, shortlist_entries, subject, needs_type=needs_type
            )
        except UnusableProposalError as exc:
            return self._skipped(subject, str(exc), ())
        except _InvalidProposal as second_exc:
            both = (*first_exc.problems, *second_exc.problems)
            reason = MESSAGES.roadmap.intake_invalid.format(problems="; ".join(both))
            return self._skipped(subject, reason, ())
        return self._place(subject, proposal, judgement)

    def _skipped(self, subject: Subject, reason: str, notes: tuple[str, ...]) -> IntakeDecision:
        """A candidate with no usable proposal: nothing is written."""
        return IntakeDecision(subject, Outcome.SKIP, reason=reason, notes=notes)

    def _place(self, subject: Subject, proposal: Proposal, judgement: _Judgement) -> IntakeDecision:
        type_label = subject.type_label or proposal.type
        priority = _priority(self.run.store, subject, proposal)
        placement = _placement(subject)
        fields = _fields(subject, proposal)
        added = None if subject.type_label else type_label
        lines = _reason_lines(proposal, added, fields, priority, judgement)
        comment = (
            None
            if _has_comment(self.run.store, subject, CONST_ROADMAP_INTAKE_REASON_MARKER)
            else _comment(placement, lines)
        )
        return IntakeDecision(
            subject,
            Outcome.PLACE,
            labels=(added,) if added else (),
            placement=placement,
            fields=fields,
            priority=priority[0],
            comment=comment,
            filing_labels=_filing_labels(subject),
            shown=_shown(subject, type_label, priority[0], proposal),
            notes=judgement.notes + proposal.notes,
            reasons=lines,
            possible_duplicate=judgement.possible_duplicate,
            duplicate_reason=judgement.reason if judgement.possible_duplicate is not None else "",
            related=judgement.related,
            related_reason=judgement.reason if judgement.related is not None else "",
        )


def plan_intake(
    store: RoadmapStore,
    *,
    repo: str,
    model: IntakeModel,
    ref: str | None = None,
    issues: Collection[int] = (),
    new: NewCandidate | None = None,
    limit: int | None = None,
    waiting: Mapping[int, Waiting] | None = None,
) -> IntakePlan:
    """Decide every candidate of `repo`, whose roadmap `store` reads, or only `issues`, or only
    the `new` candidate, writing nothing; with `limit`, at most that many, fresh ones first, by
    what `waiting` says was decided before.

    A `new` candidate whose text looks like it holds a secret raises `SecurityError` first.
    """
    if new is not None:
        new.refuse_secrets()
    run = _Run(
        store=store,
        repo=repo,
        model=model,
        ref=ref,
        issues=store.issues(),
        board={item.number: item for item in store.items()},
    )
    subjects, missing = _subjects(run, issues, new)
    queue = _Queue(subjects, (), False) if limit is None else _queue(subjects, waiting or {}, limit)
    decisions = tuple(_Planner(run, off_board=new is not None).decide_all(queue.decided))
    return IntakePlan(
        decisions=decisions,
        missing=missing,
        limit=limit,
        left=queue.left,
        fresh_left=queue.fresh_left,
    )


def dry_run_intake(
    repo: str,
    *,
    ref: str | None = None,
    issues: Collection[int] = (),
    new: NewCandidate | None = None,
    limit: int | None = None,
) -> IntakePlan:
    """The plan a dry run returns: no request made, the requests a run on `repo` over every
    candidate, only `issues`, or only the `new` candidate makes, in order, with placeholders for
    what a read gives; with `limit`, its per-candidate requests say they are for that many. A
    `new` candidate whose text looks like it holds a secret raises `SecurityError`, as it does
    for a run."""
    each = new is None and not issues
    if new is not None:
        new.refuse_secrets()
        subjects = [MESSAGES.roadmap.intake_new.format(title=new.title)]
    elif issues:
        subjects = [f"#{number}" for number in sorted(set(issues))]
    else:
        subjects = [MESSAGES.roadmap.intake_placeholder_each]
    reads, writes = planned_requests(
        subjects, repo=repo, ref=ref, new=new is not None, each=each, limit=limit
    )
    return IntakePlan(decisions=(), limit=limit, dry_run=True, requests=reads, writes=writes)


# ── Writing ───────────────────────────────────────────────────────────────────


def _unset(item: AddedItem, board_field: ItemField, value: str) -> bool:
    """Whether the card the add returned holds no value for `board_field`; on a card the add
    did not restore, also the Status New the board's "Item added to project" workflow sets,
    which intake writes again so that its job record holds it."""
    held = item.field_value(board_field)
    new_status = not item.restored and board_field is ItemField.STATUS and held == value
    return held is None or new_status


def _on_card(decision: IntakeDecision, item: AddedItem) -> IntakeDecision | None:
    """The decision for the card the add returned, which planning did not see: None when it
    holds a Priority, as an item intake would not have taken; otherwise the planned writes of
    the fields it holds no value for, with the milestone a restored card has kept, as an item's
    is, and the reason comment for those writes (#1403)."""
    if item.priority is not None:
        return None
    kept = decision.subject.milestone
    placement = _resumed(kept) if item.restored and kept is not None else decision.placement
    fields = tuple((f, v) for f, v in decision.fields if _unset(item, f, v))
    held = {f.value for f, _ in decision.fields} - {f.value for f, _ in fields}
    lines = tuple(line for line in decision.reasons if line[0] not in held)
    comment = None if decision.comment is None or placement is None else _comment(placement, lines)
    return replace(decision, placement=placement, fields=fields, reasons=lines, comment=comment)


def _apply_placement(
    store: RoadmapStore, decision: IntakeDecision
) -> tuple[int, IntakeDecision | None]:
    """Make one placement's writes in order, Priority last; the issue's number, and the
    decision the writes followed, None when the card the add returned holds a Priority."""
    subject = decision.subject
    number = subject.number
    if number is None:
        filed = store.create_issue(subject.title, subject.body, labels=decision.filing_labels)
        number = filed.number
    for label in decision.labels:
        store.label_issue(number, label)
    item: Item | None = subject.item
    if item is None:
        item = store.add_item(number)
        on_card = _on_card(decision, item)
        if on_card is None:
            return number, None
        decision = on_card
    _write_fields(store, item, decision, number)
    return number, decision


def _write_fields(store: RoadmapStore, item: Item, decision: IntakeDecision, number: int) -> None:
    """The writes after the add: the fields, the reason comment, then Priority."""
    assert decision.priority is not None
    for board_field, value in decision.fields:
        store.set_field(item, board_field, value)
    if decision.comment:
        store.comment(number, decision.comment)
    store.set_field(item, ItemField.PRIORITY, decision.priority)


def _apply_decision(store: RoadmapStore, decision: IntakeDecision) -> IntakeApplied:
    """One candidate's writes, and what they wrote."""
    if decision.outcome is not Outcome.PLACE:
        return IntakeApplied()
    number, applied = _apply_placement(store, decision)
    filed = () if decision.subject.number else (number,)
    if applied is None:
        return IntakeApplied(filed=filed, finished=(number,))
    return IntakeApplied(placed=1, filed=filed)


def _failed_placement(subject: Subject, exc: GitHubOperationError) -> PlacementFailure:
    """Record `subject` as skipped for its failed write, with the error's class."""
    failure = PlacementFailure(subject.number, subject.title, type(exc).__name__)
    logger.warning(MESSAGES.roadmap.intake_skipped.format(name=failure.name, error=exc))
    return failure


def apply_intake(
    store: RoadmapStore,
    plan: IntakePlan,
) -> IntakeApplied:
    """Make the plan's writes, one candidate at a time. A candidate whose write fails is
    skipped and named in `failed`, and the others are still written (#1443). A rate limit, a
    GraphQL budget refusal or a token GitHub refuses stops the round, since every later write
    would be refused too (#983)."""
    written: list[IntakeApplied] = []
    failed: list[PlacementFailure] = []
    for decision in plan.decisions:
        try:
            written.append(_apply_decision(store, decision))
        except GitHubRateLimitError, GitHubUnauthenticatedError:
            raise
        except GitHubOperationError as exc:
            failed.append(_failed_placement(decision.subject, exc))
    return IntakeApplied(
        placed=sum(each.placed for each in written),
        filed=tuple(number for each in written for number in each.filed),
        finished=tuple(number for each in written for number in each.finished),
        failed=tuple(failed),
    )


def raise_for_failed_placements(applied: IntakeApplied) -> None:
    """Fail a round in which any candidate's write failed, once the others are written: the
    error names each skipped candidate with its error's class (#1443)."""
    if not applied.failed:
        return
    texts = MESSAGES.roadmap
    items = ", ".join(
        texts.intake_failed_item.format(name=failure.name, error=failure.error)
        for failure in applied.failed
    )
    raise RoadmapIntakeError(
        texts.intake_failed.format(count=len(applied.failed), items=items),
        failed_items=[failure.number for failure in applied.failed if failure.number is not None],
    )


def intake_candidate(
    store: RoadmapStore,
    candidate: NewCandidate,
    *,
    repo: str,
    model: IntakeModel,
    ref: str | None = None,
    confirm: bool = False,
) -> CandidateOutcome:
    """The entry point discovery (#745) and the review hand-off call: decide one candidate that
    is not an issue yet, and with `confirm` file and place it, or place the issue that a stopped
    run filed for it."""
    plan = plan_intake(store, repo=repo, model=model, ref=ref, new=candidate)
    (decision,) = plan.decisions
    applied = apply_intake(store, plan) if confirm else None
    if applied is not None:
        raise_for_failed_placements(applied)
    number = applied.filed[0] if applied and applied.filed else None
    if applied is not None and number is None and decision.outcome is Outcome.PLACE:
        number = decision.subject.number
    return CandidateOutcome(plan=plan, decision=decision, number=number)


# ── The report ────────────────────────────────────────────────────────────────


def _decision_lines(decision: IntakeDecision) -> list[str]:
    texts = MESSAGES.roadmap
    subject = decision.subject.name
    if decision.outcome is Outcome.SKIP:
        return [texts.intake_skip_line.format(subject=subject, reason=decision.reason)]
    assert decision.placement is not None
    kind, priority, value, effort = decision.shown
    placed = texts.intake_place_line.format(
        subject=subject,
        type=kind,
        priority=priority,
        value=value,
        effort=effort,
        placement=decision.placement.text,
    )
    lines = [placed]
    if decision.possible_duplicate is not None:
        possible = texts.intake_possible_duplicate_line.format(
            number=decision.possible_duplicate, reason=decision.duplicate_reason
        )
        lines.append(possible.rstrip())
    if decision.related is not None:
        related = texts.intake_related_line.format(
            number=decision.related, reason=decision.related_reason
        )
        lines.append(related.rstrip())
    return lines


def render_intake_dry_run(plan: IntakePlan, *, repo: str) -> None:
    """Print a dry run's report: the requests a run makes, numbered in order, then the writes
    `--confirm` adds, each command as it would run."""
    texts = MESSAGES.roadmap
    heading = "\n\n".join([texts.intake_title.format(repo=repo), texts.intake_dry_run])
    render_request_plan(heading, plan.requests, described=True)
    notes = texts.plan_dry_run_notes
    render_request_plan(texts.intake_dry_run_writes, plan.writes, notes, described=True)


def render_intake(plan: IntakePlan, *, repo: str) -> str:
    """The run's report: each candidate, its writes and notes, and what the run spent. A dry
    run prints through `render_intake_dry_run`."""
    texts = MESSAGES.roadmap
    lines = [texts.intake_title.format(repo=repo), ""]
    if not plan.decisions and not plan.missing:
        lines.append(texts.intake_nothing)
    for decision in plan.decisions:
        lines += _decision_lines(decision)
        if decision.has_writes:
            lines.append(texts.intake_writes.format(writes="; ".join(decision.writes())))
        lines += [texts.intake_note.format(note=note) for note in decision.notes]
    lines += [texts.intake_not_candidate.format(number=number) for number in plan.missing]
    left = ", ".join(f"#{number}" for number in plan.left)
    lines += [texts.intake_left.format(limit=plan.limit, left=left)] if plan.left else []
    lines += ["", plan.spend.render()] if plan.spend is not None else []
    return "\n".join(lines) + "\n"


__all__ = [
    "CandidateOutcome",
    "Filer",
    "IntakeApplied",
    "IntakeDecision",
    "IntakePlan",
    "IntakeRecord",
    "NewCandidate",
    "Outcome",
    "Placement",
    "PlacementFailure",
    "Proposal",
    "Subject",
    "Waiting",
    "apply_intake",
    "dry_run_intake",
    "intake_candidate",
    "plan_intake",
    "raise_for_failed_placements",
    "render_intake",
    "render_intake_dry_run",
    "validate_proposal",
]
