"""Unit tests for Pydantic AI Spend and budget management capabilities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devops_cli.ai.agents import (
    BudgetExceededError,
    ModelPricing,
    RunContext,
    Spend,
    SpendGuard,
    SpendUsage,
)


def test_model_pricing_cost_calculation() -> None:
    """Verify ModelPricing USD calculation across token boundaries."""
    pricing = ModelPricing(prompt_usd_per_million=3.00, completion_usd_per_million=15.00)

    # 10,000 prompt tokens = $0.03, 2,000 completion tokens = $0.03
    cost = pricing.calculate_cost(prompt_tokens=10_000, completion_tokens=2_000)
    assert cost == 0.06

    # Zero tokens = $0.00
    assert pricing.calculate_cost(0, 0) == 0.0


def test_spend_usage_accumulation() -> None:
    """Verify SpendUsage token and cost aggregation."""
    usage = SpendUsage()
    usage.add(prompt_tokens=1000, completion_tokens=500, cost_usd=0.015)
    assert usage.prompt_tokens == 1000
    assert usage.completion_tokens == 500
    assert usage.total_tokens == 1500
    assert usage.total_usd == 0.015
    assert usage.turn_count == 1

    usage.add(prompt_tokens=2000, completion_tokens=1000, cost_usd=0.03)
    assert usage.prompt_tokens == 3000
    assert usage.total_tokens == 4500
    assert usage.total_usd == 0.045
    assert usage.turn_count == 2


def test_spend_guard_budget_limits_and_errors() -> None:
    """Verify SpendGuard limit checking for USD, tokens, and turns."""
    spend = SpendGuard(max_usd=0.05, max_tokens=10_000, max_turns=3)

    # 1. Under budget succeeds
    cost1 = spend.record_usage("gpt-4o", prompt_tokens=2_000, completion_tokens=500)
    assert cost1 > 0.0
    assert spend.usage.total_usd <= 0.05

    # 2. Exceeding token limit raises BudgetExceededError
    spend_token_limit = SpendGuard(max_tokens=1000)
    with pytest.raises(BudgetExceededError, match="Token budget limit exceeded"):
        spend_token_limit.record_usage("gpt-4o", prompt_tokens=800, completion_tokens=300)

    # 3. Exceeding USD budget raises BudgetExceededError
    spend_usd_limit = SpendGuard(max_usd=0.01)
    with pytest.raises(BudgetExceededError, match="Financial spend limit exceeded"):
        spend_usd_limit.record_usage("claude-3-opus", prompt_tokens=2_000, completion_tokens=1_000)

    # 4. Exceeding turn limit raises BudgetExceededError
    spend_turns = SpendGuard(max_turns=1)
    spend_turns.record_usage("ollama", prompt_tokens=10, completion_tokens=10)
    with pytest.raises(BudgetExceededError, match="Turn count limit exceeded"):
        spend_turns.record_usage("ollama", prompt_tokens=10, completion_tokens=10)


def test_spend_guard_lifecycle_hooks() -> None:
    """Verify SpendGuard hook bindings for before and after model requests."""
    spend = Spend(max_usd=1.0)
    hooks = spend.get_hooks()
    assert hooks is not None
    assert len(hooks.before_model_request) > 0
    assert len(hooks.after_model_request) > 0

    ctx = RunContext(model="gpt-4o")

    # Before request passes when under limit
    hooks.before_model_request[0](ctx)

    # After request records response tokens
    mock_resp = MagicMock()
    mock_resp.prompt_tokens = 500
    mock_resp.completion_tokens = 100
    hooks.after_model_request[0](ctx, mock_resp)

    assert spend.usage.prompt_tokens == 500
    assert spend.usage.completion_tokens == 100
    assert spend.usage.total_tokens == 600

    # System prompt additions
    prompts = spend.get_system_prompt_additions(ctx)
    assert any("Spend guardrails active" in p for p in prompts)
