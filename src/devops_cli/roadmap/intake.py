"""`devops roadmap intake`: the single way new work becomes an item (#742).

A candidate is an open issue not on the board (an archived card is not on it), a board item intake
left without a Priority (an unfinished item), or a candidate that is not an issue yet
(`NewCandidate`), which `--title` and `--body-file` and the Python entry point `intake_candidate`
take. Intake plans every candidate before it writes anything, model calls included, so a model
gateway that does not answer (`ModelGatewayUnreachableError`) leaves GitHub as it was.

**Duplicates.** A candidate is compared with every item on the board, open or closed, and every
issue closed as not planned, plus the candidates this run placed before it; a new candidate is
also compared with the open agent issues off the board, which a run that stopped after filing
leaves. Each text is embedded once, and the model judges the candidate against its nearest
`DEFAULT_ROADMAP_INTAKE_SHORTLIST` items, by cosine similarity. A duplicate issue is closed as a
duplicate of the original, with one comment, and stays off the board; a new candidate that is a
duplicate is not filed. An unfinished item, and an issue whose timeline shows a duplicate close
that a person reversed by reopening it, skip the check. A new candidate whose text holds what
looks like a secret is refused before it reaches a model or GitHub.

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

**Placement.** A critical fix (P0 with `type/bug` or `type/security`) goes where #740's table
admits a fix joining the current release (`decide`): into the current release, its release
pull request open or not, or into the next planned one once that pull request has merged.
Everything else, a P0 feature included, goes to the backlog. A planned release a person set
stands; the current release goes through the same table. An unfinished item keeps any milestone
it has.

**Writes**, in order, with Priority last, which marks the item finished: file the issue (a new
candidate only), add a `type/*` label when it has none, put it on the board, set the milestone
when the placement changes it, set the empty ones of Status (New), Value and Effort, leave one
reason comment carrying `CONST_ROADMAP_INTAKE_REASON_MARKER` unless one is there, then set
Priority. Each field write goes to the card the item has, or the card the add returned: no
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

A duplicate close comments with `CONST_ROADMAP_INTAKE_DUPLICATE_MARKER` unless that comment is
there, then closes. A run that stops part-way leaves an open issue off the board, an item with no
Priority, or an open duplicate, and the next run finishes it. Intake writes to no issue but the
candidate.

**Dry run, plan, confirm** (the dry-run rule of #412). `dry_run_intake` makes no request, to
GitHub or a model: it returns an `IntakePlan` marked `dry_run`, with no quota or decision, that
holds the requests a run makes, in order, with placeholders for what a read gives
(`intake_requests`). `plan_intake` makes the reads and the model calls and writes nothing; the
command reports what it spent. `apply_intake` makes the writes.

**The agent filing quota (#1153).** Every run reads the counts the quota needs through REST
search and reports them. A new candidate comes from an agent unless its caller says a person
filed it (`Filer`); an agent's is labeled `source/agent` and opens while the cycle's agent
openings are below the allowance. Beyond it, a split or a required follow-up (`BorrowReason`)
with the link it came from, or a P0/P1 bug or security issue, borrows (`budget/borrowed`), and
anything else folds into its nearest open item: nothing is filed, and the report names the
item. A duplicate folds into its original. An open `source/agent` issue filed outside intake is
already counted: it opens when it is within the allowance by the order agents opened issues
this cycle, borrows (and is labeled) when it may, and otherwise stays off the board for a person
to fold. Two runs at once can both open within one slot, as search lags recent filings.
"""

from __future__ import annotations

import logging
import string
from collections.abc import Callable, Collection, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from functools import cached_property
from typing import Any

import yaml
from pydantic import TypeAdapter
from pydantic import ValidationError as InvalidLabelsError

