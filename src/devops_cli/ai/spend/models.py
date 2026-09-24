"""Data models for AI/LLM request spend tracking and pricing registry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPricing(BaseModel):
    """Token pricing in USD per 1,000,000 tokens."""

    model_config = ConfigDict(extra="ignore")

    prompt_usd_per_million: float = 0.0
    completion_usd_per_million: float = 0.0
    source: str = "default"
    updated_at: str | None = None

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate total USD cost for the given token counts."""
        prompt_cost = (prompt_tokens / 1_000_000.0) * self.prompt_usd_per_million
        completion_cost = (completion_tokens / 1_000_000.0) * self.completion_usd_per_million
        return round(prompt_cost + completion_cost, 6)


class SpendRecord(BaseModel):
    """Single AI request spend and usage ledger record."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    timestamp: str
    provider: str
    server: str
    backend_info: str | None = None
    # The backend a gateway routed the call to (its api_base); None without a gateway.
    served_by: str | None = None
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    request_type: str = "chat"
    duration_seconds: float = 0.0


class ServerSpendSummary(BaseModel):
    """Aggregated spend and token metrics for a single backend service/server."""

    model_config = ConfigDict(extra="ignore")

    server: str
    provider: str
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    approx_spend_usd: float = 0.0
    models: list[str] = Field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None


class ModelSpendSummary(BaseModel):
    """Aggregated spend and token metrics for a specific model."""

    model_config = ConfigDict(extra="ignore")

    model: str
    provider: str
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    approx_spend_usd: float = 0.0
    prompt_usd_per_million: float = 0.0
    completion_usd_per_million: float = 0.0


class ProviderSpendSummary(BaseModel):
    """Aggregated spend and token metrics for a provider category."""

    model_config = ConfigDict(extra="ignore")

    provider: str
    request_count: int = 0
    total_tokens: int = 0
    approx_spend_usd: float = 0.0
    server_count: int = 1


class BackendSpendSummary(BaseModel):
    """Usage of one backend that a gateway routed calls to."""

    served_by: str
    models: list[str] = Field(default_factory=list)
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    completion_tokens_per_request: float = 0.0
    mean_duration_seconds: float = 0.0


class LifetimeSpendReport(BaseModel):
    """Consolidated lifetime spend and usage report across all backends."""

    model_config = ConfigDict(extra="ignore")

    total_spend_usd: float = 0.0
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    cached_requests: int = 0
    active_servers_count: int = 0
    active_models_count: int = 0
    first_recorded_at: str | None = None
    last_recorded_at: str | None = None
    servers: list[ServerSpendSummary] = Field(default_factory=list)
    models: list[ModelSpendSummary] = Field(default_factory=list)
    providers: list[ProviderSpendSummary] = Field(default_factory=list)
    backends: list[BackendSpendSummary] = Field(default_factory=list)
