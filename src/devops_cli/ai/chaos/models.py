"""Data models and enums for AI Model Dependency Chaos Engineering Suite."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ChaosMode(StrEnum):
    """Supported failure modes for AI model dependency chaos testing."""

    LATENCY = "latency"
    RATE_LIMIT = "rate-limit"
    TIMEOUT = "timeout"
    MALFORMED_JSON = "malformed-json"
    ALL = "all"


class ChaosStatus(StrEnum):
    """Execution status and recovery outcome of a chaos fault injection."""

    INJECTED = "injected"
    RECOVERED = "recovered"
    FAILED = "failed"
    SKIPPED = "skipped"


class ChaosConfig(BaseModel):
    """Configuration options for model dependency chaos fault injection."""

    model_config = ConfigDict(frozen=True)

    mode: ChaosMode = ChaosMode.ALL
    latency_ms: int = Field(default=500, ge=0)
    error_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    primary_provider: str = "openai"
    primary_model: str = "gpt-4o"
    fallback_provider: str = "ollama"
    fallback_model: str = "qwen2.5-coder:7b"
    prompt: str = "def test_health(): return True"
    dry_run: bool = False
    max_retries: int = Field(default=2, ge=0)


class ChaosFaultResult(BaseModel):
    """Outcome report for an individual chaos fault simulation."""

    mode: ChaosMode
    primary_provider: str
    primary_model: str
    fault_injected: str
    fault_latency_ms: float = 0.0
    fallback_engaged: bool = False
    fallback_provider: str = ""
    fallback_model: str = ""
    status: ChaosStatus = ChaosStatus.INJECTED
    recovery_response: str = ""
    error: str = ""
    metrics_recorded: dict[str, float] = Field(default_factory=dict)


class ModelChaosReport(BaseModel):
    """Aggregated resilience report across all injected chaos fault modes."""

    summary: str = ""
    total_faults: int = 0
    recovered_faults: int = 0
    failed_faults: int = 0
    results: list[ChaosFaultResult] = Field(default_factory=list)
    all_passed: bool = True
    duration_seconds: float = 0.0