from devops_cli.ai.vector_similarity import cosine_similarity
from devops_cli.config.constants import (
    CONST_ROADMAP_BORROWED_LABEL,
    CONST_ROADMAP_BORROWING_PRIORITIES,
    CONST_ROADMAP_CRITICAL_FIX_LABELS,
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_EVIDENCE_PATTERNS,
    CONST_ROADMAP_INTAKE_DUPLICATE_MARKER,
    CONST_ROADMAP_INTAKE_REASON_MARKER,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_MODEL_PRIORITIES,
    CONST_ROADMAP_P0_PRIORITY,
    CONST_ROADMAP_SIZE_OPTIONS,
    CONST_ROADMAP_SOURCE_AGENT_LABEL,
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
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.exceptions.security import SecurityError
from devops_cli.github.labels import LabelSpec
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import quota
from devops_cli.roadmap.config import RoadmapConfig
from devops_cli.roadmap.intake_model import (
    IntakeModel,
    ModelEvidence,
    ModelProposal,
    Neighbour,
    ProposalRequest,
    UnusableProposalError,
)
from devops_cli.roadmap.intake_requests import Spend, planned_requests
from devops_cli.roadmap.reprioritize import (
    Action,
    Event,
    Reason,
    ReleaseState,
    admission_event,
    current_release,
    decide,
    release_state,
)
from devops_cli.roadmap.store import (
    AddedItem,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    EvidenceKind,
    GitHubState,
    IssueQuery,
    IssueRecord,
    Item,
    ItemField,
    Release,
    RoadmapStore,
    in_release,
)
from devops_cli.security.sanitizer import redact_text

_LABEL_SPECS = TypeAdapter(list[LabelSpec])
_P0_PROPOSALS = frozenset({CONST_ROADMAP_CRITICAL_PRIORITY, CONST_ROADMAP_P0_PRIORITY})
logger = logging.getLogger(__name__)


class BorrowReason(StrEnum):
    """Why a new candidate may open beyond the allowance: work in flight needs it (#1153)."""

    SPLIT = "split"
    FOLLOW_UP = "follow-up"


class Filer(StrEnum):
    """Who files a new candidate: an agent's counts toward the quota, a person's never does."""

    AGENT = "agent"
    PERSON = "person"


class QuotaDecision(StrEnum):
    """What the agent filing quota decides for a candidate."""

    OPEN = "open"
    BORROW = "borrow"
    FOLD = "fold"
    NOT_COUNTED = "not_counted"


class Outcome(StrEnum):
    """What intake does with a candidate."""

    PLACE = "place"
    DUPLICATE = "duplicate"
    FOLD = "fold"
    SKIP = "skip"


@dataclass(frozen=True)
class NewCandidate:
    """A candidate that is not an issue yet: its title and body, the link it came from, the
    evidence its caller attaches, why it may borrow (which needs `source`), and who files it."""

    title: str
    body: str
    source: str | None = None
    evidence: tuple[Evidence, ...] = ()
    borrow_reason: BorrowReason | None = None
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
    release: str | None = None
    author_association: str | None = None
    item: Item | None = None
    new: NewCandidate | None = None

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
    """Where a candidate goes (None for the backlog), and the comment's words for it."""

    release: str | None
    text: str


@dataclass(frozen=True)
class QuotaStanding:
    """The quota's numbers for this cycle, which every run reports (#1153)."""

    open_issues: int
    delivered: int
    previous: str | None
    since: datetime | None
    agent_openings: int
    borrowed: int
    closures: int
    ratio: float
    credit: int
    allowance: int | float

    def render(self) -> str:
        unlimited = self.allowance == float("inf")
        return MESSAGES.roadmap.intake_quota.format(
            open=self.open_issues,
            ratio=self.ratio,
            credit=self.credit,
            delivered=self.delivered,
            previous=self.previous or MESSAGES.roadmap.intake_no_previous,
            closures=self.closures,
            since=self.since.isoformat() if self.since else MESSAGES.roadmap.intake_since_ever,
            allowance=MESSAGES.roadmap.intake_unlimited if unlimited else self.allowance,
            openings=self.agent_openings,
            borrowed=self.borrowed,
        )


@dataclass(frozen=True)
class IntakeDecision:
    """What intake does with one candidate, and every write it makes for it.

    `shown` is the type, Priority, Value and Effort the item ends with, for the report.
    `reasons` holds the reason comment's lines, each value intake sets with its reason, so the
    comment can be written for the placement and fields the writes make.
    """

    subject: Subject
    outcome: Outcome
    quota: QuotaDecision = QuotaDecision.NOT_COUNTED
    original: int | None = None
    reason: str = ""
    fold_into: int | None = None
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
        if self.outcome is Outcome.DUPLICATE:
            return self.subject.number is not None
        return self.outcome is Outcome.PLACE

    @property
    def moves(self) -> bool:
        """Whether the placement changes the milestone."""
        return self.placement is not None and self.placement.release != self.subject.release

    def writes(self) -> list[str]:
        """Each write, in the order intake makes it."""
        texts = MESSAGES.roadmap
        if self.outcome is Outcome.DUPLICATE:
            close = texts.intake_write_close if self.comment else texts.intake_write_close_only
            return [close.format(original=self.original)]
        filing = ", ".join(self.filing_labels) or texts.intake_no_labels
        planned = [texts.intake_write_file.format(labels=filing)]
        planned = planned if self.subject.number is None else []
        planned += [texts.intake_write_label.format(label=label) for label in self.labels]
        planned += [texts.intake_write_add] if self.subject.item is None else []
        if self.moves and self.placement is not None:
            target = self.placement.release
            planned.append(
                texts.intake_write_release.format(release=target)
                if target
                else texts.intake_write_backlog
            )
        planned += [texts.intake_write_field.format(field=f.value, value=v) for f, v in self.fields]
        planned += [texts.intake_write_comment] if self.comment else []
        planned.append(
            texts.intake_write_field.format(field=ItemField.PRIORITY.value, value=self.priority)
        )
        return planned


@dataclass(frozen=True)
class IntakePlan:
    """The quota's numbers, a decision for each candidate, and the asked-for issues that are not
    candidates; with `spend`, the requests the planning run made.

    A dry run (`dry_run`) made no request, so it has no quota and no decision: `requests` holds
    the reads and model calls a run makes, in order, and `writes` those `--confirm` adds.
    """

    quota: QuotaStanding | None
    decisions: tuple[IntakeDecision, ...]
    missing: tuple[int, ...] = ()
    spend: Spend | None = None
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    writes: tuple[PlannedRequest, ...] = ()

    @property
    def has_writes(self) -> bool:
        return any(decision.has_writes for decision in self.decisions)


@dataclass(frozen=True)
class IntakeApplied:
    """What a run wrote: items placed, duplicates closed, and the issues it filed. `finished`
    names each candidate whose card the add returned holding a Priority, a card a person
    archived that the add restored or one a lagging listing left out: intake wrote nothing
    else to it (#1403)."""

    placed: int
    closed: int
    filed: tuple[int, ...]
    finished: tuple[int, ...] = ()


@dataclass(frozen=True)
class CandidateOutcome:
    """The entry point's answer: the plan, the candidate's decision, and the issue filed for it."""

    plan: IntakePlan
    decision: IntakeDecision
    number: int | None


class _InvalidProposal(ValueError):
    """A proposal with a value off its list."""


# ── Reading the roadmap ───────────────────────────────────────────────────────


def _previous_release(releases: Sequence[Release], current: Release | None) -> Release | None:
    """The closed Release the current cycle follows: the newest one older than the current one."""
    closed = (
        release
        for release in releases
        if release.state is GitHubState.CLOSED
        and (current is None or release.version < current.version)
    )
    return max(closed, key=lambda release: release.version, default=None)


def read_quota(store: RoadmapStore, config: RoadmapConfig) -> QuotaStanding:
    """The quota's counts through REST search, and the allowance #1153's function gives.

    The cycle starts when the previous Release closed; its closed issues are what it delivered.
    A closure is an issue closed since then, less those closed as not planned with no comment;
    a borrowed opening is an agent opening labeled `budget/borrowed`.
    """
    releases = store.releases()
    previous = _previous_release(releases, current_release(releases))
    since = previous.closed_at if previous else None
    delivered = previous.closed_issues if previous else 0

    def count(**conditions: object) -> int:
        return store.count_issues(IssueQuery.model_validate(conditions))

    open_issues = count(state=GitHubState.OPEN)
    closed = count(state=GitHubState.CLOSED, closed_since=since)
    bulk = count(
        state=GitHubState.CLOSED,
        closed_since=since,
        reason=CloseReason.NOT_PLANNED,
        uncommented=True,
    )
    return QuotaStanding(
        open_issues=open_issues,
        delivered=delivered,
        previous=previous.title if previous else None,
        since=since,
        agent_openings=count(labels=(CONST_ROADMAP_SOURCE_AGENT_LABEL,), created_since=since),
        borrowed=count(
            labels=(CONST_ROADMAP_SOURCE_AGENT_LABEL, CONST_ROADMAP_BORROWED_LABEL),
            created_since=since,
        ),
        closures=closed - bulk,
        ratio=quota.ratio(open_issues, config),
        credit=quota.release_credit(delivered, config),
        allowance=quota.allowance(open_issues, delivered, closed - bulk, config),
    )


@dataclass
class _Run:
    """What one run reads once, from `repo`'s `store`."""

    store: RoadmapStore
    repo: str
    config: RoadmapConfig
    model: IntakeModel
    ref: str | None
    releases: list[Release]
    issues: list[IssueRecord]
    board: dict[int, Item]
    standing: QuotaStanding

    @cached_property
    def current(self) -> Release | None:
        return current_release(self.releases)

    @cached_property
    def state(self) -> ReleaseState:
        """The current release's state, a shipped one read as merged: a critical fix joins
        neither."""
        assert self.current is not None
        found = release_state(self.store, self.current, self.store.default_branch().name)
        return ReleaseState.MERGED if found is ReleaseState.SHIPPED else found

    @cached_property
    def next_release(self) -> Release | None:
        """The planned release after the current one."""
        later = (
            release
            for release in self.releases
            if release.state is GitHubState.OPEN
            and self.current is not None
            and release.version > self.current.version
        )
        return min(later, key=lambda release: release.version, default=None)

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

    @cached_property
    def openings(self) -> list[int]:
        """This cycle's agent openings, oldest first: the issues labeled `source/agent` created
        since the cycle started."""
        since = self.standing.since
        opened = [
            (issue.created_at, issue.number)
            for issue in self.issues
            if CONST_ROADMAP_SOURCE_AGENT_LABEL in issue.labels
            and issue.created_at is not None
            and (since is None or issue.created_at >= since)
        ]
        return [number for _, number in sorted(opened)]

    def within_allowance(self, subject: Subject, opened: int) -> bool:
        """Whether the agent's candidate opens within the allowance: a new one while the
        cycle's openings, this run's included, are below it; an issue already open when it is
        among the first `allowance` openings, or was opened before the cycle."""
        standing = self.standing
        if subject.new is not None:
            return standing.agent_openings + opened < standing.allowance
        if subject.number not in self.openings:
            return True
        return self.openings.index(subject.number) < standing.allowance


def _subject(issue: IssueRecord, item: Item | None = None) -> Subject:
    return Subject(
        title=issue.title,
        body=issue.body,
        number=issue.number,
        labels=issue.labels,
        release=issue.release,
        author_association=issue.author_association,
        item=item,
    )


def _subjects(
    run: _Run, issues: Collection[int], new: NewCandidate | None
) -> tuple[list[Subject], tuple[int, ...]]:
    """The candidates this run decides, by number, and the asked-for numbers that are none."""
    if new is not None:
        return [Subject(title=new.title, body=new.filed_body(), new=new)], ()
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


# ── The duplicate check ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Entry:
    """An item, a not-planned issue or an open agent issue off the board, that a candidate is
    compared with; `item` when it is on the board, or placed by this run."""

    number: int | None
    title: str
    body: str
    state: str
    item: bool = True

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.body}"[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS]

    def neighbour(self) -> Neighbour:
        assert self.number is not None
        excerpt = self.body[:DEFAULT_ROADMAP_INTAKE_EXCERPT_CHARS]
        return Neighbour(number=self.number, title=self.title, state=self.state, excerpt=excerpt)


