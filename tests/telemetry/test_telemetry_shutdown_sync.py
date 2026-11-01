"""Unit tests for OpenTelemetry client shutdown synchronization and thread joining."""

from __future__ import annotations

import logging
import threading
from typing import Any

import pytest

import devops_cli.telemetry.tracer as tr
from devops_cli.telemetry.logging_bridge import (
    attach_otel_logging_handler,
    detach_otel_logging_handler,
)
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    reset_tracer,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


def test_shutdown_joins_all_worker_threads(
    monkeypatch: pytest.MonkeyPatch, refusing_port: int
) -> None:
    """Verify shutdown waits for in-flight executor threads before returning."""
    initial_threads = {
        t for t in threading.enumerate() if t.name.startswith("devops-otel") and t.is_alive()
    }
    started = threading.Event()
    completed = threading.Event()
    finish = threading.Event()

    def slow_send(self: OTelTelemetryClient, path: str, payload: dict[str, Any]) -> None:
        started.set()
        finish.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        completed.set()

    monkeypatch.setattr(OTelTelemetryClient, "_send_payload_sync", slow_send)
    client = OTelTelemetryClient(endpoint=f"http://127.0.0.1:{refusing_port}", enabled=True)

    client._send_payload("/v1/traces", {"resourceSpans": []})
    assert started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    shutdown_thread = threading.Thread(target=client.shutdown, name="test-otel-shutdown")
    shutdown_thread.start()

    try:
        assert not completed.is_set()
        assert shutdown_thread.is_alive()
    finally:
        finish.set()
        shutdown_thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert not shutdown_thread.is_alive()
    assert completed.is_set()
    assert client._executor is None
    otel_threads = [
        t
        for t in threading.enumerate()
        if t.name.startswith("devops-otel") and t.is_alive() and t not in initial_threads
    ]
    assert otel_threads == []


def test_logging_handler_does_not_resurrect_tracer_when_none_is_active() -> None:
    """A log record emitted after reset_tracer must not instantiate a new global tracer."""
    reset_tracer()
    attach_otel_logging_handler()
    try:
        assert tr._GLOBAL_TRACER is None
        logging.getLogger("test.component").warning("Transient warning during teardown")
        assert tr._GLOBAL_TRACER is None
    finally:
        detach_otel_logging_handler()
