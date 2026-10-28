"""The OpenTelemetry collector's fake: an `OtlpExporter` that records each export (#1319).

`OTelTelemetryClient` hands each export request to an `OtlpExporter`
(`devops_cli.telemetry.exporter`). `FakeCollector` is that exporter for tests: it records each
request as the collector receives it, and reads back the exported spans, metric data points and
log records as plain values. `answer(status)` and `refuse()` make its exports and its probe fail
with the texts of the real exporter, and `accept()` makes them succeed again.

The `otlp` fixture installs the fake as the process's exporter with export on, so code under test
exports to it. Each read first waits for the exports the tracer queued, through the tracer's
public `flush()`, so no test sleeps. `tests/telemetry/test_otlp_exporter_contract.py` holds the
fake to `HttpOtlpExporter` over a loopback OTLP/HTTP receiver.

Every support module is a plugin of each run, and the fail-to-pass replay runs new tests on the
base tree, so the names of `devops_cli.telemetry.exporter` are imported in the functions that use
them.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from devops_cli.telemetry.exporter import OtlpSignal, ProbeResult
    from devops_cli.telemetry.tracer import OTelTelemetryClient

FAKE_COLLECTOR_ENDPOINT = "http://otlp.example.com:4318"


@dataclass(frozen=True)
class Export:
    """One export request as the collector receives it."""

    signal: OtlpSignal
    payload: dict[str, Any]


@dataclass(frozen=True)
class ExportedSpan:
    """One exported span, as plain values."""

    name: str
    attributes: dict[str, Any]
    trace_id: str
    span_id: str
    parent_span_id: str | None
    kind: str
    status_code: str
    status_message: str
    links: tuple[tuple[str, str], ...]
    events: tuple[str, ...]


def plain_attributes(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    """OTLP key-value attributes as a dict of their plain values."""
    return {attr["key"]: next(iter(attr["value"].values())) for attr in attributes}


def _exported_span(span: dict[str, Any]) -> ExportedSpan:
    status = span.get("status", {})
    return ExportedSpan(
        name=span["name"],
        attributes=plain_attributes(span.get("attributes", [])),
        trace_id=span["traceId"],
        span_id=span["spanId"],
        parent_span_id=span.get("parentSpanId"),
        kind=span.get("kind", ""),
        status_code=status.get("code", ""),
        status_message=status.get("message", ""),
        links=tuple((link["traceId"], link["spanId"]) for link in span.get("links", [])),
        events=tuple(event["name"] for event in span.get("events", [])),
    )


def _metric_points(metric: dict[str, Any]) -> list[tuple[dict[str, Any], float]]:
    data = (
        metric.get("sum")
        or metric.get("exponentialHistogram")
        or metric.get("histogram")
        or metric["gauge"]
    )
    return [
        (plain_attributes(point["attributes"]), point.get("asDouble", point.get("sum")))
        for point in data["dataPoints"]
    ]


def exported_metrics(payloads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The metrics of OTLP/JSON export requests; a request of another signal holds none."""
    return [
        metric
        for payload in payloads
        for resource in payload.get("resourceMetrics", [])
        for scope in resource["scopeMetrics"]
        for metric in scope["metrics"]
    ]


def metric_points(
    payloads: Iterable[dict[str, Any]], name: str
) -> list[tuple[dict[str, Any], float]]:
    """Each data point of the metric `name` in OTLP/JSON export requests, as (attributes, value)."""
    return [
        point
        for metric in exported_metrics(payloads)
        if metric["name"] == name
        for point in _metric_points(metric)
    ]


