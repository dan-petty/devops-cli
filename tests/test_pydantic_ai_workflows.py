"""Tests for Pydantic AI structured workflows, prompt caching, and token governance."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from pydantic_ai import Agent, CachePoint
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage, UsageLimits

from devops_cli.ai.gateway import GatewayRouter
from devops_cli.ai.governance import TokenBucketGovernance, TokenBudgetConfig
from devops_cli.ai.pydantic_ai_bridge import (
    DevOpsAgentContext,
    _resolve_workflow_usage_limits,
    build_fallback_cascade_model,
    create_cached_user_prompt,
    execute_structured_workflow,
    execute_structured_workflow_sync,
    inject_prompt_cache_points,
    resolve_pydantic_ai_model,
)
from devops_cli.config.constants import (
    CONST_AI_PROMPT_CACHE_TTL_1H,
    CONST_AI_PROMPT_CACHE_TTL_5M,
)
from devops_cli.config.settings import AIConfig


def test_token_budget_config_conversion() -> None:
    """Validate TokenBudgetConfig properties and conversion to UsageLimits."""
    config = TokenBudgetConfig(
        input_tokens_limit=5000,
        output_tokens_limit=1000,
        total_tokens_limit=6000,
        request_limit=10,
        cost_limit=0.50,
        count_tokens_before_request=True,
    )
    limits = config.to_usage_limits()

    assert (
        limits.input_tokens_limit,
        limits.output_tokens_limit,
        limits.total_tokens_limit,
        limits.request_limit,
        limits.cost_limit,
        limits.count_tokens_before_request,
    ) == (
        5000,
        1000,
        6000,
        10,
        Decimal("0.5"),
        True,
    )


def test_token_bucket_governance_pacing_and_consumption() -> None:
    """Validate token bucket rate pacing, deficit calculation, and usage tracking."""
    governor = TokenBucketGovernance(capacity=1000, refill_rate=500.0)

    # Acquire permits within capacity
    delay1 = governor.acquire_token_permit(estimated_tokens=400)
    avail1 = governor.available_tokens()

    assert (delay1, round(avail1, -1)) == (0.0, 600.0)

    # Exceed capacity to trigger throttling delay
    delay2 = governor.acquire_token_permit(estimated_tokens=800)
    assert delay2 > 0.0

    # Record actual usage
    governor.record_token_usage(input_tokens=300, output_tokens=100, request_count=1)
    telemetry = governor.get_governance_telemetry()

    assert (
        telemetry["consumed_input_tokens"],
        telemetry["consumed_output_tokens"],
        telemetry["consumed_total_tokens"],
        telemetry["total_requests"],
    ) == (300, 100, 400, 1)

    # Record usage from a RunUsage object
    governor.record_run_usage(RunUsage(input_tokens=50, output_tokens=25, requests=2))
    assert (
        governor.consumed_input_tokens,
        governor.consumed_output_tokens,
        governor.consumed_total_tokens,
        governor.total_requests,
    ) == (350, 125, 475, 3)

    # Reset governor
    governor.reset()
    assert (
        governor.consumed_total_tokens,
        governor.total_requests,
        round(governor.tokens, -1),
    ) == (0, 0, 1000.0)


def test_inject_prompt_cache_points() -> None:
    """Verify CachePoint injection on strings and sequences."""
    # String input
    res_str = inject_prompt_cache_points("system instructions", ttl=CONST_AI_PROMPT_CACHE_TTL_5M)
    assert (len(res_str), res_str[0], isinstance(res_str[1], CachePoint)) == (
        2,
        "system instructions",
        True,
    )
    assert res_str[1].ttl == "5m"

    # Sequence input without CachePoint
    res_seq = inject_prompt_cache_points(["part1", "part2"], ttl=CONST_AI_PROMPT_CACHE_TTL_1H)
    assert (len(res_seq), res_seq[0], res_seq[1], res_seq[2].ttl) == (
        3,
        "part1",
        "part2",
        "1h",
    )

    # Sequence with existing CachePoint (idempotent)
    existing_cp = CachePoint(ttl="5m")
    res_existing = inject_prompt_cache_points(["part1", existing_cp])
    assert (len(res_existing), res_existing[1]) == (2, existing_cp)


def test_create_cached_user_prompt() -> None:
    """Verify construction of UserPromptPart with embedded cache points."""
    part_with_preamble = create_cached_user_prompt(
        prompt="Review this code",
        preamble="You are a reviewer",
        ttl=CONST_AI_PROMPT_CACHE_TTL_5M,
    )
    part_without_preamble = create_cached_user_prompt(
        prompt="Review this code",
        ttl=CONST_AI_PROMPT_CACHE_TTL_1H,
    )

    assert (
        isinstance(part_with_preamble, UserPromptPart),
        len(part_with_preamble.content),
        isinstance(part_without_preamble, UserPromptPart),
        len(part_without_preamble.content),
    ) == (True, 3, True, 2)


def test_build_fallback_cascade_model_and_runtime_failover() -> None:
    """Verify FallbackModel chaining and failover upon provider errors."""

    class FailingTestModel(TestModel):
        async def request(self, *args: Any, **kwargs: Any) -> Any:
            raise ModelHTTPError(status_code=503, model_name="test-fail", body="unavailable")

    m1 = FailingTestModel()
    m2 = TestModel(custom_output_text="Fallback succeeded")

    fb_model = build_fallback_cascade_model([m1, m2])
    assert isinstance(fb_model, FallbackModel)

    agent = Agent(model=fb_model)
    result = agent.run_sync("test prompt")
    assert (result.output, isinstance(result.usage, RunUsage)) == (
        "Fallback succeeded",
        True,
    )


def test_resolve_pydantic_ai_model_cascade() -> None:
    """Verify resolve_pydantic_ai_model supports cascade aliases and sequences."""
    m1 = TestModel()
    m2 = TestModel()
    cascade_model = resolve_pydantic_ai_model([m1, m2])
    assert isinstance(cascade_model, FallbackModel)

    single_model = resolve_pydantic_ai_model([m1])
    assert single_model == m1

    empty_model = resolve_pydantic_ai_model([])
    assert empty_model is None


def test_execute_structured_workflow_sync() -> None:
    """Verify synchronous structured workflow execution with governance tracking."""
    agent = Agent(model=TestModel(custom_output_text="Analysis complete"))
    governor = TokenBucketGovernance(capacity=5000, refill_rate=1000.0)
    budget = TokenBudgetConfig(request_limit=5)
    ctx = DevOpsAgentContext(governance=governor, budget=budget)

    result = execute_structured_workflow_sync(
        agent=agent,
        prompt="Evaluate architecture",
        deps=ctx,
    )

    assert (
        result.output,
        governor.total_requests >= 1,
        governor.consumed_total_tokens > 0,
    ) == ("Analysis complete", True, True)


@pytest.mark.asyncio
async def test_execute_structured_workflow_async() -> None:
    """Verify asynchronous structured workflow execution with governance tracking."""
    agent = Agent(model=TestModel(custom_output_text="Async complete"))
    governor = TokenBucketGovernance(capacity=5000, refill_rate=1000.0)
    budget = TokenBudgetConfig(request_limit=5)
    ctx = DevOpsAgentContext(governance=governor, budget=budget)

    result = await execute_structured_workflow(
        agent=agent,
        prompt="Evaluate security",
        deps=ctx,
    )

    assert (
        result.output,
        governor.total_requests >= 1,
        governor.consumed_total_tokens > 0,
    ) == ("Async complete", True, True)


def test_resolve_workflow_usage_limits() -> None:
    """Verify _resolve_workflow_usage_limits precedence across arguments."""
    budget = TokenBudgetConfig(input_tokens_limit=1000)
    ctx = DevOpsAgentContext(budget=budget)

    direct_limits = UsageLimits(input_tokens_limit=2000)
    resolved_direct = _resolve_workflow_usage_limits(direct_limits, ctx)
    resolved_budget = _resolve_workflow_usage_limits(budget, None)
    resolved_ctx = _resolve_workflow_usage_limits(None, ctx)
    resolved_none = _resolve_workflow_usage_limits(None, None)

    assert (
        resolved_direct.input_tokens_limit if resolved_direct else None,
        resolved_budget.input_tokens_limit if resolved_budget else None,
        resolved_ctx.input_tokens_limit if resolved_ctx else None,
        resolved_none,
    ) == (2000, 1000, 1000, None)


def test_llm_gateway_build_pydantic_cascade_model() -> None:
    """Verify GatewayRouter.build_pydantic_cascade_model creates a valid model."""
    gw = GatewayRouter(AIConfig())
    with patch("devops_cli.ai.pydantic_ai_bridge.resolve_pydantic_ai_model") as mock_resolve:
        mock_resolve.side_effect = lambda m, **kw: TestModel()
        model = gw.build_pydantic_cascade_model("devops-chat")
        assert isinstance(model, FallbackModel)
