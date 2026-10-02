"""The in-memory roadmap store: the roadmap held in process, with no I/O, for tests.

It keeps the promises the GitHub adapter keeps, so the contract suite runs against it. A
test seeds issues with `seed_issue` and acts as a person with `as_actor`: a person's writes
change fields and record changes under their name, but never touch the job record.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from devops_cli.config.constants import CONST_GH_PROJECT_JOB_RECORD_FIELD
from devops_cli.config.defaults import DEFAULT_ROADMAP_MEMORY_ACTOR, DEFAULT_ROADMAP_MEMORY_REPO
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.store import (
    BoardEntry,
    Candidate,
    Change,
    ChangeKind,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    Release,
    RoadmapStore,
    as_utc,
    find_release,
    in_release,
    join_items,
    parse_release_version,
    release_edits,
    require_job_record_field,
    require_new_release,
    require_option,
    require_release,
    select_candidates,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class _Roadmap:
    """The state every view of one in-memory roadmap shares."""

    repo: str
    board_fields: dict[str, tuple[str, ...]]
    clock: Callable[[], datetime]
    releases: dict[int, Release] = field(default_factory=dict)
    issues: dict[int, IssueRecord] = field(default_factory=dict)
    board: dict[int, BoardEntry] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)


class InMemoryRoadmapStore(RoadmapStore):
    """The roadmap in memory: Releases, issues and pull requests, and a board of issues.

    `board_options` gives each single-select board field its options; a field left out is
    not on the board. `job_record_field=False` models a board that has no `Job record` field.
    """

    def __init__(
        self,
        *,
        board_options: Mapping[ItemField, Iterable[str]] | None = None,
        job_record_field: bool = True,
        repo: str = DEFAULT_ROADMAP_MEMORY_REPO,
        actor: str = DEFAULT_ROADMAP_MEMORY_ACTOR,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        board_fields = {f.value: tuple(names) for f, names in (board_options or {}).items()}
        if job_record_field:
            board_fields[CONST_GH_PROJECT_JOB_RECORD_FIELD] = ()
        self._roadmap = _Roadmap(repo=repo, board_fields=board_fields, clock=clock)
        self._actor = actor
        self._writes_job_record = True

    def as_actor(self, actor: str) -> InMemoryRoadmapStore:
        """The same roadmap, written by a person: changes carry their name, and no job record."""
        person = InMemoryRoadmapStore(actor=actor)
        person._roadmap, person._writes_job_record = self._roadmap, False
        return person

    def seed_issue(
        self,
        title: str,
        *,
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
            state=state,
            state_reason=state_reason,
            labels=tuple(labels),
            release=release,
            pull_request=pull_request,
        )
        if on_board:
            self._roadmap.board[number] = BoardEntry(number=number)
        return number

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
        number = len(self._roadmap.releases) + 1
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

    # ── Items ──

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""
        issue = self._roadmap.issues.get(number)
        return next(iter(join_items([issue], self._roadmap.board)), None) if issue else None

    def items(self, *, release: str | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the Release of `release`."""
        issues = list(self._roadmap.issues.values())
        if release is not None:
            version = parse_release_version(release)
            issues = [issue for issue in issues if in_release(issue.release, version)]
        return join_items(issues, self._roadmap.board)

    def backlog(self) -> list[Item]:
        """The open Items in no Release."""
        return [
            item for item in self.items() if item.state is GitHubState.OPEN and item.release is None
        ]

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""
        return select_candidates(self._roadmap.issues.values(), self._roadmap.board)

    def changes_since(self, since: datetime) -> list[Change]:
        """The Item changes made at or after `since`, oldest first."""
        cutoff = as_utc(since)
        return [change for change in self._roadmap.changes if change.at >= cutoff]

    # ── Item writes ──

    def add_item(self, number: int) -> None:
        """Put issue `number` on the board, raising if it is not an issue of this repository."""
        issue = self._roadmap.issues.get(number)
        if issue is None or issue.pull_request:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}, so it can't be an Item.",
                operation="roadmap.item.add",
                details={"number": number},
            )
        self._roadmap.board.setdefault(number, BoardEntry(number=number))

    def set_field(self, item: Item, field: ItemField, value: str | None) -> None:
        """Set or clear one of the Item's fields; the store's own writes also record the value."""
        entry = self._roadmap.board.get(item.number)
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
            require_option(self._roadmap.board_fields, field, value)
            entry = entry.model_copy(update={field.name.lower(): value})
            recorded = value
        if self._writes_job_record:
            entry = entry.model_copy(update={"job_record": entry.job_record | {field: recorded}})
        self._roadmap.board[item.number] = entry

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
            self._roadmap.changes.extend(
                Change(
                    kind=kind,
                    number=number,
                    actor=self._actor,
                    at=self._roadmap.clock(),
                    release=title,
                )
                for kind, title in moves
                if title is not None
            )
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
