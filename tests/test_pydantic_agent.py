"""Unit tests for PydanticAI standardized agent framework adapter and bridge."""

from __future__ import annotations

from devops_cli.ai.personas import Persona
from devops_cli.ai.pydantic_ai_bridge import (
    DevOpsAgentContext,
    create_pydantic_ai_agent,
    get_persona_pydantic_agent,
    is_pydantic_ai_available,
)
from devops_cli.ai.review_schema import ReviewResult


def test_is_pydantic_ai_available() -> None:
    assert is_pydantic_ai_available() is True


def test_devops_agent_context_model() -> None:
    ctx = DevOpsAgentContext(
        target_repo="/workspaces/test",
        active_persona="devsecops",
        context_tokens_budget=8192,
    )
    assert ctx.target_repo == "/workspaces/test"
    assert ctx.active_persona == "devsecops"
    assert ctx.context_tokens_budget == 8192


def test_create_pydantic_ai_agent() -> None:
    agent = create_pydantic_ai_agent(
        model_name="ollama:test-model",
        system_prompt="You are a test reviewer.",
        result_type=ReviewResult,
        deps_type=DevOpsAgentContext,
    )
    assert agent is not None


def test_get_persona_pydantic_agent() -> None:
    agent = get_persona_pydantic_agent(Persona.DEVSECOPS)
    assert agent is not None
