"""Tests for devops sandbox traces CLI command and distributed trace correlation."""

from __future__ import annotations

import json
from typing import Any

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
    build_span_waterfall_tree,
    clear_span_buffer,
    record_completed_span,
)
from devops_cli.telemetry.waterfall import (
    flatten_waterfall_tree,
    normalize_tempo_spans,
    render_waterfall_bar,
)
from tests.support.paths import FIXTURES


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


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


def test_normalize_tempo_spans() -> None:
    """Verify conversion of captured Tempo /api/v2/traces/{id} OTLP JSON into waterfall span tree."""
    fixture_path = FIXTURES / "traces" / "tempo-otlp-trace.json"
    tempo_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    spans = normalize_tempo_spans(tempo_payload)
    roots = build_span_waterfall_tree(spans)

    assert len(roots) == 1
    root = roots[0]
    child = root.children[0]
    assert (
        len(spans),
        root.trace_id,
        root.span_id,
        root.name,
        root.duration_ms,
        root.status_code,
        root.attributes,
        len(root.children),
        child.span_id,
        child.parent_id,
        child.name,
        child.duration_ms,
        child.status_code,
        child.status_message,
        child.depth,
        child.attributes,
    ) == (
        2,
        "4bf92f3577b34da6a3ce929d0e0e4736",
        "00f067aa0ba902b7",
        "cli.telemetry.profile",
        50.0,
        "STATUS_CODE_OK",
        {"cli.command": "telemetry profile", "http.status_code": 200},
        1,
        "b9c7c989f97918e1",
        "00f067aa0ba902b7",
        "cli.k8s.contexts",
        30.0,
        "STATUS_CODE_ERROR",
        "context check failed",
        1,
        {"k8s.namespace": "otel", "retry.enabled": True},
    )


def test_sandbox_traces_help(runner: CliRunner) -> None:
    """Verify devops sandbox traces --help output."""
    res = runner.invoke(app, ["traces", "--help"])
    assert res.exit_code == 0
    assert "traces" in res.output
    assert "--trace-id" in res.output
    assert "--last" in res.output
    assert "--probe" in res.output


def test_sandbox_traces_dry_run(runner: CliRunner) -> None:
    """Verify dry-run mode for devops sandbox traces."""
    res = runner.invoke(app, ["traces", "test-sandbox", "--dry-run"])
    assert res.exit_code == 0
    assert "Planned requests for devops sandbox traces" in res.output
    assert "http://tempo.monitoring.svc:3200/api/traces/<latest-trace-id>" in res.output


def test_sandbox_traces_with_buffered_spans(runner: CliRunner) -> None:
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


def test_sandbox_traces_json_output(runner: CliRunner) -> None:
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


def test_sandbox_traces_missing(runner: CliRunner) -> None:
    """Verify behavior when no trace spans are found."""
    clear_span_buffer()
    res = runner.invoke(app, ["traces", "--trace-id", "nonexistent_trace_999"])
    assert res.exit_code == 0
    assert "No telemetry spans recorded" in res.output


def test_sandbox_traces_last(runner: CliRunner) -> None:
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


def test_sandbox_traces_probe_flag(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_resolve_trace_spans_with_tempo_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_trace_spans retrieves spans from Tempo when not in memory buffer."""
    from devops_cli.telemetry.waterfall import resolve_trace_spans

    test_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    mock_spans = [{"traceId": test_trace_id, "name": "root"}]

    monkeypatch.setattr(
        "devops_cli.telemetry.waterfall.query_tempo_trace",
        lambda tid, tempo_url=None: mock_spans if tid == test_trace_id else [],
    )
    tid, spans = resolve_trace_spans(test_trace_id)
    assert tid == test_trace_id
    assert spans == mock_spans

    tid_unknown, spans_empty = resolve_trace_spans("00000000000000000000000000000000")
    assert tid_unknown == "00000000000000000000000000000000"
    assert spans_empty == []
