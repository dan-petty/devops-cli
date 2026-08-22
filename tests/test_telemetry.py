"""Unit tests for OpenTelemetry tracer and metrics emitter."""

from __future__ import annotations

import pytest

from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    record_metric,
    trace_span,
)


def test_telemetry_disabled() -> None:
    client = OTelTelemetryClient(enabled=False)
    with client.span("test_span") as span_id:
        assert span_id == ""
    # Should not raise
    client.record_metric("test_metric", 1.0)


def test_telemetry_span_and_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_payloads: list[tuple[str, dict]] = []

    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with client.span("pipeline_stage", {"persona": "devsecops"}) as span_id:
        assert len(span_id) == 16  # 8 bytes hex = 16 hex chars
        client.record_metric("findings_count", 3, unit="1", attributes={"severity": "HIGH"})

    assert len(sent_payloads) == 2
    # First was metric
    assert sent_payloads[0][0] == "/v1/metrics"
    assert (
        sent_payloads[0][1]["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]["name"]
        == "findings_count"
    )

    # Second was trace span
    assert sent_payloads[1][0] == "/v1/traces"
    span_data = sent_payloads[1][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["name"] == "pipeline_stage"
    assert span_data["status"]["code"] == "STATUS_CODE_OK"


def test_telemetry_span_error_recording(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_payloads: list[tuple[str, dict]] = []

    client = OTelTelemetryClient(endpoint="http://localhost:4318", enabled=True)
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with pytest.raises(ValueError, match="simulated failure"):
        with client.span("failing_span"):
            raise ValueError("simulated failure")

    assert len(sent_payloads) == 1
    span_data = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span_data["status"]["code"] == "STATUS_CODE_ERROR"
    assert span_data["status"]["message"] == "simulated failure"


def test_global_trace_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    tracer = get_tracer()
    sent_payloads: list[tuple[str, dict]] = []
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    with trace_span("helper_span", {"env": "test"}):
        record_metric("helper_metric", 42.0)

    assert len(sent_payloads) == 2


def test_inject_and_extract_trace_context() -> None:
    client = OTelTelemetryClient(enabled=True)
    headers = client.inject_trace_context({"existing": "header"})
    assert "existing" in headers
    assert "traceparent" in headers
    assert headers["traceparent"].startswith("00-")

    trace_id, span_id = client.extract_trace_context(headers)
    assert trace_id is not None
    assert span_id is not None
    assert len(trace_id) == 32
    assert len(span_id) == 16


def test_traced_decorator(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.telemetry.tracer import traced

    client = get_tracer()
    sent_payloads: list[tuple[str, dict]] = []
    monkeypatch.setattr(client, "_send_payload", lambda path, p: sent_payloads.append((path, p)))

    @traced(name="decorated_func", attributes={"module": "test"})
    def my_function(x: int) -> int:
        return x * 2

    res = my_function(5)
    assert res == 10
    span_name = sent_payloads[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"]
    assert span_name == "decorated_func"


def test_test_connection_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    client = OTelTelemetryClient(enabled=True)
    mock_post = MagicMock(return_value=MagicMock(status_code=200, text="OK"))
    monkeypatch.setattr("httpx2.Client.post", mock_post)

    ok, msg, latency = client.test_connection(timeout=1.0)
    assert ok is True
    assert "HTTP 200 OK" in msg
    assert latency >= 0
