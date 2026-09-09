"""Unit and integration tests for Logfire Structured AI Observability Bridge."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.review import _init_logfire_if_enabled
from devops_cli.config.settings import Settings, get_logfire_token
from devops_cli.exceptions.telemetry import LogfireConfigurationError
from devops_cli.main import app
from devops_cli.telemetry.logfire import (
    AgentTurnHandle,
    LogfireBridge,
    LogfireOTelBridgeProcessor,
    LogfireStatus,
    get_logfire_bridge,
    logfire_agent_turn,
    render_agent_turn_panel,
    render_agent_turn_table,
    reset_logfire_bridge,
)
from devops_cli.telemetry.tracer import (
    build_span_waterfall_tree,
    clear_span_buffer,
    get_current_span_context,
    get_recent_spans,
    record_completed_span,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clean_logfire_state() -> Generator[None]:
    """Reset LogfireBridge and span buffers before and after each test."""
    reset_logfire_bridge()
    clear_span_buffer()
    yield
    reset_logfire_bridge()
    clear_span_buffer()


def test_logfire_status_model() -> None:
    """Validate LogfireStatus model serialization and defaults."""
    status = LogfireStatus(
        enabled=True,
        token_configured=True,
        send_to_logfire=True,
        active_spans_count=3,
        token_metrics={"input_tokens": 120, "output_tokens": 45, "total_tokens": 165},
        turns_count=2,
    )
    assert status.enabled is True
    assert status.token_configured is True
    assert status.send_to_logfire is True
    assert status.active_spans_count == 3
    assert status.token_metrics["total_tokens"] == 165
    assert status.turns_count == 2

    data = status.model_dump()
    assert data["turns_count"] == 2
    assert "token_metrics" in data


def test_logfire_bridge_configuration_with_token() -> None:
    """Verify LogfireBridge configuration with token provided via argument."""
    bridge = LogfireBridge()
    with (
        patch("logfire.configure") as mock_configure,
        patch("logfire.instrument_pydantic") as mock_pydantic,
        patch("logfire.instrument_pydantic_ai") as mock_pydantic_ai,
    ):
        bridge.configure(token="test-secret-token", send_to_logfire=True)
        assert bridge.is_active() is True
        mock_configure.assert_called_once()
        mock_pydantic.assert_called_once()
        mock_pydantic_ai.assert_called_once()

        status = bridge.get_status()
        assert status.enabled is True
        assert status.token_configured is True
        assert status.send_to_logfire is True


def test_logfire_bridge_configuration_without_token_fallback() -> None:
    """Verify LogfireBridge falls back gracefully to send_to_logfire=False when no token exists."""
    bridge = LogfireBridge()
    settings = Settings()
    settings.telemetry.logfire = True

    with (
        patch("logfire.configure") as mock_configure,
        patch("devops_cli.config.settings.get_keyring_secret", return_value=None),
        patch.dict("os.environ", {"LOGFIRE_TOKEN": "", "DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN": ""}),
    ):
        bridge.configure(settings=settings)
        assert bridge.is_active() is True
        mock_configure.assert_called_once()
        call_kwargs = mock_configure.call_args.kwargs
        assert (
            call_kwargs.get("send_to_logfire") is False
            or call_kwargs.get("send_to_logfire") == "if-token-present"
        )

        status = bridge.get_status()
        assert status.enabled is True
        assert status.token_configured is False


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


def test_logfire_agent_turn_recording_and_metrics() -> None:
    """Verify logfire_agent_turn context manager records turns, tokens, tools, and updates metrics."""
    bridge = get_logfire_bridge()
    bridge._enabled = True

    with patch("logfire.span") as mock_span, patch("logfire.metric_counter") as mock_metric:
        mock_span_ctx = MagicMock()
        mock_span.return_value.__enter__.return_value = mock_span_ctx

        with logfire_agent_turn(
            agent_name="devsecops",
            turn_index=1,
            prompt="Find path traversal vulnerabilities",
            model="ollama/qwen2.5-coder",
        ) as turn:
            assert isinstance(turn, AgentTurnHandle)
            turn.record_tool_call("scan_gitleaks", {"path": "src/"}, result={"findings": 0})
            turn.record_tokens(input_tokens=250, output_tokens=80)
            turn.set_response("No path traversal found.")

        assert mock_span.called
        assert mock_metric.called

        status = bridge.get_status()
        assert status.turns_count >= 1
        assert status.token_metrics["input_tokens"] == 250
        assert status.token_metrics["output_tokens"] == 80
        assert status.token_metrics["total_tokens"] == 330


def test_logfire_traceparent_propagation() -> None:
    """Verify get_current_span_context falls back to active OpenTelemetry context if ContextVar unset."""
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


def test_logfire_terminal_formatters() -> None:
    """Verify Rich table and panel formatters for agent turns."""
    turn_info: dict[str, Any] = {
        "agent_name": "architect",
        "turn_index": 2,
        "prompt": "Evaluate container network policies",
        "response": "Enforce default-deny network policy across pods.",
        "tools_called": ["k8s_pods", "k8s_status"],
        "token_usage": {"input_tokens": 300, "output_tokens": 120, "total_tokens": 420},
        "duration_ms": 142.5,
    }

    table = render_agent_turn_table(turn_info)
    assert table is not None

    panel = render_agent_turn_panel(turn_info)
    assert panel is not None


def test_logfire_cli_status_command() -> None:
    """Verify devops telemetry status displays Logfire status."""
    result = runner.invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Logfire" in result.output or "Telemetry" in result.output


def test_logfire_cli_subcommand_table_and_json() -> None:
    """Verify devops telemetry logfire command outputs table and json formats."""
    table_result = runner.invoke(app, ["telemetry", "logfire"])
    assert table_result.exit_code == 0
    assert "Logfire" in table_result.output

    json_result = runner.invoke(app, ["telemetry", "logfire", "--json"])
    assert json_result.exit_code == 0
    data = json.loads(json_result.output)
    assert "enabled" in data
    assert "token_configured" in data
    assert "token_metrics" in data


def test_logfire_cli_test_command_flag() -> None:
    """Verify devops telemetry test --logfire emits test span via Logfire bridge."""
    with patch("logfire.span") as mock_logfire_span:
        result = runner.invoke(app, ["telemetry", "test", "--logfire", "--name", "test-unit-span"])
        assert result.exit_code == 0
        assert "Test span emitted successfully" in result.output
        assert mock_logfire_span.called


def test_review_commands_support_logfire_flag() -> None:
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
    assert "telemetry_logfire_status" in tool_names

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
            bridge.configure(token="bad-token")
        assert "Failed to configure Logfire bridge" in str(exc_info.value)
        assert bridge.is_active() is False


def test_logfire_agent_turn_custom_attributes_and_span_exception() -> None:
    """Verify logfire_agent_turn passes custom attributes and handles span creation failure."""
    bridge = get_logfire_bridge()
    bridge._enabled = True

    # Custom attributes
    with patch("logfire.span") as mock_span:
        with logfire_agent_turn(
            agent_name="reviewer",
            turn_index=3,
            prompt="Check for bugs",
            attributes={"review.stage": "orchestrator", "custom.flag": True},
        ) as turn:
            assert turn.agent_name == "reviewer"
        mock_span.assert_called_once()
        call_kwargs = mock_span.call_args.kwargs
        assert call_kwargs.get("review.stage") == "orchestrator"
        assert call_kwargs.get("custom.flag") is True

    # logfire.span exception falls back to nullcontext
    with patch("logfire.span", side_effect=RuntimeError("span creation failed")):
        with logfire_agent_turn(
            agent_name="fallback-agent",
            turn_index=1,
            prompt="Fallback test",
        ) as turn:
            turn.record_tokens(10, 20)
            turn.set_response("Done without span.")
            assert turn.response == "Done without span."


def test_agent_turn_handle_without_span() -> None:
    """Verify AgentTurnHandle works correctly when span_handle is None."""
    handle = AgentTurnHandle(
        agent_name="standalone",
        turn_index=1,
        prompt="No span test",
        model="gpt-4",
        span_handle=None,
    )
    handle.record_tool_call("test_tool", {"arg": 1}, result="ok")
    handle.record_tokens(50, 25)
    handle.set_response("Completed.")
    handle.finalize()

    assert handle.tools_called == ["test_tool"]
    assert handle.total_tokens == 75
    assert handle.input_tokens == 50
    assert handle.output_tokens == 25
    assert handle.duration_ms >= 0


def test_get_logfire_token_resolution_order() -> None:
    """Verify token resolution order: keyring > DEVOPS_CLI env > settings config > LOGFIRE_TOKEN."""
    settings = Settings()

    # 1. Keyring takes precedence
    with (
        patch("devops_cli.config.settings._keyring_get", return_value="keyring-token"),
        patch.dict(
            "os.environ",
            {"DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN": "env-cli-token", "LOGFIRE_TOKEN": "env-token"},
        ),
    ):
        settings.telemetry.logfire_token = "config-token"
        assert get_logfire_token(settings) == "keyring-token"

    # 2. DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN
    with (
        patch("devops_cli.config.settings._keyring_get", return_value=None),
        patch.dict(
            "os.environ",
            {"DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN": "env-cli-token", "LOGFIRE_TOKEN": "env-token"},
        ),
    ):
        settings.telemetry.logfire_token = "config-token"
        assert get_logfire_token(settings) == "env-cli-token"

    # 3. settings.telemetry.logfire_token
    with (
        patch("devops_cli.config.settings._keyring_get", return_value=None),
        patch.dict(
            "os.environ", {"DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN": "", "LOGFIRE_TOKEN": "env-token"}
        ),
    ):
        settings.telemetry.logfire_token = "config-token"
        assert get_logfire_token(settings) == "config-token"

    # 4. Fallback to LOGFIRE_TOKEN
    with (
        patch("devops_cli.config.settings._keyring_get", return_value=None),
        patch.dict(
            "os.environ", {"DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN": "", "LOGFIRE_TOKEN": "env-token"}
        ),
    ):
        settings.telemetry.logfire_token = None
        assert get_logfire_token(settings) == "env-token"


def test_init_logfire_if_enabled_error_handling() -> None:
    """Verify _init_logfire_if_enabled propagates error when explicitly requested, suppresses when ambient."""
    settings = Settings()

    # Explicit flag logfire=True: exception must propagate
    with patch("devops_cli.telemetry.logfire.get_logfire_bridge") as mock_bridge:
        mock_bridge.return_value.configure.side_effect = LogfireConfigurationError(
            "Explicit config failure"
        )
        with pytest.raises(LogfireConfigurationError):
            _init_logfire_if_enabled(True, settings)

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
