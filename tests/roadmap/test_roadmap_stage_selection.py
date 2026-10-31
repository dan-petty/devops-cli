"""`devops roadmap stage`: which items the job takes, and why it leaves the others out (#2654)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.config.defaults import DEFAULT_ROADMAP_STAGE_FILTER
from devops_cli.exceptions import ValidationError
from devops_cli.lang import MESSAGES
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
    sub_issues: int = 0,
) -> int:
    return store.seed_issue(
        title,
        body=body,
        labels=labels,
        fields={ItemField.STATUS: status, ItemField.PRIORITY: priority},
        author_association=author,
        state=state,
        sub_issues=sub_issues,
    )


def _select(
    store: InMemoryRoadmapStore,
    *filters: str,
    holder_of: Callable[[int, str], str | None] = _no_holder,
    planned: PlannedChanges = NO_PLANS,
    item: int | None = None,
    limit: int = 3,
    probe: int | None = None,
) -> StageSelection:
    return select_stageable(
        store,
        filters=parse_filters(filters),
        holder_of=holder_of,
        planned=planned,
        item_number=item,
        limit=limit,
        probe=probe,
    )


def _numbers(selection: StageSelection) -> list[int]:
    return [target.item.number for target in selection.selected]


def _reasons(selection: StageSelection) -> dict[int, str]:
    return {left.number: left.reason for left in selection.left_out}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


def test_the_default_filter_names_every_ready_item(store: InMemoryRoadmapStore) -> None:
    bug = _seed(store)
    docs = _seed(store, "docs(k8s): fix a path", priority="P2-Medium", labels=("type/docs",))
    chore = _seed(store, "chore(deps): bump a tool", priority="P3-Low", labels=("type/chore",))
    _seed(store, status="New")
    _seed(store, status="In Progress", priority="P0-Critical")

    selection = _select(store, *DEFAULT_ROADMAP_STAGE_FILTER)

    assert _numbers(selection) == [bug, docs, chore]
    assert selection.left_out == ()


def test_a_ready_p0_item_goes_before_a_ready_p3_item_under_the_default_filter(
    store: InMemoryRoadmapStore,
) -> None:
    chore = _seed(store, "chore(deps): bump a tool", priority="P3-Low", labels=("type/chore",))
    feature = _seed(store, "feat(cli): add a flag", priority="P2-Medium", labels=("type/feature",))
    docs = _seed(store, "docs(k8s): fix a path", priority="P0-Critical", labels=("type/docs",))

    selection = _select(store, *DEFAULT_ROADMAP_STAGE_FILTER, limit=2)

    assert _numbers(selection) == [docs, feature]
    assert chore not in _numbers(selection)


def test_a_staged_item_takes_the_type_of_its_title_not_fix(store: InMemoryRoadmapStore) -> None:
    feature = _seed(store, "feat(cli): add a flag", labels=("type/feature",))
    docs = _seed(store, "docs(k8s): fix a path", labels=("type/docs",))
    tests = _seed(store, "test(cli): hold a flag", labels=("type/test",))

    selection = _select(store, *DEFAULT_ROADMAP_STAGE_FILTER)

    assert {target.item.number: target.branch for target in selection.selected} == {
        feature: f"feat/{feature}-add-a-flag",
        docs: f"docs/{docs}-fix-a-path",
        tests: f"test/{tests}-hold-a-flag",
    }


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
    with pytest.raises(ValidationError) as raised:
        parse_filters([option])
    assert raised.value.error_code == "VALIDATION_ERROR"


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


@pytest.mark.parametrize(
    ("labels", "sub_issues"),
    [(("type/epic",), 0), (BUG, 2), (("type/epic",), 3)],
    ids=["epic-label", "sub-issues", "epic-with-sub-issues"],
)
def test_a_tracker_is_left_out_under_the_wide_default_filter(
    store: InMemoryRoadmapStore, labels: tuple[str, ...], sub_issues: int
) -> None:
    tracker = _seed(store, "feat(roadmap): the tracker", labels=labels, sub_issues=sub_issues)
    plain = _seed(store, "fix(roadmap): a plain bug")

    selection = _select(store, *DEFAULT_ROADMAP_STAGE_FILTER)

    assert _numbers(selection) == [plain]
    assert "tracker" in _reasons(selection)[tracker]


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


@pytest.mark.parametrize(
    ("owner", "reason"),
    [("owner/human", "It is claimed by human."), ("owner/agent", "It is claimed by agent.")],
)
def test_an_item_that_an_agent_or_a_person_claimed_is_left_out(
    store: InMemoryRoadmapStore, owner: str, reason: str
) -> None:
    number = _seed(store, labels=(*BUG, owner))

    selection = _select(store)

    assert (selection.selected, _reasons(selection)) == ((), {number: reason})


def test_a_named_item_that_an_agent_claimed_is_left_out(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, labels=(*BUG, "owner/agent"))

    selection = _select(store, item=number)

    assert (selection.selected, _reasons(selection)) == (
        (),
        {number: "It is claimed by agent."},
    )


def test_an_item_that_the_service_holds_is_staged_as_one_with_no_owner(
    store: InMemoryRoadmapStore,
) -> None:
    held = _seed(store, labels=(*BUG, "owner/service"))

    assert _numbers(_select(store)) == [held]


# ── The reason of a filter, the limit and the shared texts (#2911) ────────────


def test_the_filter_names_the_family_the_item_misses_with_both_values(
    store: InMemoryRoadmapStore,
) -> None:
    held = store.item(_seed(store, labels=(*BUG, "effort/medium")))
    assert held is not None

    miss = parse_filters(("type=bug", "effort=low")).mismatch(held)

    assert miss == "The filter takes effort low. The item has effort medium."


def test_the_filter_lists_its_alternatives_and_says_none_for_a_family_the_item_lacks(
    store: InMemoryRoadmapStore,
) -> None:
    held = store.item(_seed(store))
    assert held is not None

    miss = parse_filters(("value=medium", "value=high")).mismatch(held)

    assert miss == "The filter takes value high or medium. The item has value none."


def test_an_item_that_the_filter_names_has_no_mismatch(store: InMemoryRoadmapStore) -> None:
    held = store.item(_seed(store, labels=(*BUG, "effort/low")))
    assert held is not None

    assert parse_filters(("type=bug", "effort=low")).mismatch(held) is None


def test_the_walk_judges_no_item_past_the_limit_unless_it_is_the_probe(
    store: InMemoryRoadmapStore,
) -> None:
    first = _seed(store, priority="P0-Critical")
    skipped = _seed(store, priority="P2-Medium", status="New")
    last = _seed(store, priority="P3-Low")

    plain = _select(store, "type=bug", limit=1)
    probed = _select(store, "type=bug", limit=1, probe=last)

    assert (_numbers(plain), plain.left_out, plain.beyond) == ([first], (), ())
    assert (_numbers(probed), probed.beyond, skipped in _reasons(probed)) == (
        [first],
        (last,),
        False,
    )


def test_the_probe_past_the_limit_that_breaks_a_rule_has_its_reason(
    store: InMemoryRoadmapStore,
) -> None:
    first = _seed(store, priority="P0-Critical")
    late = _seed(store, priority="P3-Low", status="New")

    selection = _select(store, "type=bug", limit=1, probe=late)

    assert (_numbers(selection), selection.beyond, set(_reasons(selection))) == (
        [first],
        (),
        {late},
    )


def test_a_named_issue_that_is_closed_has_the_shared_reason(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, state=GitHubState.CLOSED)

    assert _reasons(_select(store, item=number)) == {number: MESSAGES.roadmap.item_left_closed}


def test_a_named_issue_that_is_no_item_has_the_shared_reason(store: InMemoryRoadmapStore) -> None:
    assert _reasons(_select(store, item=99)) == {99: MESSAGES.roadmap.item_left_not_item}
