"""Unit tests for the native Pydantic AI Run subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.run import (
    AgentRun,
    AgentRunResult,
    AgentRunResultEvent,
    BaseNode,
    End,
    EndMarker,
    ErrorMarker,
    GraphRun,
    GraphRunContext,
    GraphTaskRequest,
    JoinItem,
    NodeStep,
    PendingMessage,
    create_pending_message,
    current_otel_traceparent,
    format_run_summary,
    get_active_traceparent,
)


class TestPydanticAIRunSubsystem:
    """Validate native Pydantic AI run integration, results, and traceparent propagation."""

    def test_core_classes_and_type_exports(self) -> None:
        """Verify core types, classes, and markers are exported correctly."""
        assert AgentRun is not None
        assert AgentRunResult is not None
        assert AgentRunResultEvent is not None
        assert BaseNode is not None
        assert End is not None
        assert EndMarker is not None
        assert ErrorMarker is not None
        assert GraphRun is not None
        assert GraphRunContext is not None
        assert GraphTaskRequest is not None
        assert JoinItem is not None
        assert NodeStep is not None
        assert PendingMessage is not None
        assert callable(current_otel_traceparent)
        assert callable(get_active_traceparent)
        assert callable(create_pending_message)
        assert callable(format_run_summary)

    def test_create_pending_message(self) -> None:
        """Verify create_pending_message builds native PendingMessage instances."""
        msg_idle = create_pending_message("Please review the findings", priority="when_idle")
        assert isinstance(msg_idle, PendingMessage)
        assert msg_idle.priority == "when_idle"

        msg_asap = create_pending_message("Emergency halt requested", priority="asap")
        assert isinstance(msg_asap, PendingMessage)
        assert msg_asap.priority == "asap"

    def test_get_active_traceparent(self) -> None:
        """Verify get_active_traceparent returns string or None depending on active span."""
        tp = get_active_traceparent()
        assert tp is None or isinstance(tp, str)

    def test_format_run_summary(self) -> None:
        """Verify format_run_summary extracts structured metadata from an AgentRunResult."""
        now = datetime.now(UTC)
        mock_result = MagicMock()
        mock_result.run_id = "run-12345"
        mock_result.conversation_id = "conv-abcde"
        mock_result.timestamp = now
        mock_result.output = "Review completed successfully"
        mock_result.usage = MagicMock(input_tokens=150, output_tokens=50, total_tokens=200)
        mock_result._traceparent_value = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

        summary = format_run_summary(mock_result)
        assert summary["run_id"] == "run-12345"
        assert summary["conversation_id"] == "conv-abcde"
        assert summary["timestamp"] == now.isoformat()
        assert summary["output"] == "Review completed successfully"
        assert summary["usage"]["total_tokens"] == 200
        assert summary["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    def test_agent_response_from_run_result_with_run_metadata(self) -> None:
        """Verify AgentResponse.from_run_result extracts run metadata and traceparent."""
        mock_result = MagicMock()
        mock_result.output = "Security scan passed"
        mock_result.usage = MagicMock(input_tokens=250, output_tokens=75, total_tokens=325)
        mock_result.response = MagicMock(model_name="openai:gpt-4o")
        mock_result.run_id = "run-999"
        mock_result.conversation_id = "conv-888"
        mock_result.all_messages.return_value = []
        mock_result.new_messages.return_value = []

        resp = AgentResponse.from_run_result(mock_result)
        assert resp.content == "Security scan passed"
        assert resp.backend_info == "openai:gpt-4o"
        assert resp.usage.input_tokens == 250
        assert resp.usage.output_tokens == 75

    def test_package_reexports(self) -> None:
        """Verify run symbols are re-exported across package tiers."""
        import devops_cli.ai
        import devops_cli.ai.agents
        import devops_cli.ai.agents.pydantic_agent

        for pkg in (
            devops_cli.ai,
            devops_cli.ai.agents,
            devops_cli.ai.agents.pydantic_agent,
        ):
            assert hasattr(pkg, "AgentRun")
            assert hasattr(pkg, "AgentRunResult")
            assert hasattr(pkg, "AgentRunResultEvent")
            assert hasattr(pkg, "BaseNode")
            assert hasattr(pkg, "End")
            assert hasattr(pkg, "EndMarker")
            assert hasattr(pkg, "ErrorMarker")
            assert hasattr(pkg, "GraphRun")
            assert hasattr(pkg, "GraphRunContext")
            assert hasattr(pkg, "GraphTaskRequest")
            assert hasattr(pkg, "JoinItem")
            assert hasattr(pkg, "NodeStep")
            assert hasattr(pkg, "PendingMessage")
            assert hasattr(pkg, "current_otel_traceparent")
            assert hasattr(pkg, "get_active_traceparent")
            assert hasattr(pkg, "create_pending_message")
            assert hasattr(pkg, "format_run_summary")
