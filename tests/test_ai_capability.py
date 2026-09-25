"""Unit tests for AI model capability tier gating, parameter evaluation, and failover validation."""

from __future__ import annotations

import pytest

from devops_cli.ai.capability import (
    ModelCapabilityTier,
    evaluate_model_capability,
    get_minimum_tier_b,
    is_tier_satisfied,
    resolve_capability_tier,
    validate_failover_capability,
)
from devops_cli.exceptions.ai import CapabilityDegradationError


def test_resolve_capability_tier() -> None:
    """Verify virtual models and role identifiers map to correct capability tiers."""
    assert (
        resolve_capability_tier("devops-reasoning"),
        resolve_capability_tier("architecture"),
        resolve_capability_tier("devops-coder"),
        resolve_capability_tier("coder"),
        resolve_capability_tier("devops-chat"),
        resolve_capability_tier("general"),
        resolve_capability_tier("devops-embedding"),
        resolve_capability_tier("unknown-alias"),
    ) == (
        ModelCapabilityTier.REASONING,
        ModelCapabilityTier.REASONING,
        ModelCapabilityTier.CODING,
        ModelCapabilityTier.CODING,
        ModelCapabilityTier.CHAT,
        ModelCapabilityTier.CHAT,
        ModelCapabilityTier.EMBEDDING,
        ModelCapabilityTier.CHAT,
    )


def test_get_minimum_tier_b() -> None:
    """Verify minimum required parameter count in billions across capability tiers."""
    assert (
        get_minimum_tier_b(ModelCapabilityTier.REASONING),
        get_minimum_tier_b(ModelCapabilityTier.CODING),
        get_minimum_tier_b(ModelCapabilityTier.CHAT),
        get_minimum_tier_b(ModelCapabilityTier.EMBEDDING),
        get_minimum_tier_b("devops-reasoning"),
        get_minimum_tier_b("devops-coder"),
        get_minimum_tier_b("devops-chat"),
    ) == (
        30,
        7,
        0,
        0,
        30,
        7,
        0,
    )


def test_evaluate_model_capability_local_and_cloud() -> None:
    """Verify parameter extraction for local weights and designated frontier equivalent."""
    assert (
        evaluate_model_capability("qwen2.5-coder:1.5b"),
        evaluate_model_capability("qwen2.5-coder:7b"),
        evaluate_model_capability("qwen2.5-coder:14b"),
        evaluate_model_capability("qwen2.5:32b"),
        evaluate_model_capability("llama3.3:70b"),
        evaluate_model_capability("gpt-4o"),
        evaluate_model_capability("claude-3-7-sonnet"),
        evaluate_model_capability("gemini-2.0-flash"),
        evaluate_model_capability("deepseek-chat"),
        evaluate_model_capability("custom-model", provider="openai"),
        evaluate_model_capability("completely-unknown-model"),
    ) == (
        1,
        7,
        14,
        32,
        70,
        70,
        70,
        70,
        70,
        70,
        None,
    )


def test_is_tier_satisfied() -> None:
    """Verify tier satisfaction predicate across reasoning, coding, and chat workloads."""
    assert (
        is_tier_satisfied("devops-reasoning", "qwen2.5:32b"),
        is_tier_satisfied("devops-reasoning", "qwen2.5-coder:14b"),
        is_tier_satisfied("devops-coder", "qwen2.5-coder:7b"),
        is_tier_satisfied("devops-coder", "qwen2.5-coder:1.5b"),
        is_tier_satisfied("devops-chat", "tiny-model:1b"),
        is_tier_satisfied("devops-reasoning", "gpt-4o"),
        is_tier_satisfied("devops-reasoning", "unrecognized-model"),
    ) == (
        True,
        False,
        True,
        False,
        True,
        True,
        True,
    )


def test_validate_failover_capability_rejection_and_override() -> None:
    """Verify validate_failover_capability raises on underpowered model and allows --force override."""
    # Underpowered fallback raises CapabilityDegradationError
    with pytest.raises(CapabilityDegradationError) as exc_info:
        validate_failover_capability("devops-reasoning", "qwen2.5-coder:7b")

    err = exc_info.value
    assert (
        err.error_code,
        err.details["role"],
        err.details["required_tier_b"],
        err.details["model"],
        err.details["candidate_tier_b"],
    ) == (
        "CAPABILITY_DEGRADATION",
        "devops-reasoning",
        30,
        "qwen2.5-coder:7b",
        7,
    )

    # Forced failover passes without exception
    validate_failover_capability("devops-reasoning", "qwen2.5-coder:7b", force=True)

    # Satisfied model passes without exception
    validate_failover_capability("devops-reasoning", "qwen2.5:32b")
    validate_failover_capability("devops-coder", "qwen2.5-coder:7b")
