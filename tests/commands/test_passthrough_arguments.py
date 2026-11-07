"""Arguments after `--` belong to the command that a devops command passes them through to."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_a_help_flag_after_the_separator_runs_the_command_and_keeps_its_exit_code(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """`devops uv run -- pytest --help` runs pytest, so the exit code of pytest is kept."""
    process_fake.answer("uv", ProcessAnswer(returncode=3))

    result = cli("uv", "run", "--", "pytest", "--help")

    assert result.exit_code == 3
    assert [call.argv[-3:] for call in process_fake.calls] == [("run", "pytest", "--help")]


def test_a_help_flag_before_the_separator_shows_help_and_runs_nothing(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = cli("uv", "run", "--help")

    assert result.exit_code == 0
    assert "Usage: devops uv run" in result.output
    assert process_fake.calls == []
