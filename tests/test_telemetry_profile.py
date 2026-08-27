"""Tests for OpenTelemetry trace waterfall visualizer and profiling CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from devops_cli.commands.telemetry import app
from devops_cli.telemetry.tracer import (
    build_span_waterfall_tree,
    clear_span_buffer,
    get_recent_spans,
    get_trace_spans,
    trace_span,
)

runner = CliRunner()


def test_build_span_waterfall_tree_structure() -> None:
    """Verify conversion of raw span dicts into hierarchy with correct offsets and depths."""
    clear_span_buffer()
    spans = [
        {
            "traceId": "trace123",
            "spanId": "root_span",
            "name": "cli.root",
            "startTimeUnixNano": "1000000000",
            "endTimeUnixNano": "2000000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [{"key": "service.name", "value": {"stringValue": "devops-cli"}}],
        },
        {
            "traceId": "trace123",
            "spanId": "child_span",
            "parentSpanId": "root_span",
            "name": "child.database",
            "startTimeUnixNano": "1200000000",
            "endTimeUnixNano": "1600000000",
            "status": {"code": "STATUS_CODE_OK"},
            "attributes": [{"key": "db.system", "value": {"stringValue": "sqlite"}}],
        },
    ]

    tree = build_span_waterfall_tree(spans)
    assert len(tree) == 1
    root = tree[0]
    assert root.name == "cli.root"
    assert root.depth == 0
    assert root.relative_offset_pct == 0.0
    assert root.relative_duration_pct == 100.0
    assert len(root.children) == 1

    child = root.children[0]
    assert child.name == "child.database"
    assert child.depth == 1
    assert child.relative_offset_pct == 20.0  # (1.2 - 1.0) / 1.0 * 100
    assert child.relative_duration_pct == 40.0  # (1.6 - 1.2) / 1.0 * 100
    assert child.attributes.get("db.system") == "sqlite"


def test_span_recording_buffer() -> None:
    """Verify that completed spans are captured in the in-memory ring buffer."""
    clear_span_buffer()
    with trace_span("test.buffer.span", attributes={"test.key": "val123"}):
        pass

    spans = get_recent_spans()
    assert len(spans) >= 1
    assert any(s.get("name") == "test.buffer.span" for s in spans)

    trace_spans = get_trace_spans(None)
    assert len(trace_spans) >= 1


def test_telemetry_profile_dry_run() -> None:
    """Verify dry-run execution of telemetry profile command."""
    result = runner.invoke(app, ["profile", "--dry-run"])
    assert result.exit_code == 0
    assert "PROFILED_DRY_RUN" in result.output or "profile_trace_waterfall" in result.output


def test_telemetry_profile_json_output() -> None:
    """Verify structured JSON output from telemetry profile."""
    clear_span_buffer()
    with trace_span("test.json.span", attributes={"op": "query"}):
        with trace_span("child.nested", attributes={"sub": 1}):
            pass

    result = runner.invoke(app, ["profile", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "trace_id" in data
    assert "waterfall" in data
    assert data["span_count"] >= 2
    assert len(data["waterfall"]) >= 1


def test_telemetry_profile_table_rendering() -> None:
    """Verify Rich table waterfall output formatting."""
    clear_span_buffer()
    with trace_span("profile.parent"):
        with trace_span("profile.child"):
            pass

    result = runner.invoke(app, ["profile"])
    assert result.exit_code == 0
    assert "Trace Waterfall Profile" in result.output
    assert "profile.parent" in result.output
    assert "profile.child" in result.output


def test_telemetry_profile_command_execution() -> None:
    """Verify that profiling a command executes it and captures its trace spans."""
    clear_span_buffer()
    result = runner.invoke(app, ["profile", "echo hello"])
    assert result.exit_code == 0
    assert "Profiling command" in result.output or "Trace Waterfall Profile" in result.output
