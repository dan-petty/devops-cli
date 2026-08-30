"""Unit tests for Pydantic AI common tools (web_fetch_tool, duckduckgo_search_tool, tavily_search_tool)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.common_tools import (
    _html_to_markdown,
    _is_private_or_loopback,
    duckduckgo_search_tool,
    tavily_search_tool,
    web_fetch_tool,
)
from devops_cli.exceptions.security import SSRFBlockedError


def test_is_private_or_loopback() -> None:
    assert _is_private_or_loopback("localhost") is True
    assert _is_private_or_loopback("127.0.0.1") is True
    assert _is_private_or_loopback("10.0.0.1") is True
    assert _is_private_or_loopback("192.168.1.1") is True
    assert _is_private_or_loopback("169.254.169.254") is True
    assert _is_private_or_loopback("cluster.local") is True
    assert _is_private_or_loopback("api.github.com") is False
    assert _is_private_or_loopback("pydantic.dev") is False


def test_html_to_markdown() -> None:
    html_sample = "<h1>Title</h1><p>Hello <b>World</b> with <a href='https://example.com'>link</a></p><script>alert(1);</script>"
    md = _html_to_markdown(html_sample)
    assert "# Title" in md
    assert "Hello World" in md
    assert "[link](https://example.com)" in md
    assert "alert(1)" not in md


@patch("devops_cli.ai.common_tools.new_http_client")
def test_web_fetch_tool_success(mock_get_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.content = b"<html><body><h1>Docs</h1><p>Welcome to docs</p></body></html>"
    mock_resp.text = "<html><body><h1>Docs</h1><p>Welcome to docs</p></body></html>"
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_get_client.return_value = mock_client

    fetch_tool = web_fetch_tool(max_content_length=1000)
    assert fetch_tool.name == "web_fetch"

    res = fetch_tool.execute(url="https://example.com/docs")
    assert "# Docs" in res
    assert "Welcome to docs" in res


def test_web_fetch_tool_ssrf_protection() -> None:
    fetch_tool = web_fetch_tool()
    with pytest.raises(SSRFBlockedError):
        fetch_tool.execute(url="http://127.0.0.1:8080/admin")

    with pytest.raises(SSRFBlockedError):
        fetch_tool.execute(url="http://localhost:5000/metrics")


@patch("devops_cli.ai.common_tools.new_http_client")
def test_duckduckgo_search_tool(mock_get_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.text = """
    <a class="result__snippet" href="https%3A%2F%2Fpython.org">Python Programming <b>Language</b></a>
    <a class="result__snippet" href="https%3A%2F%2Fdocs.python.org">Python <i>Documentation</i></a>
    """
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_get_client.return_value = mock_client

    ddg_tool = duckduckgo_search_tool(max_results=2)
    assert ddg_tool.name == "duckduckgo_search"

    res = ddg_tool.execute(query="python programming")
    assert "https://python.org" in res
    assert "Python Programming Language" in res


@patch("devops_cli.ai.common_tools.new_http_client")
def test_tavily_search_tool(mock_get_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "Pydantic AI",
                "url": "https://ai.pydantic.dev",
                "content": "Agent framework for Python.",
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_get_client.return_value = mock_client

    tav_tool = tavily_search_tool(api_key="test-key", max_results=3)
    assert tav_tool.name == "tavily_search"

    res = tav_tool.execute(query="pydantic ai")
    assert "Pydantic AI" in res
    assert "https://ai.pydantic.dev" in res
