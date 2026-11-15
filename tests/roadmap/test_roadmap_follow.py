"""The console of a run (#3076): the trace of the last implement run as the table of the pull
request comment, from one read of the item."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item

TEXTS = MESSAGES.roadmap


def _trace() -> ImplementTrace:
    """A trace of two steps: one that failed its check and one that passed."""
    trace = ImplementTrace(step="group 1")
    trace.model_call("test-model", 1000, 200, 3.0)
    trace.check("uv run mypy", 1)
    trace.attempt(1, "standard", "check_failed", "mypy failed", repair=True)
    trace.step = "group 2"
    trace.model_call("test-model", 2000, 300, 4.0)
    trace.check("uv run pytest", 0)
    trace.attempt(1, "standard", "", "", repair=False)
    return trace


def _item(trace: ImplementTrace | None, job: str | None = None) -> Item:
    """An item whose job record holds `trace` and the runner Job `job`."""
    record = {}
    if trace is not None:
        record[ImplementRecordKey.TRACE] = trace.encode()
    if job is not None:
        record[ImplementRecordKey.JOB] = job
    return Item(number=7, title="work", url="https://example.com/7", job_record=record)


def test_the_table_holds_one_row_for_each_step_of_the_trace() -> None:
    from devops_cli.roadmap.follow import follow_state, render_recorded

    state = follow_state(_item(_trace(), "runner-7"), 7)

    assert state.trace is not None
    assert state.job == "runner-7"
    assert state.job_state is None
    lines = render_recorded(state).splitlines()
    assert lines[0].startswith("| Step | Status | Attempts | Tokens in/out |")
    assert len(lines) == 4
    assert lines[2] == "| group 1 | stopped | 1 | 1000/200 | `uv run mypy` |"
    assert lines[3] == "| group 2 | done | 1 | 2000/300 | - |"


def test_an_item_with_no_trace_and_no_job_is_named_as_never_run() -> None:
    from devops_cli.roadmap.follow import follow_state, render_recorded

    state = follow_state(_item(None), 7)

    assert state.trace is None
    assert state.job is None
    assert render_recorded(state) == TEXTS.follow_never_run.format(number=7)
    assert "#7" in render_recorded(state)


def test_a_running_job_with_no_recorded_event_is_no_never_run_line() -> None:
    from devops_cli.roadmap.follow import follow_state, render_recorded

    state = follow_state(_item(None, "runner-7"), 7)

    assert state.trace is None
    assert state.job == "runner-7"
    assert render_recorded(state) == ""


def test_a_trace_that_is_no_trace_names_the_issue() -> None:
    from devops_cli.roadmap.follow import follow_state

    item = Item(
        number=7,
        title="work",
        url="https://example.com/7",
        job_record={ImplementRecordKey.TRACE: "not a trace"},
    )

    with pytest.raises(RoadmapImplementError) as raised:
        follow_state(item, 7)

    assert "#7" in str(raised.value)


def test_a_secret_in_a_recorded_text_is_masked() -> None:
    from devops_cli.roadmap.follow import follow_state, render_recorded

    trace = ImplementTrace(step="group 1")
    trace.check("curl -H 'Authorization: Bearer ghp_ABC1234567890123456789012345678901234567'", 1)

    rendered = render_recorded(follow_state(_item(trace, "runner-7"), 7))

    assert "ghp_ABC1234567890123456789012345678901234567" not in rendered
    assert "<masked" in rendered


def test_the_follow_command_names_the_item() -> None:
    from devops_cli.roadmap.follow import follow_command

    assert follow_command(7) == "devops roadmap follow 7"


def test_one_attempt_event_for_each_attempt_of_a_step() -> None:
    from devops_cli.roadmap.follow import recorded_rows

    trace = ImplementTrace(step="group 1")
    trace.attempt(1, "standard", "check_failed", "mypy failed", repair=True)
    trace.attempt(2, "standard", "", "", repair=False)

    rows = recorded_rows(trace)

    assert len(rows) == 1
    assert rows[0].attempts == 2
    assert rows[0].status == "done"
