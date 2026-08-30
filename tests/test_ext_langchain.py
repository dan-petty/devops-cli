"""Unit tests for third-party tool adapters (tool_from_langchain, LangChainToolset)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from devops_cli.ai.agents import PydanticAgent
from devops_cli.ai.ext_langchain import LangChainToolset, tool_from_langchain


class MockSearchSchema(BaseModel):
    query: str = Field(description="Search query string")
    max_results: int = Field(default=5, description="Max results")


class MockLangChainTool:
    """Mock representing a LangChain BaseTool / StructuredTool."""

    name: str = "mock_langchain_search"
    description: str = "Search for external resources."
    args_schema = MockSearchSchema

    def invoke(self, input_dict: dict[str, Any]) -> str:
        return f"Results for: {input_dict.get('query')}"


class MockSimpleTool:
    """Mock representing a simple LangChain tool with .run()."""

    name: str = "simple_calc"
    description: str = "Simple calculator."
    args: dict[str, Any] = {"expr": {"type": "str"}}

    def run(self, input_dict: dict[str, Any]) -> str:
        return f"Evaluated: {input_dict.get('expr')}"


def test_tool_from_langchain_with_schema() -> None:
    lc_tool = MockLangChainTool()
    tool = tool_from_langchain(lc_tool)

    assert tool.name == "mock_langchain_search"
    assert "Search for external resources" in tool.description
    assert "query" in tool.parameters
    assert "max_results" in tool.parameters

    res = tool.execute(query="kubernetes manifests", max_results=3)
    assert res == "Results for: kubernetes manifests"


def test_tool_from_langchain_with_run() -> None:
    lc_tool = MockSimpleTool()
    tool = tool_from_langchain(lc_tool)

    assert tool.name == "simple_calc"
    res = tool.execute(expr="2 + 2")
    assert res == "Evaluated: 2 + 2"


def test_tool_from_langchain_invalid() -> None:
    with pytest.raises(TypeError):
        tool_from_langchain("not_a_tool")


def test_langchain_toolset_and_agent_integration() -> None:
    lc_tool = MockLangChainTool()
    toolset = LangChainToolset(tools=[lc_tool], instructions="Always cite LangChain sources.")

    assert len(toolset.get_tools()) == 1
    assert "Always cite LangChain sources" in toolset.get_instructions()[0]

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent(
        client=mock_client,
        name="LangChainAgent",
        toolsets=[toolset],
    )

    assert "mock_langchain_search" in agent._tools
    sys_prompt = agent._build_system_prompt_with_tools()
    assert "Always cite LangChain sources" in sys_prompt