def _compared(issue: IssueRecord, run: _Run, *, off_board: bool) -> bool:
    """Whether a candidate is compared with `issue`: an item, an issue closed as not planned,
    and with `off_board` an open agent issue that is not on the board."""
    if issue.number in run.board:
        return True
    if issue.state is GitHubState.CLOSED:
        return issue.state_reason == CloseReason.NOT_PLANNED
    return off_board and CONST_ROADMAP_SOURCE_AGENT_LABEL in issue.labels


def _comparison(run: _Run, *, off_board: bool) -> list[_Entry]:
    """Every item, open or closed, and every issue closed as not planned; with `off_board`, for
    a new candidate, also the open agent issues off the board."""
    return [
        _Entry(issue.number, issue.title, issue.body, issue.state.value, issue.number in run.board)
        for issue in run.issues
        if _compared(issue, run, off_board=off_board)
    ]


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
    if value in _P0_PROPOSALS:
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
        raise _InvalidProposal(MESSAGES.roadmap.intake_invalid.format(problems="; ".join(problems)))
    return proposal


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


def _reason(reason: Reason, run: _Run) -> str:
    current = run.current.title if run.current else ""
    later = run.next_release.title if run.next_release else ""
    return MESSAGES.roadmap.reasons[reason.value].format(release=current, next=later)


