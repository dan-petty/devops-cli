"""Contract suite for the roadmap store (ADR 0016).

Each case pins one promise `RoadmapStore` makes. The cases of the label families and the job
record run against both adapters: the in-memory one, and the GitHub one over `GitHubFake`, the
`gh` process edge, its REST listings read through `RunnerSession`. A person acts on GitHub
through the world's own helpers, never through the job's store. The GitHub store keeps the
listing of every issue for its life, so a case reads an Item after a person's change with
`item`, which reads the issue again, as the next store would. The other cases run against the
in-memory adapter; `tests/test_roadmap_github_store.py` pins the GitHub adapter's own requests.
A milestone is a planning bucket: any title, identified by its number and ordered by its due
date.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

import pytest

from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import (
    ChangeKind,
    CloseReason,
    Evidence,
    EvidenceKind,
    GitHubState,
    IssueComment,
    Item,
    ItemField,
    OpenPull,
    RefineRecordKey,
    RepositoryFacts,
    RepositoryLabel,
    RoadmapStore,
)
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import API, GitHubApiFake, RunnerSession, github_json

REPO = "example/roadmap"
RECORD = "<!-- devops-roadmap-record"


class World(Protocol):
    """One repository, the job's store on it, and what a person does on GitHub."""

    store: RoadmapStore

    def seed(
        self,
        title: str,
        *,
        labels: tuple[str, ...] = (),
        body: str = "",
        state: GitHubState = GitHubState.OPEN,
        pull_request: bool = False,
        author_association: str = "COLLABORATOR",
        updated_at: datetime | None = None,
    ) -> int: ...

    def seed_pull(
        self,
        title: str,
        *,
        head_ref: str,
        draft: bool = False,
        state: GitHubState = GitHubState.OPEN,
        updated_at: datetime | None = None,
    ) -> int: ...

    def seed_label(self, name: str, color: str, description: str | None = None) -> None: ...

    def person_adds(self, number: int, label: str) -> None: ...

    def labels(self, number: int) -> list[str]: ...

    def raw_body(self, number: int) -> str: ...

    def writes(self) -> int: ...


class MemoryWorld:
    """The in-memory adapter: a person writes through `as_actor`."""

    def __init__(self) -> None:
        self._roadmap = InMemoryRoadmapStore(repo=REPO)
        self.store: RoadmapStore = self._roadmap

    def seed(
        self,
        title: str,
        *,
        labels: tuple[str, ...] = (),
        body: str = "",
        state: GitHubState = GitHubState.OPEN,
        pull_request: bool = False,
        author_association: str = "COLLABORATOR",
        updated_at: datetime | None = None,
    ) -> int:
        return self._roadmap.seed_issue(
            title,
            labels=labels,
            body=body,
            state=state,
            pull_request=pull_request,
            author_association=author_association,
            updated_at=updated_at,
        )

    def seed_pull(
        self,
        title: str,
        *,
        head_ref: str,
        draft: bool = False,
        state: GitHubState = GitHubState.OPEN,
        updated_at: datetime | None = None,
    ) -> int:
        return self._roadmap.seed_pull(
            title, head_ref=head_ref, draft=draft, state=state, updated_at=updated_at
        )

    def seed_label(self, name: str, color: str, description: str | None = None) -> None:
        self._roadmap.seed_label(name, color, description or "")

    def person_adds(self, number: int, label: str) -> None:
        self._roadmap.as_actor("alice").add_label(number, label)

    def labels(self, number: int) -> list[str]:
        return next(list(i.labels) for i in self._roadmap.issues() if i.number == number)

    def raw_body(self, number: int) -> str:
        return self._roadmap.raw_body(number)

    def writes(self) -> int:
        return len(self._roadmap.job_writes())


class GitHubWorld:
    """The GitHub adapter over `GitHubFake`: a person changes the fake's issues."""

    def __init__(self) -> None:
        self.github = GitHubFake(REPO)
        self.store: RoadmapStore = GitHubRoadmapStore(
            REPO, runner=self.github, session=RunnerSession(self.github)
        )

    def seed(
        self,
        title: str,
        *,
        labels: tuple[str, ...] = (),
        body: str = "",
        state: GitHubState = GitHubState.OPEN,
        pull_request: bool = False,
        author_association: str = "COLLABORATOR",
        updated_at: datetime | None = None,
    ) -> int:
        number = len(self.github.issues) + 1
        self.github.seed_issue(
            number,
            title,
            labels=labels,
            body=body,
            state=state.value,
            pull_request=pull_request,
            author_association=author_association,
            updated_at=updated_at,
        )
        return number

    def seed_pull(
        self,
        title: str,
        *,
        head_ref: str,
        draft: bool = False,
        state: GitHubState = GitHubState.OPEN,
        updated_at: datetime | None = None,
    ) -> int:
        number = len(self.github.issues) + 1
        self.github.seed_pull(
            number, title, head_ref=head_ref, draft=draft, state=state.value, updated_at=updated_at
        )
        return number

    def seed_label(self, name: str, color: str, description: str | None = None) -> None:
        self.github.seed_label(name, color, description)

    def person_adds(self, number: int, label: str) -> None:
        self.github.issues[number]["labels"].append({"name": label})

    def labels(self, number: int) -> list[str]:
        return self.github.labels(number)

    def raw_body(self, number: int) -> str:
        return self.github.body(number)

    def writes(self) -> int:
        return len(self.github.writes())


