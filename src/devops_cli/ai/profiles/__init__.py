"""Model profile resolution and thinking block configuration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from devops_cli.config.defaults import (
    DEFAULT_THINKING_INITIAL_STATE,
    DEFAULT_THINKING_TAGS,
)

if TYPE_CHECKING:
    from pydantic_ai.profiles import ModelProfileSpec


def _apply_profile_spec(
    profile: ModelProfileSpec | None = None,
    base_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve and apply a ModelProfileSpec against base profile defaults."""
    base: dict[str, Any] = {
        "initial_state": DEFAULT_THINKING_INITIAL_STATE,
        "thinking_tags": DEFAULT_THINKING_TAGS,
        "supports_thinking": False,
        **(base_profile or {}),
    }
    if profile is None:
        return base
    if callable(profile):
        profile_fn = cast(Callable[..., Any], profile)
        result = profile_fn(base)
        return {**base, **(result or {})}
    if isinstance(profile, dict):
        return {**base, **profile}
    return base


def get_model_thinking_tags(
    model_name: str | None = None,
    profile: ModelProfileSpec | None = None,
) -> tuple[str, str]:
    """Return thinking tags tuple for the model or profile."""
    resolved = _apply_profile_spec(profile)
    tags = resolved.get("thinking_tags")
    if isinstance(tags, (list, tuple)) and len(tags) == 2 and tags[0] and tags[1]:
        return (str(tags[0]), str(tags[1]))
    return DEFAULT_THINKING_TAGS


def supports_thinking(
    model_name: str | None = None,
    profile: ModelProfileSpec | None = None,
) -> bool:
    """Return True if the model or profile supports thinking blocks."""
    resolved = _apply_profile_spec(profile)
    if resolved.get("supports_thinking"):
        return True
    if model_name:
        lowered = model_name.lower()
        return any(
            pattern in lowered
            for pattern in ("r1", "deepseek", "qwen", "claude-3-7", ":thinking", "thinking")
        )
    return False


__all__ = [
    "_apply_profile_spec",
    "get_model_thinking_tags",
    "supports_thinking",
]
