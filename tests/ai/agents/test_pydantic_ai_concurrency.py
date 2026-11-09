"""Unit tests for the concurrency limits the bridge hands to Pydantic AI."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.concurrency import ConcurrencyLimitedModel
from pydantic_ai.models.test import TestModel

from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model


def test_resolve_pydantic_ai_model_limits_a_model_concurrency_only_when_asked() -> None:
    """Verify the bridge wraps a model in the concurrency limit it is given and no other."""
    test_model = TestModel(call_tools=[])

    unwrapped = resolve_pydantic_ai_model(test_model, model_concurrency=None)
    wrapped = resolve_pydantic_ai_model(test_model, model_concurrency=2)

    assert unwrapped is test_model
    assert isinstance(wrapped, ConcurrencyLimitedModel)
    assert Agent(wrapped).run_sync("hello").output == "success (no tool calls)"
