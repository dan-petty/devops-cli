"""Unit tests for native Pydantic AI concurrency, limiters, and model-level concurrency controls."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.agents.pipeline import MultiAgentPipeline
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.concurrency import (
    AbstractConcurrencyLimiter,
    ConcurrencyLimit,
    ConcurrencyLimitedModel,
    ConcurrencyLimiter,
    ConcurrencyLimitExceeded,
    get_concurrency_context,
    get_model_concurrency_limiter,
    get_shared_concurrency_limiter,
    limit_model_concurrency,
    normalize_to_limiter,
    track_concurrency_slot,
)
from devops_cli.ai.personas import Persona
from devops_cli.ai.pydantic_ai_bridge import (
    create_pydantic_ai_agent,
    get_persona_pydantic_agent,
)


def test_concurrency_limiter_creation_and_attributes() -> None:
    """Verify ConcurrencyLimiter attributes, capacity, and representation."""
    limiter = ConcurrencyLimiter(max_running=3, max_queued=5, name="test-pool")
    assert isinstance(limiter, AbstractConcurrencyLimiter)
    assert limiter.max_running == 3
    assert limiter.name == "test-pool"
    assert limiter.waiting_count == 0
    assert limiter.running_count == 0
    assert limiter.available_count == 3


def test_concurrency_limit_from_limit_and_normalization() -> None:
    """Verify ConcurrencyLimit configuration and normalize_to_limiter helper."""
    assert normalize_to_limiter(None) is None

    limiter_int = normalize_to_limiter(4, name="int-pool")
    assert isinstance(limiter_int, ConcurrencyLimiter)
    assert limiter_int.max_running == 4

    cfg = ConcurrencyLimit(max_running=5, max_queued=10)
    assert cfg.max_running == 5
    assert cfg.max_queued == 10

    limiter_cfg = normalize_to_limiter(cfg, name="cfg-pool")
    assert isinstance(limiter_cfg, ConcurrencyLimiter)
    assert limiter_cfg.max_running == 5

    # Idempotent normalization
    assert normalize_to_limiter(limiter_cfg) is limiter_cfg


@pytest.mark.asyncio
async def test_concurrency_limit_exceeded_backpressure() -> None:
    """Verify that queue depth exceeding max_queued raises ConcurrencyLimitExceeded."""
    limiter = ConcurrencyLimiter(max_running=1, max_queued=0, name="strict-pool")

    async def worker(worker_id: int) -> int:
        await limiter.acquire(f"worker-{worker_id}")
        try:
            await asyncio.sleep(0.05)
            return worker_id
        finally:
            limiter.release()

    t1 = asyncio.create_task(worker(1))
    await asyncio.sleep(0.01)  # Allow worker 1 to acquire the only slot

    with pytest.raises(ConcurrencyLimitExceeded) as exc_info:
        await worker(2)

    assert "exceeds max_queued" in str(exc_info.value)
    await t1


@pytest.mark.asyncio
async def test_get_concurrency_context_manager() -> None:
    """Verify async context manager behavior with None and active limiter."""
    # None limiter produces a no-op context manager
    async with get_concurrency_context(None, source="noop"):
        pass

    limiter = ConcurrencyLimiter(max_running=2, name="context-test")
    assert limiter.running_count == 0

    async with get_concurrency_context(limiter, source="context-test"):
        assert limiter.running_count == 1

    assert limiter.running_count == 0

    async with track_concurrency_slot(limiter, source="slot-test"):
        assert limiter.running_count == 1

    assert limiter.running_count == 0


def test_limit_model_concurrency_wrapper() -> None:
    """Verify limit_model_concurrency wraps models with ConcurrencyLimitedModel."""
    test_model = TestModel(call_tools=[])

    # Passing None returns model unchanged
    unwrapped = limit_model_concurrency(test_model, None)
    assert unwrapped is test_model

    # Passing integer limit wraps model in ConcurrencyLimitedModel
    wrapped = limit_model_concurrency(test_model, 2)
    assert isinstance(wrapped, ConcurrencyLimitedModel)

    from pydantic_ai import Agent

    agent = Agent(wrapped)
    res = agent.run_sync("hello")
    assert res.output == "success (no tool calls)"


def test_shared_concurrency_limiter_registry() -> None:
    """Verify get_shared_concurrency_limiter returns singleton limiters by name."""
    lim1 = get_shared_concurrency_limiter("ollama:localhost:11434", max_running=3)
    lim2 = get_shared_concurrency_limiter("ollama:localhost:11434", max_running=3)
    assert lim1 is lim2
    assert lim1.max_running == 3

    model_lim = get_model_concurrency_limiter("gemma4:26b", default_max=4)
    assert model_lim.name == "model:gemma4:26b"
    assert model_lim.max_running == 4


def test_create_pydantic_ai_agent_with_concurrency() -> None:
    """Verify create_pydantic_ai_agent accepts max_concurrency and model_concurrency."""
    agent = create_pydantic_ai_agent(
        model_name="test",
        max_concurrency=2,
        model_concurrency=2,
    )
    assert agent is not None


def test_get_persona_pydantic_agent_with_concurrency() -> None:
    """Verify get_persona_pydantic_agent accepts concurrency configurations."""
    agent = get_persona_pydantic_agent(
        persona=Persona.DEVSECOPS,
        model_name="test",
        max_concurrency=3,
        model_concurrency=2,
    )
    assert agent is not None


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
