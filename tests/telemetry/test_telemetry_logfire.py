"""Unit and integration tests for Logfire Structured AI Observability Bridge."""

from __future__ import annotations

import json
from unittest.mock import ANY, MagicMock, patch

import pytest
from opentelemetry.sdk.environment_variables import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT,
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
)
from typer.testing import CliRunner

from devops_cli.commands.review import _init_logfire_if_enabled
from devops_cli.config.settings import Settings
from devops_cli.exceptions.telemetry import LogfireConfigurationError
from devops_cli.main import app
from devops_cli.telemetry.logfire import (
    LogfireBridge,
    LogfireOTelBridgeProcessor,
    LogfireStatus,
)
from devops_cli.telemetry.tracer import (
    build_span_waterfall_tree,
    clear_span_buffer,
    get_current_span_context,
    get_recent_spans,
    record_completed_span,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_logfire_status_model() -> None:
    """Validate LogfireStatus model serialization and defaults."""
    status = LogfireStatus(enabled=True, active_spans_count=3)

    assert status.model_dump() == {"enabled": True, "active_spans_count": 3}


@pytest.mark.usefixtures("keyring_store")
def test_the_bridge_sends_nothing_to_logfire_cloud_also_with_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the bridge turns Logfire's cloud off and passes no token, also when one is set."""
    monkeypatch.setenv("LOGFIRE_TOKEN", "pylf_v1_us_example")
    bridge = LogfireBridge()

    with (
        patch("logfire.configure") as configure,
        patch("logfire.instrument_pydantic_ai") as instrument,
    ):
        bridge.configure(settings=Settings())

    kwargs = configure.call_args.kwargs
    assert (kwargs["send_to_logfire"], kwargs.get("token"), instrument.called) == (
        False,
        None,
        True,
    )
    assert bridge.get_status().model_dump() == {"enabled": True, "active_spans_count": ANY}


@pytest.mark.parametrize(
    "variable",
    [
        OTEL_EXPORTER_OTLP_ENDPOINT,
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
        OTEL_EXPORTER_OTLP_METRICS_ENDPOINT,
        OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
    ],
)
def test_the_bridge_refuses_to_start_when_logfire_would_add_its_own_exporter(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    """Verify the bridge does not configure Logfire while a variable names an OTLP endpoint."""
    monkeypatch.setenv(variable, "http://collector.example.com:4318")
    bridge = LogfireBridge()

    with (
        patch("logfire.configure") as configure,
        pytest.raises(LogfireConfigurationError, match=variable),
    ):
        bridge.configure(settings=Settings())

    assert (configure.called, bridge.is_active()) == (False, False)


def test_logfire_otel_bridge_processor_span_forwarding() -> None:
    """Verify LogfireOTelBridgeProcessor converts finished Logfire spans to internal tracer spans."""
    processor = LogfireOTelBridgeProcessor()

    mock_span = MagicMock()
    mock_span.name = "agent.test_step"
    mock_span.context.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
    mock_span.context.span_id = 0x1122334455667788
    mock_span.parent = None
    mock_span.start_time = 1_700_000_000_000_000_000
    mock_span.end_time = 1_700_000_000_050_000_000
    mock_span.attributes = {"agent.name": "architect", "step": 1}
    mock_span.status.status_code.name = "OK"

    processor.on_end(mock_span)

    spans = get_recent_spans()[:10]
    assert len(spans) >= 1
    matched = [s for s in spans if s.get("name") == "agent.test_step"]
    assert len(matched) == 1
    record = matched[0]
    assert record["name"] == "agent.test_step"
    assert record["traceId"] == format(0x1234567890ABCDEF1234567890ABCDEF, "032x")
    assert record["spanId"] == format(0x1122334455667788, "016x")
    assert isinstance(record["attributes"], list)
    assert any(a.get("key") == "agent.name" for a in record["attributes"])

    nodes = build_span_waterfall_tree([record])
    assert len(nodes) == 1
    assert nodes[0].attributes.get("agent.name") == "architect"
    assert nodes[0].attributes.get("step") == 1


def test_logfire_traceparent_propagation() -> None:
    """Verify get_current_span_context reads the span of the OpenTelemetry API context."""
    with patch("opentelemetry.trace.get_current_span") as mock_get_span:
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
        mock_ctx.span_id = 0xBBBBBBBBBBBBBBBB
        mock_span.get_span_context.return_value = mock_ctx
        mock_get_span.return_value = mock_span

        ctx = get_current_span_context()
        assert ctx["trace_id"] == format(0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA, "032x")
        assert ctx["span_id"] == format(0xBBBBBBBBBBBBBBBB, "016x")


def test_logfire_cli_status_command(runner: CliRunner) -> None:
    """Verify devops telemetry status displays Logfire status."""
    result = runner.invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Logfire" in result.output or "Telemetry" in result.output


def test_logfire_cli_subcommand_table_and_json(runner: CliRunner) -> None:
    """Verify devops telemetry logfire command outputs table and json formats."""
    table_result = runner.invoke(app, ["telemetry", "logfire"])
    assert table_result.exit_code == 0
    assert "Logfire" in table_result.output

    json_result = runner.invoke(app, ["telemetry", "logfire", "--json"])
    assert json_result.exit_code == 0
    data = json.loads(json_result.output)
    assert set(data) == {"enabled", "active_spans_count"}


def test_review_commands_support_logfire_flag(runner: CliRunner) -> None:
    """Verify devops review path/branch/pr commands expose --logfire and --no-logfire."""
    for cmd in ["path", "branch", "pr"]:
        result = runner.invoke(app, ["review", cmd, "--help"])
        assert result.exit_code == 0
        assert "--logfire" in result.output
        assert "--no-logfire" in result.output


def test_logfire_fastmcp_tool_and_resource() -> None:
    """Verify FastMCP tool telemetry_logfire_status and resource://telemetry/logfire."""
    import asyncio

    from devops_cli.ai.mcp.server import list_mcp_tools, mcp

    tool_names = {t.name for t in list_mcp_tools()}
    assert "telemetry_logfire" in tool_names

    resources = asyncio.run(mcp.list_resources())
    resource_uris = {str(r.uri) for r in resources}
    assert "resource://telemetry/logfire" in resource_uris


def test_logfire_otel_bridge_processor_edge_cases() -> None:
    """Verify processor handles missing context, invalid IDs, parent spans, and flush/shutdown."""
    processor = LogfireOTelBridgeProcessor()

    # None context
    mock_span_no_ctx = MagicMock()
    mock_span_no_ctx.context = None
    processor.on_end(mock_span_no_ctx)

    # Missing trace_id or span_id
    mock_span_no_ids = MagicMock()
    mock_span_no_ids.context.trace_id = None
    mock_span_no_ids.context.span_id = None
    processor.on_end(mock_span_no_ids)

    # Parent span
    mock_span_parent = MagicMock()
    mock_span_parent.name = "child.span"
    mock_span_parent.context.trace_id = 0x11111111111111111111111111111111
    mock_span_parent.context.span_id = 0x2222222222222222
    mock_parent = MagicMock()
    mock_parent.span_id = 0x3333333333333333
    mock_span_parent.parent = mock_parent
    mock_span_parent.status.status_code.name = "OK"
    mock_span_parent.attributes = {"key": "val"}
    processor.on_end(mock_span_parent)

    records = [s for s in get_recent_spans() if s.get("name") == "child.span"]
    assert len(records) == 1
    assert records[0]["parentSpanId"] == format(0x3333333333333333, "016x")

    # Exception during processing
    with patch(
        "devops_cli.telemetry.logfire.record_completed_span", side_effect=RuntimeError("boom")
    ):
        processor.on_end(mock_span_parent)

    # Shutdown, force_flush, and on_start
    processor.on_start(mock_span_parent)
    processor.shutdown()
    assert processor.force_flush() is True


def test_logfire_bridge_flush_and_shutdown() -> None:
    """Verify LogfireBridge flush and shutdown behavior when enabled and disabled."""
    bridge = LogfireBridge()

    # Disabled - should be no-ops
    bridge.flush()
    bridge.shutdown()
    assert bridge.is_active() is False

    # Enabled with active flush/shutdown
    bridge._enabled = True
    with (
        patch("logfire.force_flush") as mock_flush,
        patch("logfire.shutdown") as mock_shutdown,
    ):
        bridge.flush()
        mock_flush.assert_called_once()

        bridge.shutdown()
        mock_shutdown.assert_called_once()
        assert bridge.is_active() is False

    # Enabled with exceptions handled gracefully
    bridge._enabled = True
    with (
        patch("logfire.force_flush", side_effect=RuntimeError("flush failed")),
        patch("logfire.shutdown", side_effect=RuntimeError("shutdown failed")),
    ):
        bridge.flush()
        bridge.shutdown()
        assert bridge.is_active() is False


def test_logfire_bridge_configure_exception_raises_logfire_configuration_error() -> None:
    """Verify bridge.configure raises LogfireConfigurationError on configuration failure."""
    bridge = LogfireBridge()
    with patch("logfire.configure", side_effect=RuntimeError("Logfire initialization error")):
        with pytest.raises(LogfireConfigurationError) as exc_info:
            bridge.configure(settings=Settings())
        assert "Failed to configure Logfire bridge" in str(exc_info.value)
        assert bridge.is_active() is False


def test_init_logfire_if_enabled_error_handling() -> None:
    """Verify _init_logfire_if_enabled propagates error when explicitly requested, suppresses when ambient."""
    settings = Settings()

    # Explicit flag logfire=True: exception must propagate
    with patch("devops_cli.telemetry.logfire.get_logfire_bridge") as mock_bridge:
        mock_bridge.return_value.configure.side_effect = LogfireConfigurationError(
            "Explicit config failure"
        )
        with pytest.raises(LogfireConfigurationError) as raised:
            _init_logfire_if_enabled(True, settings)
        assert raised.value.error_code == "LOGFIRE_CONFIG_ERROR"

    # Ambient logfire=None but settings.telemetry.logfire=True: exception must be suppressed
    settings.telemetry.logfire = True
    with patch("devops_cli.telemetry.logfire.get_logfire_bridge") as mock_bridge:
        mock_bridge.return_value.configure.side_effect = LogfireConfigurationError(
            "Ambient config failure"
        )
        # Should not raise
        _init_logfire_if_enabled(None, settings)


def test_logfire_bridge_status_reports_all_active_spans() -> None:
    """Verify LogfireBridge.get_status().active_spans_count counts the full span buffer beyond 100 spans."""
    bridge = LogfireBridge()
    # Insert 150 dummy spans into buffer
    clear_span_buffer()
    for i in range(150):
        record_completed_span(
            {"name": f"span-{i}", "spanId": f"{i:016x}", "traceId": "0" * 32, "attributes": []}
        )

    status = bridge.get_status()
    assert status.active_spans_count == 150
