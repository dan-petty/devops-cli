"""The table of the steps for the comments of the job (#3032)."""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS,
    CONST_ROADMAP_IMPLEMENT_TABLE_ROWS,
)
from devops_cli.roadmap.implement_trace import (
    ImplementTrace,
    SummaryRow,
    last_failing_command,
    summary_table,
)


def _row(step: str = "group 1", command: str = "", **more: int) -> SummaryRow:
    return SummaryRow(step, "done", more.get("attempts", 1), 4100, 320, command)


def test_a_row_shows_the_step_the_attempts_the_tokens_and_the_command() -> None:
    table = summary_table([_row("group 2", "uv run mypy", attempts=2)])

    header, rule, row = table.splitlines()
    assert header.startswith("| Step | Status | Attempts | Tokens in/out |")
    assert rule.startswith("| ---")
    assert row == "| group 2 | done | 2 | 4100/320 | `uv run mypy` |"


def test_a_step_with_no_failing_command_shows_a_dash() -> None:
    assert summary_table([_row()]).splitlines()[-1].endswith("| - |")


def test_a_pipe_in_a_command_is_escaped_to_stay_in_one_cell() -> None:
    row = summary_table([_row(command="a | b")]).splitlines()[-1]

    assert "a \\| b" in row
    assert row.count("|") - row.count("\\|") == 6


def test_a_command_longer_than_the_limit_is_cut() -> None:
    row = summary_table([_row(command="x" * 1000)]).splitlines()[-1]

    assert "x" * CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS in row
    assert "x" * (CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS + 1) not in row


def test_more_rows_than_the_limit_keep_the_newest() -> None:
    steps = [f"group {n}" for n in range(CONST_ROADMAP_IMPLEMENT_TABLE_ROWS + 5)]

    lines = summary_table([_row(step) for step in steps]).splitlines()[2:]

    assert len(lines) == CONST_ROADMAP_IMPLEMENT_TABLE_ROWS
    assert lines[-1].startswith(f"| {steps[-1]} ")
    assert lines[0].startswith("| group 5 ")


def test_no_rows_give_no_table() -> None:
    assert summary_table([]) == ""


def test_the_last_failing_command_is_that_of_the_last_check_that_did_not_exit_0() -> None:
    trace = ImplementTrace(step="group 2")
    trace.check("ruff check", 1)
    trace.check("mypy", 1)
    trace.check("pytest", 0)
    trace.step = "group 3"
    trace.check("other", 2)

    assert last_failing_command(trace.events, "group 2") == "mypy"


def test_a_timeout_is_a_failing_check() -> None:
    trace = ImplementTrace(step="docs")
    trace.check("uv run devops docs generate", None)

    assert last_failing_command(trace.events, "docs") == "uv run devops docs generate"


def test_the_name_of_the_check_stands_in_when_no_event_failed() -> None:
    trace = ImplementTrace(step="checks")
    trace.check("ruff check", 0)

    assert last_failing_command(trace.events, "checks", "Tests & Coverage") == "Tests & Coverage"
