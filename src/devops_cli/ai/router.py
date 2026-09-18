"""Dynamic Cost-, Latency-, and Freshness-Aware LLM Query Router.

Intelligently steers tasks based on two primary decision axes:
1. Complexity Axis:
   - Low (token budgeting, regex pre-filtering, simple summarization) -> Local Ollama (qwen2.5-coder / granite)
   - Medium (single-file AST review, finding verification, unit test generation) -> Fast cloud models (gpt-4o-mini / claude-3-5-haiku)
   - High (multi-file architecture review, threat modeling, code patching) -> Frontier models (claude-3-7-sonnet / gpt-4o)
   - Frontier (novel system synthesis, cross-repo planning, adversarial debate) -> Frontier reasoning models (claude-3-7-sonnet:thinking / o3-mini)

2. Freshness Axis:
   - Static Context: Solvable via model knowledge and local AST / RAG context (no live network lookups).
   - Live MCP Lookup: Requires live workstation or cluster state (k8s_pods, docker_stats, etc.).
   - External Web Search: Requires real-time vulnerability lookups, package indexes, or current documentation.

3. Data Sensitivity Axis:
   - Confidential / Air-Gapped: Strictly forces local open-weight execution ("Own the Sensitive, Rent the Frontier").
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.defaults import (
    DEFAULT_AI_MODEL,
    DEFAULT_ROUTER_LATENCY_TIER,
)
from devops_cli.config.settings import AIConfig

logger = logging.getLogger(__name__)


class TaskComplexity(StrEnum):
    """Complexity tiers for LLM task classification."""

    LOW = "low"  # Token budgeting, regex pre-filtering, simple summarization
    MEDIUM = "medium"  # Single-file AST review, finding verification, test generation
    HIGH = "high"  # Multi-file architecture review, threat modeling, code patching
    FRONTIER = "frontier"  # Cross-repo planning, multi-agent adversarial debate, novel synthesis


class TaskFreshness(StrEnum):
    """Freshness requirements determining whether live lookups are required."""

    STATIC_CONTEXT = "static"  # Solvable with static context or local RAG
    LIVE_MCP_LOOKUP = "live_mcp"  # Requires live cluster or tool MCP lookup
    EXTERNAL_WEB_SEARCH = "web_search"  # Requires external web/CVE search


class DataSensitivity(StrEnum):
    """Data sensitivity classification for sovereign model routing."""

    PUBLIC = "public"  # Public code or documentation
    INTERNAL = "internal"  # Internal enterprise codebase
    CONFIDENTIAL_AIRGAP = "confidential"  # Air-gapped / sovereign, strictly no cloud egress


_DEFAULT_MODEL_BY_TIER: Final[dict[tuple[str, TaskComplexity], str]] = {
    ("ollama", TaskComplexity.LOW): "qwen2.5-coder:7b",
    ("ollama", TaskComplexity.MEDIUM): "qwen2.5-coder:14b",
    ("ollama", TaskComplexity.HIGH): "qwen2.5-coder:32b",
    ("ollama", TaskComplexity.FRONTIER): "deepseek-r1:32b",
    ("openai", TaskComplexity.LOW): "gpt-4o-mini",
    ("openai", TaskComplexity.MEDIUM): "gpt-4o-mini",
    ("openai", TaskComplexity.HIGH): "gpt-4o",
    ("openai", TaskComplexity.FRONTIER): "o3-mini",
    ("claude", TaskComplexity.LOW): "claude-3-5-haiku-20241022",
    ("claude", TaskComplexity.MEDIUM): "claude-3-5-haiku-20241022",
    ("claude", TaskComplexity.HIGH): "claude-3-7-sonnet-20250219",
    ("claude", TaskComplexity.FRONTIER): "claude-3-7-sonnet-20250219",
    ("copilot", TaskComplexity.LOW): "gpt-4o-mini",
    ("copilot", TaskComplexity.MEDIUM): "gpt-4o-mini",
    ("copilot", TaskComplexity.HIGH): "claude-3-7-sonnet",
    ("copilot", TaskComplexity.FRONTIER): "claude-3-7-sonnet",
    ("gateway", TaskComplexity.LOW): "devops-chat",
    ("gateway", TaskComplexity.MEDIUM): "devops-coder",
    ("gateway", TaskComplexity.HIGH): "devops-reasoning",
    ("gateway", TaskComplexity.FRONTIER): "devops-reasoning",
}

_LATENCY_TIER_BY_COMPLEXITY: Final[dict[TaskComplexity, str]] = {
    TaskComplexity.LOW: "sub-second",
    TaskComplexity.MEDIUM: "fast-interactive",
    TaskComplexity.HIGH: "multi-second",
    TaskComplexity.FRONTIER: "deep-reasoning",
}


class ModelRouteDecision(BaseModel):
    """Routing decision outcome containing target provider, model, and rationale."""

    model_config = ConfigDict(frozen=True)

    task_name: str
    complexity: TaskComplexity
    freshness: TaskFreshness = TaskFreshness.STATIC_CONTEXT
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    provider_name: str
    model_name: str
    enable_thinking: bool = False
    reasoning_effort: str | None = None
    fallback_chain: list[tuple[str, str]] = Field(default_factory=list)
    estimated_cost_usd: float = 0.0
    estimated_latency_tier: str = DEFAULT_ROUTER_LATENCY_TIER
    requires_live_tools: bool = False
    rationale: str = ""


class LLMRouter:
    """Evaluates multi-axis task context and determines optimal provider and model route."""

    def __init__(self, config: AIConfig | None = None) -> None:
        self.config = config or AIConfig()

    def _classify_complexity(
        self,
        task_name: str,
        token_count: int,
        requires_frontier: bool,
    ) -> TaskComplexity:
        """Classify task complexity based on token count, task profile, and frontier flag."""
        if requires_frontier or task_name in ("novel_synthesis", "adversarial_debate"):
            return TaskComplexity.FRONTIER
        if token_count > 8000 or task_name in ("architecture", "threat_model", "cross_repo"):
            return TaskComplexity.HIGH
        if token_count > 2000 or task_name in ("persona_review", "verify_finding", "test_gen"):
            return TaskComplexity.MEDIUM
        return TaskComplexity.LOW

    def _resolve_model_for_provider(
        self,
        provider: str,
        complexity: TaskComplexity,
        default_model: str,
    ) -> str:
        """Resolve model name considering custom user configuration and tier defaults."""
        is_custom = bool(
            self.config.model
            and self.config.model != DEFAULT_AI_MODEL
            and self.config.provider == provider
        )
        return (
            self.config.model
            if is_custom
            else _DEFAULT_MODEL_BY_TIER.get((provider, complexity), default_model)
        )

    def _select_provider_for_complexity(
        self,
        complexity: TaskComplexity,
        configured_provider: str,
        allowed_providers: list[str] | None,
    ) -> str:
        """Select target provider based on task complexity and allowed providers constraint."""
        if complexity == TaskComplexity.LOW:
            return (
                "ollama"
                if (not allowed_providers or "ollama" in allowed_providers)
                else configured_provider
            )
        if complexity == TaskComplexity.MEDIUM:
            if configured_provider in ("openai", "claude"):
                return configured_provider
            return "ollama"
        return configured_provider if configured_provider != "ollama" else "claude"

    def _resolve_provider_and_model(
        self,
        complexity: TaskComplexity,
        sensitivity: DataSensitivity,
        allowed_providers: list[str] | None,
    ) -> tuple[str, str]:
        """Resolve primary provider and model considering sensitivity and provider overrides."""
        if sensitivity == DataSensitivity.CONFIDENTIAL_AIRGAP:
            model = self._resolve_model_for_provider("ollama", complexity, "qwen2.5-coder:7b")
            return "ollama", model

        configured_provider = self.config.provider or "ollama"
        if (self.config.gateway_enabled or configured_provider == "gateway") and (
            not allowed_providers or "gateway" in allowed_providers
        ):
            model = self._resolve_model_for_provider("gateway", complexity, "devops-chat")
            return "gateway", model

        if allowed_providers and configured_provider not in allowed_providers:
            configured_provider = allowed_providers[0]

        provider = self._select_provider_for_complexity(
            complexity, configured_provider, allowed_providers
        )
        default_m = (
            "qwen2.5-coder:7b"
            if complexity == TaskComplexity.LOW
            else (
                "gpt-4o-mini"
                if complexity == TaskComplexity.MEDIUM
                else "claude-3-7-sonnet-20250219"
            )
        )
        model = self._resolve_model_for_provider(provider, complexity, default_m)
        return provider, model

    def _build_fallback_chain(
        self,
        primary_provider: str,
        primary_model: str,
        complexity: TaskComplexity,
        sensitivity: DataSensitivity,
    ) -> list[tuple[str, str]]:
        """Construct an ordered fallback cascade ring for resilience."""
        if sensitivity == DataSensitivity.CONFIDENTIAL_AIRGAP:
            fallbacks = [("ollama", "qwen2.5-coder:14b"), ("ollama", "qwen2.5-coder:7b")]
            return [fb for fb in fallbacks if fb != (primary_provider, primary_model)]

        cascade_providers = ["gateway", "claude", "openai", "copilot", "ollama"]
        chain: list[tuple[str, str]] = []
        for prov in cascade_providers:
            candidate = (prov, _DEFAULT_MODEL_BY_TIER.get((prov, complexity), "qwen2.5-coder:7b"))
            if candidate != (primary_provider, primary_model) and candidate not in chain:
                chain.append(candidate)
        return chain

    def _generate_rationale(
        self,
        complexity: TaskComplexity,
        freshness: TaskFreshness,
        sensitivity: DataSensitivity,
        provider: str,
        model: str,
    ) -> str:
        """Compose human-readable explanation of the routing decision."""
        if provider == "gateway":
            return f"Routed to high-throughput LLM gateway '{provider}' ({model}) with least-latency load balancing."
        if sensitivity == DataSensitivity.CONFIDENTIAL_AIRGAP:
            return f"Routed strictly to local air-gapped provider '{provider}' ({model}) to prevent cloud data egress."
        if complexity == TaskComplexity.LOW:
            return f"Routed to local/fast provider '{provider}' ({model}) for zero-cost and sub-second execution."
        if complexity == TaskComplexity.MEDIUM:
            return f"Routed to fast cloud/local model '{provider}' ({model}) balancing speed and inference cost."
        if complexity == TaskComplexity.FRONTIER:
            return f"Routed to frontier reasoning engine '{provider}' ({model}) for deep architectural synthesis."
        return f"Routed to high-capacity provider '{provider}' ({model}) for multi-file code reasoning."

    def _estimate_cost(self, provider: str, model: str, token_count: int) -> float:
        """Estimate execution cost in USD based on provider pricing rules and token volume."""
        if provider.lower() in ("ollama", "copilot", "gateway"):
            return 0.0
        from devops_cli.ai.agents.spend import DEFAULT_MODEL_PRICING, ModelPricing

        pricing = (
            DEFAULT_MODEL_PRICING.get(model)
            or DEFAULT_MODEL_PRICING.get(provider.lower())
            or DEFAULT_MODEL_PRICING.get("default", ModelPricing())
        )
        tokens = max(token_count, 1000)
        return pricing.calculate_cost(prompt_tokens=tokens, completion_tokens=0)

    def route_task(
        self,
        task_name: str,
        token_count: int = 0,
        requires_frontier: bool = False,
        freshness: TaskFreshness = TaskFreshness.STATIC_CONTEXT,
        sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
        allowed_providers: list[str] | None = None,
    ) -> ModelRouteDecision:
        """Route a task to the optimal provider, model, and fallback chain across both axes."""
        complexity = self._classify_complexity(task_name, token_count, requires_frontier)
        provider, model = self._resolve_provider_and_model(
            complexity, sensitivity, allowed_providers
        )
        fallback_chain = self._build_fallback_chain(provider, model, complexity, sensitivity)

        cost = self._estimate_cost(provider, model, token_count)
        latency = _LATENCY_TIER_BY_COMPLEXITY.get(complexity, DEFAULT_ROUTER_LATENCY_TIER)
        requires_tools = freshness in (
            TaskFreshness.LIVE_MCP_LOOKUP,
            TaskFreshness.EXTERNAL_WEB_SEARCH,
        )
        rationale = self._generate_rationale(complexity, freshness, sensitivity, provider, model)
        enable_thinking = complexity in (TaskComplexity.HIGH, TaskComplexity.FRONTIER)
        reasoning_effort = (
            "high"
            if complexity == TaskComplexity.FRONTIER
            else ("medium" if complexity == TaskComplexity.HIGH else None)
        )

        return ModelRouteDecision(
            task_name=task_name,
            complexity=complexity,
            freshness=freshness,
            sensitivity=sensitivity,
            provider_name=provider,
            model_name=model,
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,
            fallback_chain=fallback_chain,
            estimated_cost_usd=cost,
            estimated_latency_tier=latency,
            requires_live_tools=requires_tools,
            rationale=rationale,
        )
