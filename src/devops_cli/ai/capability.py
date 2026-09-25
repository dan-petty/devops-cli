"""Model capability tier evaluation, minimum parameter gating, and failover validation."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Final

from devops_cli.ai.spend.pricing import _extract_param_size_b, _normalize_model_name
from devops_cli.config.constants import (
    CONST_FRONTIER_EQUIVALENT_TIER_B,
    CONST_FRONTIER_MODEL_PREFIXES,
    CONST_MIN_CODING_MODEL_TIER_B,
    CONST_MIN_REASONING_MODEL_TIER_B,
)
from devops_cli.exceptions.ai import CapabilityDegradationError
from devops_cli.telemetry.tracer import record_metric

logger = logging.getLogger(__name__)


class ModelCapabilityTier(StrEnum):
    """Hierarchical capability classifications for AI models and workloads."""

    REASONING = "reasoning"
    CODING = "coding"
    CHAT = "chat"
    EMBEDDING = "embedding"


VIRTUAL_MODEL_TIER_MAPPING: Final[dict[str, ModelCapabilityTier]] = {
    "devops-reasoning": ModelCapabilityTier.REASONING,
    "reasoning": ModelCapabilityTier.REASONING,
    "architecture": ModelCapabilityTier.REASONING,
    "threat_model": ModelCapabilityTier.REASONING,
    "deep_review": ModelCapabilityTier.REASONING,
    "devops-coder": ModelCapabilityTier.CODING,
    "coding": ModelCapabilityTier.CODING,
    "coder": ModelCapabilityTier.CODING,
    "devops-chat": ModelCapabilityTier.CHAT,
    "chat": ModelCapabilityTier.CHAT,
    "general": ModelCapabilityTier.CHAT,
    "devops-embedding": ModelCapabilityTier.EMBEDDING,
    "embedding": ModelCapabilityTier.EMBEDDING,
}

TIER_MINIMUM_PARAMS_B: Final[dict[ModelCapabilityTier, int]] = {
    ModelCapabilityTier.REASONING: CONST_MIN_REASONING_MODEL_TIER_B,
    ModelCapabilityTier.CODING: CONST_MIN_CODING_MODEL_TIER_B,
    ModelCapabilityTier.CHAT: 0,
    ModelCapabilityTier.EMBEDDING: 0,
}

FRONTIER_CLOUD_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"openai", "anthropic", "gemini", "google"}
)


def resolve_capability_tier(role_or_virtual_model: str) -> ModelCapabilityTier:
    """Resolve role or virtual model name to its standardized capability tier."""
    key = role_or_virtual_model.strip().lower()
    return VIRTUAL_MODEL_TIER_MAPPING.get(key, ModelCapabilityTier.CHAT)


def get_minimum_tier_b(role_or_virtual_model: str | ModelCapabilityTier) -> int:
    """Return the minimum required parameter count in billions for a tier or virtual model."""
    if isinstance(role_or_virtual_model, ModelCapabilityTier):
        tier = role_or_virtual_model
    else:
        tier = resolve_capability_tier(role_or_virtual_model)
    return TIER_MINIMUM_PARAMS_B.get(tier, 0)


def evaluate_model_capability(model: str, provider: str = "") -> int | None:
    """Estimate model capability tier in equivalent billions of parameters.

    Returns parameter count for open/local models (e.g. 7, 14, 32, 70),
    or a designated frontier equivalent (70) for recognized cloud frontier models.
    """
    clean_model = _normalize_model_name(model)
    clean_provider = provider.strip().lower()

    if clean_provider in FRONTIER_CLOUD_PROVIDERS:
        return CONST_FRONTIER_EQUIVALENT_TIER_B

    for prefix in CONST_FRONTIER_MODEL_PREFIXES:
        if clean_model.startswith(prefix):
            return CONST_FRONTIER_EQUIVALENT_TIER_B

    return _extract_param_size_b(clean_model)


def is_tier_satisfied(
    role_or_virtual_model: str,
    fallback_model: str,
    fallback_provider: str = "",
) -> bool:
    """Return True if candidate fallback model satisfies the role's capability threshold."""
    required_b = get_minimum_tier_b(role_or_virtual_model)
    if required_b <= 0:
        return True

    candidate_b = evaluate_model_capability(fallback_model, fallback_provider)
    if candidate_b is None:
        return True
    return candidate_b >= required_b


def validate_failover_capability(
    role_or_virtual_model: str,
    fallback_model: str,
    fallback_provider: str = "",
    *,
    force: bool = False,
) -> None:
    """Validate fallback model meets the minimum capability tier, raising if breached.

    If force is True, the capability check is bypassed and an override metric is recorded.
    """
    required_b = get_minimum_tier_b(role_or_virtual_model)
    if required_b <= 0:
        return

    candidate_b = evaluate_model_capability(fallback_model, fallback_provider)

    if force:
        record_metric(
            "ai.failover.capability_override",
            1,
            attributes={"role": role_or_virtual_model, "model": fallback_model},
        )
        logger.warning(
            "Capability gate bypassed (--force) for role '%s': routing to '%s' (%sB vs required %sB)",
            role_or_virtual_model,
            fallback_model,
            candidate_b or "unknown",
            required_b,
        )
        return

    if candidate_b is not None and candidate_b < required_b:
        record_metric(
            "ai.failover.capability_rejection",
            1,
            attributes={"role": role_or_virtual_model, "model": fallback_model},
        )
        raise CapabilityDegradationError(
            f"Failover to '{fallback_model}' ({candidate_b}B) breaches minimum capability tier "
            f"for '{role_or_virtual_model}' ({required_b}B). Pass --force to override capability gating.",
            role=role_or_virtual_model,
            required_tier_b=required_b,
            model=fallback_model,
            candidate_tier_b=candidate_b,
        )


__all__ = [
    "FRONTIER_CLOUD_PROVIDERS",
    "TIER_MINIMUM_PARAMS_B",
    "VIRTUAL_MODEL_TIER_MAPPING",
    "ModelCapabilityTier",
    "evaluate_model_capability",
    "get_minimum_tier_b",
    "is_tier_satisfied",
    "resolve_capability_tier",
    "validate_failover_capability",
]
