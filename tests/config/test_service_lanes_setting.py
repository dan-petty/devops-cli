"""The setting `service.lanes` (#5553): a map of lane names to the rows that each lane runs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import ServiceConfig


def test_the_default_puts_no_row_into_a_shared_lane() -> None:
    """With no value, no lane groups rows, so each row keeps a lane of its own."""
    assert ServiceConfig().lanes == {}


def test_a_lane_keeps_the_rows_that_it_names() -> None:
    """A lane holds its rows as the setting names them."""
    assert ServiceConfig(lanes={"model": ["stage", "refine"]}).lanes == {
        "model": ["stage", "refine"]
    }


@pytest.mark.parametrize(
    ("lanes", "named"),
    [
        ({"a": ["stage"], "b": ["stage", "refine"]}, "stage"),
        ({"model": []}, "model"),
        ({"Model": ["stage"]}, "Model"),
        ({"model": ["../stage"]}, "../stage"),
    ],
    ids=["row-in-two-lanes", "lane-with-no-row", "upper-case-lane", "path-in-row"],
)
def test_the_setting_refuses_a_row_in_two_lanes_an_empty_lane_and_a_bad_name(
    lanes: dict[str, list[str]], named: str
) -> None:
    """A row in two lanes, a lane with no row, and a name that is not a lowercase name are refused,
    and the error names the value."""
    with pytest.raises(ValidationError) as raised:
        ServiceConfig(lanes=lanes)

    assert named in str(raised.value)
