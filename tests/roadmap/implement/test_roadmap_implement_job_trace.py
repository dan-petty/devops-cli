"""The trace of a run of the implement job in the job record (#3032): what it holds, when it is
written, and how it is bound.

Git runs for real on a clone with an `origin`. The model is scripted and the process edge answers
every other program.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import ModelRequestParameters, StreamedResponse
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

from devops_cli.roadmap.implement import implement_trace
from devops_cli.roadmap.implement.implement_trace import ImplementTrace, TraceEventKind, decode
from devops_cli.roadmap.stores.store import ImplementRecordKey
from tests.support.fakes.process import ProcessAnswer
from tests.support.implement_step import command_text, tool_reads
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    SHOUT,
    TASKS_PATH,
    TICKED_FIRST,
    JobWorld,
    group_one_calls,
    group_two_calls,
    two_groups,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

STALE = "stale-event-of-the-last-run"
TOKENS_PER_MESSAGE = 1000


class _GrowingModel(FunctionModel):
    """A `FunctionModel` whose streamed replies report an input that grows with the messages of
    the request, as a provider does. A streamed `FunctionModel` by itself reports the same input
    for every request."""

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any = None,
    ) -> AsyncIterator[StreamedResponse]:
        async with super().request_stream(
            messages, model_settings, model_request_parameters, run_context
        ) as response:
            response._usage = RequestUsage(input_tokens=TOKENS_PER_MESSAGE * len(messages))
            yield response


class _GrowingScript(ModelScript):
    """A script whose requests report an input that grows with the conversation."""

    def model(self) -> FunctionModel:
        return _GrowingModel(self, stream_function=self.stream)


def _trace(world: JobWorld) -> ImplementTrace:
    held = world.store.item(1)
    assert held is not None
    return decode(held.job_record[ImplementRecordKey.TRACE] or "")


def _writes(world: JobWorld, monkeypatch: pytest.MonkeyPatch) -> list[dict[Any, str | None]]:
    """Every marks dict that the job writes to the record, in order."""
    seen: list[dict[Any, str | None]] = []
    set_marks, set_field = world.store.set_marks, world.store.set_field

    def marks(item: Any, written: dict[Any, str | None], *, body: str | None = None) -> Any:
        seen.append(dict(written))
        return set_marks(item, written, body=body)

    def field(
        item: Any,
        name: Any,
        value: Any,
        *,
        marks: dict[Any, str | None] | None = None,
        body: str | None = None,
    ) -> Any:
        seen.append(dict(marks or {}))
        return set_field(item, name, value, marks=marks, body=body)

    monkeypatch.setattr(world.store, "set_marks", marks)
    monkeypatch.setattr(world.store, "set_field", field)
    return seen


def test_a_run_to_a_ready_pull_request_leaves_the_events_of_the_steps_and_the_commands(
    job_world: JobWorld,
) -> None:
    applied = job_world.run(two_groups())

    trace = _trace(job_world)
    kinds = {event.kind for event in trace.events}
    commands = [str(e.fields["command"]) for e in trace.events if e.kind is TraceEventKind.CHECK]
    assert applied.ready == (1,)
    assert {TraceEventKind.MODEL, TraceEventKind.TOOL, TraceEventKind.CHECK} <= kinds
    assert any("docs generate" in command for command in commands)
    assert any("ci --check --only" in command for command in commands)
    assert {"group 1", "group 2"} <= {event.step for event in trace.events}


def test_a_stopped_group_leaves_the_events_of_the_stop(job_world: JobWorld) -> None:
    script = ModelScript(
        tool_calls(*group_one_calls()), say("Group 1 is done."), say("I could not do group 2.")
    )

    applied = job_world.run(script)

    steps = [event.step for event in _trace(job_world).events]
    assert applied.stopped == (1,)
    assert steps[-1] == "group 2"
    assert steps.count("group 1") > 0


def test_the_record_after_group_one_holds_the_events_of_group_one(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes = _writes(job_world, monkeypatch)

    job_world.run(two_groups())

    first = next(w for w in writes if w.get(ImplementRecordKey.GROUP) == "1")
    steps = {event.step for event in decode(first[ImplementRecordKey.TRACE] or "").events}
    assert steps == {"group 1"}


def test_a_new_run_clears_the_trace_of_the_last_run_before_its_first_step(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = job_world.store.item(1)
    assert item is not None
    stale = ImplementTrace(step="old")
    stale.retry(STALE)
    job_world.store.set_marks(item, {ImplementRecordKey.TRACE: stale.encode()})
    writes = _writes(job_world, monkeypatch)

    job_world.run(two_groups())

    assert writes[0][ImplementRecordKey.TRACE] is None
    held = job_world.store.item(1)
    assert held is not None
    assert STALE not in (held.job_record[ImplementRecordKey.TRACE] or "")


def _first_requests(world: JobWorld) -> dict[str, int]:
    """The input tokens of the first request of each step, as the spend of the record holds them."""
    held = world.store.item(1)
    assert held is not None
    spend = json.loads(held.job_record[ImplementRecordKey.SPEND] or "{}")
    return {row["step"]: row["first_request_tokens"] for row in spend["steps"]}


def test_the_spend_holds_the_size_of_the_first_request_of_each_step(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    events = _trace(job_world).events
    firsts = {
        step: next(
            e.fields["tokens_in"]
            for e in events
            if e.kind is TraceEventKind.MODEL and e.step == step
        )
        for step in ("group 1", "group 2")
    }
    assert firsts["group 1"] > 0
    assert _first_requests(job_world) == firsts


def test_a_run_with_more_events_than_the_bound_keeps_the_size_of_its_first_requests(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(implement_trace, "CONST_ROADMAP_IMPLEMENT_TRACE_CHARS", 700)

    job_world.run(two_groups())

    trace = _trace(job_world)
    firsts = _first_requests(job_world)
    assert trace.dropped > 0
    assert not any(e.kind is TraceEventKind.MODEL and e.step == "group 1" for e in trace.events)
    assert set(firsts) == {"group 1", "group 2"}
    assert all(tokens > 0 for tokens in firsts.values())


def test_a_run_with_more_events_than_the_bound_leaves_the_newest_and_counts_the_rest(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(implement_trace, "CONST_ROADMAP_IMPLEMENT_TRACE_CHARS", 700)

    job_world.run(two_groups())

    held = job_world.store.item(1)
    assert held is not None
    value = held.job_record[ImplementRecordKey.TRACE] or ""
    trace = decode(value)
    assert len(value) <= 700
    assert trace.dropped > 0
    assert trace.events


def _spend(world: JobWorld) -> dict[str, Any]:
    held = world.store.item(1)
    assert held is not None
    spend: dict[str, Any] = json.loads(held.job_record[ImplementRecordKey.SPEND] or "{}")
    return spend


def _model_events(world: JobWorld, step: str) -> list[dict[str, Any]]:
    return [
        e.fields for e in _trace(world).events if e.kind is TraceEventKind.MODEL and e.step == step
    ]


def test_the_spend_holds_the_requests_the_tokens_and_the_largest_request_of_each_step(
    job_world: JobWorld,
) -> None:
    script = two_groups()
    job_world.run(_GrowingScript(*script.replies))

    spend = _spend(job_world)
    rows = {row["step"]: row for row in spend["steps"]}
    for step in ("group 1", "group 2"):
        events = _model_events(job_world, step)
        assert {
            key: rows[step][key]
            for key in ("requests", "input_tokens", "output_tokens", "largest_request_tokens")
        } == {
            "requests": len(events),
            "input_tokens": sum(e["tokens_in"] for e in events),
            "output_tokens": sum(e["tokens_out"] for e in events),
            "largest_request_tokens": max(e["tokens_in"] for e in events),
        }, step
        assert rows[step]["repair_rounds"] == 0
    assert rows["group 1"]["largest_request_tokens"] > rows["group 1"]["first_request_tokens"]
    assert sum(row["input_tokens"] for row in rows.values()) == spend["input_tokens"]


def test_the_spend_holds_the_repair_rounds_of_a_step_and_the_requests_of_its_rounds(
    job_world: JobWorld,
) -> None:
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=tool_reads("import os", "F401 unused")),
    )
    shout = "src/devops_cli/shout.py"
    script = ModelScript(
        tool_calls(
            ("write_file", {"path": shout, "content": "import os\n" + SHOUT}),
            ("write_file", {"path": TASKS_PATH, "content": TICKED_FIRST}),
        ),
        say("Group 1 is done."),
        tool_calls(("write_file", {"path": shout, "content": SHOUT})),
        say("The unused import is gone."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    job_world.run(script)

    rows = {row["step"]: row for row in _spend(job_world)["steps"]}
    assert rows["group 1"]["repair_rounds"] == 1
    assert rows["group 1"]["requests"] == len(_model_events(job_world, "group 1")) == 4
