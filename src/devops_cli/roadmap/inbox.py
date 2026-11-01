"""The inbox: what waits for a person on the roadmap (#2915).

`read_inbox` reads the open issues, the open pull requests, the labels of the repository and
`.github/labels.yml`, and returns the lines that a person must clear, with the number, the age and
the one step that clears each. It writes nothing and calls no model. It never reads every issue:
a closed item holds no `status/*` and no `owner/*` label (`clear-status.yml`), so the open ones
are enough.

**The jobs' lines**, in the order of the gates (docs/ROADMAP_WORKFLOW.md): ready plan pull
requests (G1), ready implementation pull requests (G2), the release pull request (G3), items in
`status/blocked` with their cause, old claims, and labels that the repository lacks. A pull
request is a job's when the job record of an open item names it: `implement.pr` makes it an
implementation, `stage.pr` a plan, and `implement.pr` wins because a staged branch keeps one pull
request through both jobs. A draft of a job waits for its checks, so it is not listed, and a pull
request that a runner Job holds is not listed: the Job pushes to it. The release pull request is
the open one whose head branch starts with the prefix of release-please.

**The people's lines** are every other open pull request, so a person's own pull requests are
apart from the jobs'. A draft is marked as a draft.

**Age.** The time since the last update of the pull request or the issue. For a claim it is the
time since the newest update of the issue and of each open pull request on a branch that names
the issue (`<type>/<issue>-<slug>`). The inbox shows an old claim and never removes it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT,
    CONST_ROADMAP_INBOX_CLAIM_DAYS,
    CONST_ROADMAP_INBOX_LABEL_NAMES,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_RELEASE_BRANCH_PREFIX,
    CONST_ROADMAP_STATUS_BLOCKED,
)
from devops_cli.git.branch_form import issue_of_branch
from devops_cli.github.labels import diff_labels
from devops_cli.lang import MESSAGES
from devops_cli.output import format_duration
from devops_cli.roadmap.pull_labels import declared_specs
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.store import (
    ImplementRecordKey,
    Item,
    OpenPull,
    RefineRecordKey,
    RoadmapStore,
    StageRecordKey,
)


class InboxKind(StrEnum):
    """What a line of the inbox is. The members are in the order the inbox lists them."""

    PLAN = "plan"
    IMPLEMENT = "implement"
    RELEASE = "release"
    BLOCKED = "blocked"
    CLAIM = "claim"
    LABELS = "labels"
    PERSON = "person"


@dataclass(frozen=True)
class InboxLine:
    """One thing that waits for a person: what it is, the number of its issue or pull request
    (None when it has none), the time since its last update (None when GitHub gave none), what
    it is about, and the one command or action that clears it."""

    kind: InboxKind
    number: int | None
    age: timedelta | None
    subject: str
    clear: str


@dataclass(frozen=True)
class Inbox:
    """The lines of the jobs and the repository, in the order of the gates, and the lines of the
    pull requests of people and agents. Within a kind the oldest line comes first."""

    jobs: tuple[InboxLine, ...]
    people: tuple[InboxLine, ...]


def _recorded_number(text: str | None) -> int | None:
    return int(text) if text is not None and text.isdecimal() else None


def _named_pulls(items: Iterable[Item]) -> dict[int, InboxKind | None]:
    """The pull requests that the job record of an item names, by number: the kind they have as
    a job's, or None when a runner Job holds the item. A stage pull request is a plan, and an
    implement pull request is an implementation and wins for the same number."""
    named: dict[int, InboxKind | None] = {}
    for item in items:
        held = job_holds(item)
        for key, kind in (
            (StageRecordKey.PR, InboxKind.PLAN),
            (ImplementRecordKey.PR, InboxKind.IMPLEMENT),
        ):
            number = _recorded_number(item.job_record.get(key))
            if number is not None:
                named[number] = None if held else kind
    return named


def _pull_kind(pull: OpenPull, named: Mapping[int, InboxKind | None]) -> InboxKind | None:
    """The kind of the line of `pull`, or None when no person must act on it now: a draft of a
    job or the release, or a pull request that a runner Job holds."""
    if pull.head_ref.startswith(CONST_ROADMAP_RELEASE_BRANCH_PREFIX):
        kind: InboxKind | None = InboxKind.RELEASE
    elif pull.number in named:
        kind = named[pull.number]
    else:
        return InboxKind.PERSON
    return None if pull.draft else kind


def _age(now: datetime, moment: datetime | None) -> timedelta | None:
    return None if moment is None else now - moment


def _pull_line(pull: OpenPull, kind: InboxKind, repo: str, now: datetime) -> InboxLine:
    texts = MESSAGES.roadmap
    clear_key = kind.value
    if kind is InboxKind.PERSON:
        clear_key = "person_draft" if pull.draft else "person_ready"
    subject = texts.inbox_subjects["draft" if pull.draft else "pull"].format(title=pull.title)
    clear = texts.inbox_clears[clear_key].format(url=pull.url, number=pull.number, repo=repo)
    return InboxLine(kind, pull.number, _age(now, pull.updated_at), subject, clear)


def _pull_lines(
    pulls: Iterable[OpenPull], named: Mapping[int, InboxKind | None], repo: str, now: datetime
) -> list[InboxLine]:
    lines: list[InboxLine] = []
    for pull in pulls:
        kind = _pull_kind(pull, named)
        if kind is not None:
            lines.append(_pull_line(pull, kind, repo, now))
    return lines


def _blocked_line(item: Item, repo: str, now: datetime) -> InboxLine:
    """The line of a blocked item with its cause: the step that stopped it, else the items that
    refine says it waits for, else the words that no cause is recorded."""
    texts = MESSAGES.roadmap
    subjects, clears = texts.inbox_subjects, texts.inbox_clears
    stopped = item.job_record.get(ImplementRecordKey.STOPPED)
    blockers = item.job_record.get(RefineRecordKey.BLOCKED_BY)
    if stopped:
        subject = subjects["stopped"].format(title=item.title, step=stopped)
        clear = clears["stopped"].format(
            retry=CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT, number=item.number
        )
    else:
        key = "blocked_by" if blockers else "no_cause"
        subject = subjects[key].format(title=item.title, blockers=blockers)
        clear = clears["blocked"].format(number=item.number, repo=repo)
    return InboxLine(InboxKind.BLOCKED, item.number, _age(now, item.updated_at), subject, clear)


def _blocked_lines(items: Iterable[Item], repo: str, now: datetime) -> list[InboxLine]:
    return [
        _blocked_line(item, repo, now)
        for item in items
        if item.status == CONST_ROADMAP_STATUS_BLOCKED
    ]


def _activity(item: Item, pulls: Sequence[OpenPull]) -> datetime | None:
    """The newest update of the issue of `item` and of each open pull request on a branch that
    names the issue."""
    moments = [item.updated_at]
    moments += [pull.updated_at for pull in pulls if issue_of_branch(pull.head_ref) == item.number]
    return max((moment for moment in moments if moment is not None), default=None)


def _claim_lines(
    items: Iterable[Item], pulls: Sequence[OpenPull], repo: str, now: datetime
) -> list[InboxLine]:
    texts = MESSAGES.roadmap
    limit = timedelta(days=CONST_ROADMAP_INBOX_CLAIM_DAYS)
    lines: list[InboxLine] = []
    for item in items:
        age = _age(now, _activity(item, pulls))
        if item.owner is None or (age is not None and age <= limit):
            continue
        subject = texts.inbox_subjects["claim"].format(title=item.title, owner=item.owner.lower())
        clear = texts.inbox_clears["claim"].format(number=item.number, repo=repo)
        lines.append(InboxLine(InboxKind.CLAIM, item.number, age, subject, clear))
    return lines


def _label_names(names: Sequence[str]) -> str:
    shown = ", ".join(names[:CONST_ROADMAP_INBOX_LABEL_NAMES])
    more = len(names) - CONST_ROADMAP_INBOX_LABEL_NAMES
    if more <= 0:
        return shown
    return MESSAGES.roadmap.inbox_subjects["more_labels"].format(names=shown, more=more)


def _label_lines(store: RoadmapStore, repo: str, now: datetime) -> list[InboxLine]:
    """One line for the labels of `.github/labels.yml` that the repository lacks or holds with
    another color or description. Its age is the time since the file last changed, which is a
    lower bound on how long the repository has been behind; the commit is read only then."""
    texts = MESSAGES.roadmap
    existing = [label.model_dump() for label in store.repository_labels()]
    to_create, to_update, _ = diff_labels(declared_specs(store, ref=None), existing)
    names = [spec.name for spec in (*to_create, *to_update)]
    if not names:
        return []
    subject = texts.inbox_subjects["labels"].format(
        count=len(names), path=CONST_ROADMAP_LABELS_PATH, names=_label_names(names)
    )
    age = _age(now, store.path_changed_at(CONST_ROADMAP_LABELS_PATH))
    clear = texts.inbox_clears["labels"].format(repo=repo)
    return [InboxLine(InboxKind.LABELS, None, age, subject, clear)]


def _order(line: InboxLine) -> tuple[int, bool, float]:
    """Kind order, then the oldest first, a line with no age last."""
    seconds = line.age.total_seconds() if line.age is not None else 0.0
    return (list(InboxKind).index(line.kind), line.age is None, -seconds)


def read_inbox(store: RoadmapStore, *, repo: str, now: datetime) -> Inbox:
    """What waits for a person in `repo` at `now`. It reads the open items, the open pull
    requests, the labels and the labels file, and the newest commit of that file when the labels
    differ, and writes nothing. A read that fails raises its error, and the labels file of a
    repository that has none fails the read."""
    items = store.open_items()
    pulls = store.open_pulls()
    lines = [
        *_pull_lines(pulls, _named_pulls(items), repo, now),
        *_blocked_lines(items, repo, now),
        *_claim_lines(items, pulls, repo, now),
        *_label_lines(store, repo, now),
    ]
    ordered = sorted(lines, key=_order)
    return Inbox(
        jobs=tuple(line for line in ordered if line.kind is not InboxKind.PERSON),
        people=tuple(line for line in ordered if line.kind is InboxKind.PERSON),
    )


def _render_line(line: InboxLine) -> str:
    texts = MESSAGES.roadmap
    number = texts.inbox_no_number if line.number is None else f"#{line.number}"
    age = texts.inbox_no_age if line.age is None else format_duration(line.age.total_seconds())
    head = texts.inbox_line.format(number=number, age=age, subject=line.subject)
    return f"{head}\n{texts.inbox_clear.format(clear=line.clear)}"


def _render_section(kind: InboxKind, lines: Sequence[InboxLine]) -> str:
    heading = MESSAGES.roadmap.inbox_headings[kind.value].format(
        days=CONST_ROADMAP_INBOX_CLAIM_DAYS
    )
    return "\n".join([heading, *(_render_line(line) for line in lines)])


def render_inbox(inbox: Inbox, *, repo: str) -> str:
    """The inbox as the report of the command: a section for each kind that has a line, the
    jobs' sections first, then the people's, and the note on what the inbox leaves out."""
    texts = MESSAGES.roadmap
    lines = (*inbox.jobs, *inbox.people)
    if not lines:
        return f"{texts.inbox_empty.format(repo=repo)}\n\n{texts.inbox_footer}"
    sections = [
        _render_section(kind, [line for line in lines if line.kind is kind])
        for kind in InboxKind
        if any(line.kind is kind for line in lines)
    ]
    return "\n\n".join([texts.inbox_title.format(repo=repo), *sections, texts.inbox_footer])


__all__ = ["Inbox", "InboxKind", "InboxLine", "read_inbox", "render_inbox"]
