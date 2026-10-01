"""Tests for OpenTelemetry trace waterfall visualizer and profiling CLI."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
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


_TRACE = "0af7651916cd43dd8448eb211c80319c"


def _span(
    span_id: str, name: str, parent: str | None, start_ms: int, end_ms: int
) -> dict[str, object]:
    span: dict[str, object] = {
        "traceId": _TRACE,
        "spanId": span_id,
        "name": name,
        "startTimeUnixNano": start_ms * 1_000_000,
        "endTimeUnixNano": end_ms * 1_000_000,
    }
    if parent:
        span["parentSpanId"] = parent
    return span


def _profile_tracer(enabled: bool = True) -> MagicMock:
    tracer = MagicMock(enabled=enabled)
    tracer.current_trace_id = _TRACE
    return tracer


@pytest.fixture
def no_poll_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("devops_cli.commands.telemetry.DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS", 0.0)
    monkeypatch.setattr(
        "devops_cli.commands.telemetry.DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS", 0.0
    )


def test_profile_without_a_command_or_trace_exits_with_usage() -> None:
    """There is no sample trace to fall back on."""
    result = runner.invoke(app, ["profile"])
    assert (result.exit_code, "--trace-id" in result.output) == (2, True)


def test_profile_refuses_a_command_when_telemetry_export_is_off() -> None:
    with (
        patch("devops_cli.commands.telemetry.get_tracer", return_value=_profile_tracer(False)),
        patch("devops_cli.core.process.run_subprocess") as mock_run,
    ):
        result = runner.invoke(app, ["profile", "echo hello"])
    assert (result.exit_code, mock_run.called, "export is off" in result.output) == (1, False, True)


def test_profile_shows_the_child_spans_jaeger_recorded(no_poll_wait: None) -> None:
    """The child's spans come back from Jaeger under the trace the profile span handed it."""
    spans = [
        _span("a1", "telemetry.profile", None, 0, 40),
        _span("b2", "subprocess.devops", "a1", 1, 39),
        _span("c3", "child.k8s.contexts", "b2", 5, 30),
    ]
    with (
        patch("devops_cli.commands.telemetry.get_tracer", return_value=_profile_tracer()),
        patch(
            "devops_cli.core.process.run_subprocess",
            return_value=subprocess.CompletedProcess(["devops"], 0),
        ) as mock_run,
        patch("devops_cli.commands.telemetry.query_jaeger_trace", return_value=spans) as mock_query,
    ):
        result = runner.invoke(app, ["profile", "devops k8s contexts"])
    assert (
        result.exit_code,
        "child.k8s.contexts" in result.output,
        mock_query.call_args[0][0],
        mock_run.call_args.kwargs["isolate_env"],
    ) == (0, True, _TRACE, False)


def test_profile_output_follows_what_jaeger_holds(no_poll_wait: None) -> None:
    """Different spans in Jaeger give a different waterfall for the same trace."""
    first = [_span("a1", "first.span", None, 0, 10)]
    second = [_span("a1", "second.span", None, 0, 10)]
    with patch("devops_cli.commands.telemetry.query_jaeger_trace", side_effect=[first, first]):
        before = runner.invoke(app, ["profile", "--trace-id", _TRACE])
    with patch("devops_cli.commands.telemetry.query_jaeger_trace", side_effect=[second, second]):
        after = runner.invoke(app, ["profile", "--trace-id", _TRACE])
    assert (
        "first.span" in before.output,
        "second.span" in after.output,
        "first.span" in after.output,
    ) == (True, True, False)


def test_profile_waits_until_the_trace_stops_growing() -> None:
    """Spans reach Jaeger asynchronously, so a half-exported trace is read again."""
    from devops_cli.commands.telemetry import _read_trace_from_jaeger

    parent = _span("a1", "parent", None, 0, 10)
    child = _span("b2", "child", "a1", 1, 9)
    with (
        patch(
            "devops_cli.commands.telemetry.query_jaeger_trace",
            side_effect=[[], [parent], [parent, child], [parent, child]],
        ),
        patch("devops_cli.commands.telemetry.time.sleep"),
    ):
        spans = _read_trace_from_jaeger(_TRACE, "http://localhost:16686")
    assert [s["name"] for s in spans] == ["parent", "child"]


def test_profile_exits_non_zero_when_jaeger_has_no_spans(no_poll_wait: None) -> None:
    with patch("devops_cli.commands.telemetry.query_jaeger_trace", return_value=[]):
        result = runner.invoke(app, ["profile", "--trace-id", _TRACE])
    assert (result.exit_code, "check the collector" in result.output) == (1, True)


def test_profile_json_output(no_poll_wait: None) -> None:
    spans = [_span("a1", "root", None, 0, 20), _span("b2", "leaf", "a1", 2, 18)]
    with patch("devops_cli.commands.telemetry.query_jaeger_trace", return_value=spans):
        result = runner.invoke(app, ["profile", "--trace-id", _TRACE, "--json"])
    data = json.loads(result.output)
    assert (result.exit_code, data["trace_id"], data["span_count"]) == (0, _TRACE, 2)
