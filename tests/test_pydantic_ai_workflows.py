"""Tests for the fallback cascade models the bridge builds and the gateway routes through."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from devops_cli.ai.gateway import GatewayRouter
from devops_cli.ai.pydantic_ai_bridge import (
    build_fallback_cascade_model,
    resolve_pydantic_ai_model,
)
from devops_cli.config.settings import AIConfig


def test_build_fallback_cascade_model_and_runtime_failover() -> None:
    """Verify FallbackModel chaining and failover upon provider errors."""

    class FailingTestModel(TestModel):
        async def request(self, *args: Any, **kwargs: Any) -> Any:
            raise ModelHTTPError(status_code=503, model_name="test-fail", body="unavailable")

    m1 = FailingTestModel()
    m2 = TestModel(custom_output_text="Fallback succeeded")

    fb_model = build_fallback_cascade_model([m1, m2])
    assert isinstance(fb_model, FallbackModel)

    agent = Agent(model=fb_model)
    result = agent.run_sync("test prompt")
    assert result.output == "Fallback succeeded"
    assert isinstance(result.usage, RunUsage)


def test_resolve_pydantic_ai_model_cascade() -> None:
    """Verify resolve_pydantic_ai_model supports cascade aliases and sequences."""
    m1 = TestModel()
    m2 = TestModel()
    cascade_model = resolve_pydantic_ai_model([m1, m2])
    assert isinstance(cascade_model, FallbackModel)

    single_model = resolve_pydantic_ai_model([m1])
    assert single_model == m1

    empty_model = resolve_pydantic_ai_model([])
    assert empty_model is None


def test_llm_gateway_build_pydantic_cascade_model() -> None:
    """Verify GatewayRouter.build_pydantic_cascade_model creates a valid model."""
    gw = GatewayRouter(AIConfig())
    with patch("devops_cli.ai.pydantic_ai_bridge.resolve_pydantic_ai_model") as mock_resolve:
        mock_resolve.side_effect = lambda m, **kw: TestModel()
        model = gw.build_pydantic_cascade_model("devops-chat")
        assert isinstance(model, FallbackModel)
        assert len(model.models) > 0
