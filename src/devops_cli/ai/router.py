"""Dynamic Cost- and Latency-Aware LLM Query Router.

Intelligently steers tasks based on complexity, token budget, and latency requirements:
- Simple token counting and classification -> Local Ollama (qwen2.5-coder / llama3.2)
- Moderate AST review passes -> Fast cloud models (gpt-4o-mini / claude-3-5-haiku)
- Complex multi-file architectural refactoring -> Frontier models (claude-3-7-sonnet / gpt-4o)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from devops_cli.config.settings import AIConfig

logger = logging.getLogger(__name__)


class TaskComplexity(StrEnum):
    """Complexity tiers for LLM task classification."""

    LOW = "low"  # Token budgeting, regex pre-filtering, simple summarization
    MEDIUM = "medium"  # Single-file AST review, finding verification
    HIGH = "high"  # Multi-file architecture review, threat modeling, code patching


@dataclass(frozen=True)
class ModelRouteDecision:
    """Routing decision outcome containing target provider, model, and rationale."""

    task_name: str
    complexity: TaskComplexity
    provider_name: str
    model_name: str
    estimated_cost_usd: float = 0.0
    rationale: str = ""


class LLMRouter:
    """Evaluates task context and determines the optimal provider and model route."""

    def __init__(self, config: AIConfig | None = None) -> None:
        self.config = config or AIConfig()

    def route_task(
        self,
        task_name: str,
        token_count: int = 0,
        requires_frontier: bool = False,
    ) -> ModelRouteDecision:
        """Route a task to the most cost-effective and performant provider and model."""
        # Classify complexity
        complexity = TaskComplexity.LOW
        if requires_frontier or token_count > 8000 or task_name in ("architecture", "threat_model"):
            complexity = TaskComplexity.HIGH
        elif token_count > 2000 or task_name in ("persona_review", "verify_finding"):
            complexity = TaskComplexity.MEDIUM

        # Default provider resolution
        if complexity == TaskComplexity.LOW:
            return ModelRouteDecision(
                task_name=task_name,
                complexity=complexity,
                provider_name="ollama",
                model_name=self.config.model or "qwen2.5-coder:7b",
                estimated_cost_usd=0.0,
                rationale="Routed to local Ollama model for zero-cost and sub-second latency.",
            )

        if complexity == TaskComplexity.MEDIUM:
            provider = "openai" if self.config.provider == "openai" else "claude"
            model = "gpt-4o-mini" if provider == "openai" else "claude-3-5-haiku-20241022"
            return ModelRouteDecision(
                task_name=task_name,
                complexity=complexity,
                provider_name=provider,
                model_name=model,
                estimated_cost_usd=0.001,
                rationale="Routed to fast cloud model for balanced cost and speed.",
            )

        # High complexity
        provider = self.config.provider if self.config.provider != "ollama" else "claude"
        model = self.config.model or "claude-3-7-sonnet-20250219"
        return ModelRouteDecision(
            task_name=task_name,
            complexity=complexity,
            provider_name=provider,
            model_name=model,
            estimated_cost_usd=0.015,
            rationale="Routed to frontier reasoning model for complex architectural analysis.",
        )
