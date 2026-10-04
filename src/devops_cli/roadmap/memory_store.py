"""The in-memory roadmap store: the roadmap held in process, with no I/O, for tests.

It keeps the promises the GitHub adapter keeps, so the contract suite runs against it. A
test seeds issues with `seed_issue` and acts as a person with `as_actor`: a person's writes
change fields and record changes under their name, but never touch the job record. Cards hold
option names, and `edit_options_by_hand` renames or clears them by option id, as GitHub's
cards, which hold option ids, show after a person edits a field's options in its settings.

A person also opens, closes and merges pull requests, publishes GitHub Releases, closes and
reopens issues and adds blocked-by links through the helpers below; each records the change a
poll would find. `seed_evidence` makes a piece of evidence one GitHub confirms. Every
write the store makes as a job, not as a person, is kept in `job_writes`, so a test can check
what a job wrote and that a preview wrote nothing. The only draft issue the board holds is the
run record card, once a job has written the run record.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from devops_cli.config.constants import (
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_ROADMAP_RUN_RECORD_TITLE,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_MEMORY_ACTOR,
    DEFAULT_ROADMAP_MEMORY_BOARD_NUMBER,
    DEFAULT_ROADMAP_MEMORY_DEFAULT_BRANCH,
    DEFAULT_ROADMAP_MEMORY_HEAD_SHA,
    DEFAULT_ROADMAP_MEMORY_REPO,
)
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.roadmap.store import (
    BOARD_FIELDS,
    RELEASE_CHANGE_KINDS,
    Board,
    BoardEntry,
    BoardField,
    Branch,
    Candidate,
    Card,
    CardKind,
    Change,
    ChangeKind,
    CloseReason,
    Closure,
    Dependency,
    Evidence,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueQuery,
    IssueRecord,
    Item,
    ItemField,
    JobMark,
    JobRecord,
    PullRequest,
    PullRequestState,
    Release,
    RoadmapStore,
    Workflow,
    as_utc,
    field_options,
    find_release,
    in_release,
    is_release_pull_request,
    is_release_title,
    join_items,
    parse_release_version,
    release_edits,
    require_board_field,
    require_field,
    require_job_record_field,
    require_new_release,
    require_option,
    require_release,
    select_candidates,
    with_marks,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _at_or_after(moment: datetime | None, since: datetime) -> bool:
    return moment is not None and moment >= as_utc(since)


def _card_id(number: int) -> str:
    return f"card-{number}"


# The run record card's id: the only draft issue the in-memory board holds.
_RUN_RECORD_CARD_ID = "card-run-record"


def _board_field_named(name: str) -> ItemField | None:
    return next((board_field for board_field in BOARD_FIELDS if board_field.value == name), None)


@dataclass(frozen=True)
class JobWrite:
    """One write the store made as a job: the operation, the issue or Release it touched, and
    the field or mark it set with its value."""

    operation: str
    number: int | None = None
    key: str | None = None
    value: str | None = None


@dataclass
class _Roadmap:
    """The state every view of one in-memory roadmap shares."""

    repo: str
    clock: Callable[[], datetime]
    board: Board | None
    board_fields: dict[str, BoardField] = field(default_factory=dict)
    releases: dict[int, Release] = field(default_factory=dict)
    issues: dict[int, IssueRecord] = field(default_factory=dict)
    cards: dict[int, BoardEntry] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    comments: dict[int, list[str]] = field(default_factory=dict)
    files: dict[tuple[str, str | None], str] = field(default_factory=dict)
    workflows: list[Workflow] = field(default_factory=list)
    status_times: dict[int, datetime] = field(default_factory=dict)
    dependencies: dict[int, list[int]] = field(default_factory=dict)
    pull_requests: dict[int, PullRequest] = field(default_factory=dict)
    published: set[str] = field(default_factory=set)
    closures: dict[int, list[Closure]] = field(default_factory=dict)
    evidence: set[Evidence] = field(default_factory=set)
    default_branch: str = DEFAULT_ROADMAP_MEMORY_DEFAULT_BRANCH
    branches: dict[str, str] = field(
        default_factory=lambda: {
            DEFAULT_ROADMAP_MEMORY_DEFAULT_BRANCH: DEFAULT_ROADMAP_MEMORY_HEAD_SHA
        }
    )
    job_writes: list[JobWrite] = field(default_factory=list)
    # The run record card's job record, or None while the board has no such card.
    run_record: JobRecord | None = None
    ids: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    def new_id(self, kind: str) -> str:
        return f"{kind}-{next(self.ids)}"


class InMemoryRoadmapStore(RoadmapStore):
    """The roadmap in memory: Releases, issues and pull requests, and a board of them.

    `board_options` gives each single-select board field its options; a field left out is
    not on the board, and `seed_field` adds any other. `job_record_field=False` models a board
    that has no `Job record` field, and `board_exists=False` a board number that names no
    board.
    """

    def __init__(
        self,
        *,
        board_options: Mapping[ItemField, Iterable[str]] | None = None,
        job_record_field: bool = True,
        board_exists: bool = True,
        repo: str = DEFAULT_ROADMAP_MEMORY_REPO,
        actor: str = DEFAULT_ROADMAP_MEMORY_ACTOR,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._roadmap = _Roadmap(repo=repo, clock=clock, board=None)
        self._actor = actor
        self._writes_job_record = True
        if board_exists:
            self._roadmap.board = self._new_board("Roadmap")
        specs = [
            FieldSpec(
                name=board_field.value,
                single_select=True,
                options=tuple(FieldOption(name=name) for name in names),
            )
            for board_field, names in (board_options or {}).items()
        ]
        if job_record_field:
            specs.append(FieldSpec(name=CONST_GH_PROJECT_JOB_RECORD_FIELD))
        for spec in specs:
            self.seed_field(spec)

    def as_actor(self, actor: str) -> InMemoryRoadmapStore:
        """The same roadmap, written by a person: changes carry their name, and no job record."""
        person = InMemoryRoadmapStore(actor=actor)
        person._roadmap, person._writes_job_record = self._roadmap, False
        return person

    # ── Seeding ──

    def seed_issue(
        self,
        title: str,
        *,
        body: str = "",
        state: GitHubState = GitHubState.OPEN,
        state_reason: str | None = None,
        labels: Iterable[str] = (),
        release: str | None = None,
        pull_request: bool = False,
        on_board: bool = False,
        author_association: str | None = None,
    ) -> int:
        """Open an issue (or a pull request) as GitHub would, returning its number.

        Seeding records no change. `on_board` puts it on the board with no fields set, which
        `add_item` refuses for a pull request but GitHub's board allows. The issue is created
        now by the store's clock, and closed now when seeded closed.
        """
        number = len(self._roadmap.issues) + 1
        kind = "pull" if pull_request else "issues"
        now = self._roadmap.clock()
        self._roadmap.issues[number] = IssueRecord(
            number=number,
            title=title,
            url=f"https://github.com/{self._roadmap.repo}/{kind}/{number}",
            body=body,
            state=state,
            state_reason=state_reason,
            labels=tuple(labels),
            release=release,
            pull_request=pull_request,
            author_association=author_association,
            created_at=now,
            closed_at=now if state is GitHubState.CLOSED else None,
        )
        if on_board:
            self._roadmap.cards[number] = BoardEntry(number=number)
        return number

    def seed_field(self, spec: FieldSpec) -> BoardField:
        """Put a field on the board, giving it and each of its options an id."""
        options = tuple(self._with_id(option) for option in spec.options)
        created = BoardField(
            id=self._roadmap.new_id("field"),
            name=spec.name,
            single_select=spec.single_select,
            options=options,
        )
        self._roadmap.board_fields[created.name] = created
        return created

    def seed_file(self, path: str, text: str, *, ref: str | None = None) -> None:
        """Commit `text` at `path` on `ref`, or on the default branch when `ref` is None."""
        self._roadmap.files[(path, ref)] = text

    def seed_workflow(self, name: str, *, enabled: bool) -> None:
        """Give the board a built-in workflow that is on or off."""
        number = len(self._roadmap.workflows) + 1
        self._roadmap.workflows.append(Workflow(number=number, name=name, enabled=enabled))

    def edit_options_by_hand(self, name: str, options: Sequence[FieldOption]) -> BoardField:
        """Edit field `name`'s options as a person does in the board's field settings.

        An option given with a current id keeps it under the name given, so its cards keep
        their value; a current option left out is removed, and its cards lose their value.
        No store operation does this, because GitHub's API takes no option id.
        """
        current = require_field(self.board_fields(), name, "roadmap.board.edit_options")
        kept = {option.id: option.name for option in options if option.id is not None}
        renamed = {option.name: kept.get(option.id or "") for option in current.options}
        edited = current.model_copy(
            update={"options": tuple(self._with_id(option) for option in options)}
        )
        self._roadmap.board_fields[name] = edited
        self._map_card_values(name, lambda value: renamed.get(value) if value else None)
        return edited

    def job_writes(self) -> list[JobWrite]:
        """Every write the store made as a job, oldest first; a person's writes are not kept."""
        return list(self._roadmap.job_writes)

    # ── What a person does on GitHub ──

    def add_label(self, number: int, label: str) -> None:
        """Label issue `number`, as a person does on GitHub."""
        issue = self._require_issue(number, "roadmap.issue.label")
        if label not in issue.labels:
            self._roadmap.issues[number] = issue.model_copy(
                update={"labels": (*issue.labels, label)}
            )
            self._record(ChangeKind.LABELED, number, issue.release, label=label)

    def reopen_issue(self, number: int) -> None:
        """Reopen a closed issue, as a person does on GitHub."""
        issue = self._require_issue(number, "roadmap.issue.reopen")
        if issue.state is GitHubState.CLOSED:
            self._roadmap.issues[number] = issue.model_copy(
                update={"state": GitHubState.OPEN, "state_reason": None, "closed_at": None}
            )
            self._closure(number, ChangeKind.REOPENED)
            self._record(ChangeKind.REOPENED, number, issue.release)

    def close_by_hand(self, number: int, reason: CloseReason) -> None:
        """Close an issue without a comment, as a person's bulk close does on GitHub."""
        self._close(self._require_issue(number, "roadmap.issue.close"), reason)

    def seed_evidence(self, evidence: Evidence) -> None:
        """Make `evidence` one GitHub confirms: the advisory, failed run or commit exists."""
        self._roadmap.evidence.add(evidence)

    def link_dependency(self, number: int, on: int) -> None:
        """Add a blocked-by link: issue `number` waits on issue `on`."""
        self._require_issue(number, "roadmap.dependency.add")
        self._require_issue(on, "roadmap.dependency.add")
        self._roadmap.dependencies.setdefault(number, []).append(on)
        self._record(ChangeKind.BLOCKED_BY_ADDED, number, self._roadmap.issues[number].release)

    def open_pull_request(
        self,
        title: str,
        *,
        base: str,
        head: str,
        body: str = "",
        labels: Iterable[str] = (),
        release: str | None = None,
        draft: bool = False,
    ) -> int:
        """Open a pull request, returning its number; opening the Release's pull request cuts it."""
        labels = tuple(labels)
        number = self.seed_issue(
            title, body=body, labels=labels, release=release, pull_request=True
        )
        now = self._roadmap.clock()
        opened = PullRequest(
            number=number,
            url=self._roadmap.issues[number].url,
            draft=draft,
            base=base,
            head=head,
            body=body,
            labels=tuple(labels),
            release=release,
            updated_at=now,
            last_commit_at=now,
        )
        self._roadmap.pull_requests[number] = opened
        if self._is_release_pull_request(opened):
            self._record(ChangeKind.RELEASE_CUT, number, release)
        return number

    def close_pull_request(self, number: int, *, merged: bool = False) -> None:
        """Merge the pull request, or close it unmerged, which un-cuts its Release."""
        closed = self._roadmap.pull_requests[number].model_copy(
            update={
                "state": PullRequestState.MERGED if merged else PullRequestState.CLOSED,
                "updated_at": self._roadmap.clock(),
            }
        )
        self._roadmap.pull_requests[number] = closed
        if not merged and self._is_release_pull_request(closed):
            self._record(ChangeKind.RELEASE_UNCUT, number, closed.release)

    def push_to_pull_request(self, number: int) -> None:
        """Push a commit to an open pull request, which also updates it."""
        now = self._roadmap.clock()
        self._roadmap.pull_requests[number] = self._roadmap.pull_requests[number].model_copy(
            update={"updated_at": now, "last_commit_at": now}
        )

    def publish_release(self, version: str) -> None:
        """Publish GitHub Release `vX.Y.Z`; once its pull request has merged, the Release ships."""
        title = require_release(self.releases(), version, "roadmap.release.publish").title
        self._roadmap.published.add(title)
        self._record(ChangeKind.RELEASE_SHIPPED, 0, title)

    def seed_branch(self, name: str, sha: str) -> None:
        """Push branch `name` at commit `sha`."""
        self._roadmap.branches[name] = sha

    # ── Releases ──

    def releases(self) -> list[Release]:
        """Every Release, sorted by version."""
        counted = (self._counted(release) for release in self._roadmap.releases.values())
        return sorted(counted, key=lambda release: release.version)

    def release(self, version: str) -> Release | None:
        """The Release of `version`, with or without its leading `v`, or None."""
        return find_release(self.releases(), version)

    def create_release(
        self,
        version: str,
        *,
        description: str = "",
        due_on: date | None = None,
        state: GitHubState = GitHubState.OPEN,
    ) -> Release:
        """Create the Release of `version`, raising if it already exists."""
        title = require_new_release(self.releases(), version, "roadmap.release.create")
        number = max(self._roadmap.releases, default=0) + 1
        created = Release(
            number=number,
            title=title,
            description=description,
            state=state,
            due_on=due_on,
            closed_at=self._roadmap.clock() if state is GitHubState.CLOSED else None,
        )
        self._roadmap.releases[number] = created
        self._log("create_release", value=title)
        return self._counted(created)

    def edit_release(
        self,
        version: str,
        *,
        title: str | None = None,
        description: str | None = None,
        due_on: date | None = None,
        state: GitHubState | None = None,
    ) -> Release:
        """Change only the given fields of the Release of `version`, raising if there is none.

        A new title is the one its issues and pull requests show from then on: GitHub keeps a
        milestone by its number, so a rename moves nothing.
        """
        releases = self.releases()
        current = require_release(releases, version, "roadmap.release.edit")
        edits = release_edits(
            releases, current, title=title, description=description, due_on=due_on, state=state
        )
        edited = current.model_copy(update=edits | self._closed_at(current, edits.get("state")))
        self._roadmap.releases[current.number] = edited
        if edited.title != current.title:
            self._retitle(current.title, edited.title)
        self._log("edit_release", key=current.title, value=str(edits.get("state") or "") or None)
        return self._counted(edited)

    def close_release(self, version: str) -> Release:
        """Close the Release of `version`, raising if there is none."""
        return self.edit_release(version, state=GitHubState.CLOSED)

    def delete_release(self, version: str) -> None:
        """Delete the Release of `version`; its issues lose their Release, as on GitHub."""
        deleted = require_release(self.releases(), version, "roadmap.release.delete")
        del self._roadmap.releases[deleted.number]
        self._log("delete_release", value=deleted.title)
        for number, issue in self._roadmap.issues.items():
            if in_release(issue.release, deleted.version):
                self._roadmap.issues[number] = issue.model_copy(update={"release": None})

    # ── Issues ──

    def issues(self) -> list[IssueRecord]:
        """Every issue, open and closed, on the board or not; never pull requests."""
        return [issue for issue in self._roadmap.issues.values() if not issue.pull_request]

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""
        number = self.seed_issue(title, body=body, labels=labels)
        self._log("create_issue", number, value=title)
        return self._roadmap.issues[number]

    def close_issue(self, number: int, reason: CloseReason, comment: str) -> None:
        """Comment on issue `number`, then close it for `reason`."""
        issue = self._require_issue(number, "roadmap.issue.close")
        self.comment(number, comment)
        self._close(issue, reason)
        self._log("close_issue", number, value=reason.value)

    def close_as_duplicate(self, number: int, original: int, comment: str | None) -> None:
        """Comment on issue `number` unless `comment` is None, then close it as a duplicate of
        issue `original`."""
        issue = self._require_issue(number, "roadmap.issue.close_as_duplicate")
        self._require_issue(original, "roadmap.issue.close_as_duplicate")
        if comment is not None:
            self.comment(number, comment)
        self._close(issue, CloseReason.DUPLICATE, duplicate_of=original)
        self._log("close_as_duplicate", number, value=str(original))

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number`, oldest first."""
        return list(self._roadmap.closures.get(number, []))

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue `number`, keeping its other labels."""
        issue = self._require_issue(number, "roadmap.issue.label")
        if label not in issue.labels:
            self._roadmap.issues[number] = issue.model_copy(
                update={"labels": (*issue.labels, label)}
            )
            self._record(ChangeKind.LABELED, number, issue.release, label=label)
        self._log("label_issue", number, value=label)

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether the evidence was seeded as one GitHub confirms."""
        return evidence in self._roadmap.evidence

    def count_issues(self, query: IssueQuery) -> int:
        """How many issues match `query`, never pull requests."""
        return sum(self._matches(issue, query) for issue in self.issues())

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""
        issue = self._require_issue(number, "roadmap.issue.comment")
        self._roadmap.comments.setdefault(number, []).append(body)
        self._log("comment", number, value=body)
        self._record(ChangeKind.COMMENTED, number, issue.release)

    def comments_on(self, number: int) -> list[str]:
        """The body of every comment on issue `number`, oldest first."""
        return list(self._roadmap.comments.get(number, []))

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The text committed at `path` on `ref`, raising when there is none."""
        text = self._roadmap.files.get((path, ref))
        if text is None:
            raise GitHubFileNotFoundError(
                f"{self._roadmap.repo} has no {path} on {ref or 'its default branch'}.",
                operation="roadmap.read",
                details={"path": path[:256], "ref": (ref or "")[:256]},
            )
        return text

    # ── Items ──

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""
        self._require_board()
        issue = self._roadmap.issues.get(number)
        return next(iter(join_items([issue], self._roadmap.cards)), None) if issue else None

    def items(self, *, release: str | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the Release of `release`."""
        self._require_board()
        issues = list(self._roadmap.issues.values())
        if release is not None:
            version = parse_release_version(release)
            issues = [issue for issue in issues if in_release(issue.release, version)]
        return join_items(issues, self._roadmap.cards)

    def backlog(self) -> list[Item]:
        """The open Items in no Release."""
        return [
            item for item in self.items() if item.state is GitHubState.OPEN and item.release is None
        ]

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""
        self._require_board()
        return select_candidates(self._roadmap.issues.values(), self._roadmap.cards)

    def changes_since(self, since: datetime) -> list[Change]:
        """The changes made at or after `since`, oldest first, each as a poll reads it now."""
        cutoff = as_utc(since)
        return [self._as_read(change) for change in self._roadmap.changes if change.at >= cutoff]

    # ── Item writes ──

    def add_item(self, number: int) -> None:
        """Put issue `number` on the board, raising if it is not an issue of this repository."""
        self._require_board()
        issue = self._roadmap.issues.get(number)
        if issue is None or issue.pull_request:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}, so it can't be an Item.",
                operation="roadmap.item.add",
                details={"number": number},
            )
        self._roadmap.cards.setdefault(number, BoardEntry(number=number))
        self._log("add_item", number)

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[JobMark, str | None] | None = None,
    ) -> None:
        """Set or clear one of the Item's fields; the store's own writes also record the value,
        and `marks` with it, in one step, so no write stops between the two.

        `job_writes` keeps the field's entry, then one entry for each mark.
        """
        entry = self._require_entry(item, "roadmap.item.set_field")
        if field is ItemField.RELEASE:
            recorded = self._place_in_release(item.number, value)
        else:
            require_option(field_options(self._roadmap.board_fields.values()), field, value)
            entry = entry.model_copy(update={field.name.lower(): value})
            recorded = value
            self._field_changed(item.number, field, value)
        entry = self._recorded(entry, field, recorded)
        self._log("set_field", item.number, field.value, recorded)
        for mark, marked in (marks or {}).items():
            entry = self._recorded(entry, mark, marked)
            self._log("set_mark", item.number, mark.value, marked)
        self._roadmap.cards[item.number] = entry

    def set_marks(
        self,
        item: Item,
        marks: Mapping[JobMark, str | None],
        *,
        recorded: Mapping[ItemField, str | None] | None = None,
        forgotten: Collection[ItemField] = (),
    ) -> None:
        """Set or clear a job's marks in the Item's job record, and record or forget a value for
        a field; a person's view keeps no record.

        `job_writes` keeps one entry for each field it records, then each it forgets, then each
        mark.
        """
        entry = self._require_entry(item, "roadmap.item.set_marks")
        for field_recorded, value in (recorded or {}).items():
            entry = self._recorded(entry, field_recorded, value)
            self._log("record_field", item.number, field_recorded.value, value)
        for field_forgotten in forgotten:
            entry = self._forgotten(entry, field_forgotten)
            self._log("forget_field", item.number, field_forgotten.value)
        for mark, value in marks.items():
            entry = self._recorded(entry, mark, value)
            self._log("set_mark", item.number, mark.value, value)
        self._roadmap.cards[item.number] = entry

    def run_record(self) -> JobRecord:
        """The run record card's job record, empty while the board has no such card."""
        self._require_board()
        return dict(self._roadmap.run_record or {})

    def set_run_record(self, marks: Mapping[JobMark, str | None]) -> None:
        """Set or clear marks in the run record, putting its card on the board when needed."""
        self._require_board()
        require_job_record_field(self._roadmap.board_fields)
        if not self._writes_job_record:
            return
        self._roadmap.run_record = with_marks(self._roadmap.run_record or {}, marks)
        for mark, value in marks.items():
            self._log("set_run_record", key=mark.value, value=value)

    def release_changes(self, number: int) -> list[Change]:
        """Every time issue `number` joined or left a Release, oldest first."""
        moves = (ChangeKind.JOINED_RELEASE, ChangeKind.LEFT_RELEASE)
        return [
            change
            for change in self._roadmap.changes
            if change.number == number and change.kind in moves
        ]

    # ── What the release rules read and write ──

    def dependencies(self, number: int) -> list[Dependency]:
        """The issues issue `number` waits on through blocked-by links, as they are now."""
        return [
            Dependency(
                number=on,
                url=self._roadmap.issues[on].url,
                repository=self._roadmap.repo,
                state=self._roadmap.issues[on].state,
                release=self._roadmap.issues[on].release,
            )
            for on in self._roadmap.dependencies.get(number, [])
        ]

    def status_changed_at(self, number: int) -> datetime | None:
        """When the Item's Status last changed, or None when it was never set."""
        return self._roadmap.status_times.get(number)

    def open_pull_requests(self) -> list[PullRequest]:
        """Every open pull request, by number."""
        return [
            pull_request
            for _, pull_request in sorted(self._roadmap.pull_requests.items())
            if pull_request.state is PullRequestState.OPEN
        ]

    def release_pull_requests(self, version: str) -> list[PullRequest]:
        """Every pull request with the `release` label in the Release's milestone."""
        wanted = require_release(self.releases(), version, "roadmap.release.pull_requests")
        return [
            pull_request
            for _, pull_request in sorted(self._roadmap.pull_requests.items())
            if is_release_pull_request(pull_request, wanted.version, pull_request.base)
        ]

    def release_published(self, version: str) -> bool:
        """Whether GitHub Release `vX.Y.Z` of `version` is published."""
        return f"v{parse_release_version(version)}" in self._roadmap.published

    def default_branch(self) -> Branch:
        """The default branch and its head commit."""
        name = self._roadmap.default_branch
        return Branch(name=name, sha=self._roadmap.branches[name])

    def branch(self, name: str) -> str | None:
        """The head commit of branch `name`, or None."""
        return self._roadmap.branches.get(name)

    def create_branch(self, name: str, sha: str) -> None:
        """Create branch `name` at `sha`, raising if it already exists."""
        if name in self._roadmap.branches:
            raise GitHubOperationError(
                f"Branch {name} already exists in {self._roadmap.repo}.",
                operation="roadmap.branch.create",
                details={"branch": name[:256]},
            )
        self._roadmap.branches[name] = sha
        self._log("create_branch", key=name, value=sha)

    # ── The board ──

    def board(self) -> Board | None:
        """The board, or None when the board number names no board."""
        return self._roadmap.board

    def create_board(self, title: str, fields: Sequence[FieldSpec]) -> Board:
        """Create the one board this roadmap holds, with `fields`, raising if it has one."""
        if self._roadmap.board is not None:
            raise GitHubOperationError(
                "The in-memory roadmap already has its one board.",
                operation="roadmap.board.create",
                details={"number": self._roadmap.board.number},
            )
        self._roadmap.board = self._new_board(title)
        for spec in fields:
            self.seed_field(spec)
        self._log("create_board", value=title)
        return self._roadmap.board

    def board_fields(self) -> list[BoardField]:
        """Every field on the board, with each option's id, color and description."""
        self._require_board()
        return list(self._roadmap.board_fields.values())

    def delete_field(self, name: str) -> None:
        """Delete the board field `name`; every card loses its value for it."""
        require_field(self.board_fields(), name, "roadmap.board.delete_field")
        del self._roadmap.board_fields[name]
        self._map_card_values(name, lambda _: None)
        self._log("delete_field", key=name)

    def cards(self) -> list[Card]:
        """Every card: this repository's issues and pull requests on the board, then the run
        record card when there is one."""
        self._require_board()
        cards = [self._card(entry) for _, entry in sorted(self._roadmap.cards.items())]
        if self._roadmap.run_record is not None:
            cards.append(
                Card(
                    id=_RUN_RECORD_CARD_ID,
                    kind=CardKind.DRAFT_ISSUE,
                    job_record=self._roadmap.run_record,
                )
            )
        return cards

    def set_card_field(self, card: Card, field: ItemField, value: str | None) -> None:
        """Set or clear a board field on any card; the store's own writes also record it."""
        require_board_field(field)
        number = self._card_number(card, "roadmap.card.set_field")
        if self._writes_job_record:
            require_job_record_field(self._roadmap.board_fields)
        require_option(field_options(self._roadmap.board_fields.values()), field, value)
        entry = self._roadmap.cards[number].model_copy(update={field.name.lower(): value})
        self._roadmap.cards[number] = self._recorded(entry, field, value)
        self._field_changed(number, field, value)
        self._log("set_card_field", number, field.value, value)

    def remove_card(self, card: Card) -> None:
        """Take `card` off the board, raising if it is not on it."""
        if card.id == _RUN_RECORD_CARD_ID and self._roadmap.run_record is not None:
            self._roadmap.run_record = None
            self._log("remove_card", value=CONST_ROADMAP_RUN_RECORD_TITLE)
            return
        number = self._card_number(card, "roadmap.card.remove")
        del self._roadmap.cards[number]
        self._log("remove_card", number)

    def workflows(self) -> list[Workflow]:
        """The board's built-in workflows."""
        self._require_board()
        return list(self._roadmap.workflows)

    # ── Helpers ──

    def _closed_at(self, current: Release, state: object) -> dict[str, datetime | None]:
        """When an edit closes the Release, now; when it reopens it, never; else unchanged."""
        if state is None or state == current.state:
            return {}
        return {"closed_at": self._roadmap.clock() if state == GitHubState.CLOSED else None}

    def _close(
        self, issue: IssueRecord, reason: CloseReason, *, duplicate_of: int | None = None
    ) -> None:
        """Close the issue for `reason` now, recording the close in its timeline and changes."""
        self._roadmap.issues[issue.number] = issue.model_copy(
            update={
                "state": GitHubState.CLOSED,
                "state_reason": reason.value,
                "closed_at": self._roadmap.clock(),
            }
        )
        self._closure(issue.number, ChangeKind.CLOSED, reason.value, duplicate_of)
        self._record(ChangeKind.CLOSED, issue.number, issue.release)

    def _closure(
        self,
        number: int,
        kind: ChangeKind,
        reason: str | None = None,
        duplicate_of: int | None = None,
    ) -> None:
        closure = Closure(
            kind=kind, at=self._roadmap.clock(), reason=reason, duplicate_of=duplicate_of
        )
        self._roadmap.closures.setdefault(number, []).append(closure)

    def _matches(self, issue: IssueRecord, query: IssueQuery) -> bool:
        """Whether the issue meets every condition `query` gives, as GitHub's search counts it."""
        conditions = (
            query.state is None or issue.state is query.state,
            set(query.labels) <= set(issue.labels),
            query.created_since is None or _at_or_after(issue.created_at, query.created_since),
            query.closed_since is None or _at_or_after(issue.closed_at, query.closed_since),
            query.reason is None or issue.state_reason == query.reason.value,
            not query.uncommented or not self._roadmap.comments.get(issue.number),
        )
        return all(conditions)

    def _require_issue(self, number: int, operation: str) -> IssueRecord:
        issue = self._roadmap.issues.get(number)
        if issue is None or issue.pull_request:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}.",
                operation=operation,
                details={"number": number},
            )
        return issue

    def _require_entry(self, item: Item, operation: str) -> BoardEntry:
        """The Item's board entry, refusing an Item off the board or a board with no record field."""
        self._require_board()
        entry = self._roadmap.cards.get(item.number)
        if entry is None:
            raise GitHubOperationError(
                f"#{item.number} is not on the board.",
                operation=operation,
                details={"number": item.number},
            )
        if self._writes_job_record:
            require_job_record_field(self._roadmap.board_fields)
        return entry

    def _log(
        self,
        operation: str,
        number: int | None = None,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        if self._writes_job_record:
            self._roadmap.job_writes.append(JobWrite(operation, number, key, value))

    def _as_read(self, change: Change) -> Change:
        """The change as a poll reads it now, as the GitHub adapter reads an issue event: with the
        Item's job record, the field's value now, and, unless it names the Release it joined,
        left or concerns, the Release the Item is in now."""
        issue = self._roadmap.issues.get(change.number)
        if change.kind in RELEASE_CHANGE_KINDS or issue is None:
            return change
        entry = self._roadmap.cards.get(change.number, BoardEntry(number=change.number))
        values = entry.model_dump() | {"release": issue.release}
        moved = change.field is ItemField.RELEASE
        return change.model_copy(
            update={
                "job_record": entry.job_record,
                "release": change.release if moved else issue.release,
                "value": values.get(change.field.name.lower()) if change.field else None,
            }
        )

    def _field_changed(self, number: int, field: ItemField, value: str | None) -> None:
        if field is ItemField.STATUS:
            self._roadmap.status_times[number] = self._roadmap.clock()
        release = self._roadmap.issues[number].release
        self._record(ChangeKind.FIELD_CHANGED, number, release, field=field, value=value)

    def _is_release_pull_request(self, pull_request: PullRequest) -> bool:
        if pull_request.release is None or not is_release_title(pull_request.release):
            return False
        version = parse_release_version(pull_request.release)
        return is_release_pull_request(pull_request, version, self._roadmap.default_branch)

    def _require_board(self) -> Board:
        if self._roadmap.board is None:
            raise GitHubOperationError(
                "The board number names no board, so its cards and fields can't be read or written.",
                operation="roadmap.board",
                details={"repo": self._roadmap.repo[:256]},
            )
        return self._roadmap.board

    def _new_board(self, title: str) -> Board:
        number = DEFAULT_ROADMAP_MEMORY_BOARD_NUMBER
        owner = self._roadmap.repo.split("/")[0]
        return Board(
            id=self._roadmap.new_id("board"),
            number=number,
            title=title,
            url=f"https://github.com/users/{owner}/projects/{number}",
        )

    def _with_id(self, option: FieldOption) -> FieldOption:
        return (
            option
            if option.id
            else option.model_copy(update={"id": self._roadmap.new_id("option")})
        )

    def _map_card_values(self, field_name: str, change: Callable[[str | None], str | None]) -> None:
        """Change every card's value for the board field `field_name`, if it is one Items carry."""
        board_field = _board_field_named(field_name)
        if board_field is None:
            return
        attribute = board_field.name.lower()
        for number, entry in self._roadmap.cards.items():
            self._roadmap.cards[number] = entry.model_copy(
                update={attribute: change(getattr(entry, attribute))}
            )

    def _recorded(
        self, entry: BoardEntry, field: ItemField | JobMark, value: str | None
    ) -> BoardEntry:
        if not self._writes_job_record:
            return entry
        return entry.model_copy(update={"job_record": entry.job_record | {field: value}})

    def _forgotten(self, entry: BoardEntry, field: ItemField) -> BoardEntry:
        if not self._writes_job_record:
            return entry
        record = {key: value for key, value in entry.job_record.items() if key != field}
        return entry.model_copy(update={"job_record": record})

    def _card(self, entry: BoardEntry) -> Card:
        issue = self._roadmap.issues[entry.number]
        kind = CardKind.PULL_REQUEST if issue.pull_request else CardKind.ISSUE
        return Card(
            id=_card_id(entry.number),
            kind=kind,
            url=issue.url,
            repository=self._roadmap.repo,
            **entry.model_dump(),
        )

    def _card_number(self, card: Card, operation: str) -> int:
        self._require_board()
        number = next((n for n in self._roadmap.cards if _card_id(n) == card.id), None)
        if number is None:
            raise GitHubOperationError(
                f"Card {card.id} is not on the board.",
                operation=operation,
                details={"card": card.id[:256]},
            )
        return number

    def _record(
        self,
        kind: ChangeKind,
        number: int,
        release: str | None = None,
        *,
        field: ItemField | None = None,
        value: str | None = None,
        label: str | None = None,
    ) -> None:
        self._roadmap.changes.append(
            Change(
                kind=kind,
                number=number,
                actor=self._actor,
                at=self._roadmap.clock(),
                release=release,
                label=label,
                field=field,
                value=value,
            )
        )

    def _place_in_release(self, number: int, version: str | None) -> str | None:
        """Move the issue into the Release of `version`, or out of its Release, recording it."""
        issue = self._roadmap.issues[number]
        target = (
            require_release(self.releases(), version, "roadmap.item.set_field").title
            if version is not None
            else None
        )
        if target != issue.release:
            self._roadmap.issues[number] = issue.model_copy(update={"release": target})
            moves = ((ChangeKind.LEFT_RELEASE, issue.release), (ChangeKind.JOINED_RELEASE, target))
            for kind, title in moves:
                if title is not None:
                    self._record(kind, number, title, field=ItemField.RELEASE, value=target)
        return target

    def _retitle(self, old: str, new: str) -> None:
        """Show a renamed Release's new title on its issues and pull requests."""
        for number, issue in self._roadmap.issues.items():
            if issue.release == old:
                self._roadmap.issues[number] = issue.model_copy(update={"release": new})
        for number, pull_request in self._roadmap.pull_requests.items():
            if pull_request.release == old:
                self._roadmap.pull_requests[number] = pull_request.model_copy(
                    update={"release": new}
                )

    def _counted(self, release: Release) -> Release:
        """The Release with its open and closed issue counts, as GitHub reports them."""
        states = [
            issue.state
            for issue in self._roadmap.issues.values()
            if in_release(issue.release, release.version)
        ]
        return release.model_copy(
            update={
                "open_issues": states.count(GitHubState.OPEN),
                "closed_issues": states.count(GitHubState.CLOSED),
            }
        )


__all__ = ["InMemoryRoadmapStore", "JobWrite"]
