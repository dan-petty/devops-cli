"""The trace of a run of the implement job in the job record (#3032): what it holds, when it is
written, and how it is bound.

Git runs for real on a clone with an `origin`. The model is scripted and the process edge answers
every other program.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap import implement_trace
from devops_cli.roadmap.implement_trace import ImplementTrace, TraceEventKind, decode
from devops_cli.roadmap.store import ImplementRecordKey
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import JobWorld, group_one_calls, two_groups

pytestmark = pytest.mark.usefixtures("keyring_store")

STALE = "stale-event-of-the-last-run"


def _trace(world: JobWorld) -> ImplementTrace:
    held = world.store.item(1)
    assert held is not None
    return decode(held.job_record[ImplementRecordKey.TRACE] or "")


def _writes(world: JobWorld, monkeypatch: pytest.MonkeyPatch) -> list[dict[Any, str | None]]:
    """Every marks dict that the job writes to the record, in order."""
    seen: list[dict[Any, str | None]] = []
    set_marks, set_field = world.store.set_marks, world.store.set_field

    def marks(item: Any, written: dict[Any, str | None]) -> Any:
        seen.append(dict(written))
        return set_marks(item, written)

    def field(
        item: Any, name: Any, value: Any, *, marks: dict[Any, str | None] | None = None
    ) -> Any:
        seen.append(dict(marks or {}))
        return set_field(item, name, value, marks=marks)

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
