"""Contract suite for the roadmap store, run against the in-memory adapter.

Each case pins one promise `RoadmapStore` makes. The GitHub adapter, built with the GitHub
session it reads its REST listings through, keeps the same promises in
`tests/test_roadmap_github_store.py`, over recorded `gh` output, but one: of the changes a poll
reads, it reports the issue events' four kinds (#1360), and not a board field set, a comment or
an edit, which only the in-memory adapter records (`ChangeKind`). A milestone is a planning
bucket: any title, identified by its number and ordered by its due date.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest

from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapCardChangedError
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore, JobWrite
from devops_cli.roadmap.store import (
    BoardField,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    EvidenceKind,
    FieldOption,
    GitHubState,
    IssueComment,
    ItemField,
    RefineRecordKey,
    RoadmapStore,
)
from tests.support.fakes.github import GitHubApiFake, github_json

BOARD_OPTIONS = {
    ItemField.STATUS: ("Backlog", "Ready", "In Progress", "Done"),
    ItemField.PRIORITY: ("P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
    ItemField.VALUE: ("High", "Medium", "Low"),
    ItemField.EFFORT: ("Low", "Medium", "High"),
}


class SteppedClock:
    """A clock that stands still until a test moves it."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> SteppedClock:
    return SteppedClock()


@pytest.fixture
def store(clock: SteppedClock) -> InMemoryRoadmapStore:
    roadmap = InMemoryRoadmapStore(board_options=BOARD_OPTIONS, clock=clock)
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
    item = store.seed_issue("planned", milestone="Q4 hardening", on_board=True)
    before = store.milestone("Q4 hardening")
    renamed = store.as_actor("alice").edit_milestone("Q4 hardening", title="2026-12-01")
    found = store.item(item)
    assert (
        renamed.number == (before.number if before else None),
        found.milestone if found else None,
        [i.number for i in store.items(milestone=renamed.number)],
    ) == (True, "2026-12-01", [item])


def test_items_in_a_milestone_are_its_open_and_closed_items(store: InMemoryRoadmapStore) -> None:
    open_item = store.seed_issue("open", milestone="Q4 hardening", on_board=True)
    closed_item = store.seed_issue(
        "closed",
        state=GitHubState.CLOSED,
        state_reason="completed",
        milestone="Q4 hardening",
        on_board=True,
    )
    store.seed_issue("off the board", milestone="Q4 hardening")
    store.seed_issue("a pull request", milestone="Q4 hardening", pull_request=True, on_board=True)
    store.seed_issue("another milestone", milestone="Docs pass", on_board=True)
    store.seed_issue("no milestone", on_board=True)

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
    backlog_item = store.seed_issue("backlog", on_board=True)
    store.seed_issue("closed", state=GitHubState.CLOSED, on_board=True)
    store.seed_issue("planned", milestone="Q4 hardening", on_board=True)
    store.seed_issue("not on the board")
    assert [item.number for item in store.backlog()] == [backlog_item]


def test_an_item_carries_the_body_of_the_issue_listing_it_was_read_from(
    store: InMemoryRoadmapStore,
) -> None:
    """A job judges an Item by its text without a read per Item (#1539): every read of Items
    returns each issue's body, and a body written since is the next read's."""
    planned = store.seed_issue(
        "planned", body="Planned text", milestone="Q4 hardening", on_board=True
    )
    unplanned = store.seed_issue("backlog", body="Backlog text", on_board=True)
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


def test_candidates_are_open_issues_not_on_the_board(store: InMemoryRoadmapStore) -> None:
    candidate = store.seed_issue("intake me", labels=("type/bug",))
    store.seed_issue("closed", state=GitHubState.CLOSED)
    store.seed_issue("on the board", on_board=True)
    store.seed_issue("a pull request", pull_request=True)
    assert [(c.number, c.labels) for c in store.candidates()] == [(candidate, ("type/bug",))]