def _to_backlog(reason: str) -> Placement:
    return Placement(None, MESSAGES.roadmap.intake_placement_backlog.format(reason=reason))


def _into(release: str, reason: str) -> Placement:
    return Placement(
        release, MESSAGES.roadmap.intake_placement_release.format(release=release, reason=reason)
    )


def _kept(release: str, reason: str) -> Placement:
    return Placement(
        release, MESSAGES.roadmap.intake_placement_kept.format(release=release, reason=reason)
    )


def _resumed(release: str) -> Placement:
    """An item's milestone, which it keeps."""
    return _kept(release, MESSAGES.roadmap.intake_reason_resumed.format(release=release))


def _by_table(run: _Run, event: Event, already_there: bool) -> Placement:
    """Where #740's table sends a candidate joining the current release."""
    assert run.current is not None
    transition = decide(run.state, event)
    reason = _reason(transition.reason, run)
    if transition.action is Action.ADMIT:
        place = _kept if already_there else _into
        return place(run.current.title, reason)
    if transition.action is Action.TO_NEXT and run.next_release is not None:
        return _into(run.next_release.title, reason)
    if transition.action is Action.TO_NEXT:
        return _to_backlog(MESSAGES.roadmap.intake_reason_no_next.format(release=run.current.title))
    return _to_backlog(reason)


def _placement(run: _Run, subject: Subject, labels: tuple[str, ...], priority: str) -> Placement:
    """Where the candidate goes."""
    probe = Item(
        number=subject.number or 0, title=subject.title, url="", labels=labels, priority=priority
    )
    event = admission_event(probe)
    if subject.release is not None:
        if subject.item is not None:
            return _resumed(subject.release)
        if run.current is not None and in_release(subject.release, run.current.version):
            if event is not Event.FIX_JOINED:
                return _to_backlog(MESSAGES.roadmap.intake_reason_current_not_critical)
            return _by_table(run, event, already_there=True)
        return _kept(
            subject.release, MESSAGES.roadmap.intake_reason_person.format(release=subject.release)
        )
    if event is not Event.FIX_JOINED:
        return _to_backlog(MESSAGES.roadmap.intake_reason_backlog)
    if run.current is None:
        return _to_backlog(MESSAGES.roadmap.intake_reason_no_release)
    return _by_table(run, event, already_there=False)


# ── Deciding ──────────────────────────────────────────────────────────────────


