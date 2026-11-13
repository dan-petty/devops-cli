"""The settings `roadmap.implement.deadline_stall_seconds`, `deadline_extension_seconds` and
`deadline_ceiling_seconds` (#3063): their defaults, their relations, the bounds that the
runner sets on them and the values that `docs/CLUSTER.md` states for them (#5016)."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config import settings
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_SERVICE_POLL_INTERVAL_SECONDS,
)
from tests.support.paths import REPO_ROOT

VARIABLES = (
    "DEVOPS_CLI_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS",
    "DEVOPS_CLI_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS",
    "DEVOPS_CLI_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS",
)
# What a silent wait of the runner may last beyond the longest wait, so that a slow tick does not
# end a healthy run.
MARGIN_SECONDS = 600
CLUSTER_DOC = REPO_ROOT / "docs" / "CLUSTER.md"


@pytest.fixture(autouse=True)
def unset_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave the deadline variables unset, so the config file and the defaults decide."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _deadlines() -> tuple[int, int, int]:
    loaded = settings.load_settings().roadmap.implement
    return (
        loaded.deadline_stall_seconds,
        loaded.deadline_extension_seconds,
        loaded.deadline_ceiling_seconds,
    )


def test_the_defaults_are_70_minutes_90_minutes_and_four_hours() -> None:
    assert _deadlines() == (4200, 5400, 14400)


def test_a_config_file_and_a_variable_set_the_stall_the_extension_and_the_ceiling(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config(
        roadmap={
            "implement": {
                "deadline_stall_seconds": 3000,
                "deadline_extension_seconds": 4000,
                "item_time_limit_seconds": 9000,
            }
        }
    )
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS", "10000")

    assert _deadlines() == (3000, 4000, 10000)


@pytest.mark.parametrize(
    ("stall", "extension", "ceiling"),
    [
        pytest.param(3601, 3600, 14400, id="stall-above-extension"),
        pytest.param(2400, 14401, 14400, id="extension-above-ceiling"),
        pytest.param(2400, 3600, 14401, id="ceiling-above-the-cap"),
        pytest.param(0, 3600, 14400, id="no-stall"),
    ],
)
def test_a_stall_above_the_extension_or_an_extension_above_the_ceiling_is_refused(
    config: Callable[..., Path], stall: int, extension: int, ceiling: int
) -> None:
    config(
        roadmap={
            "implement": {
                "deadline_stall_seconds": stall,
                "deadline_extension_seconds": extension,
                "deadline_ceiling_seconds": ceiling,
            }
        }
    )

    with pytest.raises(ValidationError, match="deadline"):
        settings.load_settings()


def test_the_default_ceiling_is_the_cap_of_the_admission_policy() -> None:
    policy = (REPO_ROOT / "k8s/devops/roadmap-service/admissionpolicy.yaml").read_text("utf-8")

    assert (
        DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS,
        CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS,
        f"activeDeadlineSeconds <= {CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS}" in policy,
    ) == (14400, 14400, True)


def test_the_default_stall_covers_the_longest_wait_in_which_the_runner_writes_no_line() -> None:
    silent = max(
        DEFAULT_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
        DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
        DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
    )

    assert DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS >= silent + MARGIN_SECONDS


def test_the_default_extension_outlasts_the_stall_by_the_delay_of_the_row_and_the_tick() -> None:
    delay = (
        timedelta(minutes=DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES).total_seconds()
        + DEFAULT_SERVICE_POLL_INTERVAL_SECONDS
    )

    assert DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS >= (
        DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS + delay
    )


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        pytest.param(
            r"`roadmap\.implement\.deadline_stall_seconds` \(default (\d+)\)",
            DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS,
            id="stall",
        ),
        pytest.param(
            r"`roadmap\.implement\.deadline_extension_seconds` \(default (\d+)\)",
            DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS,
            id="extension",
        ),
        pytest.param(
            r"`roadmap\.implement\.deadline_ceiling_seconds` \(default (\d+)\)",
            DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS,
            id="ceiling",
        ),
        pytest.param(
            r"the watch of the checks of a pull request, (\d+) s\.",
            DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
            id="watch",
        ),
        pytest.param(
            r"The stall is (\d+) s above it\.",
            DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS
            - DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
            id="margin",
        ),
        pytest.param(
            r"ends by its stall after (\d+) minutes",
            DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS // 60,
            id="stall-minutes",
        ),
    ],
)
def test_the_cluster_document_states_the_default_deadline_values(
    pattern: str, expected: int
) -> None:
    stated = {int(value) for value in re.findall(pattern, CLUSTER_DOC.read_text("utf-8"))}

    assert stated == {expected}


def test_each_setting_has_its_variable() -> None:
    from devops_cli.config.env import setting_variables

    variables = set(setting_variables().values())

    assert set(VARIABLES) <= variables
