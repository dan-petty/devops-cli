"""The tracer's queue of export payloads is bounded, and it counts what it drops (#4116).

The tracer hands each span and metric payload to two export threads. A collector that answers
slowly for hours left every payload waiting in an unbounded queue of the Service. With a cap, the
tracer keeps the newest-first payloads that fit, drops the rest and counts them.
"""

from __future__ import annotations

import threading

import pytest

from devops_cli.telemetry import tracer as tracer_module
from devops_cli.telemetry.tracer import OTelTelemetryClient
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

PAYLOADS = 1000
CAP = 16


class BlockedCollector:
    """An exporter whose exports wait until the test opens it, as a collector that does not
    answer."""

    endpoint = "http://otlp.example.com:4318"

    def __init__(self) -> None:
        self.opened = threading.Event()
        self.taken = 0
        self._lock = threading.Lock()

    def export(self, signal: object, body: bytes, content_type: str) -> None:
        self.opened.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        with self._lock:
            self.taken += 1

    def probe(self, timeout: float) -> object:
        raise NotImplementedError

    def close(self) -> None:
        return None


def test_a_collector_that_does_not_answer_leaves_at_most_the_cap_of_payloads_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the exporter blocked and 1000 payloads sent, the collector gets at most the cap once
    it answers, and the client counts every payload it dropped.

    `raising=False`: the base tree has no cap, so the replay of this test on the base fails on
    the payloads kept, not on the missing name.
    """
    monkeypatch.setattr(tracer_module, "DEFAULT_OTEL_EXPORT_QUEUE_MAX_PAYLOADS", CAP, raising=False)
    collector = BlockedCollector()
    client = OTelTelemetryClient(endpoint=collector.endpoint, enabled=True, exporter=collector)
    try:
        for number in range(PAYLOADS):
            client._send_payload("/v1/traces", {"resourceSpans": [], "number": number})
        collector.opened.set()
        client.flush()
    finally:
        collector.opened.set()
        client.shutdown()
    dropped = getattr(client, "export_dropped", None)
    assert (collector.taken, dropped) == (CAP, PAYLOADS - CAP)
