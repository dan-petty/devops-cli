"""Valkey-backed atomic sliding-window token bucket rate limiter."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from devops_cli.exceptions.valkey import ValkeyConnectionError, ValkeyTimeoutError

if TYPE_CHECKING:
    from devops_cli.valkey.client import ValkeyClient

_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if not tokens then
    tokens = capacity
    last_updated = now
else
    local delta = math.max(0, now - last_updated)
    local fill = delta * (rate / 60.0)
    tokens = math.min(capacity, tokens + fill)
    last_updated = now
end

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, math.ceil(60.0 * 2))
    return {1, math.floor(tokens), 0}
else
    local deficit = cost - tokens
    local retry_ms = math.ceil((deficit / (rate / 60.0)) * 1000)
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, math.ceil(60.0 * 2))
    return {0, math.floor(tokens), retry_ms}
end
"""


class ValkeyTokenBucketRateLimiter:
    """Atomic token bucket rate limiter powered by Valkey Lua scripts."""

    def __init__(
        self,
        client: ValkeyClient,
        key_prefix: str = "rate:limiter",
        rate_per_minute: int = 60,
        burst_capacity: int = 60,
        rate_limit_per_second: float | None = None,
    ) -> None:
        self.client = client
        self.key_prefix = key_prefix
        if rate_limit_per_second is not None:
            self.rate_per_minute = max(1, int(rate_limit_per_second * 60))
        else:
            self.rate_per_minute = max(1, rate_per_minute)
        self.burst_capacity = max(1, burst_capacity)

    def acquire(
        self,
        key_suffix: str = "default",
        cost: int = 1,
        tokens: int | None = None,
    ) -> bool:
        """Attempt to acquire tokens from bucket and return True if successful."""
        effective_cost = tokens if tokens is not None else cost
        allowed, _, _ = self.acquire_detailed(key_suffix=key_suffix, cost=effective_cost)
        return allowed

    def acquire_detailed(
        self, key_suffix: str = "default", cost: int = 1
    ) -> tuple[bool, int, float]:
        """Attempt to acquire tokens from bucket with detailed status.

        Returns:
            Tuple of (allowed: bool, remaining_tokens: int, retry_after_seconds: float)
        """
        full_key = f"{self.key_prefix}:{key_suffix}"
        now_ts = time.time()
        try:
            res: Any = self.client.eval(
                _TOKEN_BUCKET_LUA,
                1,
                full_key,
                str(self.rate_per_minute),
                str(self.burst_capacity),
                str(cost),
                str(now_ts),
            )
        except ValkeyConnectionError, ValkeyTimeoutError, OSError, TimeoutError:
            # In case of Valkey network or socket failure, fail-open to preserve availability
            return True, self.burst_capacity, 0.0

        if isinstance(res, list) and len(res) >= 1:
            allowed = bool(res[0] == 1)
            remaining = int(res[1]) if len(res) > 1 else 0
            retry_ms = float(res[2]) if len(res) > 2 else 0.0
            return allowed, remaining, round(retry_ms / 1000.0, 3)

        return True, self.burst_capacity, 0.0
