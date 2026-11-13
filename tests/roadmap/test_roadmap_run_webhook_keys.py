"""The rows that each `issues` webhook key makes due, and the wake of the model lane after a
scoped update (#4412)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    JobOutcome,
    build_stub_table,
    scoped_update_wakes_lanes,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    TWENTY_MINUTES_AGO,
    poll_round,
    recorded,
    stamp_successes,
    webhook_delivery,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

_ROWS = tuple(row.name for row in DEFAULT_DUE_TABLE)


@pytest.mark.parametrize(
    ("action", "due"),
    [
        ("edited", {"refine", "retitle"}),
        ("labeled", {"refine", "stage", "implement"}),
        ("unlabeled", {"refine", "stage", "implement"}),
        ("closed", {"stage", "implement"}),
        ("assigned", set()),
    ],
)
def test_an_issues_key_makes_due_only_the_rows_that_declare_it(
    action: str, due: set[str], roadmap_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """With every row fresh by its interval, a delivery of `issues` with `action` makes due the
    rows that declare its key, and no other row (#4412)."""
    stamp_successes(tmp_path, **{name: NOW for name in _ROWS})
    ran: list[str] = []
    stubs = {name: recorded(ran, name) for name in _ROWS}
    result = poll_round(
        roadmap_store,
        tmp_path,
        table=build_stub_table(stubs),
        batch={("webhook", "issues", action): 1},
    )
    assert (set(result), set(ran)) == (due, due)


@pytest.mark.parametrize(
    ("action", "outcome", "wakes"),
    [
        ("edited", None, True),
        ("edited", JobOutcome(), True),
        ("opened", JobOutcome(placed_critical_or_p0=True), True),
        ("reopened", JobOutcome(placed_critical_or_p0=True), True),
        ("opened", JobOutcome(), False),
        ("opened", None, False),
    ],
)
def test_a_scoped_update_wakes_the_other_lanes_for_an_edit_or_a_critical_placement(
    action: str, outcome: JobOutcome | None, wakes: bool
) -> None:
    """An edit of an Item, and a placement of a critical fix or a P0 item, wake the other lanes;
    another scoped update does not (#4412, #5553)."""
    assert scoped_update_wakes_lanes(webhook_delivery(action, 7), outcome) is wakes


def test_a_critical_placement_stamps_refine_due_and_the_model_lane_round_runs_refine(
    roadmap_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """With `refine_due` stamped after refine's last success, a round that a webhook that no row declares
    starts runs `refine` before its interval (#4412)."""
    stamp_successes(
        tmp_path,
        **{**{name: NOW for name in _ROWS}, "refine": TWENTY_MINUTES_AGO, "refine_due": NOW},
    )
    ran: list[str] = []
    result = poll_round(
        roadmap_store,
        tmp_path,
        table=build_stub_table({name: recorded(ran, name) for name in _ROWS}),
        batch={("webhook", "issues", "assigned"): 1},
    )
    assert (set(result), set(ran)) == ({"refine"}, {"refine"})
