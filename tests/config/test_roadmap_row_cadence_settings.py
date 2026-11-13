"""The cadence settings of the rows intake, stage, fix_plan, refine and alternatives: the interval of
each row, and the backlog rule that makes a row with a large queue due sooner (#5470)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config import settings
from devops_cli.config.settings import RoadmapConfig, RowCadenceConfig

SECTIONS = ("intake", "stage", "fix_plan", "refine", "alternatives")


def _cadence(name: str) -> RowCadenceConfig:
    """The cadence section `roadmap.<name>` of the loaded settings."""
    section = getattr(settings.load_settings().roadmap, name)
    assert isinstance(section, RowCadenceConfig)
    return section


def test_the_defaults_are_the_old_intervals_and_no_backlog_rule() -> None:
    """Each row keeps the interval of its old constant, and no backlog rule applies until a person
    sets one."""
    found = {
        name: (
            _cadence(name).interval_minutes,
            _cadence(name).backlog_interval_minutes,
            _cadence(name).backlog_threshold,
        )
        for name in SECTIONS
    }

    assert found == {
        "intake": (29, None, None),
        "stage": (37, None, None),
        "fix_plan": (53, None, None),
        "refine": (17, None, None),
        "alternatives": (719, None, None),
    }


@pytest.mark.parametrize("name", SECTIONS)
def test_a_variable_sets_each_field_of_each_row(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A variable named by the dotted key sets each of the three fields, so the ConfigMap or the
    environment of the Service changes a loop with no release."""
    prefix = f"DEVOPS_CLI_ROADMAP_{name.upper()}_"
    monkeypatch.setenv(f"{prefix}INTERVAL_MINUTES", "31")
    monkeypatch.setenv(f"{prefix}BACKLOG_INTERVAL_MINUTES", "11")
    monkeypatch.setenv(f"{prefix}BACKLOG_THRESHOLD", "40")

    found = _cadence(name)

    assert (found.interval_minutes, found.backlog_interval_minutes, found.backlog_threshold) == (
        31,
        11,
        40,
    )


def test_a_backlog_interval_above_the_interval_is_refused() -> None:
    """A longer loop for a larger queue is the opposite of the rule, so the section refuses it, also
    when a later assignment makes the interval shorter than the backlog interval."""
    roadmap = RoadmapConfig()

    with pytest.raises(ValidationError, match="backlog_interval_minutes"):
        roadmap.stage.backlog_interval_minutes = 40
    roadmap.stage.backlog_interval_minutes = 13
    with pytest.raises(ValidationError, match="backlog_interval_minutes"):
        roadmap.stage.interval_minutes = 12


@pytest.mark.parametrize(
    "field", ["interval_minutes", "backlog_interval_minutes", "backlog_threshold"]
)
def test_a_value_below_one_is_refused(field: str) -> None:
    """No loop runs at 0 minutes, and a threshold of 0 would hold for every queue."""
    with pytest.raises(ValidationError, match=field):
        setattr(RoadmapConfig().refine, field, 0)


@pytest.mark.parametrize(
    ("interval", "threshold", "queue", "minutes"),
    [
        (13, 50, 50, 13),
        (13, 50, 177, 13),
        (13, 50, 49, 37),
        (13, 50, None, 37),
        (None, 50, 177, 37),
        (13, None, 177, 37),
    ],
)
def test_the_minutes_follow_the_queue_and_the_threshold(
    interval: int | None, threshold: int | None, queue: int | None, minutes: int
) -> None:
    """A queue at or above the threshold gives the backlog interval. A queue below it, an unknown
    queue and a rule with one empty setting give the interval."""
    stage = RoadmapConfig().stage
    stage.backlog_interval_minutes = interval
    stage.backlog_threshold = threshold

    assert stage.minutes_for(queue) == minutes
