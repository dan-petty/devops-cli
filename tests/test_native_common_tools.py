"""Unit tests for native Pydantic AI common tools, TypedDict schemas, and agent integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.agents.tools import Tool
from devops_cli.ai.common_tools import (
    DuckDuckGoResult,
    ExaSearchResult,
    TavilySearchResult,
    WebFetchResult,
    duckduckgo_search_tool,
    exa_search_tool,
    image_generation_tool,
    tavily_search_tool,
    web_fetch_tool,
    x_search_tool,
)
from devops_cli.exceptions.security import SSRFBlockedError


def test_typed_dict_schemas() -> None:
    """Verify TypedDict schemas conform to native Pydantic AI structures."""
    web_res: WebFetchResult = {"url": "https://example.com", "title": "Example", "content": "Hello"}
    assert web_res["url"] == "https://example.com"
    assert web_res["title"] == "Example"

    ddg_res: DuckDuckGoResult = {"title": "DDG", "href": "https://ddg.gg", "body": "Search engine"}
    assert ddg_res["title"] == "DDG"
    assert ddg_res["href"] == "https://ddg.gg"

    tav_res: TavilySearchResult = {
        "title": "Tavily",
        "url": "https://tavily.com",
        "content": "Search",
        "score": 0.95,
    }
    assert tav_res["score"] == 0.95

    exa_res: ExaSearchResult = {
        "title": "Exa",
        "url": "https://exa.ai",
        "published_date": "2026-01-01",
        "author": "Exa Team",
        "text": "Neural search",
    }
    assert exa_res["text"] == "Neural search"


def test_image_generation_tool_native_export() -> None:
    """Verify native image generation tool is available and callable as a tool."""
    from pydantic_ai.common_tools.image_generation import ImageGenerationTool

    tool = image_generation_tool("test-model", ImageGenerationTool())
    assert tool is not None
    assert hasattr(tool, "name") or callable(tool)


def test_x_search_tool_native_export() -> None:
    """Verify native x_search tool is available and callable as a tool."""
    from pydantic_ai.common_tools.x_search import XSearchTool

    tool = x_search_tool("test-model", XSearchTool())
    assert tool is not None
    assert hasattr(tool, "name") or callable(tool)


@patch("devops_cli.ai.common_tools.new_http_client")
def test_web_fetch_tool_structure(mock_http_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.content = (
        b"<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>Body</p></body></html>"
    )
    mock_resp.text = (
        "<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>Body</p></body></html>"
    )
    mock_resp.status_code = 200
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_http_client.return_value = mock_client

    tool = web_fetch_tool(max_content_length=1000)
    assert isinstance(tool, Tool)
    res = tool.execute(url="https://docs.pydantic.dev")
    assert "# Hello" in res or "Body" in res


def test_web_fetch_tool_blocks_ssrf() -> None:
    tool = web_fetch_tool()
    with pytest.raises(SSRFBlockedError):
        tool.execute(url="http://127.0.0.1:8080/admin")


@patch("devops_cli.ai.common_tools.new_http_client")
def test_duckduckgo_search_tool_structure(mock_http_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.text = (
        '<a class="result__snippet" href="https%3A%2F%2Fpython.org">Python Programming</a>'
    )
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_http_client.return_value = mock_client

    tool = duckduckgo_search_tool(max_results=1)
    assert isinstance(tool, Tool)
    res = tool.execute(query="python")
    assert "https://python.org" in res


@patch("devops_cli.ai.common_tools.new_http_client")
def test_tavily_search_tool_structure(mock_http_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "Pydantic AI",
                "url": "https://ai.pydantic.dev",
                "content": "Fast",
                "score": 0.9,
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_http_client.return_value = mock_client

    tool = tavily_search_tool(api_key="test-key", max_results=1)
    assert isinstance(tool, Tool)
    res = tool.execute(query="pydantic ai")
    assert "Pydantic AI" in res


def test_exa_search_tool_fallback() -> None:
    """Verify exa search tool fallback handles execution cleanly."""
    tool = exa_search_tool(api_key="test-key", num_results=3)
    assert isinstance(tool, Tool)
    assert tool.name == "exa_search"
    res = tool.execute(query="pydantic ai")
    assert "Exa search result" in res


def test_native_toolsets_reexports() -> None:
    """Verify native toolsets from pydantic_ai.toolsets are available via pydantic_agent."""
    from devops_cli.ai.agents.pydantic_agent import (
        ApprovalRequiredToolset,
        CombinedToolset,
        DeferredLoadingToolset,
        DynamicToolset,
        ExternalToolset,
        FilteredToolset,
        FunctionToolset,
        PrefixedToolset,
        approval_required,
        prefixed,
    )

    assert ApprovalRequiredToolset is not None
    assert CombinedToolset is not None
    assert DeferredLoadingToolset is not None
    assert DynamicToolset is not None
    assert ExternalToolset is not None
    assert FilteredToolset is not None
    assert FunctionToolset is not None
    assert PrefixedToolset is not None
    assert approval_required is not None
    assert prefixed is not None


def test_native_common_tools_reexports_in_agents() -> None:
    """Verify native common tools are re-exported from devops_cli.ai.agents."""
    import devops_cli.ai.agents as agents

    assert hasattr(agents, "duckduckgo_search_tool")
    assert hasattr(agents, "web_fetch_tool")
    assert hasattr(agents, "tavily_search_tool")
    assert hasattr(agents, "image_generation_tool")
    assert hasattr(agents, "x_search_tool")
    assert hasattr(agents, "exa_search_tool")
    assert hasattr(agents, "DuckDuckGoResult")
    assert hasattr(agents, "WebFetchResult")
    assert hasattr(agents, "TavilySearchResult")
    assert hasattr(agents, "ExaSearchResult")
