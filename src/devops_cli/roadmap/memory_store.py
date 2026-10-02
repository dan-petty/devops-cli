"""The in-memory roadmap store: the roadmap held in process, with no I/O, for tests.

It keeps the promises the GitHub adapter keeps, so the contract suite runs against it. A
test seeds issues with `seed_issue` and acts as a person with `as_actor`: a person's writes
change fields and record changes under their name, but never touch the job record. Cards hold
option names, and `edit_options_by_hand` renames or clears them by option id, as GitHub's
cards, which hold option ids, show after a person edits a field's options in its settings.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from devops_cli.config.constants import CONST_GH_PROJECT_JOB_RECORD_FIELD
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_MEMORY_ACTOR,
    DEFAULT_ROADMAP_MEMORY_BOARD_NUMBER,
    DEFAULT_ROADMAP_MEMORY_REPO,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.store import (
    BOARD_FIELDS,
    Board,
    BoardEntry,
    BoardField,
    Candidate,
    Card,
    CardKind,
    Change,
    ChangeKind,
    CloseReason,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    Release,
    RoadmapStore,
    Workflow,
    as_utc,
    field_options,
    find_release,
    in_release,
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
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _card_id(number: int) -> str:
    return f"card-{number}"


def _board_field_named(name: str) -> ItemField | None:
    return next((board_field for board_field in BOARD_FIELDS if board_field.value == name), None)


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
    ) -> int:
        """Open an issue (or a pull request) as GitHub would, returning its number.

        Seeding records no change. `on_board` puts it on the board with no fields set, which
        `add_item` refuses for a pull request but GitHub's board allows.
        """
        number = len(self._roadmap.issues) + 1
        kind = "pull" if pull_request else "issues"
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

    def comments_on(self, number: int) -> list[str]:
        """Every comment made on issue `number`, oldest first."""
        return list(self._roadmap.comments.get(number, []))

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
            number=number, title=title, description=description, state=state, due_on=due_on
        )
        self._roadmap.releases[number] = created
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
        """Change only the given fields of the Release of `version`, raising if there is none."""
        releases = self.releases()
        current = require_release(releases, version, "roadmap.release.edit")
        edits = release_edits(
            releases, current, title=title, description=description, due_on=due_on, state=state
        )
        edited = current.model_copy(update=edits)
        self._roadmap.releases[current.number] = edited
        return self._counted(edited)

    def close_release(self, version: str) -> Release:
        """Close the Release of `version`, raising if there is none."""
        return self.edit_release(version, state=GitHubState.CLOSED)

    def delete_release(self, version: str) -> None:
        """Delete the Release of `version`; its issues lose their Release, as on GitHub."""
        deleted = require_release(self.releases(), version, "roadmap.release.delete")
        del self._roadmap.releases[deleted.number]
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
        return self._roadmap.issues[number]

    def close_issue(self, number: int, reason: CloseReason, comment: str) -> None:
        """Comment on issue `number`, then close it for `reason`."""
        issue = self._roadmap.issues.get(number)
        if issue is None or issue.pull_request:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}.",
                operation="roadmap.issue.close",
                details={"number": number},
            )
        self._roadmap.comments.setdefault(number, []).append(comment)
        self._roadmap.issues[number] = issue.model_copy(
            update={"state": GitHubState.CLOSED, "state_reason": reason.value}
        )
        self._record(ChangeKind.CLOSED, number)

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The text committed at `path` on `ref`, raising when there is none."""
        text = self._roadmap.files.get((path, ref))
        if text is None:
            raise GitHubOperationError(
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
        """The Item changes made at or after `since`, oldest first."""
        cutoff = as_utc(since)
        return [change for change in self._roadmap.changes if change.at >= cutoff]

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

    def set_field(self, item: Item, field: ItemField, value: str | None) -> None:
        """Set or clear one of the Item's fields; the store's own writes also record the value."""
        self._require_board()
        entry = self._roadmap.cards.get(item.number)
        if entry is None:
            raise GitHubOperationError(
                f"#{item.number} is not on the board.",
                operation="roadmap.item.set_field",
                details={"number": item.number},
            )
        if self._writes_job_record:
            require_job_record_field(self._roadmap.board_fields)
        if field is ItemField.RELEASE:
            recorded = self._place_in_release(item.number, value)
        else:
            require_option(field_options(self._roadmap.board_fields.values()), field, value)
            entry = entry.model_copy(update={field.name.lower(): value})
            recorded = value
        self._roadmap.cards[item.number] = self._recorded(entry, field, recorded)

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

    def cards(self) -> list[Card]:
        """Every card: this repository's issues and pull requests on the board."""
        self._require_board()
        return [self._card(entry) for _, entry in sorted(self._roadmap.cards.items())]

    def set_card_field(self, card: Card, field: ItemField, value: str | None) -> None:
        """Set or clear a board field on any card; the store's own writes also record it."""
        require_board_field(field)
        number = self._card_number(card, "roadmap.card.set_field")
        if self._writes_job_record:
            require_job_record_field(self._roadmap.board_fields)
        require_option(field_options(self._roadmap.board_fields.values()), field, value)
        entry = self._roadmap.cards[number].model_copy(update={field.name.lower(): value})
        self._roadmap.cards[number] = self._recorded(entry, field, value)

    def remove_card(self, card: Card) -> None:
        """Take `card` off the board, raising if it is not on it."""
        del self._roadmap.cards[self._card_number(card, "roadmap.card.remove")]

    def workflows(self) -> list[Workflow]:
        """The board's built-in workflows."""
        self._require_board()
        return list(self._roadmap.workflows)

    # ── Helpers ──

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

    def _recorded(self, entry: BoardEntry, field: ItemField, value: str | None) -> BoardEntry:
        if not self._writes_job_record:
            return entry
        return entry.model_copy(update={"job_record": entry.job_record | {field: value}})

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

    def _record(self, kind: ChangeKind, number: int, release: str | None = None) -> None:
        self._roadmap.changes.append(
            Change(
                kind=kind,
                number=number,
                actor=self._actor,
                at=self._roadmap.clock(),
                release=release,
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
                    self._record(kind, number, title)
        return target

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


__all__ = ["InMemoryRoadmapStore"]
