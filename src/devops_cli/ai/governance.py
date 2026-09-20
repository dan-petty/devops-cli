"""Client-side token bucket rate governance and token budgeting for PydanticAI."""

from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.usage import RunUsage, UsageLimits

from devops_cli.config.defaults import (
    DEFAULT_AI_TOKEN_BUCKET_CAPACITY,
    DEFAULT_AI_TOKEN_BUCKET_REFILL_RATE,
    DEFAULT_AI_USAGE_REQUEST_LIMIT,
)

logger = logging.getLogger(__name__)


class TokenBudgetConfig(BaseModel):
    """Declarative token and request budgeting configuration for AI agent workflows."""

    model_config = ConfigDict(extra="forbid")

    input_tokens_limit: int | None = None
    output_tokens_limit: int | None = None
    total_tokens_limit: int | None = None
    per_request_input_tokens_limit: int | None = None
    request_limit: int | None = Field(default=DEFAULT_AI_USAGE_REQUEST_LIMIT)
    cost_limit: float | None = None
    count_tokens_before_request: bool = False

    def to_usage_limits(self) -> UsageLimits:
        """Convert configuration into native PydanticAI UsageLimits instance."""
        cost_decimal = Decimal(str(self.cost_limit)) if self.cost_limit is not None else None
        return UsageLimits(
            input_tokens_limit=self.input_tokens_limit,
            output_tokens_limit=self.output_tokens_limit,
            total_tokens_limit=self.total_tokens_limit,
            per_request_input_tokens_limit=self.per_request_input_tokens_limit,
            request_limit=self.request_limit,
            cost_limit=cost_decimal,
            count_tokens_before_request=self.count_tokens_before_request,
        )


class TokenBucketGovernance:
    """Thread-safe client-side token bucket rate governor and consumption tracker."""

    def __init__(
        self,
        capacity: int = DEFAULT_AI_TOKEN_BUCKET_CAPACITY,
        refill_rate: float = DEFAULT_AI_TOKEN_BUCKET_REFILL_RATE,
    ) -> None:
        self.capacity: float = float(max(1, capacity))
        self.refill_rate: float = float(max(0.1, refill_rate))
        self.tokens: float = self.capacity
        self.last_refill_timestamp: float = time.monotonic()
        self.consumed_input_tokens: int = 0
        self.consumed_output_tokens: int = 0
        self.consumed_total_tokens: int = 0
        self.total_requests: int = 0
        self._lock = threading.Lock()

    def _refill_unlocked(self, now: float) -> None:
        """Internal helper to replenish tokens based on elapsed monotonic time."""
        elapsed = max(0.0, now - self.last_refill_timestamp)
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.last_refill_timestamp = now

    def available_tokens(self) -> float:
        """Return currently available tokens after monotonic replenishment."""
        with self._lock:
            self._refill_unlocked(time.monotonic())
            return max(0.0, self.tokens)

    def acquire_token_permit(self, estimated_tokens: int = 1) -> float:
        """Acquire token permits and calculate pacing delay in seconds if throttled."""
        cost = float(max(1, estimated_tokens))
        with self._lock:
            now = time.monotonic()
            self._refill_unlocked(now)
            if self.tokens >= cost:
                self.tokens -= cost
                return 0.0

            deficit = cost - self.tokens
            self.tokens -= cost
            delay = deficit / self.refill_rate
            logger.debug(
                "Token bucket throttled: deficit=%.1f, pacing_delay=%.3fs",
                deficit,
                delay,
            )
            return delay

    def record_token_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        request_count: int = 1,
    ) -> None:
        """Record consumed tokens and update internal telemetry counters."""
        total = max(0, input_tokens) + max(0, output_tokens)
        with self._lock:
            self.consumed_input_tokens += max(0, input_tokens)
            self.consumed_output_tokens += max(0, output_tokens)
            self.consumed_total_tokens += total
            self.total_requests += max(0, request_count)

    def record_run_usage(self, usage: RunUsage) -> None:
        """Record usage directly from a completed PydanticAI RunUsage event."""
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        reqs = getattr(usage, "requests", 1) or 1
        self.record_token_usage(
            input_tokens=in_tok,
            output_tokens=out_tok,
            request_count=reqs,
        )

    def get_governance_telemetry(self) -> dict[str, Any]:
        """Produce structured governance telemetry dictionary."""
        with self._lock:
            self._refill_unlocked(time.monotonic())
            return {
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "available_tokens": max(0.0, round(self.tokens, 1)),
                "consumed_input_tokens": self.consumed_input_tokens,
                "consumed_output_tokens": self.consumed_output_tokens,
                "consumed_total_tokens": self.consumed_total_tokens,
                "total_requests": self.total_requests,
            }

    def reset(self) -> None:
        """Reset token bucket to full capacity and reset counters."""
        with self._lock:
            self.tokens = self.capacity
            self.last_refill_timestamp = time.monotonic()
            self.consumed_input_tokens = 0
            self.consumed_output_tokens = 0
            self.consumed_total_tokens = 0
            self.total_requests = 0


__all__ = [
    "TokenBucketGovernance",
    "TokenBudgetConfig",
]
