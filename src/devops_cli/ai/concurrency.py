"""Native Pydantic AI Concurrency and Rate Limiting Subsystem.

Provides direct access to native Pydantic AI concurrency primitives, rate limiters,
model-level concurrency wrappers, and a shared thread-safe limiter registry for
orchestrating multi-agent pipelines and LLM provider capacity.
"""

from __future__ import annotations

import threading
from contextlib import AbstractAsyncContextManager

from pydantic_ai.concurrency import (
    AbstractConcurrencyLimiter,
    AnyConcurrencyLimit,
    ConcurrencyLimit,
    ConcurrencyLimiter,
    get_concurrency_context,
    normalize_to_limiter,
)
from pydantic_ai.exceptions import ConcurrencyLimitExceeded
from pydantic_ai.models.concurrency import ConcurrencyLimitedModel, limit_model_concurrency

# ── Shared Limiter Registry ───────────────────────────────────────────────────

_SHARED_LIMITERS: dict[str, ConcurrencyLimiter] = {}
_REGISTRY_LOCK = threading.Lock()


def get_shared_concurrency_limiter(
    name: str,
    max_running: int = 2,
    max_queued: int | None = None,
) -> ConcurrencyLimiter:
    """Retrieve or register a shared named ConcurrencyLimiter instance.

    Ensures that multiple agents, models, or pipeline stages targeting the same
    cluster node or provider share the exact same concurrency capacity limiter.
    """
    with _REGISTRY_LOCK:
        if name not in _SHARED_LIMITERS or _SHARED_LIMITERS[name].max_running != max_running:
            _SHARED_LIMITERS[name] = ConcurrencyLimiter(
                max_running=max(1, max_running),
                max_queued=max_queued,
                name=name,
            )
        return _SHARED_LIMITERS[name]


def get_model_concurrency_limiter(
    model_name: str,
    default_max: int = 2,
    max_queued: int | None = None,
) -> ConcurrencyLimiter:
    """Retrieve or register a shared model-level concurrency limiter."""
    clean_name = model_name.strip()
    return get_shared_concurrency_limiter(
        f"model:{clean_name}",
        max_running=default_max,
        max_queued=max_queued,
    )


def track_concurrency_slot(
    limiter: AbstractConcurrencyLimiter | None,
    source: str = "unnamed",
) -> AbstractAsyncContextManager[None]:
    """Context manager acquiring and releasing a concurrency slot for an operation."""
    return get_concurrency_context(limiter, source=source)


__all__ = [
    "AbstractConcurrencyLimiter",
    "AnyConcurrencyLimit",
    "ConcurrencyLimit",
    "ConcurrencyLimitExceeded",
    "ConcurrencyLimitedModel",
    "ConcurrencyLimiter",
    "get_concurrency_context",
    "get_model_concurrency_limiter",
    "get_shared_concurrency_limiter",
    "limit_model_concurrency",
    "normalize_to_limiter",
    "track_concurrency_slot",
]
