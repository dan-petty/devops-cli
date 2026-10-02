"""Contract suite for the roadmap store, run against the in-memory adapter.

Each case pins one promise `RoadmapStore` makes. The GitHub adapter keeps the same promises in
`tests/test_roadmap_github_store.py`, over recorded `gh` output.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.validation import InvalidVersionError
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import (
    BoardField,
    CardKind,
    ChangeKind,
    CloseReason,
    FieldOption,
    FieldSpec,
    GitHubState,
    ItemField,
    RoadmapStore,
)

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
    roadmap.create_release("v0.2.24", state=GitHubState.CLOSED)
    roadmap.create_release("v0.2.25", description="Multi-IDE MCP Scaffolding")
    return roadmap


def test_both_adapters_are_roadmap_stores() -> None:
    adapters = (InMemoryRoadmapStore(), GitHubRoadmapStore("example/roadmap"))
    assert [isinstance(adapter, RoadmapStore) for adapter in adapters] == [True, True]


def test_a_release_is_found_with_or_without_its_v(store: InMemoryRoadmapStore) -> None:
    found = (store.release("0.2.25"), store.release("v0.2.25"))
    assert (found[0], found[0].title if found[0] else None) == (found[1], "v0.2.25")


def test_an_unknown_version_finds_no_release(store: InMemoryRoadmapStore) -> None:
    assert store.release("9.9.9") is None


def test_a_version_that_is_not_a_version_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(InvalidVersionError, match="Release 1"):
        store.release("Release 1")


def test_creating_a_version_that_already_exists_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="already exists"):
        store.create_release("0.2.25")
    assert [release.title for release in store.releases()] == ["v0.2.24", "v0.2.25"]


def test_releases_sort_by_version_not_by_text(store: InMemoryRoadmapStore) -> None:
    store.create_release("v0.2.10")
    store.create_release("v0.2.9")
    assert [release.title for release in store.releases()] == [
        "v0.2.9",
        "v0.2.10",
        "v0.2.24",
        "v0.2.25",
    ]


def test_editing_a_description_leaves_the_state_unchanged(store: InMemoryRoadmapStore) -> None:
    edited = (
        store.edit_release("0.2.25", description="new text"),
        store.edit_release("0.2.24", description="shipped"),
    )
    assert [(release.description, release.state) for release in edited] == [
        ("new text", GitHubState.OPEN),
        ("shipped", GitHubState.CLOSED),
    ]


def test_closing_a_release_closes_only_that_release(store: InMemoryRoadmapStore) -> None:
    store.close_release("v0.2.25")
    assert [(release.title, release.state) for release in store.releases()] == [
        ("v0.2.24", GitHubState.CLOSED),
        ("v0.2.25", GitHubState.CLOSED),
    ]


def test_editing_an_unknown_release_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="No Release"):
        store.edit_release("9.9.9", description="x")


def test_renaming_a_release_onto_another_version_raises(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="already exists"):
        store.edit_release("0.2.25", title="v0.2.24")


def test_items_in_a_release_are_its_open_and_closed_items(store: InMemoryRoadmapStore) -> None:
    open_item = store.seed_issue("open", release="v0.2.25", on_board=True)
    closed_item = store.seed_issue(
        "closed",
        state=GitHubState.CLOSED,
        state_reason="completed",
        release="v0.2.25",
        on_board=True,
    )
    store.seed_issue("off the board", release="v0.2.25")
    store.seed_issue("a pull request", release="v0.2.25", pull_request=True, on_board=True)
    store.seed_issue("another release", release="v0.2.24", on_board=True)
    store.seed_issue("no release", on_board=True)

    in_release = store.items(release="v0.2.25")
    counted = store.release("0.2.25")
    assert (
        [(item.number, item.state, item.release) for item in in_release],
        (counted.open_issues, counted.closed_issues) if counted else None,
    ) == (
        [(open_item, GitHubState.OPEN, "v0.2.25"), (closed_item, GitHubState.CLOSED, "v0.2.25")],
        (3, 1),
    )


def test_backlog_is_the_open_items_in_no_release(store: InMemoryRoadmapStore) -> None:
    backlog_item = store.seed_issue("backlog", on_board=True)
    store.seed_issue("closed", state=GitHubState.CLOSED, on_board=True)
    store.seed_issue("planned", release="v0.2.25", on_board=True)
    store.seed_issue("not on the board")
    assert [item.number for item in store.backlog()] == [backlog_item]


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
    with pytest.raises(GitHubOperationError, match="No Release"):
        store.set_field(item, ItemField.RELEASE, "v9.9.9")
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


def test_an_item_the_store_never_wrote_has_an_empty_job_record(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("untouched", on_board=True))
    assert item is not None
    store.as_actor("alice").set_field(item, ItemField.STATUS, "Ready")
    untouched = store.item(item.number)
    assert untouched is not None
    assert (untouched.status, untouched.job_record) == ("Ready", {})


def test_a_board_without_a_job_record_field_refuses_item_writes() -> None:
    store = InMemoryRoadmapStore(board_options=BOARD_OPTIONS, job_record_field=False)
    item = store.item(store.seed_issue("prioritize me", on_board=True))
    assert item is not None
    with pytest.raises(GitHubOperationError, match="Job record"):
        store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    assert store.item(item.number) == item


def test_a_person_placing_an_item_in_a_release_is_one_change_by_them(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    earlier = store.item(store.seed_issue("placed by the job", on_board=True))
    item = store.item(store.seed_issue("placed by alice", on_board=True))
    assert earlier is not None and item is not None
    store.set_field(earlier, ItemField.RELEASE, "v0.2.25")
    clock.now += timedelta(minutes=5)
    t0 = clock.now

    store.as_actor("alice").set_field(item, ItemField.RELEASE, "0.2.25")

    assert [
        (change.kind, change.number, change.actor, change.release)
        for change in store.changes_since(t0)
    ] == [(ChangeKind.JOINED_RELEASE, item.number, "alice", "v0.2.25")]


def test_moving_an_item_between_releases_leaves_one_and_joins_the_other(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("moved", release="v0.2.24", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.RELEASE, "v0.2.25")
    moved = store.item(item.number)
    assert (
        [(change.kind, change.release) for change in store.changes_since(datetime.min)],
        (moved.release, moved.job_record) if moved else None,
    ) == (
        [(ChangeKind.LEFT_RELEASE, "v0.2.24"), (ChangeKind.JOINED_RELEASE, "v0.2.25")],
        ("v0.2.25", {ItemField.RELEASE: "v0.2.25"}),
    )


def test_clearing_a_release_records_that_the_store_cleared_it(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("unplanned", release="v0.2.25", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.RELEASE, None)
    cleared = store.item(item.number)
    assert ([i.number for i in store.backlog()], cleared.job_record if cleared else None) == (
        [item.number],
        {ItemField.RELEASE: None},
    )


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


# ── Board shape, cards, issues and files (#739) ───────────────────────────────

STATUS = FieldSpec(
    name="Status",
    single_select=True,
    options=(
        FieldOption(name="Todo", color="GRAY", description="Fresh"),
        FieldOption(name="Backlog", color="GRAY", description="Queued"),
        FieldOption(name="Ready", color="BLUE", description="Scoped"),
    ),
)


@pytest.fixture
def board(clock: SteppedClock) -> InMemoryRoadmapStore:
    """A board whose Status has Todo, Backlog and Ready, with one card on each."""
    roadmap = InMemoryRoadmapStore(clock=clock)
    roadmap.seed_field(STATUS)
    person = roadmap.as_actor("alice")
    for status in ("Todo", "Backlog", "Ready"):
        number = roadmap.seed_issue(f"holds {status}", on_board=True)
        card = next(card for card in roadmap.cards() if card.number == number)
        person.set_card_field(card, ItemField.STATUS, status)
    return roadmap


def _status(store: InMemoryRoadmapStore) -> BoardField:
    return next(board_field for board_field in store.board_fields() if board_field.name == "Status")


def test_board_fields_carry_each_options_id_color_and_description(
    board: InMemoryRoadmapStore,
) -> None:
    status = _status(board)
    assert (
        status.single_select,
        [(bool(o.id), o.name, o.color, o.description) for o in status.options],
        len({o.id for o in status.options}),
    ) == (
        True,
        [
            (True, "Todo", "GRAY", "Fresh"),
            (True, "Backlog", "GRAY", "Queued"),
            (True, "Ready", "BLUE", "Scoped"),
        ],
        3,
    )


def test_an_option_renamed_by_hand_keeps_its_id_and_its_cards_value(
    board: InMemoryRoadmapStore,
) -> None:
    """The in-memory model of the board's field settings, the only place an option keeps its id.

    No store operation edits options: GitHub's option input takes no id (#739).
    """
    todo, backlog, ready = _status(board).options
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
        [card.status for card in board.cards()],
    ) == ([(backlog.id, "New"), (ready.id, "Ready")], True, [None, "New", "Ready"])


def test_deleting_a_field_removes_it_and_an_unknown_field_raises(
    board: InMemoryRoadmapStore,
) -> None:
    board.seed_field(
        FieldSpec(name="Category", single_select=True, options=(FieldOption(name="Quick Win"),))
    )
    board.delete_field("Category")
    with pytest.raises(GitHubOperationError, match="no 'Category' field"):
        board.delete_field("Category")
    assert [f.name for f in board.board_fields()] == ["Job record", "Status"]


def test_cards_include_pull_requests_and_a_card_write_is_recorded(
    board: InMemoryRoadmapStore,
) -> None:
    number = board.seed_issue("a pull request", pull_request=True, on_board=True)
    card = next(card for card in board.cards() if card.number == number)
    board.set_card_field(card, ItemField.STATUS, "Ready")
    written = next(card for card in board.cards() if card.number == number)
    assert (written.kind, written.status, written.job_record, board.item(number)) == (
        CardKind.PULL_REQUEST,
        "Ready",
        {ItemField.STATUS: "Ready"},
        None,
    )


def test_a_card_write_refuses_the_release_a_foreign_option_and_a_card_off_the_board(
    board: InMemoryRoadmapStore,
) -> None:
    card = board.cards()[0]
    gone = card.model_copy(update={"id": "card-99"})
    with pytest.raises(GitHubOperationError, match="not a board field"):
        board.set_card_field(card, ItemField.RELEASE, "v0.2.25")
    with pytest.raises(GitHubOperationError, match="not a Status option"):
        board.set_card_field(card, ItemField.STATUS, "Icebox")
    with pytest.raises(GitHubOperationError, match="not on the board"):
        board.set_card_field(gone, ItemField.STATUS, "Ready")


def test_removing_a_card_takes_it_off_the_board(board: InMemoryRoadmapStore) -> None:
    card = board.cards()[0]
    board.remove_card(card)
    with pytest.raises(GitHubOperationError, match="not on the board"):
        board.remove_card(card)
    assert ([c.number for c in board.candidates()], board.item(card.number or 0)) == ([1], None)


def test_an_issue_is_opened_then_closed_as_not_planned_with_a_comment(
    store: InMemoryRoadmapStore,
) -> None:
    opened = store.create_issue("Bare-Metal OS Installers", "Rejected.", labels=["type/feature"])
    store.close_issue(opened.number, CloseReason.NOT_PLANNED, "Not planned (ADR 0001).")
    closed = next(issue for issue in store.issues() if issue.number == opened.number)
    assert (
        (closed.title, closed.body, closed.labels, closed.state, closed.state_reason),
        store.comments_on(opened.number),
        [(c.kind, c.number) for c in store.changes_since(datetime.min)],
    ) == (
        (
            "Bare-Metal OS Installers",
            "Rejected.",
            ("type/feature",),
            GitHubState.CLOSED,
            "not_planned",
        ),
        ["Not planned (ADR 0001)."],
        [(ChangeKind.CLOSED, opened.number)],
    )


def test_closing_a_pull_request_raises(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("a pull request", pull_request=True)
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.close_issue(number, CloseReason.NOT_PLANNED, "no")


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


def test_deleting_a_release_leaves_its_issues_in_no_release(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("planned", release="v0.2.25", on_board=True)
    store.delete_release("0.2.25")
    with pytest.raises(GitHubOperationError, match="No Release"):
        store.delete_release("v0.2.25")
    assert ([r.title for r in store.releases()], [i.number for i in store.backlog()]) == (
        ["v0.2.24"],
        [number],
    )


def test_a_repository_file_is_read_at_its_ref_and_a_missing_one_raises(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_file(".github/roadmap.toml", "board = 2\n", ref="release/v0.2.25")
    store.seed_file(".github/roadmap.toml", "board = 1\n")
    read = (
        store.repository_file(".github/roadmap.toml", ref="release/v0.2.25"),
        store.repository_file(".github/roadmap.toml"),
    )
    with pytest.raises(GitHubOperationError, match=r"no docs/ROADMAP\.md"):
        store.repository_file("docs/ROADMAP.md")
    assert read == ("board = 2\n", "board = 1\n")


def test_a_board_number_that_names_no_board_reads_none_until_one_is_created() -> None:
    store = InMemoryRoadmapStore(board_exists=False)
    missing = store.board()
    with pytest.raises(GitHubOperationError, match="names no board"):
        store.items()
    created = store.create_board("Roadmap", [STATUS])
    assert (missing, created == store.board(), [f.name for f in store.board_fields()]) == (
        None,
        True,
        ["Job record", "Status"],
    )


def test_workflows_lists_the_boards_built_in_workflows(store: InMemoryRoadmapStore) -> None:
    store.seed_workflow("Item closed", enabled=True)
    store.seed_workflow("Auto-add sub-issues to project", enabled=False)
    assert [(w.name, w.enabled) for w in store.workflows()] == [
        ("Item closed", True),
        ("Auto-add sub-issues to project", False),
    ]