def test_adding_an_item_puts_an_issue_on_the_board(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("intake me")
    store.add_item(number)
    assert ([c.number for c in store.candidates()], store.item(number) is not None) == ([], True)


def test_adding_an_item_returns_it_with_its_card_and_adding_it_again_keeps_that_card(
    store: InMemoryRoadmapStore,
) -> None:
    """The writes that place it go to the card the add returns (#1361)."""
    number = store.seed_issue("intake me")
    added = store.add_item(number)
    store.set_field(added, ItemField.STATUS, "Ready")
    again = store.add_item(number)
    assert (
        added.number,
        added.card_id is not None,
        again.card_id == added.card_id,
        again.status,
        [item.card_id for item in store.items()] == [added.card_id],
    ) == (number, True, True, "Ready", True)


def test_an_archived_card_leaves_the_board_and_adding_its_issue_restores_it_with_its_fields(
    store: InMemoryRoadmapStore,
) -> None:
    """A person archives a card: the issue is a candidate again and no read holds the card.
    The add restores that card, marked `restored`, with its fields and job record (#1403)."""
    number = store.seed_issue("archived by a person")
    added = store.add_item(number)
    store.set_field(added, ItemField.STATUS, "Ready")
    store.as_actor("alice").archive_card(number)
    archived = ([c.number for c in store.candidates()], store.item(number), store.items())
    restored = store.add_item(number)
    assert (
        added.restored,
        archived,
        (restored.restored, restored.card_id, restored.status, restored.job_record),
        [c.number for c in store.candidates()],
        store.add_item(number).restored,
    ) == (
        False,
        ([number], None, []),
        (True, added.card_id, "Ready", {ItemField.STATUS: "Ready"}),
        [],
        False,
    )


def test_archiving_a_card_that_is_not_on_the_board_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="not on the board"):
        store.archive_card(store.seed_issue("never added"))


def test_an_item_whose_card_is_not_its_own_is_not_on_the_board(
    store: InMemoryRoadmapStore,
) -> None:
    """A write goes to the Item's card: one built without the card it has raises, and writes
    nothing."""
    item = store.add_item(store.seed_issue("intake me"))
    before = len(store.job_writes())
    with pytest.raises(GitHubOperationError, match="not on the board"):
        store.set_field(item.model_copy(update={"card_id": None}), ItemField.STATUS, "Ready")
    assert store.job_writes()[before:] == []


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