def _borrows_by_reason(subject: Subject) -> bool:
    """Whether the caller says the new candidate is a split or a required follow-up, and links
    the item or review it came from."""
    new = subject.new
    return new is not None and new.borrow_reason is not None and bool(new.source)


def _may_borrow(subject: Subject, type_label: str, priority: str) -> bool:
    """A split or a required follow-up with its link, or a P0/P1 bug or security issue (#1153)."""
    critical_kind = type_label in CONST_ROADMAP_CRITICAL_FIX_LABELS
    return _borrows_by_reason(subject) or (
        critical_kind and priority in CONST_ROADMAP_BORROWING_PRIORITIES
    )


def _quota_decision(
    run: _Run, opened: int, subject: Subject, type_label: str = "", priority: str = ""
) -> QuotaDecision:
    """Open, borrow or fold for an agent's candidate; a person's is not counted. An issue on
    the board, or already labeled `budget/borrowed`, keeps the decision made when it opened."""
    if not subject.agent:
        return QuotaDecision.NOT_COUNTED
    borrowed = CONST_ROADMAP_BORROWED_LABEL in subject.labels
    if subject.item is not None or borrowed:
        return QuotaDecision.BORROW if borrowed else QuotaDecision.OPEN
    if run.within_allowance(subject, opened):
        return QuotaDecision.OPEN
    if _may_borrow(subject, type_label, priority):
        return QuotaDecision.BORROW
    return QuotaDecision.FOLD


def _judged_borrow(subject: Subject, type_label: str, priority: str) -> tuple[str, ...]:
    """A note when a borrow rests on the model's type or priority, not on the caller's reason, a
    type already on the issue and verified P0 evidence."""
    if _borrows_by_reason(subject) or (
        subject.type_label is not None and priority == CONST_ROADMAP_CRITICAL_PRIORITY
    ):
        return ()
    return (
        MESSAGES.roadmap.intake_note_borrow_judged.format(
            type=type_label, priority=priority, label=CONST_ROADMAP_BORROWED_LABEL
        ),
    )


def _filing_labels(subject: Subject, decided: QuotaDecision) -> tuple[str, ...]:
    """The labels a new candidate is filed with: an agent's `source/agent`, and
    `budget/borrowed` when it borrows."""
    if subject.new is None or not subject.agent:
        return ()
    borrowed = (CONST_ROADMAP_BORROWED_LABEL,) if decided is QuotaDecision.BORROW else ()
    return (CONST_ROADMAP_SOURCE_AGENT_LABEL, *borrowed)


def _added_labels(
    subject: Subject, type_label: str | None, decided: QuotaDecision
) -> tuple[str, ...]:
    """The labels added once the issue exists: its `type/*` label when it has none, and
    `budget/borrowed` for an agent issue already open that borrows."""
    borrows = (
        decided is QuotaDecision.BORROW
        and subject.new is None
        and CONST_ROADMAP_BORROWED_LABEL not in subject.labels
    )
    return ((type_label,) if type_label else ()) + (
        (CONST_ROADMAP_BORROWED_LABEL,) if borrows else ()
    )


def _reason_lines(
    proposal: Proposal,
    type_label: str | None,
    fields: Sequence[tuple[ItemField, str]],
    priority: tuple[str, str],
) -> tuple[tuple[str, str, str], ...]:
    """Each value intake sets that the reason comment gives, with its name and reason."""
    reasons = {ItemField.VALUE: proposal.value_reason, ItemField.EFFORT: proposal.effort_reason}
    lines = [("Type", type_label, proposal.type_reason)] if type_label else []
    lines.append((ItemField.PRIORITY.value, priority[0], priority[1]))
    lines += [(f.value, value, reasons[f]) for f, value in fields if f in reasons]
    return tuple(lines)


def _comment(placement: Placement, lines: Sequence[tuple[str, str, str]]) -> str:
    """The reason comment: where the item went, and each value intake set with its reason."""
    rendered = "\n".join(
        MESSAGES.roadmap.intake_comment_field.format(field=name, value=value, reason=reason)
        for name, value, reason in lines
    )
    return MESSAGES.roadmap.intake_comment.format(
        marker=CONST_ROADMAP_INTAKE_REASON_MARKER, placement=placement.text, fields=rendered
    )


