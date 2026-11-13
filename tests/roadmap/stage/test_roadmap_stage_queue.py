"""The queue of the stage row: the open items that the stage filter names, counted from the listing
that the selection reads, before the rules of each item and the limit (#5470)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_STAGE_FILTER,
    DEFAULT_ROADMAP_STAGE_PLANNED_LIMIT,
)
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage.stage import parse_filters, plan_stage, select_stageable
from devops_cli.roadmap.stores.store import GitHubState, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import STAGE_REPO, seed_stageable

if TYPE_CHECKING:
    from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")


def _seed_ready(store: InMemoryRoadmapStore, title: str) -> int:
    return store.seed_issue(
        title,
        labels=("type/bug",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )


def test_the_selection_counts_every_open_item_that_the_filter_names() -> None:
    """Four open Ready items, a New item and a closed Ready item: a limit of 1 takes one item, and
    the queue holds the four open Ready items."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    for n in range(4):
        seed_stageable(store, f"fix(roadmap): the job drops comment {n}")
    store.seed_issue(
        "fix(roadmap): a new item",
        labels=("type/bug",),
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    store.seed_issue(
        "fix(roadmap): a closed item",
        labels=("type/bug",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
        state=GitHubState.CLOSED,
    )

    selection = select_stageable(
        store,
        filters=parse_filters(DEFAULT_ROADMAP_STAGE_FILTER),
        holder_of=lambda _issue, _branch: None,
        planned=PlannedChanges("main", {}, {}),
        limit=1,
        planned_limit=DEFAULT_ROADMAP_STAGE_PLANNED_LIMIT,
    )

    assert (len(selection.selected), selection.queue) == (1, 4)


def test_the_plan_of_a_round_carries_the_queue_also_when_it_takes_no_item(
    stage_repo: StageRepo,
) -> None:
    """Two Ready items whose title type the branch types do not list: the round takes neither,
    and its plan still holds a queue of 2, so a round with no work still reports its backlog."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    _seed_ready(store, "nonsense(roadmap): the first item")
    _seed_ready(store, "nonsense(roadmap): the second item")

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(DEFAULT_ROADMAP_STAGE_FILTER),
    )

    assert (plan.ready, plan.queue) == ((), 2)
