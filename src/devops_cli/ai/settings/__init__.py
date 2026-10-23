"""Typed ``pydantic_ai`` ModelSettings construction that omits unset values."""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai.settings import ModelSettings, ServiceTier, ThinkingLevel, ToolChoice


def create_model_settings(
    *,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
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


__all__ = ["create_model_settings"]
