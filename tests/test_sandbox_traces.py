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

    tp_unsampled = generate_traceparent(trace_flags="00")
    assert tp_unsampled.endswith("-00")

    with pytest.raises(ValueError, match="Invalid trace_flags"):
        generate_traceparent(trace_flags="02")

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
    test_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "traceID": test_trace_id,
                "spans": [
                    {
                        "traceID": test_trace_id,
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

    recorded: dict[str, Any] = {}

    class MockClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> MockClient:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, url: str, **kwargs: Any) -> Any:
            recorded["url"] = url
            recorded["kwargs"] = kwargs
            return mock_resp

    monkeypatch.setattr("httpx2.Client", MockClient)
    spans = query_jaeger_trace(test_trace_id, jaeger_url="http://example.com:16686")
    assert len(spans) == 1
    assert spans[0]["traceId"] == test_trace_id
    assert recorded["kwargs"].get("headers", {}).get("Host") == "example.com:16686"
    assert "example.com" not in recorded["url"]


def test_query_jaeger_trace_security_validation() -> None:
    """Verify query_jaeger_trace rejects invalid hex, path traversal, and disallowed URLs."""
    # Invalid trace IDs: path traversal, non-hex, empty
    assert query_jaeger_trace("../../admin") == []
    assert query_jaeger_trace("not-a-hex-id!") == []
    assert query_jaeger_trace("") == []

    # Invalid Jaeger URLs: invalid scheme, cloud metadata
    valid_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    assert query_jaeger_trace(valid_id, jaeger_url="ftp://example.com") == []
    assert query_jaeger_trace(valid_id, jaeger_url="http://169.254.169.254") == []
    assert query_jaeger_trace(valid_id, jaeger_url="http://10.0.0.1:16686") == []
    assert query_jaeger_trace(valid_id, jaeger_url="http://192.168.1.1:16686") == []
    assert query_jaeger_trace(valid_id, jaeger_url="http://172.16.0.1:16686") == []


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


def test_generate_traceparent_validation_error() -> None:
    """Verify generate_traceparent raises TraceValidationError on invalid trace flags."""
    from devops_cli.exceptions.validation import ValidationError
    from devops_cli.telemetry.context import TraceValidationError, generate_traceparent

    with pytest.raises(TraceValidationError) as exc_info:
        generate_traceparent(trace_flags="99")
    assert isinstance(exc_info.value, ValidationError)
    assert isinstance(exc_info.value, ValueError)
    assert "Invalid trace_flags" in str(exc_info.value)


def test_query_jaeger_trace_dns_metadata_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify query_jaeger_trace rejects hosts resolving to link-local metadata addresses."""
    import socket

    from devops_cli.telemetry.waterfall import query_jaeger_trace

    def mock_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 16686))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    spans = query_jaeger_trace(
        "0123456789abcdef0123456789abcdef",
        jaeger_url="http://example.com:16686",
    )
    assert spans == []


def test_is_blocked_metadata_host() -> None:
    """Verify _is_blocked_metadata_host flags link-local and private IPs while allowing loopback."""
    from devops_cli.telemetry.waterfall import _is_blocked_metadata_host

    assert _is_blocked_metadata_host("169.254.169.254") is True
    assert _is_blocked_metadata_host("10.0.0.1") is True
    assert _is_blocked_metadata_host("192.168.1.1") is True
    assert _is_blocked_metadata_host("127.0.0.1") is False
    assert _is_blocked_metadata_host("localhost") is False


def test_query_jaeger_trace_error_status_and_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify query_jaeger_trace returns empty list on HTTP non-200 and request errors."""
    import httpx2

    test_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

    # Test HTTP 500 error
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500

    class MockClient500:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> MockClient500:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, *args: Any, **kwargs: Any) -> Any:
            return mock_resp_500

    monkeypatch.setattr("httpx2.Client", MockClient500)
    assert query_jaeger_trace(test_trace_id, jaeger_url="http://localhost:16686") == []

    # Test network exception
    class MockClientError:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> MockClientError:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, *args: Any, **kwargs: Any) -> Any:
            raise httpx2.ConnectError("Connection refused")

    monkeypatch.setattr("httpx2.Client", MockClientError)
    assert query_jaeger_trace(test_trace_id, jaeger_url="http://localhost:16686") == []


def test_resolve_trace_spans_with_jaeger_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_trace_spans retrieves spans from Jaeger when not in memory buffer."""
    from devops_cli.telemetry.waterfall import resolve_trace_spans

    test_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    mock_spans = [{"traceId": test_trace_id, "name": "root"}]

    monkeypatch.setattr(
        "devops_cli.telemetry.waterfall.query_jaeger_trace",
        lambda tid, jaeger_url=None: mock_spans if tid == test_trace_id else [],
    )
    tid, spans = resolve_trace_spans(test_trace_id)
    assert tid == test_trace_id
    assert spans == mock_spans

    tid_unknown, spans_empty = resolve_trace_spans("00000000000000000000000000000000")
    assert tid_unknown == "00000000000000000000000000000000"
    assert spans_empty == []
