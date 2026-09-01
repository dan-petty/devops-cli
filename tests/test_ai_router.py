"""Unit tests for dynamic cost-, latency-, and freshness-aware LLM router."""

from __future__ import annotations

from devops_cli.ai.router import (
    DataSensitivity,
    LLMRouter,
    TaskComplexity,
    TaskFreshness,
)
from devops_cli.config.settings import AIConfig


def test_router_low_complexity_local_ollama() -> None:
    router = LLMRouter(AIConfig(provider="ollama"))
    decision = router.route_task("token_count", token_count=500)

    assert decision.complexity == TaskComplexity.LOW
    assert decision.freshness == TaskFreshness.STATIC_CONTEXT
    assert decision.sensitivity == DataSensitivity.INTERNAL
    assert decision.provider_name == "ollama"
    assert decision.model_name == "qwen2.5-coder:7b"
    assert decision.estimated_cost_usd == 0.0
    assert decision.estimated_latency_tier == "sub-second"
    assert not decision.requires_live_tools
    assert len(decision.fallback_chain) > 0


def test_router_medium_complexity_fast_model() -> None:
    router = LLMRouter(AIConfig(provider="openai"))
    decision = router.route_task(
        "persona_review",
        token_count=3500,
        freshness=TaskFreshness.LIVE_MCP_LOOKUP,
    )

    assert decision.complexity == TaskComplexity.MEDIUM
    assert decision.freshness == TaskFreshness.LIVE_MCP_LOOKUP
    assert decision.provider_name == "openai"
    assert decision.model_name == "gpt-4o-mini"
    assert decision.estimated_cost_usd > 0.0
    assert decision.estimated_latency_tier == "fast-interactive"
    assert decision.requires_live_tools


def test_router_high_complexity_frontier_model() -> None:
    router = LLMRouter(AIConfig(provider="claude"))
    decision = router.route_task("architecture", token_count=12000)

    assert decision.complexity == TaskComplexity.HIGH
    assert decision.provider_name == "claude"
    assert decision.model_name == "claude-3-7-sonnet-20250219"
    assert decision.estimated_cost_usd > 0.01
    assert decision.estimated_latency_tier == "multi-second"


def test_router_frontier_complexity_reasoning() -> None:
    router = LLMRouter(AIConfig(provider="claude"))
    decision = router.route_task("adversarial_debate", requires_frontier=True)

    assert decision.complexity == TaskComplexity.FRONTIER
    assert decision.provider_name == "claude"
    assert decision.model_name == "claude-3-7-sonnet-20250219"
    assert decision.estimated_latency_tier == "deep-reasoning"


def test_router_explicit_model_override() -> None:
    router = LLMRouter(AIConfig(provider="openai", model="gpt-4o-custom"))
    decision = router.route_task("persona_review", token_count=3500)

    assert decision.provider_name == "openai"
    assert decision.model_name == "gpt-4o-custom"


def test_router_confidential_airgap_forces_local_ollama() -> None:
    # Even if configured with Claude, confidential airgap data forces local Ollama
    router = LLMRouter(AIConfig(provider="claude", model="claude-3-7-sonnet-20250219"))
    decision = router.route_task(
        "security_audit",
        token_count=10000,
        sensitivity=DataSensitivity.CONFIDENTIAL_AIRGAP,
    )

    assert decision.sensitivity == DataSensitivity.CONFIDENTIAL_AIRGAP
    assert decision.provider_name == "ollama"
    assert decision.model_name == "qwen2.5-coder:32b"
    assert decision.estimated_cost_usd == 0.0
    # Fallback chain should strictly contain local models
    assert all(prov == "ollama" for prov, _ in decision.fallback_chain)
    assert "air-gapped" in decision.rationale


def test_router_external_web_search_freshness() -> None:
    router = LLMRouter(AIConfig(provider="openai"))
    decision = router.route_task(
        "cve_lookup",
        freshness=TaskFreshness.EXTERNAL_WEB_SEARCH,
    )

    assert decision.freshness == TaskFreshness.EXTERNAL_WEB_SEARCH
    assert decision.requires_live_tools


def test_router_allowed_providers_restriction() -> None:
    router = LLMRouter(AIConfig(provider="claude"))
    # Restrict to only OpenAI or Copilot
    decision = router.route_task(
        "test_gen",
        token_count=3000,
        allowed_providers=["openai", "copilot"],
    )

    assert decision.provider_name == "openai"
    assert decision.model_name == "gpt-4o-mini"


def test_router_low_complexity_allowed_providers() -> None:
    router = LLMRouter(AIConfig(provider="openai"))
    decision = router.route_task(
        "summarize",
        token_count=100,
        allowed_providers=["openai"],
    )

    assert decision.provider_name == "openai"
    assert decision.model_name == "gpt-4o-mini"
