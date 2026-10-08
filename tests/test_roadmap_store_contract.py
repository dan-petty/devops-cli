"""Contract suite for the roadmap store, run against the in-memory adapter.

Each case pins one promise `RoadmapStore` makes. The GitHub adapter keeps the same promises in
`tests/test_roadmap_github_store.py`, over recorded `gh` output.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapCardChangedError
from devops_cli.exceptions.validation import InvalidVersionError
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore, JobWrite
from devops_cli.roadmap.store import (
    BoardField,
    CardKind,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    EvidenceKind,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueQuery,
    ItemField,
    JobMark,
    PullRequestState,
    RefineRecordKey,
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


def test_a_renamed_release_keeps_its_number_issues_and_pull_requests(
    store: InMemoryRoadmapStore,
) -> None:
    """GitHub keeps a milestone by its number, so a rename moves no issue out of it."""
    item = store.seed_issue("planned", release="v0.2.25", on_board=True)
    pull_request = store.as_actor("alice").open_pull_request(
        "cut", base="main", head="chore/cut-v0.2.25", labels=("release",), release="v0.2.25"
    )
    before = store.release("v0.2.25")
    renamed = store.as_actor("alice").edit_release("v0.2.25", title="v0.3.0")
    found = store.item(item)
    assert (
        renamed.number == (before.number if before else None),
        found.release if found else None,
        [p.number for p in store.release_pull_requests("v0.3.0")],
        store.items(release="v0.2.25"),
    ) == (True, "v0.3.0", [pull_request], [])


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
        [card.id for card in store.cards()] == [added.card_id],
    ) == (number, True, True, "Ready", True)


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


def test_changes_since_leaves_out_the_changes_one_actor_made(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    since = clock.now
    number = store.seed_issue("labeled twice")
    store.as_actor("roadmap-bot").label_issue(number, "type/bug")
    store.as_actor("alice").label_issue(number, "scope/cli")
    changes = store.changes_since(since, except_actor="roadmap-bot")
    assert [(change.actor, change.label) for change in changes] == [("alice", "scope/cli")]


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


# ── A job never reverts a change it did not read (ADR 0002, #1361) ────────────


def test_a_job_write_of_a_field_a_person_changed_since_it_was_read_raises_and_writes_nothing(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("prioritize me", on_board=True))
    assert item is not None
    store.as_actor("alice").set_field(item, ItemField.PRIORITY, "P1-High")
    before = len(store.job_writes())
    with pytest.raises(RoadmapCardChangedError, match="Priority is P1-High") as raised:
        store.set_field(item, ItemField.PRIORITY, "P3-Low")
    kept = store.item(item.number)
    assert (
        store.job_writes()[before:],
        kept.priority if kept else None,
        {key: raised.value.details[key] for key in ("card", "field", "read", "now")},
    ) == (
        [],
        "P1-High",
        {"card": f"#{item.number}", "field": "Priority", "read": None, "now": "P1-High"},
    )


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


def test_a_job_write_of_the_value_the_card_holds_now_goes_ahead(
    store: InMemoryRoadmapStore,
) -> None:
    """Writing what someone else already set reverts nothing, such as the Status the board sets
    on a card just added."""
    item = store.add_item(store.seed_issue("intake me"))
    store.as_actor("alice").set_field(item, ItemField.STATUS, "Backlog")
    store.set_field(item, ItemField.STATUS, "Backlog")
    written = store.item(item.number)
    assert ((written.status, written.job_record) if written else None) == (
        "Backlog",
        {ItemField.STATUS: "Backlog"},
    )


def test_the_jobs_own_write_is_what_its_next_write_of_that_field_compares(
    store: InMemoryRoadmapStore,
) -> None:
    """A revert, then a decision, on one field of an Item read once: both go ahead."""
    item = store.item(store.seed_issue("revert then decide", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.PRIORITY, "P2-Medium")
    store.set_field(item, ItemField.PRIORITY, "P0-Critical")
    written = store.item(item.number)
    assert (written.priority if written else None) == "P0-Critical"


def test_a_job_card_write_of_a_field_a_person_changed_since_it_was_read_raises(
    store: InMemoryRoadmapStore,
) -> None:
    number = store.seed_issue("a card", on_board=True)
    (card,) = [card for card in store.cards() if card.number == number]
    person_view = store.as_actor("alice")
    person_view.set_card_field(card, ItemField.STATUS, "Ready")
    before = len(store.job_writes())
    with pytest.raises(RoadmapCardChangedError, match="Status"):
        store.set_card_field(card, ItemField.STATUS, "Done")
    kept = store.item(number)
    assert (store.job_writes()[before:], kept.status if kept else None) == ([], "Ready")


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
        [(ChangeKind.COMMENTED, opened.number), (ChangeKind.CLOSED, opened.number)],
    )


def test_a_person_reopens_a_closed_issue_in_its_release(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("done", release="v0.2.25", on_board=True)
    store.close_issue(number, CloseReason.COMPLETED, "Delivered.")
    since = store.changes_since(datetime.min)
    store.as_actor("alice").reopen_issue(number)
    found = store.item(number)
    assert (
        (found.state, found.state_reason, found.release) if found else None,
        [(c.kind, c.release) for c in store.changes_since(datetime.min)[len(since) :]],
    ) == ((GitHubState.OPEN, None, "v0.2.25"), [(ChangeKind.REOPENED, "v0.2.25")])


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
    with pytest.raises(GitHubFileNotFoundError, match=r"no docs/ROADMAP\.md"):
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


# ── What the release rules read and write (#740) ──────────────────────────────


def test_marks_are_kept_in_the_job_record_and_change_no_field(store: InMemoryRoadmapStore) -> None:
    item = store.item(store.seed_issue("admitted", release="v0.2.25", on_board=True))
    assert item is not None
    store.set_marks(item, {JobMark.ADMITTED: "v0.2.25", JobMark.PENDING: "{}"})
    store.set_field(item, ItemField.STATUS, "Ready")
    store.set_marks(item, {JobMark.ADMITTED: None, JobMark.PENDING: None})
    written = store.item(item.number)
    assert (
        (written.release, written.status, written.job_record) if written else None,
        [change.kind for change in store.changes_since(datetime.min)],
    ) == (
        (
            "v0.2.25",
            "Ready",
            {JobMark.ADMITTED: None, JobMark.PENDING: None, ItemField.STATUS: "Ready"},
        ),
        [ChangeKind.FIELD_CHANGED],
    )


def test_a_field_write_records_marks_with_its_value_and_a_persons_records_neither(
    store: InMemoryRoadmapStore,
) -> None:
    item = store.item(store.seed_issue("moved", release="v0.2.25", on_board=True))
    assert item is not None
    store.set_marks(item, {JobMark.ADMITTED: "v0.2.25"})
    store.set_field(item, ItemField.RELEASE, None, marks={JobMark.PENDING: "{}"})
    store.as_actor("alice").set_field(
        item, ItemField.STATUS, "Ready", marks={JobMark.PENDING: None}
    )
    written = store.item(item.number)
    assert ((written.release, written.status, written.job_record) if written else None) == (
        None,
        "Ready",
        {JobMark.ADMITTED: "v0.2.25", ItemField.RELEASE: None, JobMark.PENDING: "{}"},
    )


def test_marks_can_record_a_fields_value_or_forget_it_without_setting_the_field(
    store: InMemoryRoadmapStore,
) -> None:
    """A job records the value of a field write it begins before the field is set, as GitHub's
    first call does, and takes that record back, value or none, when the write never landed."""
    item = store.item(store.seed_issue("begun", release="v0.2.25", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")
    store.set_marks(item, {JobMark.PENDING: "{}"}, recorded={ItemField.RELEASE: None})
    begun = store.item(item.number)
    store.set_marks(
        item,
        {JobMark.PENDING: None},
        recorded={ItemField.STATUS: "In Progress"},
        forgotten=(ItemField.RELEASE,),
    )
    taken_back = store.item(item.number)
    assert (
        (begun.release, begun.job_record) if begun else None,
        (taken_back.release, taken_back.status, taken_back.job_record) if taken_back else None,
        [change.kind for change in store.changes_since(datetime.min)],
    ) == (
        ("v0.2.25", {ItemField.STATUS: "Ready", ItemField.RELEASE: None, JobMark.PENDING: "{}"}),
        ("v0.2.25", "Ready", {ItemField.STATUS: "In Progress", JobMark.PENDING: None}),
        [ChangeKind.FIELD_CHANGED],
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
        store.set_marks(gone, {JobMark.NUDGED: "2026-10-02T12:00:00+00:00"})
    with pytest.raises(GitHubOperationError, match="Job record"):
        unrecorded.set_marks(unrecorded_item, {JobMark.ADMITTED: "v0.2.25"})
    assert (store.job_writes(), unrecorded.item(unrecorded_item.number)) == (
        writes,
        unrecorded_item,
    )


def test_the_run_record_is_one_draft_cards_job_record_that_only_a_job_writes(
    store: InMemoryRoadmapStore,
) -> None:
    before = (store.run_record(), [card.kind for card in store.cards()])
    store.as_actor("alice").set_run_record({JobMark.STARTED: "v0.2.24"})
    by_a_person = store.run_record()
    store.set_run_record({JobMark.STARTED: "v0.2.24"})
    store.set_run_record({JobMark.STARTED: "v0.2.25"})
    unrecorded = InMemoryRoadmapStore(board_options=BOARD_OPTIONS, job_record_field=False)
    with pytest.raises(GitHubOperationError, match="Job record"):
        unrecorded.set_run_record({JobMark.STARTED: "v0.2.25"})
    assert (
        before,
        by_a_person,
        store.run_record(),
        [(card.kind, card.job_record) for card in store.cards()],
        unrecorded.run_record(),
    ) == (
        ({}, []),
        {},
        {JobMark.STARTED: "v0.2.25"},
        [(CardKind.DRAFT_ISSUE, {JobMark.STARTED: "v0.2.25"})],
        {},
    )


def test_release_changes_are_one_issues_joins_and_leaves_oldest_first(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    person = store.as_actor("alice")
    moved = store.item(store.seed_issue("moved", on_board=True))
    other = store.item(store.seed_issue("other", on_board=True))
    assert moved is not None and other is not None
    person.set_field(moved, ItemField.RELEASE, "v0.2.25")
    person.set_field(other, ItemField.RELEASE, "v0.2.25")
    clock.now += timedelta(hours=1)
    person.set_field(moved, ItemField.STATUS, "Ready")
    person.set_field(moved, ItemField.RELEASE, None)
    assert [
        (c.kind, c.number, c.release, c.actor) for c in store.release_changes(moved.number)
    ] == [
        (ChangeKind.JOINED_RELEASE, moved.number, "v0.2.25", "alice"),
        (ChangeKind.LEFT_RELEASE, moved.number, "v0.2.25", "alice"),
    ]


def test_dependencies_are_the_blocked_by_links_as_their_issues_are_now(
    store: InMemoryRoadmapStore,
) -> None:
    waiting = store.seed_issue("waits", release="v0.2.25", on_board=True)
    planned = store.seed_issue("planned", release="v0.2.25")
    shipped = store.seed_issue("shipped", state=GitHubState.CLOSED, release="v0.2.24")
    person = store.as_actor("alice")
    person.link_dependency(waiting, planned)
    person.link_dependency(waiting, shipped)
    assert (
        [(d.number, d.repository, d.state, d.release) for d in store.dependencies(waiting)],
        store.dependencies(planned),
        [(c.kind, c.number, c.release) for c in store.changes_since(datetime.min)],
    ) == (
        [
            (planned, "example/roadmap", GitHubState.OPEN, "v0.2.25"),
            (shipped, "example/roadmap", GitHubState.CLOSED, "v0.2.24"),
        ],
        [],
        [(ChangeKind.BLOCKED_BY_ADDED, waiting, "v0.2.25")] * 2,
    )


def test_status_changed_at_is_when_anyone_last_changed_the_status(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    item = store.item(store.seed_issue("in progress", on_board=True))
    assert item is not None
    never = store.status_changed_at(item.number)
    store.as_actor("alice").set_field(item, ItemField.STATUS, "In Progress")
    by_alice = clock.now
    clock.now += timedelta(hours=1)
    store.set_field(item, ItemField.PRIORITY, "P1-High")
    assert (never, store.status_changed_at(item.number)) == (None, by_alice)


def test_pull_requests_open_and_the_releases_own_whatever_their_state(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    person = store.as_actor("alice")
    release = {"base": "main", "labels": ("release",), "release": "v0.2.25"}
    closed = person.open_pull_request("first cut", head="chore/cut-v0.2.25", **release)
    person.close_pull_request(closed)
    cut = person.open_pull_request("cut", head="chore/cut-v0.2.25", draft=True, **release)
    topic = person.open_pull_request(
        "feat", base="release/v0.2.25", head="feat/x", body="Closes #1"
    )
    clock.now += timedelta(hours=1)
    person.push_to_pull_request(topic)
    with pytest.raises(GitHubOperationError, match="No Release"):
        store.release_pull_requests("9.9.9")
    assert (
        [(p.number, p.draft, p.updated_at, p.last_commit_at) for p in store.open_pull_requests()],
        [(p.number, p.state) for p in store.release_pull_requests("0.2.25")],
        [(c.kind, c.number) for c in store.changes_since(datetime.min)],
    ) == (
        [
            (cut, True, clock.now - timedelta(hours=1), clock.now - timedelta(hours=1)),
            (topic, False, clock.now, clock.now),
        ],
        [(closed, PullRequestState.CLOSED), (cut, PullRequestState.OPEN)],
        [
            (ChangeKind.RELEASE_CUT, closed),
            (ChangeKind.RELEASE_UNCUT, closed),
            (ChangeKind.RELEASE_CUT, cut),
        ],
    )


def test_a_release_is_published_once_its_github_release_is(store: InMemoryRoadmapStore) -> None:
    before = store.release_published("0.2.25")
    store.as_actor("alice").publish_release("0.2.25")
    assert (
        before,
        store.release_published("0.2.25"),
        store.release_published("v0.2.25"),
        store.release_published("v0.2.24"),
        [(c.kind, c.release) for c in store.changes_since(datetime.min)],
    ) == (False, True, True, False, [(ChangeKind.RELEASE_SHIPPED, "v0.2.25")])


def test_a_branch_is_read_by_its_name_and_created_only_once(store: InMemoryRoadmapStore) -> None:
    head = store.default_branch()
    missing = store.branch("release/v0.2.26")
    store.create_branch("release/v0.2.26", head.sha)
    with pytest.raises(GitHubOperationError, match="already exists"):
        store.create_branch("release/v0.2.26", "f" * 40)
    assert (head.name, missing, store.branch("release/v0.2.26")) == ("main", None, head.sha)


def test_a_comment_is_kept_on_its_issue(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("commented", release="v0.2.25", on_board=True)
    store.comment(number, "Moved to the backlog.")
    with pytest.raises(GitHubOperationError, match="not an issue"):
        store.comment(store.seed_issue("a pull request", pull_request=True), "no")
    assert (
        store.comments_on(number),
        [(c.kind, c.number, c.release) for c in store.changes_since(datetime.min)],
    ) == (["Moved to the backlog."], [(ChangeKind.COMMENTED, number, "v0.2.25")])


def test_a_change_reads_the_value_and_job_record_as_they_are_now(
    store: InMemoryRoadmapStore,
) -> None:
    """A job placed the item, then a person moved it to the backlog: the job's change now reads
    as no longer matching the record, which is what tells it from the job's own."""
    item = store.item(store.seed_issue("placed", on_board=True))
    assert item is not None
    store.set_field(item, ItemField.RELEASE, "v0.2.25")
    store.as_actor("alice").set_field(item, ItemField.RELEASE, None)
    assert [
        (c.kind, c.release, c.field, c.value, c.job_record)
        for c in store.changes_since(datetime.min)
    ] == [
        (
            ChangeKind.JOINED_RELEASE,
            "v0.2.25",
            ItemField.RELEASE,
            None,
            {ItemField.RELEASE: "v0.2.25"},
        ),
        (
            ChangeKind.LEFT_RELEASE,
            "v0.2.25",
            ItemField.RELEASE,
            None,
            {ItemField.RELEASE: "v0.2.25"},
        ),
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
        store.comments_on(copy),
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


def test_counting_issues_narrows_by_each_condition_given(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    start = clock.now
    store.seed_issue("before the window", labels=("source/agent",))
    clock.now += timedelta(hours=1)
    agent = store.seed_issue("agent", labels=("source/agent", "budget/borrowed"))
    done = store.seed_issue("done")
    store.close_issue(done, CloseReason.COMPLETED, "Delivered.")
    bulk = store.seed_issue("bulk")
    store.as_actor("alice").close_by_hand(bulk, CloseReason.NOT_PLANNED)
    store.seed_issue("a pull request", pull_request=True)
    since = start + timedelta(minutes=1)
    queries = [
        IssueQuery(),
        IssueQuery(state=GitHubState.OPEN),
        IssueQuery(labels=("source/agent",), created_since=since),
        IssueQuery(labels=("source/agent", "budget/borrowed")),
        IssueQuery(state=GitHubState.CLOSED, closed_since=since),
        IssueQuery(closed_since=since, reason=CloseReason.NOT_PLANNED, uncommented=True),
        IssueQuery(closed_since=clock.now + timedelta(seconds=1)),
    ]
    assert ([store.count_issues(query) for query in queries], agent) == ([4, 2, 1, 1, 2, 1, 0], 2)


def test_a_release_records_when_it_closed_and_forgets_it_when_reopened(
    store: InMemoryRoadmapStore, clock: SteppedClock
) -> None:
    store.close_release("v0.2.25")
    closed = store.release("v0.2.25")
    store.edit_release("v0.2.25", state=GitHubState.OPEN)
    reopened = store.release("v0.2.25")
    assert (
        closed.closed_at if closed else None,
        reopened.closed_at if reopened else "missing",
        (store.release("v0.2.24") or closed).closed_at,
    ) == (clock.now, None, clock.now)


def test_merged_pull_requests_are_the_ones_merged_into_the_branch_with_their_paths(
    store: InMemoryRoadmapStore,
) -> None:
    """The merged-PR read (#743): only pull requests merged into the branch, oldest first,
    each with its body, merge and head commits and changed paths."""
    person = store.as_actor("alice")
    branch = "release/v0.2.25"
    first = person.merge_pull_request(
        "feat: a", base=branch, body="Closes #1", changed_paths=("a.py", "b.md"), release="v0.2.25"
    )
    person.merge_pull_request("feat: elsewhere", base="main")
    person.open_pull_request("feat: open", base=branch, head="feat/open")
    person.close_pull_request(person.open_pull_request("feat: shut", base=branch, head="feat/x"))
    second = person.merge_pull_request("feat: b", base=branch)
    found = store.merged_pull_requests(branch)
    assert (
        [p.number for p in found],
        (found[0].body, found[0].changed_paths, found[0].release, found[1].changed_paths),
        [len({p.merge_commit, p.head_commit}) for p in found],
    ) == ([first, second], ("Closes #1", ("a.py", "b.md"), "v0.2.25", ()), [2, 2])


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
