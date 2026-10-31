"""`devops roadmap stage`: which items the job takes, and why it leaves the others out (#2654)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.exceptions import ValidationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage import (
    LeftOut,
    StageSelection,
    parse_filters,
    select_stageable,
)
from devops_cli.roadmap.store import GitHubState, ItemField, StageRecordKey

REPO = "example/roadmap"
BUG = ("type/bug",)
NO_PLANS = PlannedChanges("main", {}, {})


def _no_holder(_issue: int, _branch: str) -> str | None:
    return None


def _seed(
    store: InMemoryRoadmapStore,
    title: str = "fix(roadmap): the job drops a comment",
    *,
    status: str = "Ready",
    priority: str = "P1-High",
    labels: tuple[str, ...] = BUG,
    body: str = "",
    author: str = "OWNER",
    state: GitHubState = GitHubState.OPEN,
) -> int:
    return store.seed_issue(
        title,
        body=body,
        labels=labels,
        fields={ItemField.STATUS: status, ItemField.PRIORITY: priority},
        author_association=author,
        state=state,
    )


def _select(
    store: InMemoryRoadmapStore,
    *filters: str,
    holder_of: Callable[[int, str], str | None] = _no_holder,
    planned: PlannedChanges = NO_PLANS,
    item: int | None = None,
    limit: int = 3,
) -> StageSelection:
    return select_stageable(
        store,
        filters=parse_filters(filters),
        holder_of=holder_of,
        planned=planned,
        item_number=item,
        limit=limit,
    )


def _numbers(selection: StageSelection) -> list[int]:
    return [target.item.number for target in selection.selected]


def _reasons(selection: StageSelection) -> dict[int, str]:
    return {left.number: left.reason for left in selection.left_out}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


def test_the_default_filter_names_the_ready_p0_and_p1_bugs(store: InMemoryRoadmapStore) -> None:
    ready_p1 = _seed(store)
    ready_p0 = _seed(store, priority="P0-Critical")
    _seed(store, priority="P2-Medium")
    _seed(store, status="New")
    _seed(store, labels=("type/feature",))

    selection = _select(store)

    assert _numbers(selection) == [ready_p0, ready_p1]
    assert selection.left_out == ()


def test_values_of_one_family_are_alternatives_and_families_all_apply(
    store: InMemoryRoadmapStore,
) -> None:
    p2 = _seed(store, priority="P2-Medium", labels=("type/chore",))
    p3 = _seed(store, priority="P3-Low", labels=("type/chore",))
    _seed(store, priority="P1-High", labels=("type/chore",))
    _seed(store, priority="P2-Medium", status="New", labels=("type/chore",))

    selection = _select(
        store, "priority=p2-medium", "priority=p3-low", "status=ready", "type=chore"
    )

    assert _numbers(selection) == [p2, p3]


def test_a_filter_with_no_status_family_still_takes_only_ready_items(
    store: InMemoryRoadmapStore,
) -> None:
    ready = _seed(store)
    fresh = _seed(store, status="New")
    unset = store.seed_issue(
        "fix(roadmap): the job drops a label",
        labels=BUG,
        fields={ItemField.PRIORITY: "P1-High"},
    )

    selection = _select(store, "type=bug")

    assert _numbers(selection) == [ready]
    reasons = _reasons(selection)
    assert "Status New" in reasons[fresh]
    assert "Status none" in reasons[unset]


def test_a_filter_family_that_is_not_listed_is_refused() -> None:
    with pytest.raises(ValidationError) as refused:
        parse_filters(["color=red"])

    assert "status, priority, type, value, effort" in str(refused.value)


@pytest.mark.parametrize("option", ["status", "=ready", "status="])
def test_a_filter_without_a_family_and_a_value_is_refused(option: str) -> None:
    with pytest.raises(ValidationError):
        parse_filters([option])


@pytest.mark.parametrize(
    ("filters", "labels", "status", "reason"),
    [
        (("status=blocked",), BUG, "Blocked", "Status Blocked"),
        (("status=in-progress",), BUG, "In Progress", "Status In Progress"),
        (("status=in-review",), BUG, "In Review", "Status In Review"),
        (("status=ready",), (*BUG, "needs-split"), "Ready", "needs-split"),
    ],
)
def test_an_item_that_is_started_or_to_split_is_left_out(
    store: InMemoryRoadmapStore,
    filters: tuple[str, ...],
    labels: tuple[str, ...],
    status: str,
    reason: str,
) -> None:
    number = _seed(store, status=status, labels=labels)

    selection = _select(store, *filters, "priority=p1-high")

    assert selection.selected == ()
    assert reason in _reasons(selection)[number]


def test_an_item_of_an_account_without_write_access_is_left_out(
    store: InMemoryRoadmapStore,
) -> None:
    number = _seed(store, author="NONE")

    selection = _select(store)

    assert selection.selected == ()
    assert "NONE" in _reasons(selection)[number]


def test_an_item_that_depends_on_an_open_issue_is_left_out(store: InMemoryRoadmapStore) -> None:
    blocker = _seed(store, status="New", priority="P2-Medium")
    closed = _seed(store, state=GitHubState.CLOSED)
    waiting = _seed(store, body=f"### Dependencies\n#{blocker}, #{closed}\n")
    free = _seed(store, body=f"### Dependencies\n#{closed}\n")

    selection = _select(store)

    assert _numbers(selection) == [free]
    assert f"#{blocker}" in _reasons(selection)[waiting]


def test_a_held_item_is_left_out_with_the_sentence_of_its_holder(
    store: InMemoryRoadmapStore,
) -> None:
    held = _seed(store)
    free = _seed(store)

    selection = _select(
        store,
        holder_of=lambda issue, _branch: (
            f"Issue {issue} is held by the branch origin/fix/{issue}-x." if issue == held else None
        ),
    )

    assert _numbers(selection) == [free]
    assert _reasons(selection) == {held: f"Issue {held} is held by the branch origin/fix/{held}-x."}


def test_the_holder_is_asked_about_the_new_branch_of_the_item(
    store: InMemoryRoadmapStore,
) -> None:
    number = _seed(store)
    asked: list[tuple[int, str]] = []

    def holder(issue: int, branch: str) -> str | None:
        asked.append((issue, branch))
        return None

    _select(store, holder_of=holder)

    assert asked == [(number, f"fix/{number}-the-job-drops-a-comment")]


def test_an_item_with_a_folder_on_the_default_branch_is_left_out_by_its_issue_number_alone(
    store: InMemoryRoadmapStore,
) -> None:
    planned, archived, free = _seed(store), _seed(store), _seed(store)
    plans = PlannedChanges(
        "trunk", {planned: f"{planned}-any-slug"}, {archived: f"2026-10-28-{archived}-old"}
    )

    selection = _select(store, planned=plans)

    assert _numbers(selection) == [free]
    assert _reasons(selection) == {
        planned: f"Its plan is on trunk: the change folder `{planned}-any-slug` is there.",
        archived: (
            f"Its change is archived on trunk: the folder `2026-10-28-{archived}-old` is there."
        ),
    }


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("the job drops a comment", "Conventional Commit type"),
        ("fix(roadmap): ✨", "word for the branch name"),
        ("wip: the job drops a comment", "Conventional Commit type"),
    ],
)
def test_a_title_that_gives_no_branch_name_is_left_out(
    store: InMemoryRoadmapStore, title: str, reason: str
) -> None:
    number = _seed(store, title)

    selection = _select(store)

    assert selection.selected == ()
    assert reason in _reasons(selection)[number]


def test_the_branch_name_comes_from_the_title(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, "fix(roadmap)!: The job drops a comment, again & again, in 9 steps")

    (target,) = _select(store).selected

    assert (target.item.number, target.branch, target.change) == (
        number,
        f"fix/{number}-the-job-drops-a-comment-again",
        f"{number}-the-job-drops-a-comment-again",
    )


def test_an_item_whose_text_looks_like_a_secret_is_left_out(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, body="The key is ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8")

    selection = _select(store)

    assert selection.selected == ()
    assert "secret" in _reasons(selection)[number]


def test_an_item_with_a_recorded_split_waits_for_a_person(store: InMemoryRoadmapStore) -> None:
    number = _seed(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.NEEDS_SPLIT: "1. Group (50000 tokens)",
            StageRecordKey.FILE_CAP: str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS),
        },
    )

    assert _numbers(_select(store)) == []
    assert "1. Group (50000 tokens)" in _reasons(_select(store))[number]
    assert _numbers(_select(store, item=number)) == [number]


def test_a_recorded_split_of_an_earlier_measure_does_not_stop_the_item(
    store: InMemoryRoadmapStore,
) -> None:
    number = _seed(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {StageRecordKey.NEEDS_SPLIT: "1. Group (50000 tokens)"})
    store.set_marks(
        item, {StageRecordKey.FILE_CAP: str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS + 1)}
    )

    assert _numbers(_select(store)) == [number]


def test_the_limit_caps_the_run_by_priority_and_then_by_number(
    store: InMemoryRoadmapStore,
) -> None:
    first = _seed(store)
    second = _seed(store)
    critical = _seed(store, priority="P0-Critical")
    _seed(store)

    assert _numbers(_select(store, limit=3)) == [critical, first, second]
    assert _numbers(_select(store, limit=1)) == [critical]


def test_one_item_by_number_ignores_the_filter(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, priority="P3-Low", labels=("type/feature",))

    selection = _select(store, item=number)

    assert _numbers(selection) == [number]


@pytest.mark.parametrize("status", ["New", "In Progress", "Blocked"])
def test_one_item_by_number_must_be_ready(store: InMemoryRoadmapStore, status: str) -> None:
    number = _seed(store, status=status)

    selection = _select(store, item=number)

    assert selection.selected == ()
    assert f"Status {status}" in _reasons(selection)[number]


def test_one_item_by_number_must_be_open(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, state=GitHubState.CLOSED)

    assert "closed" in _reasons(_select(store, item=number))[number]


def test_one_item_by_number_must_be_an_item(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("fix(roadmap): an issue with no priority")

    selection = _select(store, item=number)

    assert selection.selected == ()
    assert selection.left_out == (LeftOut(number=number, reason=_reasons(selection)[number]),)
    assert "no Priority" in _reasons(selection)[number]
