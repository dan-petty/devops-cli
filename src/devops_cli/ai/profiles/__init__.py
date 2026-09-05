"""Native Pydantic AI profiles subsystem for devops-cli.

Provides unified model capability profiles, schema transformers, thinking tag
introspection, and all 14 family model profile builders from pydantic_ai.profiles.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from pydantic_ai.native_tools import SUPPORTED_NATIVE_TOOLS
from pydantic_ai.output import StructuredOutputMode
from pydantic_ai.profiles import (
    DEFAULT_PROFILE,
    DEFAULT_PROMPTED_OUTPUT_TEMPLATE,
    DEFAULT_THINKING_TAGS,
    InlineDefsJsonSchemaTransformer,
    JsonSchemaTransformer,
    ModelProfile,
    ModelProfileSpec,
    ToolAdditionMode,
    ToolDeferralMode,
    merge_profile,
)
from pydantic_ai.profiles.amazon import amazon_model_profile
from pydantic_ai.profiles.anthropic import anthropic_model_profile
from pydantic_ai.profiles.cohere import cohere_model_profile
from pydantic_ai.profiles.deepseek import deepseek_model_profile
from pydantic_ai.profiles.google import google_model_profile, google_realtime_model_profile
from pydantic_ai.profiles.grok import grok_model_profile, grok_realtime_model_profile
from pydantic_ai.profiles.groq import groq_model_profile
from pydantic_ai.profiles.harmony import harmony_model_profile
from pydantic_ai.profiles.meta import meta_model_profile
from pydantic_ai.profiles.mistral import mistral_model_profile
from pydantic_ai.profiles.moonshotai import moonshotai_model_profile
from pydantic_ai.profiles.openai import openai_model_profile, openai_realtime_model_profile
from pydantic_ai.profiles.qwen import qwen_model_profile
from pydantic_ai.profiles.zai import zai_model_profile

_FAMILY_BUILDERS: dict[str, Callable[[str], ModelProfile | None]] = {
    "amazon": amazon_model_profile,
    "anthropic": anthropic_model_profile,
    "claude": anthropic_model_profile,
    "cohere": cohere_model_profile,
    "deepseek": deepseek_model_profile,
    "google": google_model_profile,
    "grok": grok_model_profile,
    "groq": groq_model_profile,
    "harmony": harmony_model_profile,
    "meta": meta_model_profile,
    "llama": meta_model_profile,
    "mistral": mistral_model_profile,
    "moonshot": moonshotai_model_profile,
    "moonshotai": moonshotai_model_profile,
    "openai": openai_model_profile,
    "qwen": qwen_model_profile,
    "zai": zai_model_profile,
}


def _apply_profile_spec(base: ModelProfile, spec: ModelProfileSpec | None) -> ModelProfile:
    """Apply a ModelProfile or specification callable to a base profile."""
    if spec is None:
        return base
    if callable(spec):
        return spec(base)
    return merge_profile(base, spec)


def get_model_profile_builder(name: str) -> Callable[[str], ModelProfile | None] | None:
    """Retrieve family model profile builder by canonical provider or family name."""
    return _FAMILY_BUILDERS.get(name.lower().strip())


def resolve_model_profile(
    model: str | ModelProfileSpec | None = None,
    provider: str | None = None,
    overrides: ModelProfileSpec | None = None,
) -> ModelProfile:
    """Resolve a unified ModelProfile for a model string, provider, or specification.

    Dynamically queries pydantic_ai.models.infer_model_profile or registered family
    builders and merges optional user or subsystem overrides via merge_profile.
    """
    base: ModelProfile = cast(ModelProfile, dict(DEFAULT_PROFILE))

    if model is None:
        return _apply_profile_spec(base, overrides)

    if callable(model):
        base = model(base)
        return _apply_profile_spec(base, overrides)

    if isinstance(model, dict):
        base = model
        return _apply_profile_spec(base, overrides)

    model_str = model.strip()
    target_provider = provider.lower().strip() if provider else None
    target_model_name = model_str

    if ":" in model_str:
        parsed_prov, parsed_name = model_str.split(":", 1)
        target_provider = parsed_prov.lower().strip()
        target_model_name = parsed_name.strip()

    builder = get_model_profile_builder(target_provider) if target_provider else None
    if builder is not None:
        try:
            built = builder(target_model_name)
            if built is not None:
                base = built
        except Exception:
            base = cast(ModelProfile, dict(DEFAULT_PROFILE))
    else:
        try:
            from pydantic_ai.models import infer_model_profile

            inferred = infer_model_profile(model_str)
            if inferred:
                base = inferred
        except Exception:
            base = cast(ModelProfile, dict(DEFAULT_PROFILE))

    return _apply_profile_spec(base, overrides)


def get_model_thinking_tags(
    model: str | ModelProfileSpec | None = None,
    provider: str | None = None,
) -> tuple[str, str]:
    """Retrieve canonical thinking block delimiters for a given model or profile."""
    prof = resolve_model_profile(model=model, provider=provider)
    tags = prof.get("thinking_tags")
    if tags and isinstance(tags, (tuple, list)) and len(tags) == 2:
        return (tags[0], tags[1])
    return DEFAULT_THINKING_TAGS


def supports_thinking(
    model: str | ModelProfileSpec | None = None,
    provider: str | None = None,
) -> bool:
    """Check whether a given model or profile natively supports thinking / reasoning blocks."""
    prof = resolve_model_profile(model=model, provider=provider)
    return bool(prof.get("supports_thinking", False))


def thinking_always_enabled(
    model: str | ModelProfileSpec | None = None,
    provider: str | None = None,
) -> bool:
    """Check whether thinking / reasoning is always enabled and cannot be disabled."""
    prof = resolve_model_profile(model=model, provider=provider)
    return bool(prof.get("thinking_always_enabled", False))


__all__ = [
    "DEFAULT_PROFILE",
    "DEFAULT_PROMPTED_OUTPUT_TEMPLATE",
    "DEFAULT_THINKING_TAGS",
    "InlineDefsJsonSchemaTransformer",
    "JsonSchemaTransformer",
    "ModelProfile",
    "ModelProfileSpec",
    "SUPPORTED_NATIVE_TOOLS",
    "StructuredOutputMode",
    "ToolAdditionMode",
    "ToolDeferralMode",
    "amazon_model_profile",
    "anthropic_model_profile",
    "cohere_model_profile",
    "deepseek_model_profile",
    "get_model_profile_builder",
    "get_model_thinking_tags",
    "google_model_profile",
    "google_realtime_model_profile",
    "grok_model_profile",
    "grok_realtime_model_profile",
    "groq_model_profile",
    "harmony_model_profile",
    "merge_profile",
    "meta_model_profile",
    "mistral_model_profile",
    "moonshotai_model_profile",
    "openai_model_profile",
    "openai_realtime_model_profile",
    "qwen_model_profile",
    "resolve_model_profile",
    "supports_thinking",
    "thinking_always_enabled",
    "zai_model_profile",
]
