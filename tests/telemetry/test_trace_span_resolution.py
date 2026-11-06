"""The spans a trace view shows: the named trace, or the latest buffered trace as a fallback."""

from __future__ import annotations

from devops_cli.telemetry.tracer import record_completed_span
from devops_cli.telemetry.waterfall import resolve_trace_spans_or_latest

_OLDER = "4bf92f3577b34da6a3ce929d0e0e4736"
_LATEST = "00f067aa0ba902b700f067aa0ba902b7"
_UNKNOWN = "11111111111111111111111111111111"


def _buffer_two_traces() -> None:
    record_completed_span({"traceId": _OLDER, "spanId": "a1", "name": "older"})
    record_completed_span({"traceId": _LATEST, "spanId": "b1", "name": "latest"})


def test_a_named_trace_that_the_buffer_holds_returns_its_spans() -> None:
    _buffer_two_traces()

    trace_id, spans = resolve_trace_spans_or_latest(_OLDER, last=False, tempo_url=None)

    assert (trace_id, [s["name"] for s in spans]) == (_OLDER, ["older"])


def test_a_named_trace_that_the_buffer_holds_wins_over_the_last_flag() -> None:
    _buffer_two_traces()

    trace_id, spans = resolve_trace_spans_or_latest(_OLDER, last=True, tempo_url=None)

    assert (trace_id, [s["name"] for s in spans]) == (_OLDER, ["older"])


def test_an_unknown_trace_with_the_last_flag_returns_the_latest_buffered_trace() -> None:
    _buffer_two_traces()

    trace_id, spans = resolve_trace_spans_or_latest(_UNKNOWN, last=True, tempo_url=None)

    assert (trace_id, [s["name"] for s in spans]) == (_LATEST, ["latest"])


def test_an_unknown_trace_without_the_last_flag_returns_no_spans() -> None:
    _buffer_two_traces()

    assert resolve_trace_spans_or_latest(_UNKNOWN, last=False, tempo_url=None) == (_UNKNOWN, [])


def test_no_trace_id_returns_the_latest_buffered_trace() -> None:
    _buffer_two_traces()

    trace_id, spans = resolve_trace_spans_or_latest(None, last=False, tempo_url=None)

    assert (trace_id, [s["name"] for s in spans]) == (_LATEST, ["latest"])


def test_an_empty_buffer_returns_no_spans() -> None:
    assert resolve_trace_spans_or_latest(None, last=True, tempo_url=None) == ("unknown", [])