@pytest.fixture(params=["memory", "github"])
def world(request: pytest.FixtureRequest) -> Iterator[World]:
    built: World = MemoryWorld() if request.param == "memory" else GitHubWorld()
    yield built
    if isinstance(built, GitHubWorld):
        assert built.github.project_calls() == []


def read(world: World, number: int) -> Item:
    """The Item `number` as a read gives it now."""
    found = world.store.item(number)
    assert found is not None
    return found


# ── Label families (ADR 0016) ─────────────────────────────────────────────────


def test_each_field_is_read_from_its_label_family(world: World) -> None:
    number = world.seed(
        "triaged",
        labels=("priority/p1-high", "status/in-progress", "value/high", "effort/low", "type/bug"),
    )
    item = read(world, number)
    assert (item.priority, item.status, item.value, item.effort, item.job_record) == (
        "P1-High",
        "In Progress",
        "High",
        "Low",
        {},
    )


def test_a_label_a_person_adds_beside_the_jobs_is_the_fields_value(world: World) -> None:
    """The job record names the job's `New`, so the person's `Blocked` is the newer value."""
    number = world.seed("blocked by hardware", labels=("priority/p2-medium",))
    world.store.set_field(read(world, number), ItemField.STATUS, "New")
    world.person_adds(number, "status/blocked")
    item = read(world, number)
    assert (item.status, world.labels(number)) == (
        "Blocked",
        ["priority/p2-medium", "status/new", "status/blocked"],
    )


def test_two_labels_no_job_set_read_as_the_first_in_the_familys_order(world: World) -> None:
    number = world.seed("set twice by hand", labels=("priority/p3-low", "priority/p1-high"))
    assert read(world, number).priority == "P1-High"


def test_items_are_the_issues_with_a_priority_label_and_candidates_the_open_issues_without(
    world: World,
) -> None:
    placed = world.seed("placed", labels=("priority/p2-medium",))
    done = world.seed("done", labels=("priority/p3-low",), state=GitHubState.CLOSED)
    candidate = world.seed("intake me", labels=("type/bug", "status/new"))
    world.seed("closed off the roadmap", state=GitHubState.CLOSED)
    pull = world.seed("a pull request", labels=("priority/p1-high",), pull_request=True)
    assert (
        [item.number for item in world.store.items()],
        [(c.number, c.labels) for c in world.store.candidates()],
        world.store.item(candidate),
        world.store.item(pull),
        world.store.item(99),
    ) == ([placed, done], [(candidate, ("type/bug", "status/new"))], None, None, None)


def test_an_item_carries_its_authors_association_with_the_repository(world: World) -> None:
    """A refine round judges an Item by its author with no read of each issue (#2478): the
    listing of Items and the read of one Item give the association that the issue holds."""
    owners = world.seed("by the owner", labels=("priority/p2-medium",), author_association="OWNER")
    outside = world.seed("from outside", labels=("priority/p2-medium",), author_association="NONE")
    assert (
        [(item.number, item.author_association) for item in world.store.backlog()],
        read(world, outside).author_association,
    ) == ([(owners, "OWNER"), (outside, "NONE")], "NONE")


def test_a_job_sets_a_field_by_replacing_the_familys_labels(world: World) -> None:
    """Every label of the family goes, an unknown one too, and the value's label is added."""
    number = world.seed(
        "readied", labels=("priority/p2-medium", "status/new", "status/triage", "type/bug")
    )
    world.store.set_field(read(world, number), ItemField.STATUS, "Ready")
    item = read(world, number)
    assert (world.labels(number), item.status, item.job_record) == (
        ["priority/p2-medium", "type/bug", "status/ready"],
        "Ready",
        {ItemField.STATUS: "Ready"},
    )


def test_clearing_a_field_removes_its_label_and_records_none(world: World) -> None:
    number = world.seed("unsized", labels=("priority/p2-medium", "effort/high"))
    world.store.set_field(read(world, number), ItemField.EFFORT, None)
    item = read(world, number)
    assert (world.labels(number), item.effort, item.job_record) == (
        ["priority/p2-medium"],
        None,
        {ItemField.EFFORT: None},
    )


def test_a_value_that_is_not_a_fields_value_raises_and_changes_nothing(world: World) -> None:
    """A closed issue is done, so no label holds Done."""
    number = world.seed("finished", labels=("priority/p2-medium",), body="Text")
    item = read(world, number)
    with pytest.raises(GitHubOperationError, match="'Done' is not a Status value"):
        world.store.set_field(item, ItemField.STATUS, "Done")
    assert (world.labels(number), world.raw_body(number)) == (["priority/p2-medium"], "Text")


