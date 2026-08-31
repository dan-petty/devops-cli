"""Pydantic AI Spend and budget management capability for cost and token tracking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import AgentHooks, RunContext
from devops_cli.exceptions import DevOpsCLIError


class BudgetExceededError(DevOpsCLIError):
    """Raised when an agent execution exceeds defined token or financial spend limits."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message=message, error_code="BUDGET_EXCEEDED", **kwargs)


class ModelPricing(BaseModel):
    """Token pricing in USD per 1,000,000 tokens."""

    prompt_usd_per_million: float = 0.0
    completion_usd_per_million: float = 0.0

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate total USD cost for the given token counts."""
        prompt_cost = (prompt_tokens / 1_000_000.0) * self.prompt_usd_per_million
        completion_cost = (completion_tokens / 1_000_000.0) * self.completion_usd_per_million
        return round(prompt_cost + completion_cost, 6)


DEFAULT_MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI
    "gpt-4o": ModelPricing(prompt_usd_per_million=2.50, completion_usd_per_million=10.00),
    "gpt-4o-mini": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.60),
    "gpt-4-turbo": ModelPricing(prompt_usd_per_million=10.00, completion_usd_per_million=30.00),
    "o1": ModelPricing(prompt_usd_per_million=15.00, completion_usd_per_million=60.00),
    "o3-mini": ModelPricing(prompt_usd_per_million=1.10, completion_usd_per_million=4.40),
    # Anthropic Claude
    "claude-3-5-sonnet-20241022": ModelPricing(
        prompt_usd_per_million=3.00, completion_usd_per_million=15.00
    ),
    "claude-3-5-sonnet": ModelPricing(
        prompt_usd_per_million=3.00, completion_usd_per_million=15.00
    ),
    "claude-3-5-haiku": ModelPricing(prompt_usd_per_million=0.80, completion_usd_per_million=4.00),
    "claude-3-opus": ModelPricing(prompt_usd_per_million=15.00, completion_usd_per_million=75.00),
    # Local Ollama / Free
    "ollama": ModelPricing(prompt_usd_per_million=0.0, completion_usd_per_million=0.0),
    "default": ModelPricing(prompt_usd_per_million=1.00, completion_usd_per_million=2.00),
}


class SpendUsage(BaseModel):
    """Cumulative token and USD spend tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_usd: float = 0.0
    turn_count: int = 0

    def add(self, prompt_tokens: int, completion_tokens: int, cost_usd: float) -> None:
        """Accumulate usage metrics."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.total_usd = round(self.total_usd + cost_usd, 6)
        self.turn_count += 1


class SpendGuard(BaseCapability):
    """Capability enforcing token and USD financial spend budgets across agent execution."""

    id: str = "spend"
    max_usd: float | None = None
    max_tokens: int | None = None
    max_turns: int | None = None
    pricing: dict[str, ModelPricing] = Field(default_factory=lambda: dict(DEFAULT_MODEL_PRICING))
    usage: SpendUsage = Field(default_factory=SpendUsage)

    def record_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate, record, and check spend limits for a model request."""
        pricing_rule = self.pricing.get(model) or self.pricing.get(
            model.split(":")[0], self.pricing.get("default", ModelPricing())
        )
        cost = pricing_rule.calculate_cost(prompt_tokens, completion_tokens)
        self.usage.add(prompt_tokens, completion_tokens, cost)
        self.check_limits()
        return cost

    def check_limits(self) -> None:
        """Validate that current usage does not exceed configured limits."""
        if self.max_usd is not None and self.usage.total_usd > self.max_usd:
            raise BudgetExceededError(
                f"Financial spend limit exceeded: ${self.usage.total_usd:.4f} > max ${self.max_usd:.4f}"
            )
        if self.max_tokens is not None and self.usage.total_tokens > self.max_tokens:
            raise BudgetExceededError(
                f"Token budget limit exceeded: {self.usage.total_tokens:,} tokens > max {self.max_tokens:,} tokens"
            )
        if self.max_turns is not None and self.usage.turn_count > self.max_turns:
            raise BudgetExceededError(
                f"Turn count limit exceeded: {self.usage.turn_count} turns > max {self.max_turns} turns"
            )

    def get_hooks(self) -> AgentHooks | None:
        """Bind spend verification before model requests."""

        def before_req(ctx: RunContext[Any], *args: Any, **kwargs: Any) -> None:
            self.check_limits()

        def after_req(ctx: RunContext[Any], *args: Any, **kwargs: Any) -> None:
            # Extract usage if present in response metadata
            if args and hasattr(args[0], "prompt_tokens") and hasattr(args[0], "completion_tokens"):
                res = args[0]
                model = getattr(ctx, "model", "") or getattr(res, "model", "default")
                self.record_usage(
                    model=str(model),
                    prompt_tokens=int(getattr(res, "prompt_tokens", 0) or 0),
                    completion_tokens=int(getattr(res, "completion_tokens", 0) or 0),
                )

        return AgentHooks(before_model_request=[before_req], after_model_request=[after_req])

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.max_usd is not None or self.max_tokens is not None:
            limits = []
            if self.max_usd is not None:
                limits.append(
                    f"Max budget: ${self.max_usd:.2f} (Current: ${self.usage.total_usd:.4f})"
                )
            if self.max_tokens is not None:
                limits.append(
                    f"Max tokens: {self.max_tokens:,} (Current: {self.usage.total_tokens:,})"
                )
            return [f"Spend guardrails active: {', '.join(limits)}."]
        return []


Spend = SpendGuard
