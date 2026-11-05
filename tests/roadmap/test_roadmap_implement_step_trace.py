"""The trace of an implement step (#3032): its model calls, tool calls, exit checks and retries.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and `process_fake` answers every other program.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.implement_trace import ImplementTrace, TraceEvent, TraceEventKind
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.base_replay import (
    BEHAVIOR_TASKS,
    BEHAVIOR_TICKED,
    SHOUT_TEST_ID,
    answer_pytest_on_base,
    junit,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    make_checkout,
    tool_reads,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

LINT = "uv run ruff check"
BAD_TEST = "import os\n\n" + TEST_BODY
MISSING_EDIT = ("edit_file", {"path": "src/other.py", "old_text": "NOT THERE", "new_text": "x"})


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    script: ModelScript,
    trace: ImplementTrace | None,
) -> StepOutcome:
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        trace=trace,
    )


def _of(trace: ImplementTrace, kind: TraceEventKind) -> list[TraceEvent]:
    return [event for event in trace.events if event.kind is kind]


def test_two_model_replies_give_two_model_events_with_their_tokens(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    script = ModelScript(tool_call("read_file", path="src/sample.py"), say("Done."))

    outcome = _step(store, checkout, script, trace)

    models = _of(trace, TraceEventKind.MODEL)
    assert len(models) == 2
    assert sum(e.fields["tokens_in"] for e in models) == outcome.input_tokens > 0
    assert sum(e.fields["tokens_out"] for e in models) == outcome.output_tokens > 0
    assert all(e.fields["model"] and e.fields["seconds"] >= 0 for e in models)
    assert {e.step for e in models} == {"group 1"}


def test_a_refused_command_and_a_retried_edit_are_tool_events(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    script = ModelScript(
        tool_calls(("shell", {"command": "pytest tests/test_sample.py"}), MISSING_EDIT),
        say("Done."),
    )

    _step(store, checkout, script, trace)

    tools = {e.fields["tool"]: e.fields for e in _of(trace, TraceEventKind.TOOL)}
    assert (tools["shell"]["outcome"], tools["shell"]["program"]) == ("refused", "pytest")
    assert "reason" not in tools["shell"]
    assert tools["edit_file"]["outcome"] == "retry"
    assert "old_text not found" in tools["edit_file"]["reason"]


def test_the_same_call_twice_has_one_digest_and_no_event_holds_the_command(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    same = ("shell", {"command": "pytest tests/test_sample.py --flag=sentinel-value"})
    other = ("shell", {"command": "pytest tests/other_sentinel.py"})
    script = ModelScript(tool_calls(same, same, other), say("Done."))

    _step(store, checkout, script, trace)

    digests = [e.fields["digest"] for e in _of(trace, TraceEventKind.TOOL)]
    assert digests[0] == digests[1] != digests[2]
    assert all(len(digest) == 12 for digest in digests)
    assert "sentinel" not in trace.encode()


def test_a_failed_lint_one_repair_round_and_a_pass_give_check_retry_check(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith(LINT),
        ProcessAnswer(side_effect=tool_reads("import os", "F401 unused")),
    )
    trace = ImplementTrace(step="group 1")
    first = tool_calls(
        write_call("tests/test_sample.py", BAD_TEST),
        write_call("src/sample.py", "X = 1\n"),
        write_call(TASKS_PATH, TICKED),
    )
    script = ModelScript(
        first, say("Done."), tool_calls(write_call("tests/test_sample.py", TEST_BODY)), say("Ok.")
    )

    outcome = _step(store, checkout, script, trace)

    assert outcome.repair_rounds == 1
    ordered = [
        (event.kind, event.fields.get("status"))
        for event in trace.events
        if event.kind in (TraceEventKind.CHECK, TraceEventKind.RETRY)
        and (event.kind is TraceEventKind.RETRY or LINT in event.fields["command"])
    ]
    assert ordered == [
        (TraceEventKind.CHECK, 1),
        (TraceEventKind.RETRY, None),
        (TraceEventKind.CHECK, 0),
    ]


def test_a_check_that_runs_out_of_time_has_no_exit_status(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff format"),
        ProcessAnswer(side_effect=subprocess.TimeoutExpired("uv", 1)),
    )
    trace = ImplementTrace(step="group 1")
    script = ModelScript(
        tool_calls(
            write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", "X = 1\n")
        ),
        say("Done."),
    )

    outcome = _step(store, checkout, script, trace)

    timed_out = [e for e in _of(trace, TraceEventKind.CHECK) if e.fields.get("timeout")]
    assert outcome.status is StepStatus.STOPPED
    assert len(timed_out) == 1
    assert "status" not in timed_out[0].fields


def test_a_secret_and_a_private_host_in_a_reason_are_masked(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    edit: tuple[str, dict[str, Any]] = (
        "edit_file",
        {
            "path": "src/other.py",
            "old_text": "Bearer abcdefghijklmnopqrstuvwxyz0123 db.corp.internal",
        },
    )
    script = ModelScript(tool_calls(edit), say("Done."))

    _step(store, checkout, script, trace)

    text = trace.encode()
    assert "abcdefghijklmnopqrstuvwxyz0123" not in text
    assert "db.corp.internal" not in text


def test_a_step_with_no_trace_behaves_as_before(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    outcome = _step(store, checkout, ModelScript(say("Done.")), None)

    assert outcome.status is StepStatus.STOPPED


def test_a_base_run_is_a_check_event_with_its_status(
    store: InMemoryRoadmapStore, programs: ProcessFake, tmp_path: Path
) -> None:
    checkout = make_checkout(tmp_path, BEHAVIOR_TASKS)
    answer_pytest_on_base(programs, junit((SHOUT_TEST_ID, "failed")))
    trace = ImplementTrace(step="group 1")
    script = ModelScript(
        tool_calls(
            write_call("tests/test_shout.py", TEST_BODY),
            write_call("src/sample.py", SHOUT_CODE),
            write_call(TASKS_PATH, BEHAVIOR_TICKED),
        ),
        say("Done."),
    )

    outcome = _step(store, checkout, script, trace)

    checks = [
        (event.fields["command"], event.fields["status"])
        for event in _of(trace, TraceEventKind.CHECK)
        if event.fields["command"].startswith("pytest on base")
    ]
    assert (outcome.status, checks) == (
        StepStatus.DONE,
        [("pytest on base: tests/test_shout.py", 1)],
    )
