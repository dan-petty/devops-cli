from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    PydanticAgent,
    _check_path_traversal,
)
from devops_cli.ai.personas import Persona
from devops_cli.ai.pydantic_ai_bridge import (
    DevOpsAgentContext,
    create_pydantic_ai_agent,
    get_persona_pydantic_agent,
    is_pydantic_ai_available,
)
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.exceptions import SecurityError


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


def test_pydantic_agent_execution_and_tools() -> None:
    """Verify PydanticAgent tool registration, validation, path traversal guard, and run loop."""
    # 1. Path traversal guard
    with pytest.raises(SecurityError, match="Path traversal"):
        _check_path_traversal("file_path", "folder/../../../etc/passwd")

    _check_path_traversal("safe_path", "src/devops_cli/main.py")

    # 2. Tool definition and execution
    def add(a: int, b: int) -> int:
        return a + b

    tool = AgentTool(
        name="add",
        description="Add two numbers",
        func=add,
        parameters={"a": {"type": "integer"}, "b": {"type": "integer"}},
    )
    assert tool.execute(a=2, b=3) == 5
    cleaned = tool.validate_args({"a": 2, "b": 3, "extra": "ignored"})
    assert cleaned == {"a": 2, "b": 3}

    # 3. PydanticAgent with tool registration
    mock_client = MagicMock()
    mock_client.chat_messages.return_value = "The sum is 5"
    mock_client.chat_messages_stream.return_value = iter(["The ", "sum ", "is 5"])

    def multiply(x: int, y: int) -> int:
        """Multiply two numbers."""
        return x * y

    agent = PydanticAgent(
        client=mock_client,
        name="MathAgent",
        system_prompt="You are a math helper",
        tools=[multiply],
    )

    assert "multiply" in agent._tools
    assert "Multiply two numbers" in agent._tools["multiply"].description

    # 4. Agent run
    resp = agent.run("Calculate 2 + 3")
    assert resp.content == "The sum is 5"
    assert resp.turns >= 1

    # 5. Agent stream
    tokens = list(agent.run_stream("Calculate 2 + 3"))
    assert "".join(tokens) == "The sum is 5"


def test_pydantic_agent_advanced_dispatch_and_schema() -> None:
    """Verify tool execution loop, memory serialization, output schema parsing, and fallback resolution."""
    from devops_cli.ai.agents.memory import AgentMemory
    from devops_cli.ai.agents.pydantic_agent import (
        ToolCall,
        _create_tool_retry_message,
        _resolve_fallback_output,
    )

    # 1. Fallback output resolution
    assert _resolve_fallback_output("Final answer", [], []) == "Final answer"
    tc = ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, result=3)
    assert _resolve_fallback_output('{"tool":"add"}', [tc], []) == "3"
    assert _resolve_fallback_output("", [], ["Deliberation thought"]) == "Deliberation thought"

    # 2. Tool retry message creation
    def sample_fn(name: str) -> str:
        """Sample function."""
        return name

    agent_tool = AgentTool(
        name="sample_fn", description="Sample", func=sample_fn, parameters={"name": "str"}
    )
    retry_msg = _create_tool_retry_message("sample_fn", agent_tool)
    assert "sample_fn" in retry_msg.content
    assert '"tool":"sample_fn"' in retry_msg.content

    # 3. Agent with memory and output schema
    mem = AgentMemory(session_id="test_sess", summary="Prior code review passed")
    mock_llm = MagicMock()
    mock_llm.chat_messages.return_value = (
        '```json\n{"summary": "Security passed", "recommendation": "APPROVE", "findings": []}\n```'
    )

    agent = PydanticAgent(
        client=mock_llm,
        name="Reviewer",
        system_prompt="Analyze code",
        output_schema=ReviewResult,
        tools=[agent_tool],
        memory=mem,
    )

    sys_prompt = agent._build_system_prompt_with_tools()
    assert "Prior code review passed" in sys_prompt
    assert "sample_fn" in sys_prompt
    assert "Required Response Format" in sys_prompt

    resp = agent.run("Generate review report")
    assert resp.data is not None
    assert resp.data.recommendation == "APPROVE"


def test_agent_memory_and_multi_agent_pipeline() -> None:
    """Verify AgentMemory auto-summarization and MultiAgentPipeline multi-stage execution."""
    from devops_cli.ai.agents.memory import AgentMemory
    from devops_cli.ai.agents.pipeline import MultiAgentPipeline

    # 1. AgentMemory operations
    mem = AgentMemory(session_id="mem-1", max_entries=4)
    for i in range(5):
        mem.add_interaction(role="user", content=f"User question {i}")
        mem.add_interaction(role="assistant", content=f"Assistant answer {i}")

    assert len(mem.entries) == 10

    mock_summarizer = MagicMock()
    mock_summarizer.chat.return_value = "Summary of conversation: 5 questions discussed."

    summarized = mem.auto_summarize_if_needed(llm_client=mock_summarizer)
    assert summarized is True
    assert "5 questions discussed" in mem.summary

    mem.clear()
    assert len(mem.entries) == 0
    assert mem.summary == ""

    # 2. MultiAgentPipeline execution
    mock_client1 = MagicMock()
    mock_client1.chat_messages.return_value = "Agent 1 output"
    mock_client2 = MagicMock()
    mock_client2.chat_messages.return_value = "Agent 2 output"

    agent1 = PydanticAgent(client=mock_client1, name="Stage1Agent", system_prompt="Stage 1")
    agent2 = PydanticAgent(client=mock_client2, name="Stage2Agent", system_prompt="Stage 2")

    pipeline = MultiAgentPipeline(agents=[agent1, agent2])
    res = pipeline.run("Initial task input", max_turns_per_agent=2)

    assert len(res.steps) == 2
    assert res.steps[0].agent_name == "Stage1Agent"
    assert res.steps[1].agent_name == "Stage2Agent"
    assert res.final_content == "Agent 2 output"
