"""Native Pydantic AI model settings subsystem for devops-cli.

Provides unified cross-provider model configuration, thinking effort controls,
tool choice restrictions, service tier routing, and multi-tier settings merging.
"""

from __future__ import annotations

from typing import Any, cast

from httpx import Timeout
from pydantic_ai.agent import AgentModelSettings
from pydantic_ai.settings import (
    ModelSettings,
    ServiceTier,
    ThinkingEffort,
    ThinkingLevel,
    ToolChoice,
    ToolChoiceScalar,
    ToolOrOutput,
    merge_model_settings,
)

VALID_THINKING_EFFORTS = {"minimal", "low", "medium", "high", "xhigh"}
VALID_SERVICE_TIERS = {"auto", "default", "flex", "priority"}
VALID_TOOL_CHOICE_SCALARS = {"none", "required", "auto"}


def create_model_settings(
    *,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    timeout: float | Timeout | None = None,
    parallel_tool_calls: bool | None = None,
    tool_choice: ToolChoice | None = None,
    seed: int | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    logit_bias: dict[str, int] | None = None,
    stop_sequences: list[str] | None = None,
    extra_headers: dict[str, str] | None = None,
    thinking: ThinkingLevel | None = None,
    service_tier: ServiceTier | None = None,
    extra_body: object | None = None,
    **kwargs: Any,
) -> ModelSettings:
    """Construct a clean, typed ModelSettings dict omitting None values."""
    settings: dict[str, Any] = {}
    explicit = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "parallel_tool_calls": parallel_tool_calls,
        "tool_choice": tool_choice,
        "seed": seed,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logit_bias": logit_bias,
        "stop_sequences": stop_sequences,
        "extra_headers": extra_headers,
        "thinking": thinking,
        "service_tier": service_tier,
        "extra_body": extra_body,
    }
    for key, value in explicit.items():
        if value is not None:
            settings[key] = value
    for key, value in kwargs.items():
        if value is not None:
            settings[key] = value
    return cast(ModelSettings, settings)


def create_tool_or_output(*tools: str) -> ToolOrOutput:
    """Construct a ToolOrOutput instance restricting function tools while allowing output completion."""
    return ToolOrOutput(function_tools=list(tools))


def normalize_thinking_level(thinking: Any) -> ThinkingLevel | None:
    """Normalize a value into a canonical Pydantic AI ThinkingLevel."""
    if thinking is None:
        return None
    if isinstance(thinking, bool):
        return thinking
    if isinstance(thinking, str):
        lower = thinking.strip().lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        if lower in VALID_THINKING_EFFORTS:
            return cast(ThinkingEffort, lower)
    return None


def normalize_service_tier(tier: str | None) -> ServiceTier | None:
    """Validate and normalize a service tier string into a canonical ServiceTier."""
    if not tier or not isinstance(tier, str):
        return None
    lower = tier.strip().lower()
    if lower in VALID_SERVICE_TIERS:
        return cast(ServiceTier, lower)
    return None


def normalize_tool_choice(choice: Any) -> ToolChoice | None:
    """Normalize a tool choice specification into a valid ToolChoice."""
    if choice is None:
        return None
    if isinstance(choice, ToolOrOutput):
        return choice
    if isinstance(choice, list) and all(isinstance(item, str) for item in choice):
        return choice
    if isinstance(choice, str):
        lower = choice.strip().lower()
        if lower in VALID_TOOL_CHOICE_SCALARS:
            return cast(ToolChoiceScalar, lower)
    return None


def resolve_runtime_model_settings(
    base: ModelSettings | None,
    overrides: ModelSettings | None = None,
    **kwargs: Any,
) -> ModelSettings:
    """Merge base and override ModelSettings with additional keyword parameters."""
    merged: ModelSettings = merge_model_settings(base, overrides) or {}
    extra = create_model_settings(**kwargs)
    if extra:
        return merge_model_settings(merged, extra) or merged
    return merged


__all__ = [
    "AgentModelSettings",
    "ModelSettings",
    "ServiceTier",
    "ThinkingEffort",
    "ThinkingLevel",
    "Timeout",
    "ToolChoice",
    "ToolChoiceScalar",
    "ToolOrOutput",
    "create_model_settings",
    "create_tool_or_output",
    "merge_model_settings",
    "normalize_service_tier",
    "normalize_thinking_level",
    "normalize_tool_choice",
    "resolve_runtime_model_settings",
]
