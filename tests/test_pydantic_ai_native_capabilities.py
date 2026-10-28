"""Comprehensive unit tests for Pydantic AI native capabilities integration and dual compatibility."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.test import TestModel

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.agents.capabilities import (
    BaseCapability,
    HandleDeferredToolCalls,
    SystemReminders,
)
from devops_cli.ai.review_schema import ReviewResult

pytestmark = pytest.mark.usefixtures("keyring_store")


class MathCapability(BaseCapability):
    """A capability that offers one tool and one instruction."""

    id: str = "math"

    def get_tools(self) -> list[Any]:
        def multiply_numbers(x: int, y: int) -> int:
            """Multiply two integers."""
            return x * y

        return [multiply_numbers]

    def get_system_prompt_additions(self, ctx: Any = None) -> list[str]:
        return ["You are a helpful mathematical assistant."]


def test_all_capabilities_inherit_from_abstract_capability() -> None:
    """Verify that BaseCapability and every derived capability inherits from pydantic_ai AbstractCapability."""
    all_capability_classes: list[type[BaseCapability]] = [
        BaseCapability,
        HandleDeferredToolCalls,
        SystemReminders,
    ]

    for cls in all_capability_classes:
        assert issubclass(cls, AbstractCapability), (
            f"{cls.__name__} must inherit from pydantic_ai.capabilities.AbstractCapability"
        )
        assert issubclass(cls, BaseModel), (
            f"{cls.__name__} must preserve Pydantic BaseModel inheritance"
        )


def test_base_capability_native_agent_execution() -> None:
    """Verify that passing BaseCapability to native pydantic_ai.Agent runs without TypeError."""
    cap = BaseCapability(id="custom_base", description="Test Base Capability")
    assert isinstance(cap, AbstractCapability)

    agent = Agent(model=TestModel(), capabilities=[cap])
    res = agent.run_sync("ping")
    assert res.output == "success (no tool calls)"


def test_system_reminders_in_native_agent() -> None:
    """Verify SystemReminders capability in native Agent execution."""
    sr = SystemReminders(reminders=["Follow zero-trust security rules."], cadence=1)
    assert isinstance(sr, AbstractCapability)

    instructions = sr.get_instructions()
    assert "Follow zero-trust security rules." in instructions

    agent = Agent(model=TestModel(), capabilities=[sr])
    res = agent.run_sync("verify policy")
    assert res.output == "success (no tool calls)"


def test_capability_tools_and_instructions_in_native_agent() -> None:
    """Verify that tools a capability offers are exposed via get_toolset and executed natively."""
    cap = MathCapability()

    # Verify native AbstractCapability protocol methods
    instructions = cap.get_instructions()
    assert instructions == ["You are a helpful mathematical assistant."]

    toolset = cap.get_toolset()
    assert toolset is not None

    # Execute in native Agent with tool invocation
    agent = Agent(
        model=TestModel(call_tools=["multiply_numbers"]),
        capabilities=[cap],
    )
    res = agent.run_sync("multiply 4 and 5")
    assert res.output == '{"multiply_numbers":0}'


def test_dual_compatibility_with_devops_cli_pydantic_agent() -> None:
    """Verify that custom unified PydanticAgent continues to execute flawlessly with capabilities."""
    cap = MathCapability()

    agent = PydanticAgent[ReviewResult](
        name="SecurityReviewer",
        system_prompt="Base reviewer prompt",
        capabilities=[cap],
        model="test",
    )

    assert len(agent.capabilities) == 1
    assert agent.name == "SecurityReviewer"
    # Ensure tools from capability are registered
    tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in agent.tools]
    assert "multiply_numbers" in tool_names
