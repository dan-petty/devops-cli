"""The one tracker test of an Item, which the refine and the stage jobs share (#3703)."""

from __future__ import annotations

import pytest

from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_STAGE_FILTER,
    DEFAULT_ROADMAP_STAGE_PLANNED_LIMIT,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage.stage import parse_filters, select_stageable
from devops_cli.roadmap.stores.store import Item, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

BUG = ("type/bug",)
NO_PLANS = PlannedChanges("main", {}, {})


def _no_holder(_issue: int, _branch: str) -> str | None:
    return None


def _item(*, labels: tuple[str, ...] = BUG, sub_issues: int = 0) -> Item:
    return Item(
        number=1,
        title="feat(roadmap): the tracker",
        url="https://example.com/issues/1",
        labels=labels,
        sub_issues=sub_issues,
    )


@pytest.mark.parametrize(
    ("labels", "sub_issues", "tracker"),
    [(("type/epic",), 0, True), (BUG, 2, True), (("type/epic",), 3, True), (BUG, 0, False)],
    ids=["epic-label", "sub-issues", "epic-with-sub-issues", "plain"],
)
def test_is_tracker_is_true_for_sub_issues_and_for_the_epic_label(
    labels: tuple[str, ...], sub_issues: int, tracker: bool
) -> None:
    assert _item(labels=labels, sub_issues=sub_issues).is_tracker is tracker


def _seed(store: InMemoryRoadmapStore, title: str, *, sub_issues: int = 0) -> int:
    return store.seed_issue(
        title,
        labels=BUG,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
        author_association="OWNER",
        sub_issues=sub_issues,
    )


def test_the_stage_job_leaves_a_tracker_out_with_the_shared_test() -> None:
    """`_tracker` reads `Item.is_tracker`: a tracker gets the stage text and a plain item none."""
    store = InMemoryRoadmapStore()
    tracker = _seed(store, "feat(roadmap): the tracker", sub_issues=2)
    plain = _seed(store, "fix(roadmap): a plain bug")

    selection = select_stageable(
        store,
        filters=parse_filters(DEFAULT_ROADMAP_STAGE_FILTER),
        holder_of=_no_holder,
        planned=NO_PLANS,
        limit=3,
        planned_limit=DEFAULT_ROADMAP_STAGE_PLANNED_LIMIT,
    )

    assert [target.item.number for target in selection.selected] == [plain]
    assert {left.number: left.reason for left in selection.left_out}[tracker] == (
        MESSAGES.roadmap.stage_left_tracker
    )
