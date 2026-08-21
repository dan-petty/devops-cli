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
