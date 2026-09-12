"""Tests for devops sandbox traces CLI command and distributed trace correlation."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.commands.sandbox import app
from devops_cli.sandbox.models import (
    EndpointProbeResult,
    ProbeProtocol,
    ProbeStatus,
    SandboxProbeReport,
)
from devops_cli.telemetry.context import (
    extract_traceparent,
    extract_traceparent_from_headers,
    generate_traceparent,
    inject_traceparent_headers,
)
from devops_cli.telemetry.tracer import (
    SpanWaterfallNode,
    clear_span_buffer,
    record_completed_span,
)
from devops_cli.telemetry.waterfall import (
    flatten_waterfall_tree,
    normalize_jaeger_spans,
    query_jaeger_trace,
    render_waterfall_bar,
)

runner = CliRunner()


def test_w3c_traceparent_generation_and_injection() -> None:
    """Verify traceparent generation, auto-injection into headers, and extraction."""
    tp = generate_traceparent()
    assert tp.startswith("00-")
    assert tp.endswith("-01")
    parsed = extract_traceparent(tp)
    assert parsed is not None
    assert len(parsed["trace_id"]) == 32
    assert len(parsed["parent_span_id"]) == 16

    headers = inject_traceparent_headers({"User-Agent": "devops-prober"}, auto_generate=True)
    assert "traceparent" in headers
    parsed_from_headers = extract_traceparent_from_headers(headers)
    assert parsed_from_headers is not None
    assert len(parsed_from_headers["trace_id"]) == 32


def test_render_waterfall_bar() -> None:
    """Verify visual waterfall bar rendering and coloring."""
    bar_short = render_waterfall_bar(0.0, 10.0, total_slots=20, is_error=False)
    assert "green" in bar_short
    assert "█" in bar_short

    bar_err = render_waterfall_bar(10.0, 50.0, total_slots=20, is_error=True)
    assert "red" in bar_err
    assert "█" in bar_err


def test_flatten_waterfall_tree() -> None:
    """Verify tree hierarchy flattening with correct indentation prefixes."""
    root = SpanWaterfallNode(
        span_id="s1",
        trace_id="t1",
        name="root",
        start_time_ns=1000,
        end_time_ns=2000,
        duration_ms=1.0,
        status_code="STATUS_CODE_OK",
        depth=0,
    )
    child = SpanWaterfallNode(
        span_id="s2",
        trace_id="t1",
        name="child",
        parent_id="s1",
        start_time_ns=1200,
        end_time_ns=1800,
        duration_ms=0.6,
        status_code="STATUS_CODE_OK",
        depth=1,
    )
    root.children.append(child)

    flattened = flatten_waterfall_tree([root])
    assert len(flattened) == 2
    assert flattened[0][0].name == "root"
    assert flattened[0][1] == ""
    assert flattened[1][0].name == "child"
    assert "└─" in flattened[1][1] or "├─" in flattened[1][1]


def test_normalize_jaeger_spans() -> None:
    """Verify conversion of Jaeger JSON response to OpenTelemetry span dictionaries."""
    jaeger_payload = {
        "data": [
            {
                "traceID": "4bf92f3577b34da6a3ce929d0e0e4736",
                "spans": [
                    {
                        "traceID": "4bf92f3577b34da6a3ce929d0e0e4736",
                        "spanID": "00f067aa0ba902b7",
                        "operationName": "HTTP GET /healthz",
                        "startTime": 1600000000000000,
                        "duration": 50000,
                        "tags": [
                            {"key": "http.status_code", "type": "int64", "value": 200},
                            {"key": "error", "type": "bool", "value": False},
                        ],
                        "references": [],
                    }
                ],
            }
        ]
    }
    spans = normalize_jaeger_spans(jaeger_payload)
    assert len(spans) == 1
    assert spans[0]["traceId"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert spans[0]["name"] == "HTTP GET /healthz"
    assert spans[0]["status"]["code"] == "STATUS_CODE_OK"


def test_query_jaeger_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify querying Jaeger REST API with HTTP response handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "traceID": "abc123trace",
                "spans": [
                    {
                        "traceID": "abc123trace",
                        "spanID": "span01",
                        "operationName": "GET /api/v1/health",
                        "startTime": 1000000,
                        "duration": 2000,
                        "tags": [],
                        "references": [],
                    }
                ],
            }
        ]
    }

    class MockClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> MockClient:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, url: str, **kwargs: Any) -> Any:
            return mock_resp

    monkeypatch.setattr("httpx2.Client", MockClient)
    spans = query_jaeger_trace("abc123trace", jaeger_url="http://example.com:16686")
    assert len(spans) == 1
    assert spans[0]["traceId"] == "abc123trace"


def test_sandbox_traces_help() -> None:
    """Verify devops sandbox traces --help output."""
    res = runner.invoke(app, ["traces", "--help"])
    assert res.exit_code == 0
    assert "traces" in res.output
    assert "--trace-id" in res.output
    assert "--last" in res.output
    assert "--probe" in res.output


def test_sandbox_traces_dry_run() -> None:
    """Verify dry-run mode for devops sandbox traces."""
    res = runner.invoke(app, ["traces", "test-sandbox", "--dry-run"])
    assert res.exit_code == 0
    assert "dry_run" in res.output.lower()
    assert "test-sandbox" in res.output


def test_sandbox_traces_with_buffered_spans() -> None:
    """Verify rendering trace waterfall when spans exist in the completed buffer."""
    clear_span_buffer()
    tid = "trace_buffered_999"
    record_completed_span(
        {
            "traceId": tid,
            "spanId": "root_1",
            "name": "sandbox.probe",
            "startTimeUnixNano": "1000000000",
            "endTimeUnixNano": "2000000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [{"key": "sandbox.target", "value": {"stringValue": "example.com:8080"}}],
        }
    )
    record_completed_span(
        {
            "traceId": tid,
            "spanId": "child_1",
            "parentSpanId": "root_1",
            "name": "http.get",
            "startTimeUnixNano": "1200000000",
            "endTimeUnixNano": "1700000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [
                {"key": "http.url", "value": {"stringValue": "http://example.com:8080/healthz"}}
            ],
        }
    )

    res = runner.invoke(app, ["traces", "--trace-id", tid])
    assert res.exit_code == 0
    assert "sandbox.probe" in res.output
    assert "http.get" in res.output
    assert "Trace Waterfall" in res.output


def test_sandbox_traces_json_output() -> None:
    """Verify JSON formatting of sandbox trace waterfall."""
    clear_span_buffer()
    tid = "trace_json_888"
    record_completed_span(
        {
            "traceId": tid,
            "spanId": "span_root",
            "name": "sandbox.probe.http",
            "startTimeUnixNano": "1000000000",
            "endTimeUnixNano": "1500000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [],
        }
    )

    res = runner.invoke(app, ["traces", "--trace-id", tid, "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["trace_id"] == tid
    assert data["span_count"] == 1
    assert "waterfall" in data
    assert data["waterfall"][0]["name"] == "sandbox.probe.http"


def test_sandbox_traces_missing() -> None:
    """Verify behavior when no trace spans are found."""
    clear_span_buffer()
    res = runner.invoke(app, ["traces", "--trace-id", "nonexistent_trace_999"])
    assert res.exit_code == 0
    assert "No telemetry spans recorded" in res.output


def test_sandbox_traces_last() -> None:
    """Verify --last fetches latest trace in buffer."""
    clear_span_buffer()
    tid = "trace_latest_777"
    record_completed_span(
        {
            "traceId": tid,
            "spanId": "span_last",
            "name": "probe.last",
            "startTimeUnixNano": "1000000000",
            "endTimeUnixNano": "1200000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [],
        }
    )

    res = runner.invoke(app, ["traces", "--last"])
    assert res.exit_code == 0
    assert "probe.last" in res.output


def test_sandbox_traces_probe_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops sandbox traces <target> --probe executes probe and visualizes waterfall."""
    clear_span_buffer()
    mock_report = SandboxProbeReport(
        target="http://example.com:8080",
        overall_status=ProbeStatus.PASS,
        total_probes=1,
        passed_probes=1,
        failed_probes=0,
        duration_seconds=0.05,
        trace_id="probed_trace_123",
        results=[
            EndpointProbeResult(
                protocol=ProbeProtocol.HTTP,
                target="http://example.com:8080/healthz",
                status=ProbeStatus.PASS,
                latency_ms=12.5,
                status_code=200,
                message="HTTP 200 OK",
                details={"trace_id": "probed_trace_123"},
            )
        ],
    )

    def mock_run_probes(*args: Any, **kwargs: Any) -> SandboxProbeReport:
        record_completed_span(
            {
                "traceId": "probed_trace_123",
                "spanId": "probe_span_01",
                "name": "sandbox.probe",
                "startTimeUnixNano": "1000000000",
                "endTimeUnixNano": "1100000000",
                "status": {"code": "STATUS_CODE_OK"},
                "attributes": [],
            }
        )
        return mock_report

    monkeypatch.setattr("devops_cli.sandbox.probe.run_sandbox_probes", mock_run_probes)
    res = runner.invoke(app, ["traces", "http://example.com:8080", "--probe"])
    assert res.exit_code == 0
    assert "sandbox.probe" in res.output
