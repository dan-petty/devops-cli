"""The table of lanes of the Service (#5553): one lane for each row of the due table by default,
named after the row, and the setting `service.lanes` that puts rows into a shared lane."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    JobRow,
    lane_of_row,
    lanes_to_wake,
    service_jobs,
    service_lanes,
)

ROW_NAMES = [row.name for row in DEFAULT_DUE_TABLE]


def _names(lanes: Mapping[str, Sequence[JobRow]]) -> dict[str, list[str]]:
    return {lane: [row.name for row in rows] for lane, rows in lanes.items()}


def test_the_default_gives_each_row_of_the_due_table_a_lane_of_its_own() -> None:
    """With no setting, each row is a lane, named after the row, in the order of the table."""
    assert _names(service_lanes()) == {name: [name] for name in ROW_NAMES}


def test_a_group_puts_its_rows_into_one_lane_in_the_order_of_the_table() -> None:
    """A lane that names `refine` and `stage` runs `stage` first, as the table does (#4796). The
    lane takes the place of its first row, and each other row keeps a lane of its own."""
    lanes = _names(service_lanes({"model": ["refine", "stage"]}))

    expected_order = [name for name in ROW_NAMES if name != "refine"]
    assert (list(lanes), lanes["model"], lanes["intake"]) == (
        [("model" if name == "stage" else name) for name in expected_order],
        ["stage", "refine"],
        ["intake"],
    )


def test_a_lane_may_have_the_name_of_its_own_row() -> None:
    """A lane named `stage` that holds `stage` and `fix_plan` is the lane of both rows."""
    lanes = _names(service_lanes({"stage": ["stage", "fix_plan"]}))

    assert (lanes["stage"], "fix_plan" in lanes) == (["stage", "fix_plan"], False)


@pytest.mark.parametrize(
    ("groups", "named"),
    [
        ({"model": ["plan"]}, "plan"),
        ({"stage": ["refine"]}, "stage"),
    ],
    ids=["unknown-row", "lane-name-of-another-row"],
)
def test_a_group_with_an_unknown_row_or_the_name_of_another_row_is_refused(
    groups: dict[str, list[str]], named: str
) -> None:
    """An unknown row, and a lane name that is the name of a row in another lane, raise an error
    that names the setting and the name."""
    with pytest.raises(ConfigurationError) as raised:
        service_lanes(groups)

    assert (named in str(raised.value), "service.lanes" in str(raised.value)) == (True, True)


def test_the_lane_of_a_row_follows_the_groups() -> None:
    """A row that no group names is in its own lane; a grouped row is in the lane of its group."""
    groups = {"model": ["stage", "refine"]}

    assert (
        lane_of_row("intake"),
        lane_of_row("refine", groups),
        lane_of_row("intake", groups),
    ) == (
        "intake",
        "model",
        "intake",
    )


def test_the_wake_after_a_scoped_intake_skips_its_lane_only_when_intake_is_alone_there() -> None:
    """With the default lanes, the wake reaches each lane but `intake`. When `service.lanes` puts
    `refine` into the lane of `intake`, the wake reaches that lane too (#4412, #5553)."""
    groups = {"model": ["intake", "refine"]}

    assert (
        lanes_to_wake("intake", ROW_NAMES),
        lanes_to_wake("intake", ["metrics", "model"], groups),
    ) == (
        tuple(name for name in ROW_NAMES if name != "intake"),
        ("metrics", "model"),
    )


def test_service_jobs_builds_one_job_for_each_lane_of_the_setting(
    tmp_path: Path, config: Callable[..., Path]
) -> None:
    """`service_jobs` reads `service.lanes`: with no value each row has a job, and with a group the
    group has one job for its rows."""
    default = list(service_jobs(tmp_path))
    config(service={"lanes": {"model": ["stage", "refine"]}})
    grouped = service_jobs(tmp_path)

    assert (default, "model" in grouped, "stage" in grouped, len(grouped)) == (
        ROW_NAMES,
        True,
        False,
        len(ROW_NAMES) - 1,
    )
