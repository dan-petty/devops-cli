"""Tests for PydanticAgent, tools, and streaming."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pydantic import BaseModel

from devops_cli.ai.agents import AgentResponse, PydanticAgent
from devops_cli.ai.client import LLMClient


class SampleSchema(BaseModel):
    summary: str
    status: str


def dummy_tool(query: str) -> str:
    """A dummy test tool."""
    return f"result for {query}"


def test_agent_tool_registration() -> None:
    client = MagicMock(spec=LLMClient)
    agent = PydanticAgent(client=client, tools=[dummy_tool])
    assert "dummy_tool" in agent._tools
    tool = agent._tools["dummy_tool"]
    assert tool.name == "dummy_tool"
    assert tool.execute(query="test") == "result for test"


def test_agent_run_simple() -> None:
    client = MagicMock(spec=LLMClient)
    client.chat_messages.return_value = "Hello from agent!"
    agent = PydanticAgent(client=client)

    response = agent.run("Hi")
    assert isinstance(response, AgentResponse)
    assert response.content == "Hello from agent!"
    assert response.turns == 1


def test_agent_run_tool_call() -> None:
    client = MagicMock(spec=LLMClient)
    client.chat_messages.side_effect = [
        '```json\n{\n  "tool": "dummy_tool",\n  "arguments": {"query": "hello"}\n}\n```',
        "Final response after tool execution.",
    ]
    agent = PydanticAgent(client=client, tools=[dummy_tool])

    response = agent.run("Find info")
    assert response.content == "Final response after tool execution."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "dummy_tool"
    assert response.tool_calls[0].result == "result for hello"


def test_agent_stream() -> None:
    client = MagicMock(spec=LLMClient)
    client.chat_messages_stream.return_value = iter(["Hello", " ", "world!"])
    agent = PydanticAgent(client=client)

    chunks = list(agent.run_stream("Hi"))
    assert chunks == ["Hello", " ", "world!"]


def test_ollama_stream_thinking_fallback(mocker: MagicMock) -> None:
    import httpx2

    from devops_cli.config.settings import AIConfig

    config = AIConfig(
        provider="ollama", model="qwen2.5-coder:7b", ollama_urls=["http://localhost:11434"]
    )
    client = LLMClient(config)

    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "model 'qwen2.5-coder:7b' does not support thinking"
    mock_resp_400.read.return_value = None

    exc_400 = httpx2.HTTPStatusError("400 Bad Request", request=MagicMock(), response=mock_resp_400)

    mock_stream_req = mocker.patch.object(
        client,
        "_ollama_stream_request",
        side_effect=[exc_400, iter(["Response ", "without ", "thinking"])],
    )

    chunks = list(
        client._ollama_stream("sys", [{"role": "user", "content": "hi"}], enable_thinking=True)
    )
    assert "".join(chunks) == "Response without thinking"
    assert client._ollama_thinking_supported is False
    assert mock_stream_req.call_count == 2


def test_multi_agent_pipeline() -> None:
    from devops_cli.ai.agents import MultiAgentPipeline, PydanticAgent

    client1 = MagicMock(spec=LLMClient)
    client1.chat_messages.return_value = "Scanner report: files look clean."
    client2 = MagicMock(spec=LLMClient)
    client2.chat_messages.return_value = "Architect report: SOLID patterns used."

    agent1 = PydanticAgent(client=client1, name="DevSecOps", system_prompt="Scan code")
    agent2 = PydanticAgent(client=client2, name="Architect", system_prompt="Check design")

    pipeline = MultiAgentPipeline[Any](agents=[agent1, agent2])
    res = pipeline.run("Analyze workspace")

    assert len(res.steps) == 2
    assert res.steps[0].agent_name == "DevSecOps"
    assert res.steps[0].content == "Scanner report: files look clean."
    assert res.steps[1].agent_name == "Architect"
    assert res.steps[1].content == "Architect report: SOLID patterns used."
    assert res.final_content == "Architect report: SOLID patterns used."
    assert len(res.scratchpad.entries) == 2
    assert res.scratchpad.entries[0].persona == "DevSecOps"
    assert "Scratchpad Reasoning Context" in res.scratchpad.render_context_summary()


def test_get_default_tools_includes_mcp() -> None:
    from devops_cli.ai.tools import get_default_tools, get_mcp_agent_tools

    mcp_tools = get_mcp_agent_tools()
    all_tools = get_default_tools()

    assert len(mcp_tools) >= 20
    assert len(all_tools) >= len(mcp_tools) + 10
    tool_names = [t.__name__ for t in all_tools]
    assert "repos_list" in tool_names
    assert "k8s_status" in tool_names
    assert "k8s_jaeger_status" in tool_names
    assert "scan_osv" in tool_names
    assert "check_threat_intel" in tool_names
    assert "ci_run" in tool_names


def test_get_persona_tools_selection() -> None:
    from devops_cli.ai.personas import Persona
    from devops_cli.ai.tools import get_persona_tools

    sec_tools = [t.__name__ for t in get_persona_tools(Persona.DEVSECOPS)]
    assert "scan_trivy" in sec_tools
    assert "scan_osv" in sec_tools
    assert "check_threat_intel" in sec_tools
    assert "scan_bandit" in sec_tools

    arch_tools = [t.__name__ for t in get_persona_tools(Persona.ARCHITECT)]
    assert "tf_plan" in arch_tools
    assert "k8s_jaeger_status" in arch_tools
    assert "k8s_pods" in arch_tools
    assert "argo_apps" in arch_tools

    qa_tools = [t.__name__ for t in get_persona_tools(Persona.QA)]
    assert "ci_run" in qa_tools
    assert "git_diff" in qa_tools

    pm_tools = [t.__name__ for t in get_persona_tools(Persona.PM)]
    assert "repos_list" in pm_tools
    assert "repos_status" in pm_tools