def _has_comment(store: RoadmapStore, subject: Subject, marker: str) -> bool:
    """Whether intake already left the comment `marker` marks on the candidate."""
    return subject.number is not None and any(
        marker in body for body in store.comments_on(subject.number)
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
    opened: int = 0

    def decide_all(self, subjects: Sequence[Subject]) -> Iterator[IntakeDecision]:
        """Each candidate's decision, in turn. A run with a candidate reads `.github/labels.yml`
        first, so a file it can't use stops it before any timeline read or model call (#1358)."""
        if not subjects:
            return
        _ = self.run.types
        checked = [_checked(self.run, subject) for subject in subjects]
        own = self._embed(subjects, checked)
        for subject, vector in zip(subjects, own, strict=True):
            decision = self._decide(subject, vector)
            if decision.outcome is Outcome.PLACE and vector is not None:
                self.entries.append(_Entry(subject.number, subject.title, subject.body, "open"))
                self.vectors.append(vector)
            opens = decision.quota in (QuotaDecision.OPEN, QuotaDecision.BORROW)
            self.opened += decision.outcome is Outcome.PLACE and opens
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

    def _ranked(self, vector: list[float], number: int | None, *, items: bool) -> list[int]:
        """The comparison entries other than the candidate, nearest first; with `items`, only
        the open items."""
        indexes = [
            index
            for index, entry in enumerate(self.entries)
            if entry.number is not None
            and entry.number != number
            and (not items or (entry.item and entry.state == GitHubState.OPEN.value))
        ]
        return sorted(
            indexes,
            key=lambda index: cosine_similarity(self.vectors[index], vector),
            reverse=True,
        )

    def _shortlist(self, vector: list[float] | None, number: int | None) -> list[_Entry]:
        if vector is None:
            return []
        nearest = self._ranked(vector, number, items=False)[:DEFAULT_ROADMAP_INTAKE_SHORTLIST]
        return [self.entries[index] for index in nearest]

    def _nearest_item(self, vector: list[float] | None, number: int | None) -> int | None:
        """The open item nearest the candidate, which a fold names."""
        nearest = self._ranked(vector, number, items=True)[:1] if vector is not None else []
        return self.entries[nearest[0]].number if nearest else None

    def _decide(self, subject: Subject, vector: list[float] | None) -> IntakeDecision:
        shortlist = self._shortlist(vector, subject.number)
        request = ProposalRequest(
            title=subject.title,
            body=subject.body[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS],
            shortlist=tuple(entry.neighbour() for entry in shortlist),
            types=self.run.types,
        )
        try:
            raw = self.run.model.propose(request)
        except UnusableProposalError as exc:
            return self._skipped(subject, str(exc), ())
        named = _named_number(raw.duplicate_of)
        if named is not None and named in {entry.number for entry in shortlist}:
            return self._duplicate(subject, named, _line(raw.duplicate_reason))
        rejected = _rejected(named)
        try:
            proposal = validate_proposal(raw, self.run.types, needs_type=subject.type_label is None)
        except _InvalidProposal as exc:
            return self._skipped(subject, str(exc), rejected)
        nearest = self._nearest_item(vector, subject.number)
        return self._place(subject, proposal, rejected + proposal.notes, nearest)

    def _skipped(self, subject: Subject, reason: str, notes: tuple[str, ...]) -> IntakeDecision:
        """A candidate with no usable proposal: nothing is written, and the quota still decides."""
        quota = _quota_decision(self.run, self.opened, subject)
        return IntakeDecision(subject, Outcome.SKIP, quota=quota, reason=reason, notes=notes)

    def _duplicate(self, subject: Subject, original: int, reason: str) -> IntakeDecision:
        """A duplicate, which for an agent's candidate is the quota's fold into its original;
        its comment is left out when a stopped run already left it."""
        marker = CONST_ROADMAP_INTAKE_DUPLICATE_MARKER
        comment = (
            None
            if _has_comment(self.run.store, subject, marker)
            else MESSAGES.roadmap.intake_duplicate_comment.format(
                marker=marker, original=original, reason=reason
            )
        )
        return IntakeDecision(
            subject,
            Outcome.DUPLICATE,
            quota=QuotaDecision.FOLD if subject.agent else QuotaDecision.NOT_COUNTED,
            original=original,
            reason=reason,
            fold_into=original if subject.agent else None,
            comment=comment,
        )

    def _place(
        self, subject: Subject, proposal: Proposal, notes: tuple[str, ...], nearest: int | None
    ) -> IntakeDecision:
        type_label = subject.type_label or proposal.type
        priority = _priority(self.run.store, subject, proposal)
        decided = _quota_decision(self.run, self.opened, subject, type_label, priority[0])
        if decided is QuotaDecision.FOLD:
            return IntakeDecision(
                subject, Outcome.FOLD, quota=decided, fold_into=nearest, notes=notes
            )
        if decided is QuotaDecision.BORROW and subject.item is None:
            notes += _judged_borrow(subject, type_label, priority[0])
        placement = _placement(self.run, subject, (*subject.labels, type_label), priority[0])
        fields = _fields(subject, proposal)
        added = None if subject.type_label else type_label
        lines = _reason_lines(proposal, added, fields, priority)
        comment = (
            None
            if _has_comment(self.run.store, subject, CONST_ROADMAP_INTAKE_REASON_MARKER)
            else _comment(placement, lines)
        )
        return IntakeDecision(
            subject,
            Outcome.PLACE,
            quota=decided,
            labels=_added_labels(subject, added, decided),
            placement=placement,
            fields=fields,
            priority=priority[0],
            comment=comment,
            filing_labels=_filing_labels(subject, decided),
            shown=_shown(subject, type_label, priority[0], proposal),
            notes=notes,
            reasons=lines,
        )


def plan_intake(
    store: RoadmapStore,
    *,
    repo: str,
    config: RoadmapConfig,
    model: IntakeModel,
    ref: str | None = None,
    issues: Collection[int] = (),
    new: NewCandidate | None = None,
) -> IntakePlan:
    """Decide every candidate of `repo`, whose roadmap `store` reads, or only `issues`, or only
    the `new` candidate, writing nothing.

    A `new` candidate whose text looks like it holds a secret raises `SecurityError` first.
    """
    if new is not None:
        new.refuse_secrets()
    run = _Run(
        store=store,
        repo=repo,
        config=config,
        model=model,
        ref=ref,
        releases=store.releases(),
        issues=store.issues(),
        board={item.number: item for item in store.items()},
        standing=read_quota(store, config),
    )
    subjects, missing = _subjects(run, issues, new)
    decisions = tuple(_Planner(run, off_board=new is not None).decide_all(subjects))
    return IntakePlan(quota=run.standing, decisions=decisions, missing=missing)


def dry_run_intake(
    repo: str,
    *,
    ref: str | None = None,
    issues: Collection[int] = (),
    new: NewCandidate | None = None,
) -> IntakePlan:
    """The plan a dry run returns: no request made, the requests a run on `repo` over every
    candidate, only `issues`, or only the `new` candidate makes, in order, with placeholders for
    what a read gives. A `new` candidate whose text looks like it holds a secret raises
    `SecurityError`, as it does for a run."""
    each = new is None and not issues
    if new is not None:
        new.refuse_secrets()
        subjects = [MESSAGES.roadmap.intake_new.format(title=new.title)]
    elif issues:
        subjects = [f"#{number}" for number in sorted(set(issues))]
    else:
        subjects = [MESSAGES.roadmap.intake_placeholder_each]
    reads, writes = planned_requests(subjects, repo=repo, ref=ref, new=new is not None, each=each)
    return IntakePlan(quota=None, decisions=(), dry_run=True, requests=reads, writes=writes)


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
    release = decision.subject.release
    placement = _resumed(release) if item.restored and release is not None else decision.placement
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
    """The writes after the add: the milestone when the placement changes it, the fields, the
    reason comment, then Priority."""
    assert decision.priority is not None
    if decision.moves and decision.placement is not None:
        store.set_field(item, ItemField.RELEASE, decision.placement.release)
    for board_field, value in decision.fields:
        store.set_field(item, board_field, value)
    if decision.comment:
        store.comment(number, decision.comment)
    store.set_field(item, ItemField.PRIORITY, decision.priority)


def _should_refine_on_intake(decision: IntakeDecision) -> bool:
    if decision.outcome is not Outcome.PLACE:
        return False
    all_labels = set(decision.labels) | set(decision.filing_labels) | set(decision.subject.labels)
    is_crit_fix = not CONST_ROADMAP_CRITICAL_FIX_LABELS.isdisjoint(all_labels)
    is_p0 = decision.priority in (CONST_ROADMAP_CRITICAL_PRIORITY, CONST_ROADMAP_P0_PRIORITY)
    admitted = decision.placement is not None and decision.placement.release is not None
    return (is_crit_fix and admitted) or (is_p0 and not is_crit_fix)


def refine_item(store: RoadmapStore, number: int, **kwargs: Any) -> Any:
    """Refine hook called by intake when admitting a critical fix or placing a P0 feature."""
    from devops_cli.roadmap.refine import refine_item as _refine_item

    return _refine_item(store, number, **kwargs)


def _maybe_refine_intake(
    refine_hook: Callable[[RoadmapStore, int], Any],
    store: RoadmapStore,
    decision: IntakeDecision,
    number: int | None,
) -> None:
    if not _should_refine_on_intake(decision):
        return
    item_number = decision.subject.number or number
    if item_number is None:
        return
    try:
        refine_hook(store, item_number)
    except Exception as exc:
        logger.warning("Intake refine hook failed for #%d: %s", item_number, exc)


def apply_intake(
    store: RoadmapStore,
    plan: IntakePlan,
    *,
    refine: Callable[[RoadmapStore, int], Any] | None = None,
) -> IntakeApplied:
    """Make the plan's writes, one candidate at a time."""
    filed: list[int] = []
    finished: list[int] = []
    placed = closed = 0
    refine_hook = refine or refine_item
    for decision in plan.decisions:
        if decision.outcome is Outcome.PLACE:
            number, applied = _apply_placement(store, decision)
            filed += [] if decision.subject.number else [number]
            if applied is None:
                finished.append(number)
                continue
            placed += 1
            _maybe_refine_intake(refine_hook, store, applied, number)
        elif decision.outcome is Outcome.DUPLICATE and decision.subject.number is not None:
            assert decision.original is not None
            store.close_as_duplicate(decision.subject.number, decision.original, decision.comment)
            closed += 1
    return IntakeApplied(placed=placed, closed=closed, filed=tuple(filed), finished=tuple(finished))


def intake_candidate(
    store: RoadmapStore,
    candidate: NewCandidate,
    *,
    repo: str,
    config: RoadmapConfig,
    model: IntakeModel,
    ref: str | None = None,
    confirm: bool = False,
) -> CandidateOutcome:
    """The entry point discovery (#745) and the review hand-off call: decide one candidate that
    is not an issue yet, and with `confirm` file and place it unless it is a duplicate or folds."""
    plan = plan_intake(store, repo=repo, config=config, model=model, ref=ref, new=candidate)
    (decision,) = plan.decisions
    applied = apply_intake(store, plan) if confirm else None
    number = applied.filed[0] if applied and applied.filed else None
    return CandidateOutcome(plan=plan, decision=decision, number=number)


# ── The report ────────────────────────────────────────────────────────────────


def _quota_words(decision: IntakeDecision) -> str:
    """The quota's decision for an agent's skipped or duplicate candidate, to end its line."""
    texts = MESSAGES.roadmap
    if decision.quota is QuotaDecision.NOT_COUNTED:
        return ""
    if decision.outcome is Outcome.DUPLICATE:
        return " " + texts.intake_quota_fold.format(target=decision.original)
    return " " + texts.intake_quota_suffix.format(
        quota=texts.intake_quota_decisions[decision.quota.value]
    )


def _fold_line(decision: IntakeDecision, standing: QuotaStanding) -> str:
    texts = MESSAGES.roadmap
    target = f"#{decision.fold_into}" if decision.fold_into else texts.intake_fold_nowhere
    allowance = texts.intake_unlimited if standing.allowance == float("inf") else standing.allowance
    line = texts.intake_fold_line if decision.subject.number is None else texts.intake_fold_open
    return line.format(subject=decision.subject.name, target=target, allowance=allowance)


def _decision_lines(decision: IntakeDecision, standing: QuotaStanding) -> list[str]:
    texts = MESSAGES.roadmap
    subject = decision.subject.name
    if decision.outcome is Outcome.SKIP:
        line = texts.intake_skip_line.format(subject=subject, reason=decision.reason)
        return [line + _quota_words(decision)]
    if decision.outcome is Outcome.FOLD:
        return [_fold_line(decision, standing)]
    if decision.outcome is Outcome.DUPLICATE:
        action = (
            texts.intake_duplicate_closes
            if decision.subject.number is not None
            else texts.intake_duplicate_files_nothing.format(original=decision.original)
        )
        line = texts.intake_duplicate_line.format(
            subject=subject, original=decision.original, reason=decision.reason, action=action
        )
        return [line + _quota_words(decision)]
    assert decision.placement is not None
    kind, priority, value, effort = decision.shown
    return [
        texts.intake_place_line.format(
            subject=subject,
            type=kind,
            priority=priority,
            value=value,
            effort=effort,
            placement=decision.placement.text,
            quota=texts.intake_quota_decisions[decision.quota.value],
        )
    ]


def render_intake_dry_run(plan: IntakePlan, *, repo: str) -> None:
    """Print a dry run's report: the requests a run makes, numbered in order, then the writes
    `--confirm` adds, each command as it would run."""
    texts = MESSAGES.roadmap
    heading = "\n\n".join([texts.intake_title.format(repo=repo), texts.intake_dry_run])
    render_request_plan(heading, plan.requests, described=True)
    notes = texts.plan_dry_run_notes
    render_request_plan(texts.intake_dry_run_writes, plan.writes, notes, described=True)


def render_intake(plan: IntakePlan, *, repo: str) -> str:
    """The run's report: the quota's numbers, then each candidate, its writes and notes, and
    what the run spent. A dry run, which has no quota, prints through `render_intake_dry_run`."""
    texts = MESSAGES.roadmap
    assert plan.quota is not None, "a dry run prints through render_intake_dry_run"
    lines = [texts.intake_title.format(repo=repo), "", plan.quota.render(), ""]
    if not plan.decisions and not plan.missing:
        lines.append(texts.intake_nothing)
    for decision in plan.decisions:
        lines += _decision_lines(decision, plan.quota)
        if decision.has_writes:
            lines.append(texts.intake_writes.format(writes="; ".join(decision.writes())))
        lines += [texts.intake_note.format(note=note) for note in decision.notes]
    lines += [texts.intake_not_candidate.format(number=number) for number in plan.missing]
    lines += ["", plan.spend.render()] if plan.spend is not None else []
    return "\n".join(lines) + "\n"


__all__ = [
    "BorrowReason",
    "CandidateOutcome",
    "Filer",
    "IntakeApplied",
    "IntakeDecision",
    "IntakePlan",
    "NewCandidate",
    "Outcome",
    "Placement",
    "Proposal",
    "QuotaDecision",
    "QuotaStanding",
    "Subject",
    "apply_intake",
    "dry_run_intake",
    "intake_candidate",
    "plan_intake",
    "read_quota",
    "refine_item",
    "render_intake",
    "render_intake_dry_run",
    "validate_proposal",
]
