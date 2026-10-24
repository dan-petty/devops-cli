"""Unit tests for the concurrency limits the bridge, agent and pipeline hand to Pydantic AI."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.concurrency import ConcurrencyLimiter
from pydantic_ai.models.concurrency import ConcurrencyLimitedModel
from pydantic_ai.models.test import TestModel

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model


def test_resolve_pydantic_ai_model_limits_a_model_concurrency_only_when_asked() -> None:
    """Verify the bridge wraps a model in the concurrency limit it is given and no other."""
    test_model = TestModel(call_tools=[])

    unwrapped = resolve_pydantic_ai_model(test_model, model_concurrency=None)
    wrapped = resolve_pydantic_ai_model(test_model, model_concurrency=2)

    assert unwrapped is test_model
    assert isinstance(wrapped, ConcurrencyLimitedModel)
    assert Agent(wrapped).run_sync("hello").output == "success (no tool calls)"


@pytest.mark.asyncio
async def test_pydantic_agent_concurrency_run_async() -> None:
    """Verify PydanticAgent supports max_concurrency and run_async execution."""
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = "Async response content"
    mock_client.model = "test-model"

    agent: PydanticAgent[str] = PydanticAgent(
        client=mock_client,
        name="AsyncTester",
        max_concurrency=2,
    )
    assert agent.max_concurrency == 2
    assert agent._concurrency_limiter is not None

    res: AgentResponse[str] = await agent.run_async("Analyze concurrency logic")
    assert res.content == "Async response content"
    assert res.turns == 1


class MockResult(BaseModel):
    summary: str


@pytest.mark.asyncio
async def test_multi_agent_pipeline_concurrency_async() -> None:
    """Verify MultiAgentPipeline supports concurrency limits and run_parallel_async."""
    mock_client1 = MagicMock()
    mock_client1.chat_messages.return_value = '{"summary": "Agent 1 output"}'
    mock_client1.model = "test-model"

    mock_client2 = MagicMock()
    mock_client2.chat_messages.return_value = '{"summary": "Agent 2 output"}'
    mock_client2.model = "test-model"

    agent1: PydanticAgent[MockResult] = PydanticAgent(
        client=mock_client1,
        name="Agent1",
        output_type=MockResult,
    )
    agent2: PydanticAgent[MockResult] = PydanticAgent(
        client=mock_client2,
        name="Agent2",
        output_type=MockResult,
    )

    pipeline = MultiAgentPipeline[MockResult](
        agents=[agent1, agent2],
        output_schema=MockResult,
        concurrency_limit=2,
    )
    assert isinstance(pipeline.concurrency_limiter, ConcurrencyLimiter)
    assert pipeline.concurrency_limiter.max_running == 2

    res = await pipeline.run_parallel_async("Execute parallel inspection")
    assert len(res.steps) == 2
    assert res.final_data is not None
    assert "Agent" in res.final_data.summary
