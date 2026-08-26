"""Unit tests for dynamic cost- and latency-aware LLM router."""

from __future__ import annotations

from devops_cli.ai.router import LLMRouter, TaskComplexity
from devops_cli.config.settings import AIConfig


def test_router_low_complexity_local_ollama() -> None:
    router = LLMRouter(AIConfig(provider="ollama", model="qwen2.5-coder:7b"))
    decision = router.route_task("token_count", token_count=500)

    assert decision.complexity == TaskComplexity.LOW
    assert decision.provider_name == "ollama"
    assert decision.model_name == "qwen2.5-coder:7b"
    assert decision.estimated_cost_usd == 0.0


def test_router_medium_complexity_fast_model() -> None:
    router = LLMRouter(AIConfig(provider="openai", model="gpt-4o"))
    decision = router.route_task("persona_review", token_count=3500)

    assert decision.complexity == TaskComplexity.MEDIUM
    assert decision.provider_name == "openai"
    assert decision.model_name == "gpt-4o-mini"
    assert decision.estimated_cost_usd > 0.0


def test_router_high_complexity_frontier_model() -> None:
    router = LLMRouter(AIConfig(provider="claude", model="claude-3-7-sonnet-20250219"))
    decision = router.route_task("architecture", token_count=12000, requires_frontier=True)

    assert decision.complexity == TaskComplexity.HIGH
    assert decision.provider_name == "claude"
    assert decision.model_name == "claude-3-7-sonnet-20250219"
    assert decision.estimated_cost_usd > 0.01
