"""Unit tests for native Pydantic AI result subsystem integration."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from pydantic import BaseModel

from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.result import (
    AgentStream,
    AgentStreamEvent,
    FinalResult,
    OutputSchema,
    OutputValidator,
    RunUsage,
    StreamedRunResult,
    StreamedRunResultSync,
    SyncStreamBridge,
    TextOutputSchema,
    best_effort_price,
    calculate_usage_cost,
    create_run_usage,
    to_agent_response,
    to_final_result,
)


class SampleReviewData(BaseModel):
    """Sample structured model for testing result wrappers."""

    summary: str
    risk_score: int


class TestPydanticAIResultSubsystem:
    """Test suite for native Pydantic AI result subsystem."""

    def test_core_classes_and_type_exports(self) -> None:
        """Verify core pydantic_ai.result classes and protocols are exposed."""
        assert RunUsage is not None
        assert FinalResult is not None
        assert StreamedRunResult is not None
        assert StreamedRunResultSync is not None
        assert SyncStreamBridge is not None
        assert OutputValidator is not None
        assert OutputSchema is not None
        assert TextOutputSchema is not None
        assert AgentStream is not None
        assert AgentStreamEvent is not None
        assert callable(best_effort_price)

    def test_create_run_usage(self) -> None:
        """Verify create_run_usage constructs a valid RunUsage instance."""
        usage = create_run_usage(input_tokens=1500, output_tokens=300, requests=2, tool_calls=4)
        assert isinstance(usage, RunUsage)
        assert usage.input_tokens == 1500
        assert usage.output_tokens == 300
        assert usage.total_tokens == 1800
        assert usage.requests == 2
        assert usage.tool_calls == 4

        otel = usage.opentelemetry_attributes()
        assert otel.get("gen_ai.usage.input_tokens") == 1500
        assert otel.get("gen_ai.usage.output_tokens") == 300

    def test_calculate_usage_cost_with_best_effort_price(self) -> None:
        """Test calculation of financial cost using native best_effort_price."""
        usage = create_run_usage(input_tokens=10000, output_tokens=2000)
        cost_calc = calculate_usage_cost(usage, model_name="gpt-4o")
        assert cost_calc is not None
        assert hasattr(cost_calc, "total_price")
        assert isinstance(cost_calc.total_price, Decimal)
        assert cost_calc.total_price > Decimal("0.0")

        # Unknown model returns None gracefully
        unknown_cost = calculate_usage_cost(usage, model_name="unknown-custom-model-999")
        assert unknown_cost is None

    def test_to_final_result_helper(self) -> None:
        """Test creating a FinalResult container."""
        data = SampleReviewData(summary="Clean code", risk_score=1)
        res = to_final_result(data, tool_name="review_validator", tool_call_id="call_123")
        assert isinstance(res, FinalResult)
        assert res.output == data
        assert res.tool_name == "review_validator"
        assert res.tool_call_id == "call_123"

    def test_to_agent_response_from_final_result(self) -> None:
        """Test converting a FinalResult to typed AgentResponse."""
        data = SampleReviewData(summary="Secure", risk_score=0)
        final_res = FinalResult(output=data, tool_name="review_tool")
        resp = to_agent_response(final_res)

        assert isinstance(resp, AgentResponse)
        assert resp.data == data
        assert "Secure" in resp.content

    def test_to_agent_response_from_agent_run_result(self) -> None:
        """Test converting a native AgentRunResult mock to AgentResponse."""
        mock_result = MagicMock()
        mock_result.output = SampleReviewData(summary="Passed gate", risk_score=2)
        mock_result.usage = MagicMock(input_tokens=500, output_tokens=100, total_tokens=600)
        mock_result.response = MagicMock(model_name="openai:gpt-4o")
        mock_result.all_messages.return_value = [
            MagicMock(role="user", content="Review this"),
            MagicMock(role="model", content="Passed gate"),
        ]
        mock_result.new_messages.return_value = [
            MagicMock(role="model", content="Passed gate"),
        ]

        resp = to_agent_response(mock_result)
        assert isinstance(resp, AgentResponse)
        assert isinstance(resp.data, SampleReviewData)
        assert resp.data.summary == "Passed gate"
        assert resp.usage.input_tokens == 500
        assert resp.usage.output_tokens == 100
        assert resp.backend_info == "openai:gpt-4o"

    def test_agent_response_run_usage_property(self) -> None:
        """Verify AgentResponse.run_usage returns native RunUsage."""
        resp = AgentResponse[str](
            content="Done",
            turns=3,
        )
        resp.usage.input_tokens = 800
        resp.usage.output_tokens = 200
        resp.usage.total_tokens = 1000

        run_u = resp.run_usage
        assert isinstance(run_u, RunUsage)
        assert run_u.input_tokens == 800
        assert run_u.output_tokens == 200
        assert run_u.total_tokens == 1000
        assert run_u.requests == 3

    def test_agent_response_to_final_result(self) -> None:
        """Verify AgentResponse.to_final_result creates FinalResult."""
        data = SampleReviewData(summary="Verified", risk_score=1)
        resp = AgentResponse[SampleReviewData](
            content=str(data),
            data=data,
        )
        final_res = resp.to_final_result()
        assert isinstance(final_res, FinalResult)
        assert final_res.output == data

    def test_package_reexports(self) -> None:
        """Verify result classes and functions are cleanly re-exported across public tiers."""
        import devops_cli.ai as ai_pkg
        import devops_cli.ai.agents as agents_pkg
        import devops_cli.ai.agents.pydantic_agent as pa_module

        for mod in (ai_pkg, agents_pkg, pa_module):
            assert hasattr(mod, "RunUsage")
            assert hasattr(mod, "FinalResult")
            assert hasattr(mod, "StreamedRunResult")
            assert hasattr(mod, "StreamedRunResultSync")
            assert hasattr(mod, "best_effort_price")
            assert hasattr(mod, "create_run_usage")
            assert hasattr(mod, "calculate_usage_cost")
            assert hasattr(mod, "to_agent_response")
