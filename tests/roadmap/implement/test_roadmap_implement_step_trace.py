"""The trace of an implement step (#3032): its model calls, tool calls, exit checks and retries.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and `process_fake` answers every other program.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import Agent

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_TRACE_CHARS
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.implement.implement_tool_log import ToolCallLog
from devops_cli.roadmap.implement.implement_trace import (
    ImplementTrace,
    TraceEvent,
    TraceEventKind,
    decode,
)
from tests.support.base_replay import (
    BEHAVIOR_TASKS,
    BEHAVIOR_TICKED,
    SHOUT_TEST_ID,
    answer_pytest_on_base,
    junit,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
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


def test_the_outcome_holds_the_input_tokens_of_the_first_model_request(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    script = ModelScript(tool_call("read_file", path="src/sample.py"), say("Done."))

    outcome = _step(store, checkout, script, trace)

    first, second = _of(trace, TraceEventKind.MODEL)
    assert outcome.first_request_tokens == first.fields["tokens_in"] > 0
    assert outcome.first_request_tokens < outcome.input_tokens
    assert second.fields["tokens_in"] > 0


def test_a_refused_command_and_a_retried_edit_are_tool_events(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    script = ModelScript(
        tool_calls(("run_command", {"command": "pytest tests/test_sample.py"}), MISSING_EDIT),
        say("Done."),
    )

    _step(store, checkout, script, trace)

    tools = {e.fields["tool"]: e.fields for e in _of(trace, TraceEventKind.TOOL)}
    assert (tools["run_command"]["outcome"], tools["run_command"]["program"]) == (
        "refused",
        "pytest",
    )
    assert "reason" not in tools["run_command"]
    assert tools["edit_file"]["outcome"] == "retry"
    assert "old_text not found" in tools["edit_file"]["reason"]


def test_the_same_call_twice_has_one_digest_and_no_event_holds_the_command(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    same = ("run_command", {"command": "pytest tests/test_sample.py --flag=sentinel-value"})
    other = ("run_command", {"command": "pytest tests/other_sentinel.py"})
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


# ── The order of the events and the trace of a long run (#4393) ──────────────────────────


def _kinds(trace: ImplementTrace) -> list[str]:
    return [str(event.kind) for event in trace.events]


def test_the_events_of_a_run_are_in_the_order_of_the_run(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    trace = ImplementTrace(step="group 1")
    script = ModelScript(
        tool_call("read_file", path="src/sample.py"),
        tool_calls(
            ("read_file", {"path": "src/sample.py"}), ("read_file", {"path": "src/sample.py"})
        ),
        say("Done."),
    )

    _step(store, checkout, script, trace)

    assert _kinds(trace) == [
        "model",
        "tool",
        "model",
        "tool",
        "tool",
        "model",
        "attempt",
    ]


def test_a_long_run_keeps_its_tool_events_in_the_trace(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    """101 requests and 150 tool calls do not fit the bound (#4393). The model events go first, so
    the newest tool calls and the attempt stay in the order of the run. On the base the bound took
    the oldest events, and the 150 tool calls, which the step added before the model events, went
    first."""
    trace = ImplementTrace(step="group 1")
    read = ("read_file", {"path": "src/sample.py"})
    replies = [tool_calls(read, read) if number % 2 else tool_calls(read) for number in range(100)]
    script = ModelScript(*replies, say("Done."))

    _step(store, checkout, script, trace)
    text = trace.encode()
    kept = decode(text)

    kinds = _kinds(kept)
    tools = [event for event in trace.events if event.kind is TraceEventKind.TOOL]
    assert len(text) <= CONST_ROADMAP_IMPLEMENT_TRACE_CHARS
    assert len(tools) == 150
    assert sum(event.kind is TraceEventKind.MODEL for event in trace.events) == 101
    assert "model" not in kinds
    assert kinds.count("tool") >= 60
    assert kept.events[:-1] == tools[-kinds.count("tool") :]
    assert kinds[-1] == "attempt"
    assert kept.dropped == 101 + 150 - kinds.count("tool")


def _shell_result(code: int | None) -> str:
    """What the tool `run_command` of the harness returns: the labelled output, then the line of the
    exit code when it is not 0. A command that ran past its wait ends with the line of the timeout,
    and the harness killed it, so it has no exit status."""
    if code is None:
        return "[stdout]\noutput text\n[Command timed out after 41s]"
    if code == 0:
        return "[stdout]\noutput text"
    return f"[stdout]\noutput text\n[stderr]\nfatal\n[exit code: {code}]"


@pytest.mark.parametrize(
    ("result", "status"),
    [
        pytest.param(_shell_result(0), 0, id="zero"),
        pytest.param("(no output)", 0, id="no-output"),
        pytest.param(_shell_result(128), 128, id="failed"),
        pytest.param(_shell_result(-9), -9, id="signal"),
        pytest.param(_shell_result(None), None, id="timed-out"),
    ],
)
def test_a_shell_call_has_the_exit_status_that_the_shell_reports(
    result: str, status: int | None
) -> None:
    def run_command(command: str) -> str:
        return result

    trace = ImplementTrace(step="group 1")
    Agent(
        ModelScript(tool_call("run_command", command="git status"), say("Done.")).model(),
        tools=[run_command],
        capabilities=[ToolCallLog(trace=trace).hooks()],
    ).run_sync("go")

    (event,) = _of(trace, TraceEventKind.TOOL)
    assert event.fields.get("status") == status
    assert "output text" not in trace.encode()


def test_a_tool_that_is_no_shell_has_no_exit_status() -> None:
    def read_file(path: str) -> str:
        return _shell_result(1)

    trace = ImplementTrace(step="group 1")
    Agent(
        ModelScript(tool_call("read_file", path="a"), say("Done.")).model(),
        tools=[read_file],
        capabilities=[ToolCallLog(trace=trace).hooks()],
    ).run_sync("go")

    (event,) = _of(trace, TraceEventKind.TOOL)
    assert "status" not in event.fields
