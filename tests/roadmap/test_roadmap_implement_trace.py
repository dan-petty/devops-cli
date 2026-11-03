"""The trace of one implement run: events, bound, decode, digest and masking (#3032)."""

from __future__ import annotations

import json

import pytest
from pydantic_ai.messages import ToolCallPart

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_TRACE_CHARS
from devops_cli.roadmap.implement_trace import (
    ImplementTrace,
    TraceDecodeError,
    TraceEventKind,
    argument_digest,
    decode,
)


def _trace() -> ImplementTrace:
    trace = ImplementTrace(step="group 1")
    trace.model_call("model-a", 100, 20, 1.234)
    trace.tool_call("shell", "ruff", "abc", "retry", "no match")
    trace.check("ruff check .", 1)
    trace.retry("lint failed")
    return trace


def test_the_four_kinds_keep_their_order_and_fields() -> None:
    events = _trace().events

    assert [event.kind for event in events] == [
        TraceEventKind.MODEL,
        TraceEventKind.TOOL,
        TraceEventKind.CHECK,
        TraceEventKind.RETRY,
    ]
    assert events[0].fields == {
        "model": "model-a",
        "tokens_in": 100,
        "tokens_out": 20,
        "seconds": 1.2,
    }
    assert events[1].fields["reason"] == "no match"
    assert events[2].fields == {"command": "ruff check .", "status": 1}
    assert {event.step for event in events} == {"group 1"}


def test_a_check_that_timed_out_has_no_status() -> None:
    trace = ImplementTrace(step="s")
    trace.check("mypy", None)

    assert trace.events[0].fields == {"command": "mypy", "timeout": True}


def test_encode_gives_json_with_events_and_dropped_and_decode_reads_it_back() -> None:
    data = json.loads(_trace().encode())
    assert len(data["events"]) == 4
    assert data["dropped"] == 0

    again = decode(_trace().encode())
    assert [event.as_dict() for event in again.events] == data["events"]


def test_too_many_events_keep_the_newest_whole_and_count_the_rest() -> None:
    trace = ImplementTrace(step="group 1")
    for number in range(400):
        trace.retry(f"reason {number}")

    text = trace.encode()
    data = json.loads(text)

    assert len(text) <= CONST_ROADMAP_IMPLEMENT_TRACE_CHARS
    assert data["events"][-1]["reason"] == "reason 399"
    assert data["dropped"] == 400 - len(data["events"]) > 0
    assert data["events"][0]["reason"] == f"reason {data['dropped']}"


def test_a_decoded_trace_keeps_its_dropped_count() -> None:
    trace = decode('{"events":[],"dropped":5}')
    trace.retry("x")

    assert json.loads(trace.encode())["dropped"] == 5


@pytest.mark.parametrize(
    "text",
    ["not json", "[]", '{"events":3}', '{"events":[1]}', '{"events":[{"kind":"x","step":""}]}'],
)
def test_text_that_is_not_a_trace_raises_one_error(text: str) -> None:
    with pytest.raises(TraceDecodeError, match=r"."):
        decode(text)


def test_the_digest_follows_the_argument_and_never_a_secret_value() -> None:
    first = ToolCallPart("shell", {"command": "ls"})
    other = ToolCallPart("shell", {"command": "pwd"})

    assert argument_digest(first) == argument_digest(ToolCallPart("shell", {"command": "ls"}))
    assert argument_digest(first) != argument_digest(other)
    assert len(argument_digest(first)) == 12
    one = ToolCallPart("shell", {"command": "ls", "api_key": "one"})
    two = ToolCallPart("shell", {"command": "ls", "api_key": "two"})
    assert argument_digest(one) == argument_digest(two)


def test_a_text_comes_out_masked_cut_and_on_one_line() -> None:
    trace = ImplementTrace(step="s")
    trace.retry("Bearer abcdefghijklmnopqrstuvwxyz0123 at db.corp.internal\nnext " + "x" * 2000)

    reason = trace.events[0].fields["reason"]

    assert "<masked-token>" in reason
    assert "<masked-host>" in reason
    assert "abcdefghijklmnopqrstuvwxyz0123" not in reason
    assert "db.corp.internal" not in reason
    assert "\n" not in reason
    assert len(reason) <= 240