def test_a_job_never_reverts_a_persons_change(world: World) -> None:
    """The job set Status New and read the Item; a person then set Blocked (ADR 0002)."""
    number = world.seed("blocked meanwhile", labels=("priority/p2-medium",))
    world.store.set_field(read(world, number), ItemField.STATUS, "New")
    item = read(world, number)
    world.person_adds(number, "status/blocked")
    with pytest.raises(RoadmapItemChangedError) as raised:
        world.store.set_field(item, ItemField.STATUS, "Ready")
    assert (
        world.labels(number),
        {key: raised.value.details[key] for key in ("item", "field", "read", "now")},
    ) == (
        ["priority/p2-medium", "status/new", "status/blocked"],
        {"item": f"#{number}", "field": "Status", "read": "New", "now": "Blocked"},
    )


def test_a_persons_change_stays_caught_after_the_job_wrote_another_field(world: World) -> None:
    number = world.seed("sized meanwhile", labels=("priority/p2-medium",))
    item = read(world, number)
    world.person_adds(number, "priority/p1-high")
    world.store.set_field(item, ItemField.EFFORT, "Low")
    with pytest.raises(RoadmapItemChangedError) as raised:
        world.store.set_field(item, ItemField.PRIORITY, "P3-Low")
    assert raised.value.error_code == "ROADMAP_ITEM_CHANGED"
    kept = read(world, number)
    assert (kept.effort, kept.priority) == ("Low", "P1-High")


def test_a_write_of_the_value_the_issue_holds_now_goes_ahead(world: World) -> None:
    """A person set the value the job writes, so the write reverts nothing."""
    number = world.seed("agreed", labels=("priority/p2-medium",))
    item = read(world, number)
    world.person_adds(number, "status/ready")
    world.store.set_field(item, ItemField.STATUS, "Ready")
    assert read(world, number).job_record == {ItemField.STATUS: "Ready"}


def test_the_jobs_own_write_is_the_value_its_next_write_of_that_field_compares(
    world: World,
) -> None:
    number = world.seed("raised twice", labels=("priority/p2-medium",))
    item = read(world, number)
    world.store.set_field(item, ItemField.PRIORITY, "P1-High")
    world.store.set_field(item, ItemField.PRIORITY, "P0-Critical")
    assert world.labels(number) == ["priority/p0-critical"]


def test_two_writes_from_one_read_keep_both_fields_in_the_job_record(world: World) -> None:
    number = world.seed("triage me", labels=("priority/p3-low",))
    item = read(world, number)
    world.store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    world.store.set_field(item, ItemField.STATUS, "Ready")
    assert read(world, number).job_record == {
        ItemField.PRIORITY: "P2-Medium",
        ItemField.STATUS: "Ready",
    }


def test_marks_are_kept_in_the_job_record_and_change_no_field(world: World) -> None:
    number = world.seed("refined", labels=("priority/p2-medium",), body="Problem")
    item = read(world, number)
    world.store.set_marks(
        item, {RefineRecordKey.BODY_HASH: "abc", RefineRecordKey.NEEDS_SPLIT: "1"}
    )
    world.store.set_field(
        item, ItemField.STATUS, "Ready", marks={RefineRecordKey.SECTION_HASH: "def"}
    )
    world.store.set_marks(item, {RefineRecordKey.NEEDS_SPLIT: None})
    marked = read(world, number)
    assert (world.labels(number), marked.body, marked.job_record) == (
        ["priority/p2-medium", "status/ready"],
        "Problem",
        {
            RefineRecordKey.BODY_HASH: "abc",
            RefineRecordKey.NEEDS_SPLIT: None,
            RefineRecordKey.SECTION_HASH: "def",
            ItemField.STATUS: "Ready",
        },
    )


def test_a_body_write_keeps_the_job_record(world: World) -> None:
    """The body the store returns holds no record block, and a body write puts the issue's
    block back at its end."""
    number = world.seed("refined", labels=("priority/p2-medium",), body="Old text")
    world.store.set_marks(read(world, number), {RefineRecordKey.BODY_HASH: "abc"})
    world.store.write_issue_body(number, "New text")
    item = read(world, number)
    assert (
        world.store.read_issue_body(number),
        item.body,
        item.job_record,
        world.raw_body(number).startswith(f"New text\n\n{RECORD} "),
    ) == ("New text", "New text", {RefineRecordKey.BODY_HASH: "abc"}, True)


def test_a_body_with_no_record_is_written_as_given(world: World) -> None:
    number = world.seed("plain", labels=("priority/p2-medium",), body="Old text")
    world.store.write_issue_body(number, "New text")
    assert world.raw_body(number) == "New text"


