"""A process that runs on exports its metrics at a fixed interval (#5916).

The pod of a Job runs one long command. Its metrics left the pod only when the process ended, so a
Job showed no tokens, requests or spend while it ran. The interval is OpenTelemetry's
`OTEL_METRIC_EXPORT_INTERVAL`, in milliseconds, 60000 when it is not set. The Service keeps its
flush after each round, and the reader gives only what changed since the collection before it, so
a periodic export and a flush send each count once.
"""

from __future__ import annotations

import threading
from itertools import pairwise
from typing import Any

import pytest

from devops_cli.telemetry.exporter import OtlpSignal
from devops_cli.telemetry.instruments import AI_TOKENS_TOTAL, emit
from devops_cli.telemetry.tracer import OTelTelemetryClient, get_tracer, reset_tracer, trace_span
from tests.support.fakes.otlp import FakeCollector, exported_metrics, metric_points
from tests.support.waits import wait_until

_TOKENS = {"operation": "chat", "type": "prompt"}
_INTERVAL_VARIABLE = "OTEL_METRIC_EXPORT_INTERVAL"


def _received_tokens(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    return metric_points(otlp.received(OtlpSignal.METRICS), AI_TOKENS_TOTAL.name)


def _token_point_times(otlp: FakeCollector) -> list[tuple[int, int]]:
    """The start and end time of each exported token point, in the order the collector got them."""
    return [
        (int(point["startTimeUnixNano"]), int(point["timeUnixNano"]))
        for metric in exported_metrics(otlp.received(OtlpSignal.METRICS))
        if metric["name"] == AI_TOKENS_TOTAL.name
        for point in metric["sum"]["dataPoints"]
    ]


def test_a_long_command_exports_its_metrics_before_it_ends(
    otlp: FakeCollector, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the collector gets the tokens of a command while the command still runs."""
    monkeypatch.setenv(_INTERVAL_VARIABLE, "10")
    reset_tracer()

    with trace_span("cli.long-command"):
        emit(AI_TOKENS_TOTAL, 120.0, _TOKENS)
        exported_while_running = wait_until(lambda: bool(_received_tokens(otlp)))
        received = _received_tokens(otlp)

    assert (exported_while_running, received) == (True, [(_TOKENS, 120.0)])


def test_a_periodic_export_and_a_round_flush_send_each_count_once_in_time_order(
    otlp: FakeCollector, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the deltas of the periodic export and of the flush of the Service add up to what
    the process counted, and each starts where the one before it ended, so the collector drops
    none as out of order."""
    monkeypatch.setenv(_INTERVAL_VARIABLE, "10")
    reset_tracer()

    emit(AI_TOKENS_TOTAL, 3.0, _TOKENS)
    assert wait_until(lambda: bool(_received_tokens(otlp)))
    emit(AI_TOKENS_TOTAL, 2.0, _TOKENS)
    get_tracer().flush()

    values = [value for _attributes, value in _received_tokens(otlp)]
    times = _token_point_times(otlp)
    assert (len(values) >= 2, sum(values)) == (True, 5.0)
    assert all(
        later_start >= earlier_end and later_end > earlier_end
        for (_start, earlier_end), (later_start, later_end) in pairwise(times)
    )


def test_a_short_command_exports_its_metrics_once_when_it_ends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a command that ends before the first interval exports once, at its end, and leaves
    no export thread running."""
    monkeypatch.delenv(_INTERVAL_VARIABLE, raising=False)
    before = set(threading.enumerate())
    collector = FakeCollector()
    client = collector.client()

    client.increment_counter(AI_TOKENS_TOTAL.name, 7.0, attributes=_TOKENS)
    client.shutdown()

    started_and_alive = [
        thread for thread in threading.enumerate() if thread not in before and thread.is_alive()
    ]
    assert (
        len(collector.received(OtlpSignal.METRICS)),
        metric_points(collector.received(OtlpSignal.METRICS), AI_TOKENS_TOTAL.name),
        started_and_alive,
    ) == (1, [(_TOKENS, 7.0)], [])


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        pytest.param(None, 60.0, id="unset"),
        pytest.param("500", 0.5, id="milliseconds"),
        pytest.param("not-a-number", 60.0, id="not-a-number"),
        pytest.param("0", 60.0, id="zero"),
        pytest.param("-5", 60.0, id="negative"),
        pytest.param("inf", 60.0, id="infinite"),
    ],
)
def test_the_interval_comes_from_otel_metric_export_interval(
    monkeypatch: pytest.MonkeyPatch, value: str | None, seconds: float
) -> None:
    """Verify the interval is the variable's milliseconds, and the default of OpenTelemetry for a
    value that is not a number of milliseconds above zero."""
    if value is None:
        monkeypatch.delenv(_INTERVAL_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(_INTERVAL_VARIABLE, value)

    client = OTelTelemetryClient(enabled=True, exporter=FakeCollector())

    assert client.metric_export_interval == seconds
