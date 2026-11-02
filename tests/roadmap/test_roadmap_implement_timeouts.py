"""The time limits of the implement job are settings with their own variables (#3206).

The model call, the command of a step and the watch of the checks of a pull request each read
their limit from `roadmap.implement`, so a person changes it with a variable or the config file
and no code change.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.config import env
from devops_cli.config.settings import load_settings
from devops_cli.github.pr_monitor import PRMonitorResult, PRMonitorStatus
from devops_cli.roadmap import implement_pull
from devops_cli.roadmap.implement_pull import WatchKind, watch_pull
from devops_cli.roadmap.implement_scoped_ci import run_scoped_checks, scoped_checks
from devops_cli.roadmap.implement_step import StepOutcome, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import WINDOW
from tests.support.model_script import ModelScript, say

pytestmark = pytest.mark.usefixtures("keyring_store")

SETTINGS = ("request_timeout_seconds", "command_timeout_seconds", "monitor_timeout_seconds")
HEAD = "a" * 40
PRE_COMMIT_CONFIG = Path("/data/cache/pre-commit-trusted-config.yaml")


def test_the_defaults_are_20_minutes_for_a_call_30_for_a_command_and_an_hour_for_the_checks() -> (
    None
):
    implement = load_settings().roadmap.implement

    assert (
        implement.request_timeout_seconds,
        implement.command_timeout_seconds,
        implement.monitor_timeout_seconds,
    ) == (1200, 1800, 3600)


def test_each_limit_has_a_variable_named_after_its_setting() -> None:
    variables = env.setting_variables()

    assert [variables[f"roadmap.implement.{name}"] for name in SETTINGS] == [
        f"DEVOPS_CLI_ROADMAP_IMPLEMENT_{name.upper()}" for name in SETTINGS
    ]


def test_a_variable_and_the_config_file_set_the_limits(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS", "120")
    config(roadmap={"implement": {"command_timeout_seconds": 90}})

    implement = load_settings().roadmap.implement

    assert (implement.command_timeout_seconds, implement.monitor_timeout_seconds) == (90, 120)


@pytest.mark.parametrize("name", SETTINGS)
def test_a_limit_of_zero_is_refused(config: Callable[..., Path], name: str) -> None:
    config(roadmap={"implement": {name: 0}})

    with pytest.raises(ValidationError, match=name):
        load_settings()


# ── The readers ───────────────────────────────────────────────────────────────────────────


def test_a_model_call_of_a_step_gets_the_deadline_of_the_setting(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"request_timeout_seconds": 77}})
    script = ModelScript(say("Nothing to do."))

    outcome: StepOutcome = run_step(
        implement_store,
        item=1,
        group=1,
        source=implement_checkout,
        model=script.model(),
        window=WINDOW,
    )

    assert (outcome.requests, script.settings_seen[0]["request_timeout"]) == (1, 77)


def test_a_scoped_check_gets_the_command_limit_of_the_setting(
    implement_checkout: Path, implement_programs: ProcessFake, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"command_timeout_seconds": 41}})

    run_scoped_checks(
        implement_checkout,
        scoped_checks("main", ["tests/test_sample.py"], config=PRE_COMMIT_CONFIG),
    )

    assert {call.timeout for call in implement_programs.calls} == {41}


def test_a_scoped_check_that_runs_out_of_time_names_the_limit_of_the_setting(
    implement_checkout: Path, implement_programs: ProcessFake, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"command_timeout_seconds": 41}})

    def hang(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(call.argv, 41)

    implement_programs.answer(lambda _call: True, ProcessAnswer(side_effect=hang))

    (result, *_rest) = run_scoped_checks(
        implement_checkout,
        scoped_checks("main", ["tests/test_sample.py"], config=PRE_COMMIT_CONFIG),
    )

    assert (result.passed, "41" in result.log) == (False, True)


def _settled(*, timed_out: bool) -> PRMonitorResult:
    return PRMonitorResult(
        success=not timed_out,
        exit_code=3 if timed_out else 0,
        message="",
        status=PRMonitorStatus(number=5, head_sha=HEAD, pending_checks=["ci"] * timed_out),
    )


def test_the_watch_of_the_checks_waits_the_seconds_of_the_setting(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config(roadmap={"implement": {"monitor_timeout_seconds": 123}})
    seen: list[dict[str, Any]] = []

    def monitor(*_args: Any, **kwargs: Any) -> PRMonitorResult:
        seen.append(kwargs)
        return _settled(timed_out=True)

    monkeypatch.setattr(implement_pull, "monitor_pr", monitor)

    watch = watch_pull("example/repo", 5, HEAD)

    assert (seen[0]["timeout"], watch.kind, "123" in watch.reason) == (
        123,
        WatchKind.STOPPED,
        True,
    )
