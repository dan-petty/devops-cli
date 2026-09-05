"""Comprehensive unit tests for Pydantic AI native capabilities integration and dual compatibility."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.test import TestModel

from devops_cli.ai.agents.capabilities import (
    MCP,
    BaseCapability,
    Capability,
    HandleDeferredToolCalls,
    IncludeToolReturnSchemas,
    Instrumentation,
    NativeTool,
    PrefixTools,
    PrepareTools,
    ProcessEventStream,
    ProcessHistory,
    RaiseContentFilterError,
    ReinjectSystemPrompt,
    ResolveModelId,
    SelectModel,
    SetToolMetadata,
    SystemReminders,
    Thinking,
    UseThreadExecutor,
    WebFetch,
    WebSearch,
)
from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.harness.docs import PydanticAIDocs
from devops_cli.ai.personas import Persona
from devops_cli.ai.pydantic_ai_bridge import (
    DevOpsAgentContext,
    create_pydantic_ai_agent,
    get_persona_pydantic_agent,
)
from devops_cli.ai.review_schema import ReviewResult


def test_all_capabilities_inherit_from_abstract_capability() -> None:
    """Verify that BaseCapability and every derived capability inherits from pydantic_ai AbstractCapability."""
    all_capability_classes: list[type[BaseCapability]] = [
        BaseCapability,
        Capability,
        Thinking,
        WebSearch,
        WebFetch,
        MCP,
        NativeTool,
        PrefixTools,
        SetToolMetadata,
        UseThreadExecutor,
        Instrumentation,
        SelectModel,
        ResolveModelId,
        HandleDeferredToolCalls,
        IncludeToolReturnSchemas,
        RaiseContentFilterError,
        ReinjectSystemPrompt,
        PrepareTools,
        ProcessHistory,
        ProcessEventStream,
        SystemReminders,
        PydanticAIDocs,
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


def test_thinking_capability_native_agent_execution() -> None:
    """Verify that Thinking capability passes settings to native pydantic_ai.Agent without error."""
    th = Thinking(effort="medium", budget_tokens=4096, include_thoughts=True)
    assert isinstance(th, AbstractCapability)

    # Check model settings
    settings = th.get_model_settings()
    assert settings.get("thinking") == "medium"
    assert settings.get("budget_tokens") == 4096

    # Native agent execution
    agent = Agent(model=TestModel(), capabilities=[th])
    res = agent.run_sync("think deeply")
    assert res.output == "success (no tool calls)"


def test_capability_tools_and_instructions_in_native_agent() -> None:
    """Verify that tools registered on Capability are exposed via get_toolset and executed natively."""
    cap = Capability(instructions="You are a helpful mathematical assistant.")

    @cap.tool
    def multiply_numbers(x: int, y: int) -> int:
        """Multiply two integers."""
        return x * y

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


def test_system_reminders_in_native_agent() -> None:
    """Verify SystemReminders capability in native Agent execution."""
    sr = SystemReminders(reminders=["Follow zero-trust security rules."], cadence=1)
    assert isinstance(sr, AbstractCapability)

    instructions = sr.get_instructions()
    assert "Follow zero-trust security rules." in instructions

    agent = Agent(model=TestModel(), capabilities=[sr])
    res = agent.run_sync("verify policy")
    assert res.output == "success (no tool calls)"


def test_pydantic_ai_docs_capability_in_native_agent() -> None:
    """Verify PydanticAIDocs capability runs natively in pydantic_ai.Agent."""
    docs_cap = PydanticAIDocs(cache=True)
    assert isinstance(docs_cap, AbstractCapability)

    instructions = docs_cap.get_instructions()
    assert any("read_pyai_docs" in str(inst) for inst in instructions)

    agent = Agent(model=TestModel(call_tools=[]), capabilities=[docs_cap])
    res = agent.run_sync("read docs")
    assert res.output == "success (no tool calls)"


def test_dual_compatibility_with_devops_cli_pydantic_agent() -> None:
    """Verify that custom unified PydanticAgent continues to execute flawlessly with capabilities."""
    cap = Capability(instructions="Strict DevOps guidelines.")

    @cap.tool
    def calculate_uptime(days: int) -> float:
        """Calculate availability."""
        return 99.99

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
    assert "calculate_uptime" in tool_names


def test_create_pydantic_ai_agent_with_native_capabilities() -> None:
    """Verify create_pydantic_ai_agent instantiates native Agent that runs with capabilities."""
    th = Thinking(effort="low")
    cap = Capability(instructions="Always follow clean code.")

    agent = create_pydantic_ai_agent(
        model_name="test",
        system_prompt="Primary system prompt",
        output_type=ReviewResult,
        deps_type=DevOpsAgentContext,
        capabilities=[th, cap],
    )

    assert isinstance(agent, Agent)
    res = agent.run_sync("review code")
    assert isinstance(res.output, ReviewResult)


def test_get_persona_pydantic_agent_native_execution() -> None:
    """Verify persona-specialized agent instantiation and execution."""
    th = Thinking(effort="medium")
    agent = get_persona_pydantic_agent(
        persona=Persona.DEVSECOPS,
        capabilities=[th],
        model_name="test",
    )

    assert isinstance(agent, Agent)
    res = agent.run_sync("perform security check")
    assert isinstance(res.output, ReviewResult)
