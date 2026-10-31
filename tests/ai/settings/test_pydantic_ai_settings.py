"""Unit tests for the Pydantic AI model settings construction in devops-cli."""

from __future__ import annotations

from devops_cli.ai.settings import create_model_settings


def test_create_model_settings_keeps_only_the_values_given() -> None:
    """Verify create_model_settings builds ModelSettings without entries for unset values."""
    settings = create_model_settings(
        temperature=0.7,
        max_tokens=2048,
        thinking="high",
        service_tier="priority",
        parallel_tool_calls=True,
        seed=None,
        custom_extra="custom_value",
    )

    assert settings == {
        "temperature": 0.7,
        "max_tokens": 2048,
        "thinking": "high",
        "service_tier": "priority",
        "parallel_tool_calls": True,
        "custom_extra": "custom_value",
    }
