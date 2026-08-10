"""Tests for PydanticAgent, tools, and streaming."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import BaseModel

from devops_cli.ai.agent import AgentResponse, PydanticAgent
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
        provider="ollama", model="qwen2.5-coder:7b", ollama_url="http://localhost:11434"
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