def test_changes_since_with_an_empty_actor_leaves_out_nothing(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    since = clock.now
    number = store.seed_issue("labeled by a nameless actor")
    store.as_actor("").label_issue(number, "type/bug")
    changes = store.changes_since(since, except_actor="")
    assert [(change.actor, change.label) for change in changes] == [("", "type/bug")]


def test_adding_a_pull_request_raises(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("a pull request", pull_request=True)
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.add_item(number)


def test_a_value_that_is_not_a_board_option_raises_and_changes_nothing(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("prioritize me", on_board=True))
    assert item is not None
    with pytest.raises(GitHubOperationError, match="not a Priority option"):
        store.set_field(item, ItemField.PRIORITY, "P9-Someday")
    assert (store.item(item.number), store.changes_since(datetime.min)) == (item, [])


def test_the_store_records_the_value_it_sets(store: InMemoryRoadmapStore) -> None:
    item = store.item(store.seed_issue("prioritize me", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    written = store.item(item.number)
    assert written is not None
    assert (written.priority, written.job_record) == (
        "P2-Medium",
        {ItemField.PRIORITY: "P2-Medium"},
    )


def test_two_writes_from_one_read_keep_both_fields_in_the_job_record(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("triage me", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    store.set_field(item, ItemField.STATUS, "Ready")
    written = store.item(item.number)
    assert (written.job_record if written else None) == {
        ItemField.PRIORITY: "P2-Medium",
        ItemField.STATUS: "Ready",
    }


def test_a_persons_change_differs_from_the_job_record(store: InMemoryRoadmapStore) -> None:
    item = store.item(store.seed_issue("prioritize me", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    store.as_actor("alice").set_field(item, ItemField.PRIORITY, "P1-High")
    changed = store.item(item.number)
    assert changed is not None
    assert (
        changed.field_value(ItemField.PRIORITY),
        changed.job_record.get(ItemField.PRIORITY),
    ) == ("P1-High", "P2-Medium")


# ── A job never reverts a change it did not read (ADR 0002, #1361) ────────────


def test_a_persons_change_stays_caught_after_the_job_wrote_another_field_of_the_card(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("size and prioritize me", on_board=True))
    assert item is not None
    store.as_actor("alice").set_field(item, ItemField.PRIORITY, "P1-High")
    store.set_field(item, ItemField.EFFORT, "Low")
    with pytest.raises(RoadmapCardChangedError):
        store.set_field(item, ItemField.PRIORITY, "P3-Low")
    kept = store.item(item.number)
    assert ((kept.effort, kept.priority) if kept else None) == ("Low", "P1-High")


def test_a_field_the_board_does_not_have_raises() -> None:
    store = InMemoryRoadmapStore(board_options={ItemField.STATUS: ("Backlog",)})
    item = store.item(store.seed_issue("sized", on_board=True))
    assert item is not None
    with pytest.raises(GitHubOperationError, match="no 'Value' field"):
        store.set_field(item, ItemField.VALUE, "High")


def test_writing_an_item_that_left_the_board_raises(store: InMemoryRoadmapStore) -> None:
    item = store.item(store.seed_issue("on the board", on_board=True))
    assert item is not None
    stale = item.model_copy(update={"number": store.seed_issue("never on the board")})
    with pytest.raises(GitHubOperationError, match="not on the board"):
        store.set_field(stale, ItemField.STATUS, "Ready")


# ── Board fields, issues and files (#739) ─────────────────────────────────────


@pytest.fixture
def board(clock: SteppedClock) -> InMemoryRoadmapStore:
    """A board whose Status has Todo, Backlog and Ready, with one card on each."""
    roadmap = InMemoryRoadmapStore(clock=clock)
    roadmap.seed_field("Status", options=("Todo", "Backlog", "Ready"))
    person = roadmap.as_actor("alice")
    for status in ("Todo", "Backlog", "Ready"):
        item = roadmap.item(roadmap.seed_issue(f"holds {status}", on_board=True))
        assert item is not None
        person.set_field(item, ItemField.STATUS, status)
    return roadmap


def _status(store: InMemoryRoadmapStore) -> BoardField:
    return next(board_field for board_field in store.board_fields() if board_field.name == "Status")


def test_board_fields_carry_each_options_id(board: InMemoryRoadmapStore) -> None:
    status = _status(board)
    assert (
        status.single_select,
        [(bool(o.id), o.name) for o in status.options],
        len({o.id for o in status.options}),
    ) == (True, [(True, "Todo"), (True, "Backlog"), (True, "Ready")], 3)


def test_an_option_renamed_by_hand_keeps_its_id_and_its_cards_value(
    board: InMemoryRoadmapStore,
) -> None:
    """The in-memory model of the board's field settings, the only place an option keeps its id.

    No store operation edits options: GitHub's option input takes no id (#739).
    """
    _todo, backlog, ready = _status(board).options
    edited = board.edit_options_by_hand(
        "Status",
        [
            backlog.model_copy(update={"name": "New"}),
            ready,
            FieldOption(name="Blocked", color="RED"),
        ],
    )
    assert (
        [(o.id, o.name) for o in edited.options[:2]],
        bool(edited.options[2].id),
        [item.status for item in board.items()],
    ) == ([(backlog.id, "New"), (ready.id, "Ready")], True, [None, "New", "Ready"])


def test_a_person_reopens_a_closed_issue_in_its_milestone(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("done", milestone="Q4 hardening", on_board=True)
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
    number = store.seed_issue("planned by a person", on_board=True)
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
    store.seed_issue("open, off the board")
    store.seed_issue("closed, on the board", state=GitHubState.CLOSED, on_board=True)
    store.seed_issue("a pull request", pull_request=True)
    assert [issue.title for issue in store.issues()] == [
        "open, off the board",
        "closed, on the board",
    ]


def test_a_repository_file_is_read_at_its_ref_and_a_missing_one_raises(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_file(".github/roadmap.toml", "board = 2\n", ref="feat/topic")
    store.seed_file(".github/roadmap.toml", "board = 1\n")
    read = (
        store.repository_file(".github/roadmap.toml", ref="feat/topic"),
        store.repository_file(".github/roadmap.toml"),
    )
    with pytest.raises(GitHubFileNotFoundError, match=r"no \.github/labels\.yml"):
        store.repository_file(".github/labels.yml")
    assert read == ("board = 2\n", "board = 1\n")


def test_a_board_number_that_names_no_board_refuses_item_reads() -> None:
    store = InMemoryRoadmapStore(board_exists=False)
    with pytest.raises(GitHubOperationError, match="names no board"):
        store.items()
    with pytest.raises(GitHubOperationError, match="names no board"):
        store.candidates()


# ── What refine and intake mark (#744) ────────────────────────────────────────


def test_marks_are_kept_in_the_job_record_and_change_no_field(store: InMemoryRoadmapStore) -> None:
    item = store.item(store.seed_issue("refined", milestone="Q4 hardening", on_board=True))
    assert item is not None
    store.set_marks(item, {RefineRecordKey.BODY_HASH: "abc", RefineRecordKey.NEEDS_SPLIT: "true"})
    store.set_field(item, ItemField.STATUS, "Ready")
    store.set_marks(item, {RefineRecordKey.BODY_HASH: None, RefineRecordKey.NEEDS_SPLIT: None})
    written = store.item(item.number)
    assert (
        (written.milestone, written.status, written.job_record) if written else None,
        [change.kind for change in store.changes_since(datetime.min)],
    ) == (
        (
            "Q4 hardening",
            "Ready",
            {
                RefineRecordKey.BODY_HASH: None,
                RefineRecordKey.NEEDS_SPLIT: None,
                ItemField.STATUS: "Ready",
            },
        ),
        [ChangeKind.FIELD_CHANGED],
    )


def test_a_field_write_records_marks_with_its_value_and_a_persons_records_neither(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("refined", on_board=True))
    assert item is not None
    store.set_field(
        item, ItemField.STATUS, "Ready", marks={RefineRecordKey.SECTION_HASH: "section"}
    )
    store.as_actor("alice").set_field(
        item, ItemField.PRIORITY, "P1-High", marks={RefineRecordKey.SECTION_HASH: None}
    )
    written = store.item(item.number)
    assert ((written.status, written.priority, written.job_record) if written else None) == (
        "Ready",
        "P1-High",
        {ItemField.STATUS: "Ready", RefineRecordKey.SECTION_HASH: "section"},
    )


def test_marks_refuse_an_item_off_the_board_and_a_board_without_a_job_record_field(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("on the board", on_board=True))
    assert item is not None
    gone = item.model_copy(update={"number": store.seed_issue("never on the board")})
    writes = store.job_writes()
    unrecorded = InMemoryRoadmapStore(board_options=BOARD_OPTIONS, job_record_field=False)
    unrecorded_item = unrecorded.item(unrecorded.seed_issue("unrecorded", on_board=True))
    assert unrecorded_item is not None
    with pytest.raises(GitHubOperationError, match="not on the board"):
        store.set_marks(gone, {RefineRecordKey.BODY_HASH: "abc"})
    with pytest.raises(GitHubOperationError, match="Job record"):
        unrecorded.set_marks(unrecorded_item, {RefineRecordKey.BODY_HASH: "abc"})
    assert (store.job_writes(), unrecorded.item(unrecorded_item.number)) == (
        writes,
        unrecorded_item,
    )


def test_a_comment_is_kept_on_its_issue_with_the_time_it_was_made(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    number = store.seed_issue("commented", milestone="Q4 hardening", on_board=True)
    store.comment(number, "Moved to the backlog.")
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.comment(store.seed_issue("a pull request", pull_request=True), "no")
    assert (
        store.comments_on(number),
        [(c.kind, c.number) for c in store.changes_since(datetime.min)],
    ) == (
        [IssueComment(body="Moved to the backlog.", created_at=clock.now)],
        [(ChangeKind.COMMENTED, number)],
    )


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


def test_a_change_reads_the_value_and_job_record_as_they_are_now(
    store: InMemoryRoadmapStore,
) -> None:
    """A job set the Status, then a person changed it: the job's change now reads as no longer
    matching the record, which is what tells it from the job's own."""
    item = store.item(store.seed_issue("readied", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")
    store.as_actor("alice").set_field(item, ItemField.STATUS, "In Progress")
    assert [
        (c.kind, c.field, c.value, c.job_record) for c in store.changes_since(datetime.min)
    ] == [
        (ChangeKind.FIELD_CHANGED, ItemField.STATUS, "In Progress", {ItemField.STATUS: "Ready"}),
        (ChangeKind.FIELD_CHANGED, ItemField.STATUS, "In Progress", {ItemField.STATUS: "Ready"}),
    ]


# ── What intake reads and writes (#742) ───────────────────────────────────────


def test_a_duplicate_close_comments_then_closes_and_its_timeline_names_the_original(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    original = store.seed_issue("original", state=GitHubState.CLOSED, state_reason="not_planned")
    copy = store.seed_issue("copy", author_association="NONE")
    store.close_as_duplicate(copy, original, "Duplicate of #1.")
    closed_at = clock.now
    clock.now += timedelta(hours=1)
    store.as_actor("alice").reopen_issue(copy)
    issue = next(issue for issue in store.issues() if issue.number == copy)
    assert (
        [comment.body for comment in store.comments_on(copy)],
        (issue.state, issue.author_association),
        store.closures(copy),
        store.job_writes()[-2:],
    ) == (
        ["Duplicate of #1."],
        (GitHubState.OPEN, "NONE"),
        [
            Closure(kind=ChangeKind.CLOSED, at=closed_at, reason="duplicate", duplicate_of=1),
            Closure(kind=ChangeKind.REOPENED, at=clock.now),
        ],
        [
            JobWrite("comment", copy, value="Duplicate of #1."),
            JobWrite("close_as_duplicate", copy, value="1"),
        ],
    )


def test_a_duplicate_close_without_a_comment_only_closes(store: InMemoryRoadmapStore) -> None:
    """A retry whose duplicate comment is already there closes without a second one."""
    original = store.seed_issue("original")
    copy = store.seed_issue("copy")
    store.close_as_duplicate(copy, original, None)
    assert (store.comments_on(copy), store.closures(copy)[-1].duplicate_of) == ([], original)


def test_a_duplicate_close_refuses_a_pull_request_on_either_side(
    store: InMemoryRoadmapStore,
) -> None:
    issue = store.seed_issue("issue")
    pull_request = store.seed_issue("a pull request", pull_request=True)
    refused = []
    for number, original in ((pull_request, issue), (issue, pull_request)):
        with pytest.raises(GitHubOperationError, match="not an issue"):
            store.close_as_duplicate(number, original, "no")
        refused.append(store.comments_on(number))
    assert (refused, store.closures(issue)) == ([[], []], [])


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
    updated_read = store.read_issue_body(num)
    changes = [
        c.kind for c in store.changes_since(datetime.min.replace(tzinfo=UTC)) if c.number == num
    ]
    writes = [w.operation for w in store.job_writes() if w.number == num]

    assert (
        initial_read,
        updated_read,
        ChangeKind.EDITED in changes,
        "write_issue_body" in writes,
    ) == ("Initial body", "Updated body", True, True)
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


def test_refine_marks_in_job_record(store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("refinable")
    store.add_item(num)
    item = store.item(num)
    assert item is not None
    store.set_marks(
        item,
        {
            RefineRecordKey.BODY_HASH: "abc",
            RefineRecordKey.SECTION_HASH: "def",
            RefineRecordKey.NEEDS_SPLIT: "true",
        },
    )
    marked = store.item(num)
    assert marked is not None
    assert (
        marked.job_record.get(RefineRecordKey.BODY_HASH),
        marked.job_record.get(RefineRecordKey.SECTION_HASH),
        marked.job_record.get(RefineRecordKey.NEEDS_SPLIT),
    ) == ("abc", "def", "true")

    # as_actor does not write job record
    person = store.as_actor("alice")
    person.set_marks(marked, {RefineRecordKey.NEEDS_SPLIT: "false"})
    after_person = store.item(num)
    assert after_person is not None
    assert after_person.job_record.get(RefineRecordKey.NEEDS_SPLIT) == "true"
