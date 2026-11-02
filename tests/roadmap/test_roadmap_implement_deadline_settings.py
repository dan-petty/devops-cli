"""The settings `roadmap.implement.deadline_stall_seconds`, `deadline_extension_seconds` and
`deadline_ceiling_seconds` (#3063): their defaults, their relations and the bounds that the
runner sets on them."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config import settings
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS,
    CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS,
    DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES,
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


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty user config file, with the project layer absent and the variables unset."""
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_PATH", path)
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(tmp_path / "no-project-config.yaml"))
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    settings.reset_settings_cache()
    return path


def _deadlines() -> tuple[int, int, int]:
    loaded = settings.load_settings().roadmap.implement
    return (
        loaded.deadline_stall_seconds,
        loaded.deadline_extension_seconds,
        loaded.deadline_ceiling_seconds,
    )


def test_the_defaults_are_forty_minutes_one_hour_and_four_hours(config_file: Path) -> None:
    assert _deadlines() == (2400, 3600, 14400)


def test_a_config_file_and_a_variable_set_the_stall_the_extension_and_the_ceiling(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file.write_text(
        "roadmap:\n  implement:\n    deadline_stall_seconds: 3000\n"
        "    deadline_extension_seconds: 4000\n",
        encoding="utf-8",
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
    config_file: Path, stall: int, extension: int, ceiling: int
) -> None:
    config_file.write_text(
        "roadmap:\n  implement:\n"
        f"    deadline_stall_seconds: {stall}\n"
        f"    deadline_extension_seconds: {extension}\n"
        f"    deadline_ceiling_seconds: {ceiling}\n",
        encoding="utf-8",
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
        CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
        CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
        CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
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


def test_each_setting_has_its_variable() -> None:
    from devops_cli.config.env import setting_variables

    variables = set(setting_variables().values())

    assert set(VARIABLES) <= variables