@pytest.mark.parametrize(
    "block",
    [
        f"{RECORD} not json -->",
        f'{RECORD} ["Priority", "P1-High"] -->',
        f'{RECORD} {{"Priority": 25}} -->',
    ],
    ids=["not-json", "not-an-object", "a-known-key-without-text"],
)
def test_a_broken_record_block_reads_as_an_empty_record(
    world: World, block: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A person's edit of the block stops no job: the Item reads with an empty record, a
    warning names the issue, and the next write replaces the block."""
    number = world.seed("edited by hand", labels=("priority/p2-medium",), body=f"Text\n\n{block}")
    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.store"):
        item = read(world, number)
    world.store.set_marks(item, {RefineRecordKey.BODY_HASH: "abc"})
    assert (
        (item.body, item.job_record),
        any(f"#{number}" in message for message in caplog.messages),
        read(world, number).job_record,
    ) == (("Text", {}), True, {RefineRecordKey.BODY_HASH: "abc"})


QUOTED_RECORDS = {
    "code-span": f"Quote `{RECORD} {{...}} -->` here.",
    "fence": f"```text\n{RECORD} {{...}} -->\n```",
    "indented-code": f"Example:\n\n    {RECORD} {{...}} -->",
    "in-the-middle": f'{RECORD} {{"Priority": "P1-High"}} -->\n\nMore text.',
}


@pytest.mark.parametrize("quote", QUOTED_RECORDS.values(), ids=QUOTED_RECORDS.keys())
def test_a_quote_of_the_record_format_stays_in_the_body_and_is_no_record(
    world: World, quote: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Only a comment at the end of the body is the job record (#2538): text that quotes the
    format, or a comment that more text follows, stays in the body, gives no warning, and
    survives the next write of the record."""
    number = world.seed("quotes", labels=("priority/p2-medium",), body=quote)
    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.store"):
        item = read(world, number)
    world.store.set_marks(item, {RefineRecordKey.BODY_HASH: "abc"})
    assert (
        (item.body, item.job_record),
        caplog.messages,
        world.raw_body(number).startswith(f"{quote}\n\n{RECORD} "),
        read(world, number).body,
    ) == ((quote, {}), [], True, quote)


def test_a_quote_of_the_record_format_does_not_hide_the_real_record_block(world: World) -> None:
    """The record block at the end is the record, though the body quotes the format before it."""
    quote = f"Quote `{RECORD} {{...}} -->` here."
    number = world.seed("quotes", labels=("priority/p2-medium",), body=quote)
    world.store.set_marks(read(world, number), {RefineRecordKey.BODY_HASH: "abc"})
    world.store.write_issue_body(number, f"{quote} Again.")
    item = read(world, number)
    assert (item.body, item.job_record) == (f"{quote} Again.", {RefineRecordKey.BODY_HASH: "abc"})


def test_a_write_to_a_pull_request_or_an_issue_that_does_not_exist_raises(world: World) -> None:
    pull = world.seed("a pull request", labels=("priority/p1-high",), pull_request=True)
    probe = Item(number=pull, title="a pull request", url="https://example.com/pull")
    for number in (pull, 99):
        with pytest.raises(GitHubOperationError, match="is not an issue"):
            world.store.set_field(
                probe.model_copy(update={"number": number}), ItemField.STATUS, "New"
            )
        with pytest.raises(GitHubOperationError, match="is not an issue"):
            world.store.write_issue_body(number, "no")
    assert world.writes() == 0


# ── Closing an issue with a reason (#1658) ────────────────────────────────────


def _closed_as(world: World, number: int) -> tuple[GitHubState, str | None]:
    """The state of issue `number` and the reason it was closed for, as a read gives them now."""
    found = next(issue for issue in world.store.issues() if issue.number == number)
    return found.state, found.state_reason


def test_a_close_posts_its_comment_and_closes_the_issue_for_its_reason(world: World) -> None:
    number = world.seed("superseded")
    world.store.close(number, CloseReason.NOT_PLANNED, comment="Superseded by #2399.")
    assert (
        [comment.body for comment in world.store.comments_on(number)],
        _closed_as(world, number),
        world.writes(),
    ) == (["Superseded by #2399."], (GitHubState.CLOSED, "not_planned"), 2)


def test_a_close_with_no_comment_only_closes(world: World) -> None:
    number = world.seed("done")
    world.store.close(number, CloseReason.COMPLETED)
    assert (world.store.comments_on(number), _closed_as(world, number), world.writes()) == (
        [],
        (GitHubState.CLOSED, "completed"),
        1,
    )


def test_a_close_of_no_open_issue_raises_and_writes_nothing(world: World) -> None:
    """A pull request, a number that names nothing and a closed issue get no comment and no
    close: GitHub ignores a reason when the state does not change."""
    pull = world.seed("a pull request", pull_request=True)
    closed = world.seed("closed", state=GitHubState.CLOSED)
    refused = ((pull, "is not an issue"), (99, "is not an issue"), (closed, "already closed"))
    for number, says in refused:
        with pytest.raises(GitHubOperationError, match=says):
            world.store.close(number, CloseReason.NOT_PLANNED, comment="Superseded.")
    assert world.writes() == 0


# ── The in-memory adapter: milestones, issues and changes ─────────────────────


class SteppedClock:
    """A clock that stands still until a test moves it."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> SteppedClock:
    return SteppedClock()


PLACED = {ItemField.PRIORITY: "P2-Medium"}


@pytest.fixture
def store(clock: SteppedClock) -> InMemoryRoadmapStore:
    roadmap = InMemoryRoadmapStore(clock=clock)
    roadmap.seed_milestone("Docs pass", state=GitHubState.CLOSED, due_on=date(2026, 9, 1))
    roadmap.seed_milestone("Q4 hardening", description="Multi-IDE MCP Scaffolding")
    return roadmap


def test_both_adapters_are_roadmap_stores(github_api: GitHubApiFake) -> None:
    """The GitHub adapter is built with the GitHub session it reads its REST listings through
    (#983): its milestones come from that session's one read, and a title that is no version is
    a milestone like any other."""
    github_api.route(
        "GET",
        "/repos/example/roadmap/milestones?state=all&per_page=100",
        github_json([{"number": 1, "title": "Q4 hardening", "state": "open", "description": ""}]),
    )
    github = GitHubRoadmapStore("example/roadmap", session=get_github_session())
    adapters = (InMemoryRoadmapStore(), github)
    assert (
        [isinstance(adapter, RoadmapStore) for adapter in adapters],
        [milestone.title for milestone in github.milestones()],
        len(github_api.sent),
    ) == ([True, True], ["Q4 hardening"], 1)


def test_a_milestone_is_found_by_its_exact_title_or_by_its_number(
    store: InMemoryRoadmapStore,
) -> None:
    """No title is read as a version: a title found as written, else a number."""
    by_title = store.milestone("Q4 hardening")
    by_number = store.milestone(str(by_title.number if by_title else 0))
    assert (
        by_title is not None,
        by_number == by_title,
        store.milestone("q4 hardening"),
        store.milestone("99"),
    ) == (True, True, None, None)


def test_a_title_wins_over_a_number_that_another_milestone_has(
    store: InMemoryRoadmapStore,
) -> None:
    """A milestone titled "1" is found by that title, not as milestone number 1."""
    titled = store.seed_milestone("1")
    found = store.milestone("1")
    assert (found.number if found else None, titled.number != 1) == (titled.number, True)


def test_milestones_sort_by_due_date_then_number_with_no_due_date_last(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_milestone("2026-11-05", due_on=date(2026, 11, 5))
    store.seed_milestone("Someday")
    store.seed_milestone("2026-10-29", due_on=date(2026, 10, 29))
    assert [milestone.title for milestone in store.milestones()] == [
        "Docs pass",
        "2026-10-29",
        "2026-11-05",
        "Q4 hardening",
        "Someday",
    ]


def test_editing_a_description_leaves_the_state_unchanged(store: InMemoryRoadmapStore) -> None:
    edited = (
        store.edit_milestone("Q4 hardening", description="new text"),
        store.edit_milestone("Docs pass", description="done"),
    )
    assert [(milestone.description, milestone.state) for milestone in edited] == [
        ("new text", GitHubState.OPEN),
        ("done", GitHubState.CLOSED),
    ]


def test_closing_a_milestone_closes_only_that_milestone(store: InMemoryRoadmapStore) -> None:
    store.close_milestone("Q4 hardening")
    assert [(milestone.title, milestone.state) for milestone in store.milestones()] == [
        ("Docs pass", GitHubState.CLOSED),
        ("Q4 hardening", GitHubState.CLOSED),
    ]


def test_editing_an_unknown_milestone_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="No milestone has the title or number"):
        store.edit_milestone("Q5", description="x")


def test_renaming_a_milestone_onto_another_title_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="already has the title"):
        store.edit_milestone("Q4 hardening", title="Docs pass")


def test_a_renamed_milestone_keeps_its_number_and_issues(store: InMemoryRoadmapStore) -> None:
    """GitHub keeps a milestone by its number, so a rename moves no issue out of it."""
    item = store.seed_issue("planned", milestone="Q4 hardening", fields=PLACED)
    before = store.milestone("Q4 hardening")
    renamed = store.as_actor("alice").edit_milestone("Q4 hardening", title="2026-12-01")
    found = store.item(item)
    assert (
        renamed.number == (before.number if before else None),
        found.milestone if found else None,
        [i.number for i in store.items(milestone=renamed.number)],
    ) == (True, "2026-12-01", [item])


def test_items_in_a_milestone_are_its_open_and_closed_items(store: InMemoryRoadmapStore) -> None:
    open_item = store.seed_issue("open", milestone="Q4 hardening", fields=PLACED)
    closed_item = store.seed_issue(
        "closed",
        state=GitHubState.CLOSED,
        state_reason="completed",
        milestone="Q4 hardening",
        fields=PLACED,
    )
    store.seed_issue("no priority", milestone="Q4 hardening")
    store.seed_issue("a pull request", milestone="Q4 hardening", pull_request=True, fields=PLACED)
    store.seed_issue("another milestone", milestone="Docs pass", fields=PLACED)
    store.seed_issue("no milestone", fields=PLACED)

    counted = store.milestone("Q4 hardening")
    assert counted is not None
    in_milestone = store.items(milestone=counted.number)
    assert (
        [(item.number, item.state, item.milestone) for item in in_milestone],
        (counted.open_issues, counted.closed_issues),
    ) == (
        [
            (open_item, GitHubState.OPEN, "Q4 hardening"),
            (closed_item, GitHubState.CLOSED, "Q4 hardening"),
        ],
        (3, 1),
    )


def test_seeding_an_issue_in_a_milestone_that_does_not_exist_raises(
    store: InMemoryRoadmapStore,
) -> None:
    with pytest.raises(GitHubOperationError, match="No milestone"):
        store.seed_issue("lost", milestone="Q5")


def test_backlog_is_the_open_items_in_no_milestone(store: InMemoryRoadmapStore) -> None:
    backlog_item = store.seed_issue("backlog", fields=PLACED)
    store.seed_issue("closed", state=GitHubState.CLOSED, fields=PLACED)
    store.seed_issue("planned", milestone="Q4 hardening", fields=PLACED)
    store.seed_issue("a candidate")
    assert [item.number for item in store.backlog()] == [backlog_item]


def test_an_item_carries_the_body_of_the_issue_listing_it_was_read_from(
    store: InMemoryRoadmapStore,
) -> None:
    """A job judges an Item by its text without a read per Item (#1539): every read of Items
    returns each issue's body, and a body written since is the next read's."""
    planned = store.seed_issue(
        "planned", body="Planned text", milestone="Q4 hardening", fields=PLACED
    )
    unplanned = store.seed_issue("backlog", body="Backlog text", fields=PLACED)
    store.write_issue_body(unplanned, "Backlog text, edited")
    bucket = store.milestone("Q4 hardening")
    assert bucket is not None

    found = store.item(planned)
    assert (
        [(item.number, item.body) for item in store.items()],
        [(item.number, item.body) for item in store.items(milestone=bucket.number)],
        [(item.number, item.body) for item in store.backlog()],
        found.body if found else None,
    ) == (
        [(planned, "Planned text"), (unplanned, "Backlog text, edited")],
        [(planned, "Planned text")],
        [(unplanned, "Backlog text, edited")],
        "Planned text",
    )


def test_a_priority_a_person_takes_off_makes_the_item_a_candidate_again(
    store: InMemoryRoadmapStore,
) -> None:
    number = store.seed_issue("unplaced", fields=PLACED)
    placed = [c.number for c in store.candidates()]
    store.as_actor("alice").remove_label(number, "priority/p2-medium")
    assert (placed, [c.number for c in store.candidates()], store.item(number)) == (
        [],
        [number],
        None,
    )


def test_every_write_to_an_issue_a_comment_included_moves_its_updated_at(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    """Intake tells an edited candidate from one it left by `updated_at` (#1360)."""
    number = store.seed_issue("edited")
    created = clock.now

    def updated_after(write: Callable[[], object]) -> datetime | None:
        clock.now += timedelta(minutes=1)
        write()
        return next(issue.updated_at for issue in store.issues() if issue.number == number)

    person = store.as_actor("alice")
    moved = [
        updated_after(lambda: None),
        updated_after(lambda: person.write_issue_body(number, "more detail")),
        updated_after(lambda: person.comment(number, "Any update?")),
        updated_after(lambda: person.add_label(number, "type/bug")),
    ]
    assert moved == [created, *(created + timedelta(minutes=n) for n in (2, 3, 4))]


def test_a_field_write_is_a_labeled_and_an_unlabeled_change_as_a_poll_reads_them(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    """GitHub reports a label set or taken off as an issue event (ADR 0003), so a field write
    is one change for each label it adds or removes, under the actor who wrote it."""
    number = store.seed_issue("readied", fields={**PLACED, ItemField.STATUS: "New"})
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")
    assert [(c.kind, c.number, c.actor, c.label) for c in store.changes_since(clock.now)] == [
        (ChangeKind.LABELED, number, "devops-cli", "status/ready"),
        (ChangeKind.UNLABELED, number, "devops-cli", "status/new"),
    ]


def test_changes_since_with_an_empty_actor_leaves_out_nothing(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    since = clock.now
    number = store.seed_issue("labeled by a nameless actor")
    store.as_actor("").label_issue(number, "type/bug")
    changes = store.changes_since(since, except_actor="")
    assert [(change.actor, change.label) for change in changes] == [("", "type/bug")]


def test_a_persons_value_differs_from_the_job_record(store: InMemoryRoadmapStore) -> None:
    """A person's write sets the label and records nothing, so the record keeps the job's."""
    number = store.seed_issue("prioritize me", fields={ItemField.PRIORITY: "P3-Low"})
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    store.as_actor("alice").set_field(item, ItemField.PRIORITY, "P1-High")
    changed = store.item(number)
    assert changed is not None
    assert (changed.priority, changed.job_record) == ("P1-High", {ItemField.PRIORITY: "P2-Medium"})


def test_a_person_reopens_a_closed_issue_in_its_milestone(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("done", milestone="Q4 hardening", fields=PLACED)
    store.as_actor("alice").close_by_hand(number, CloseReason.COMPLETED)
    since = store.changes_since(datetime.min)
    store.as_actor("alice").reopen_issue(number)
    found = store.item(number)
    assert (
        (found.state, found.state_reason, found.milestone) if found else None,
        [(c.kind, c.number) for c in store.changes_since(datetime.min)[len(since) :]],
    ) == ((GitHubState.OPEN, "reopened", "Q4 hardening"), [(ChangeKind.REOPENED, number)])


def test_a_person_moves_an_issue_into_a_milestone_and_out_of_it(
    store: InMemoryRoadmapStore,
) -> None:
    """No job sets a milestone: a person plans the buckets, and the store reads where they put it."""
    number = store.seed_issue("planned by a person", fields=PLACED)
    person = store.as_actor("alice")
    person.move_by_hand(number, "Q4 hardening")
    moved = store.item(number)
    person.move_by_hand(number, None)
    with pytest.raises(GitHubOperationError, match="No milestone"):
        person.move_by_hand(number, "Q5")
    assert (
        moved.milestone if moved else None,
        [item.number for item in store.backlog()],
        store.job_writes(),
    ) == ("Q4 hardening", [number], [])


def test_issues_are_every_issue_open_or_closed_and_never_a_pull_request(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_issue("open, no priority")
    store.seed_issue("closed, placed", state=GitHubState.CLOSED, fields=PLACED)
    store.seed_issue("a pull request", pull_request=True)
    assert [issue.title for issue in store.issues()] == ["open, no priority", "closed, placed"]


def test_a_repository_file_is_read_at_its_ref_and_a_missing_one_raises(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_file(".github/labels.yml", "- name: type/bug\n", ref="feat/topic")
    store.seed_file(".github/labels.yml", "- name: type/feature\n")
    read_back = (
        store.repository_file(".github/labels.yml", ref="feat/topic"),
        store.repository_file(".github/labels.yml"),
    )
    with pytest.raises(GitHubFileNotFoundError, match=r"no CONTEXT\.md"):
        store.repository_file("CONTEXT.md")
    assert read_back == ("- name: type/bug\n", "- name: type/feature\n")


def test_a_field_write_records_marks_with_its_value_and_a_persons_records_neither(
    store: InMemoryRoadmapStore,
) -> None:
    number = store.seed_issue("refined", fields=PLACED)
    item = store.item(number)
    assert item is not None
    store.set_field(
        item, ItemField.STATUS, "Ready", marks={RefineRecordKey.SECTION_HASH: "section"}
    )
    store.as_actor("alice").set_field(
        item, ItemField.PRIORITY, "P1-High", marks={RefineRecordKey.SECTION_HASH: None}
    )
    written = store.item(number)
    assert ((written.status, written.priority, written.job_record) if written else None) == (
        "Ready",
        "P1-High",
        {ItemField.STATUS: "Ready", RefineRecordKey.SECTION_HASH: "section"},
    )


def test_a_persons_marks_are_not_recorded(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("refinable", fields=PLACED)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {RefineRecordKey.NEEDS_SPLIT: "true"})
    store.as_actor("alice").set_marks(item, {RefineRecordKey.NEEDS_SPLIT: "false"})
    marked = store.item(number)
    assert (marked.job_record if marked else None) == {RefineRecordKey.NEEDS_SPLIT: "true"}


def test_a_comment_is_kept_on_its_issue_with_the_time_it_was_made(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    number = store.seed_issue("commented", milestone="Q4 hardening", fields=PLACED)
    store.comment(number, "Moved to the backlog.")
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.comment(store.seed_issue("a pull request", pull_request=True), "no")
    assert store.comments_on(number) == [
        IssueComment(body="Moved to the backlog.", created_at=clock.now)
    ]


def test_a_path_changed_when_the_newest_commit_that_changed_it_was_made(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    """The time of the newest commit on the default branch that changed a path, and none for a
    path that no commit changed (#2005)."""
    later = clock.now + timedelta(hours=1)
    store.seed_commit("src/app.py", at=later)
    store.seed_commit("src/app.py", at=clock.now)
    assert (store.path_changed_at("src/app.py"), store.path_changed_at("src/other.py")) == (
        later,
        None,
    )


# ── What intake reads and writes (#742) ───────────────────────────────────────


def test_labeling_an_issue_adds_the_label_once_as_a_job_write(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("unlabeled", labels=("bug",))
    store.label_issue(number, "type/bug")
    store.label_issue(number, "type/bug")
    issue = next(issue for issue in store.issues() if issue.number == number)
    assert (issue.labels, [w.operation for w in store.job_writes()][-1:]) == (
        ("bug", "type/bug"),
        ["label_issue"],
    )


def test_evidence_holds_only_for_what_github_confirms(store: InMemoryRoadmapStore) -> None:
    store.seed_evidence(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"))
    asked = [
        Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"),
        Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="def5678"),
        Evidence(kind=EvidenceKind.FAILED_RUN, value="abc1234"),
    ]
    assert [store.evidence_holds(evidence) for evidence in asked] == [True, False, False]


def test_a_milestone_records_when_it_closed_and_forgets_it_when_reopened(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    store.close_milestone("Q4 hardening")
    closed = store.milestone("Q4 hardening")
    store.edit_milestone("Q4 hardening", state=GitHubState.OPEN)
    reopened = store.milestone("Q4 hardening")
    assert (
        closed.closed_at if closed else None,
        reopened.closed_at if reopened else "missing",
        docs.closed_at if (docs := store.milestone("Docs pass")) else "missing",
    ) == (clock.now, None, clock.now)


def test_read_and_write_issue_body(store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("task", body="Initial body")
    pr_num = store.seed_issue("pr", pull_request=True)
    initial_read = store.read_issue_body(num)
    store.write_issue_body(num, "Updated body")
    writes = [w.operation for w in store.job_writes() if w.number == num]
    assert (initial_read, store.read_issue_body(num), writes) == (
        "Initial body",
        "Updated body",
        ["write_issue_body"],
    )
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.read_issue_body(pr_num)
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.write_issue_body(pr_num, "fail")


def test_repository_visibility_contract(store: InMemoryRoadmapStore) -> None:
    initial = store.repository_is_private()
    store.seed_visibility(is_private=True)
    seeded_private = store.repository_is_private()
    fresh_private_store = InMemoryRoadmapStore(is_private=True)
    assert (
        initial,
        seeded_private,
        fresh_private_store.repository_is_private(),
    ) == (False, True, True)


def test_repository_facts_are_those_seeded_for_the_repository(store: InMemoryRoadmapStore) -> None:
    """The facts of a repository, a tool an item might use, and none for a repository that does not
    exist (#2650)."""
    facts = RepositoryFacts(
        full_name="example/tool",
        url="https://github.com/example/tool",
        license="MIT",
        pushed_at=datetime(2026, 10, 1, tzinfo=UTC),
        stars=7,
    )
    store.seed_repository(facts)
    assert (store.repository_facts("example/tool"), store.repository_facts("example/none")) == (
        facts,
        None,
    )


def test_add_sub_issue_links_child_to_parent(world: World) -> None:
    parent = world.seed("parent")
    child = world.seed("child")
    world.store.add_sub_issue(parent, child)
    parent_record = next(i for i in world.store.issues() if i.number == parent)
    child_record = next(i for i in world.store.issues() if i.number == child)
    assert (parent_record.sub_issues, child_record.parent) == (1, parent)
    with pytest.raises(GitHubOperationError, match="not an issue"):
        world.store.add_sub_issue(999, child)


def test_add_sub_issue_links_child_to_parent_with_cached_issues(world: World) -> None:
    parent = world.seed("parent")
    child = world.seed("child")
    _ = list(world.store.issues())
    world.store.add_sub_issue(parent, child)
    parent_record = next(i for i in world.store.issues() if i.number == parent)
    child_record = next(i for i in world.store.issues() if i.number == child)
    assert (parent_record.sub_issues, child_record.parent) == (1, parent)


# ── The reads of the inbox (#2915) ────────────────────────────────────────────

MOMENT = datetime(2026, 10, 20, 8, 30, tzinfo=UTC)


def test_open_items_are_the_open_items_with_the_time_of_their_last_update(world: World) -> None:
    """A closed item, a candidate and a pull request are not in the listing of open items."""
    open_item = world.seed("open", labels=("priority/p2-medium",), updated_at=MOMENT)
    world.seed("closed", labels=("priority/p3-low",), state=GitHubState.CLOSED)
    world.seed("candidate", labels=("type/bug",))
    world.seed("a pull request", labels=("priority/p1-high",), pull_request=True)
    assert [(item.number, item.updated_at) for item in world.store.open_items()] == [
        (open_item, MOMENT)
    ]


def test_open_pulls_are_the_open_pull_requests_with_their_branch_and_draft_state(
    world: World,
) -> None:
    ready = world.seed_pull("ready", head_ref="feat/7-ready", updated_at=MOMENT)
    draft = world.seed_pull("draft", head_ref="fix/8-draft", draft=True)
    world.seed_pull("merged", head_ref="fix/9-merged", state=GitHubState.CLOSED)
    world.seed("an issue")
    pulls = world.store.open_pulls()
    assert [(p.number, p.title, p.head_ref, p.draft) for p in pulls] == [
        (ready, "ready", "feat/7-ready", False),
        (draft, "draft", "fix/8-draft", True),
    ]
    assert (pulls[0].updated_at, pulls[0].url.endswith(f"/pull/{ready}")) == (MOMENT, True)
    assert all(isinstance(pull, OpenPull) for pull in pulls)


def test_repository_labels_are_the_labels_with_a_missing_description_as_empty(
    world: World,
) -> None:
    world.seed_label("type/bug", "D73A4A", "A defect")
    world.seed_label("scope/ci", "0E8A16")
    assert world.store.repository_labels() == [
        RepositoryLabel(name="type/bug", color="D73A4A", description="A defect"),
        RepositoryLabel(name="scope/ci", color="0E8A16", description=""),
    ]


def test_the_github_store_reads_open_issues_and_never_the_listing_of_every_issue() -> None:
    """The inbox reads `state=open`: the listing of every issue is about thirty pages."""
    world = GitHubWorld()
    world.seed("open", labels=("priority/p2-medium",))
    world.store.open_items()
    read = [call[0] for call in world.github.calls if call[0].startswith(API)]
    assert [path.split("/issues?", 1)[1].split("&")[0] for path in read] == ["state=open"]
