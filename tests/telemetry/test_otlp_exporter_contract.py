"""The OTLP fake against the real exporter (#1319).

Each case runs on `FakeCollector` and on `HttpOtlpExporter`. The real exporter posts to an
OTLP/HTTP receiver on a loopback port the test owns, or to `refusing_port` for a collector that
does not run. Both sides go through a telemetry client, so the tracer's success and failure
counts and its `last_export_error` are what the cases compare.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import SpanContext

from devops_cli.telemetry.exporter import (
    CONNECT_FAILED,
    JSON_CONTENT_TYPE,
    PROBE_FAILED,
    PROTOBUF_CONTENT_TYPE,
    HttpOtlpExporter,
    OtlpExporter,
    OtlpSignal,
    json_body,
)
from devops_cli.telemetry.tracer import OTelTelemetryClient
from tests.support.fakes.otlp import FakeCollector, decode_export

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID = "00f067aa0ba902b7"


class _Receiver(BaseHTTPRequestHandler):
    """Records each POST as (path, content type, decoded body) and answers the set status."""

    server: _ReceiverServer

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        self.server.received.append(
            (self.path, content_type, decode_export(OtlpSignal(self.path), body, content_type))
        )
        self.send_response(self.server.status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the receiver quiet."""


class _ReceiverServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Receiver)
        self.status = 200
        self.received: list[tuple[str, str, Any]] = []


@pytest.fixture
def receiver() -> Iterator[_ReceiverServer]:
    """The loopback OTLP/HTTP receiver the real exporter posts to."""
    server = _ReceiverServer()
    # A short poll, so `shutdown` returns at once at teardown.
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@dataclass
class Collector:
    """One side of the contract: an exporter, what its collector received, and its answers."""

    exporter: OtlpExporter
    received: Callable[[], list[tuple[str, Any]]]
    answer: Callable[[int], None]
    refuse: Callable[[], None]

    def client(self) -> OTelTelemetryClient:
        return OTelTelemetryClient(
            endpoint=self.exporter.endpoint, enabled=True, exporter=self.exporter
        )


def _fake_side() -> Collector:
    fake = FakeCollector()
    return Collector(
        exporter=fake,
        received=lambda: [(str(export.signal), export.payload) for export in fake.exports],
        answer=fake.answer,
        refuse=fake.refuse,
    )


def _real_side(receiver: _ReceiverServer, refusing_port: int) -> Collector:
    side = Collector(
        exporter=HttpOtlpExporter(f"http://127.0.0.1:{receiver.server_address[1]}"),
        received=lambda: [(path, payload) for path, _content_type, payload in receiver.received],
        answer=lambda status: setattr(receiver, "status", status),
        refuse=lambda: None,
    )

    def refuse() -> None:
        side.exporter = HttpOtlpExporter(f"http://127.0.0.1:{refusing_port}")

    side.refuse = refuse
    return side


@pytest.fixture(params=["fake", "real"])
def collector(request: pytest.FixtureRequest) -> Iterator[Collector]:
    if request.param == "fake":
        side = _fake_side()
    else:
        side = _real_side(
            request.getfixturevalue("receiver"), request.getfixturevalue("refusing_port")
        )
    yield side
    side.exporter.close()


def _export_one_span(client: OTelTelemetryClient) -> None:
    with client.span("contract_span"):
        pass
    client.flush()


@pytest.mark.parametrize("signal", list(OtlpSignal))
def test_the_collector_receives_each_request_on_its_signals_path(
    collector: Collector, signal: OtlpSignal
) -> None:
    """Verify the collector gets the request sent, on the path of its signal."""
    payload = {"case": signal.name, "values": [1, "two", True]}

    collector.exporter.export(signal, json_body(payload), JSON_CONTENT_TYPE)

    assert collector.received() == [(str(signal), payload)]


def _protobuf_trace_request() -> bytes:
    span = ReadableSpan(
        name="contract_span",
        context=SpanContext(int(TRACE_ID, 16), int(SPAN_ID, 16), is_remote=False),
        resource=Resource.create({"service.name": "contract"}),
        attributes={"case": "protobuf"},
        instrumentation_scope=InstrumentationScope("contract"),
    )
    return encode_spans([span]).SerializeToString()


def test_the_collector_receives_a_protobuf_trace_request_as_its_spans(
    collector: Collector,
) -> None:
    """Verify a protobuf trace request reaches the collector as the span it encodes."""
    body = _protobuf_trace_request()

    collector.exporter.export(OtlpSignal.TRACES, body, PROTOBUF_CONTENT_TYPE)

    [(path, payload)] = collector.received()
    [span] = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert (path, span["name"], span["traceId"], span["spanId"], span["attributes"]) == (
        str(OtlpSignal.TRACES),
        "contract_span",
        TRACE_ID,
        SPAN_ID,
        [{"key": "case", "value": {"stringValue": "protobuf"}}],
    )


@pytest.mark.parametrize("status", [200, 202])
def test_a_success_answer_counts_a_success(collector: Collector, status: int) -> None:
    """Verify a 2xx answer counts one success and records no error."""
    collector.answer(status)
    client = collector.client()

    _export_one_span(client)

    assert (client.export_successes, client.export_failures, client.last_export_error) == (
        1,
        0,
        "",
    )


@pytest.mark.parametrize(
    ("answer", "error"),
    [(404, "HTTP 404"), (503, "HTTP 503"), ("refused", CONNECT_FAILED)],
)
def test_a_refused_export_counts_a_failure_with_the_same_error(
    collector: Collector, answer: int | str, error: str
) -> None:
    """Verify a 4xx, a 5xx and a refused connection each count one failure, with one text."""
    if answer == "refused":
        collector.refuse()
    else:
        collector.answer(int(answer))
    client = collector.client()

    _export_one_span(client)

    assert (client.export_successes, client.export_failures, client.last_export_error) == (
        0,
        1,
        error,
    )


@pytest.mark.parametrize(
    ("answer", "reachable", "detail"),
    [
        (200, True, "HTTP 200 OK"),
        (503, False, "HTTP 503 probe failed"),
        ("refused", False, PROBE_FAILED),
    ],
)
def test_the_probe_reports_whether_the_collector_answers(
    collector: Collector, answer: int | str, reachable: bool, detail: str
) -> None:
    """Verify the probe of a reachable and of an unreachable collector."""
    if answer == "refused":
        collector.refuse()
    else:
        collector.answer(int(answer))

    ok, message, latency_ms = collector.client().test_connection(timeout=1.0)

    assert (ok, message, latency_ms >= 0) == (reachable, detail, True)
