"""No roadmap row takes an issue that a bot of `roadmap.skip_authors` opened (#6038).

Renovate opens its Dependency Dashboard as `dan-petty-renovate[bot]`, the bot of its App, and
writes the body again each run: the issue is a tracking issue of a tool, no work item. Each case
seeds the dashboard and the same issue of a person, both in the state that one row takes, and reads
the numbers that the selection of the row names, taken or left out with a reason. The roadmap is
the in-memory store, and no model runs. The watch row reads the same listings of Items
(`store.items`, `store.item`), which the store contract holds, and the plan_drift row reads only
pull requests.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.github.metrics import get_item_age_metrics
from devops_cli.roadmap.alternatives import select_items
from devops_cli.roadmap.implement.implement import parse_implement_filters
from devops_cli.roadmap.intake.intake import plan_intake
from devops_cli.roadmap.open_row import open_candidates
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.refine.refine import select_candidates
from devops_cli.roadmap.retitle import retitle_items
from devops_cli.roadmap.stage.stage import named_items, parse_filters, select_stageable
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ItemField,
    encode_job_record,
    with_record,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_intake import REPO, FakeModel, Roadmap

RENOVATE = "dan-petty-renovate[bot]"
NOW = datetime(2026, 11, 16, 20, 19, tzinfo=UTC)
BRANCH = "fix/6038-dashboard"
LONG_TITLE = "chore(deps): the dependency dashboard lists every update that waits for an approval"


def _intake(store: InMemoryRoadmapStore) -> set[int]:
    plan = plan_intake(store, repo=REPO, model=FakeModel())
    return {decision.subject.number for decision in plan.decisions if decision.subject.number}


def _retitle(store: InMemoryRoadmapStore) -> set[int]:
    return {item.number for item in retitle_items(store)}


def _refine(store: InMemoryRoadmapStore) -> set[int]:
    selected, waiting = select_candidates(store)
    return {item.number for item in selected} | {wait.item.number for wait in waiting}


def _alternatives(store: InMemoryRoadmapStore) -> set[int]:
    selection = select_items(
        store, item_number=None, limit=5, recheck_days=30, retry_days=1, now=NOW
    )
    return {item.number for item in (*selection.selected, *selection.current)}


def _stage(store: InMemoryRoadmapStore) -> set[int]:
    selection = select_stageable(
        store,
        filters=parse_filters(("status=ready",)),
        holder_of=lambda _issue, _branch: None,
        planned=PlannedChanges("main", {}, {}),
        limit=5,
        planned_limit=5,
    )
    taken = {target.item.number for target in selection.selected}
    return taken | {left.number for left in selection.left_out}


def _implement(store: InMemoryRoadmapStore) -> set[int]:
    return {item.number for item in named_items(store, parse_implement_filters(()))}


def _open(store: InMemoryRoadmapStore) -> set[int]:
    heads = f"{1:040x}\trefs/heads/{BRANCH}"
    return {candidate.item.number for candidate in open_candidates(store, heads)}


def _metrics(store: InMemoryRoadmapStore) -> set[int]:
    ages, _, _ = get_item_age_metrics(store, REPO, lambda: NOW, running_units=(), stall_hours=24)
    return {age.number for age in ages if age.number}


@dataclass(frozen=True)
class Row:
    """The state of an issue that one row takes, and the numbers that its selection names."""

    names: Callable[[InMemoryRoadmapStore], set[int]]
    fields: Mapping[ItemField, str] = field(default_factory=dict)
    marks: Mapping[ImplementRecordKey, str] = field(default_factory=dict)
    title: str = "Dependency Dashboard"


_PLACED = {ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"}
_PLANNED = {ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "Planned", ItemField.EFFORT: "Low"}

ROWS = [
    pytest.param(Row(_intake), id="intake"),
    pytest.param(Row(_retitle, _PLACED, title=LONG_TITLE), id="retitle"),
    pytest.param(Row(_refine, _PLACED), id="refine"),
    pytest.param(Row(_alternatives, _PLACED), id="alternatives"),
    pytest.param(Row(_stage, {**_PLACED, ItemField.STATUS: "Ready"}), id="stage"),
    pytest.param(Row(_implement, _PLANNED), id="implement"),
    pytest.param(Row(_open, _PLANNED, {ImplementRecordKey.BRANCH: BRANCH}), id="open"),
    pytest.param(Row(_metrics, _PLACED), id="metrics"),
]


def _seed(store: InMemoryRoadmapStore, row: Row, login: str | None) -> int:
    """The issue of `row` that `login` opened, or that the owner opened when `login` is None."""
    block = encode_job_record({}, row.marks) if row.marks else None
    return store.seed_issue(
        row.title,
        body=with_record("The body.", block),
        labels=("type/chore", "scope/deps"),
        fields=row.fields,
        author_association="OWNER" if login is None else "NONE",
        author_login=login,
    )


@pytest.mark.parametrize("row", ROWS)
def test_no_row_takes_the_dependency_dashboard_of_renovate(row: Row) -> None:
    store = Roadmap().store
    _seed(store, row, RENOVATE)
    person = _seed(store, row, None)

    assert row.names(store) == {person}


def test_the_setting_names_the_bots_whose_issues_no_row_takes(
    config: Callable[..., Path],
) -> None:
    """A login matches only when it is equal, so the setting replaces the default, and an empty
    list skips no author."""
    store = InMemoryRoadmapStore(repo=REPO)
    placed = {ItemField.PRIORITY: "P2-Medium"}
    renovate = store.seed_issue("Dependency Dashboard", fields=placed, author_login=RENOVATE)
    store.seed_issue("Dependency Dashboard", fields=placed, author_login="another-tool[bot]")
    lookalike = store.seed_issue(
        "Dependency Dashboard", fields=placed, author_login="another-tool[bot]x"
    )

    config(roadmap={"skip_authors": ["another-tool[bot]"]})
    named = [item.number for item in store.items()]
    config(roadmap={"skip_authors": []})
    every = [item.number for item in store.items()]

    assert (named, every) == ([renovate, lookalike], [1, 2, 3])