class FakeCollector:
    """An `OtlpExporter` that records each export request instead of sending it."""

    def __init__(self, endpoint: str = FAKE_COLLECTOR_ENDPOINT) -> None:
        self.endpoint = endpoint
        from devops_cli.telemetry.exporter import ProbeResult

        self.exports: list[Export] = []
        self._failure: str | None = None
        self._probe: ProbeResult = ProbeResult(True, "HTTP 200 OK")
        self._lock = threading.Lock()
        self._flush: Callable[[], None] = lambda: None

    # The OtlpExporter protocol.

    def export(self, signal: OtlpSignal, body: bytes, content_type: str) -> None:
        from devops_cli.exceptions.telemetry import OtlpExportError
        from devops_cli.telemetry.exporter import JSON_CONTENT_TYPE, OtlpSignal

        if self._failure is not None:
            raise OtlpExportError(self._failure)
        if content_type != JSON_CONTENT_TYPE:
            raise ValueError(f"The OTLP fake decodes {JSON_CONTENT_TYPE} only, not {content_type}")
        with self._lock:
            self.exports.append(Export(OtlpSignal(signal), json.loads(body)))

    def probe(self, timeout: float) -> ProbeResult:
        return self._probe

    def close(self) -> None:
        return None

    # How the collector answers.

    def answer(self, status_code: int) -> None:
        """Answer every export and probe with `status_code`, as a collector does."""
        from devops_cli.telemetry.exporter import ProbeResult, status_failure

        if 200 <= status_code < 300:
            self._failure = None
            self._probe = ProbeResult(True, f"HTTP {status_code} OK")
            return
        self._failure = status_failure(status_code)
        self._probe = ProbeResult(False, f"HTTP {status_code} probe failed")

    def refuse(self) -> None:
        """Refuse every connection, as a collector that does not run."""
        from devops_cli.telemetry.exporter import CONNECT_FAILED, PROBE_FAILED, ProbeResult

        self._failure = CONNECT_FAILED
        self._probe = ProbeResult(False, PROBE_FAILED)

    def accept(self) -> None:
        """Take every export again."""
        self.answer(200)

    # What the collector received.

    def client(self, **options: Any) -> OTelTelemetryClient:
        """An enabled telemetry client that exports to this fake; each read flushes it first."""
        from devops_cli.telemetry.tracer import OTelTelemetryClient

        client = OTelTelemetryClient(endpoint=self.endpoint, enabled=True, exporter=self, **options)
        self.flush_before_reads(client.flush)
        return client

    def flush_before_reads(self, flush: Callable[[], None]) -> None:
        """Call `flush` before each read, so a read sees every export queued before it."""
        self._flush = flush

    def payloads(self, signal: OtlpSignal) -> list[dict[str, Any]]:
        """The export requests of one signal, once the exports queued so far are done."""
        self._flush()
        with self._lock:
            return [export.payload for export in self.exports if export.signal == signal]

    @property
    def spans(self) -> list[ExportedSpan]:
        from devops_cli.telemetry.exporter import OtlpSignal

        return [
            _exported_span(span)
            for payload in self.payloads(OtlpSignal.TRACES)
            for resource in payload["resourceSpans"]
            for scope in resource["scopeSpans"]
            for span in scope["spans"]
        ]

    @property
    def metrics(self) -> list[dict[str, Any]]:
        from devops_cli.telemetry.exporter import OtlpSignal

        return exported_metrics(self.payloads(OtlpSignal.METRICS))

    def points(self, name: str) -> list[tuple[dict[str, Any], float]]:
        """Each data point of a metric, as (attributes, value)."""
        from devops_cli.telemetry.exporter import OtlpSignal

        return metric_points(self.payloads(OtlpSignal.METRICS), name)

    @property
    def log_records(self) -> list[dict[str, Any]]:
        from devops_cli.telemetry.exporter import OtlpSignal

        return [
            record
            for payload in self.payloads(OtlpSignal.LOGS)
            for resource in payload["resourceLogs"]
            for scope in resource["scopeLogs"]
            for record in scope["logRecords"]
        ]

    def clear(self) -> None:
        """Wait for the exports queued so far, and forget every export received."""
        self._flush()
        with self._lock:
            self.exports.clear()


@pytest.fixture
def otlp() -> Iterator[FakeCollector]:
    """The process's telemetry, exported with export on to a `FakeCollector` the test reads.

    `install_exporter` puts the fake in place of the configured exporter, so the tracer that
    `get_tracer()` builds, also after a `reset_tracer`, exports what `trace_span` and `emit`
    record to it. `remove_exporter` restores the configured exporter at teardown.
    """
    from devops_cli.telemetry.tracer import get_tracer, install_exporter, remove_exporter

    fake = FakeCollector()
    fake.flush_before_reads(lambda: get_tracer().flush())
    install_exporter(fake)
    yield fake
    remove_exporter()
