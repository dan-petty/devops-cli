"""Unit tests for Pydantic AI common tools (web_fetch_tool, duckduckgo_search_tool, tavily_search_tool)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from devops_cli.ai.common_tools import (
    _html_to_markdown,
    duckduckgo_search_tool,
    tavily_search,
    tavily_search_tool,
    web_fetch_tool,
)
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.http.broker import get_broker
from tests.web_fakes import StubWeb


def test_html_to_markdown() -> None:
    html_sample = "<h1>Title</h1><p>Hello <b>World</b> with <a href='https://example.com'>link</a></p><script>alert(1);</script>"
    md = _html_to_markdown(html_sample)
    assert "# Title" in md
    assert "Hello World" in md
    assert "[link](https://example.com)" in md
    assert "alert(1)" not in md


def test_web_fetch_tool_success(stub_web: StubWeb) -> None:
    stub_web.page(
        "https://example.com/docs", "<html><body><h1>Docs</h1><p>Welcome to docs</p></body></html>"
    )

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
    lines = [line.strip() for line in res.splitlines()]
    assert any(line.startswith("- [https://python.org]") for line in lines)
    assert any("Python Programming Language" in line for line in lines)


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
    lines = [line.strip() for line in res.splitlines()]
    assert any(line.startswith("- **Pydantic AI** (https://ai.pydantic.dev)") for line in lines)


@patch("devops_cli.ai.common_tools.new_http_client")
def test_tavily_search_raises_on_http_error(mock_get_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_resp
    )
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_get_client.return_value = mock_client

    with pytest.raises(httpx.HTTPStatusError):
        tavily_search("test query", api_key="test-key")


@patch("devops_cli.ai.common_tools.new_http_client")
def test_tavily_search_raises_on_missing_results(mock_get_client: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"query": "test query"}
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_get_client.return_value = mock_client

    with pytest.raises(ValueError, match="results"):
        tavily_search("test query", api_key="test-key")


@pytest.mark.parametrize(
    "hop",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8200/v1/sys/health",
        "http://[64:ff9b::a9fe:a9fe]/latest/meta-data/",
        "http://168.63.129.16/machine?comp=goalstate",
    ],
    ids=["link-local", "loopback", "nat64-metadata", "wireserver"],
)
def test_web_fetch_tool_never_requests_a_private_redirect_hop(
    stub_web: StubWeb, monkeypatch: pytest.MonkeyPatch, hop: str
) -> None:
    """A public, then private, then public 3xx chain stops before the private hop is sent.

    The environment admits private networks, so only the tool's own per-hop policy can refuse it.
    """
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    stub_web.redirect("https://example.com/start", hop)
    stub_web.redirect(hop, "https://example.com/final")
    stub_web.page("https://example.com/final", "<h1>Final</h1>")

    with pytest.raises(SSRFBlockedError):
        web_fetch_tool().execute(url="https://example.com/start")

    assert stub_web.requested == ["https://example.com/start"]


@pytest.mark.parametrize(
    "hop",
    ["https://blocked.com/final", "https://blocked.com./final"],
    ids=["exact", "trailing-dot"],
)
def test_web_fetch_tool_never_requests_a_redirect_to_a_blocked_domain(
    stub_web: StubWeb, hop: str
) -> None:
    """A redirect hop is held to the tool's domain lists, not only the first URL.

    A trailing dot names the same host, so it does not get past the deny-list.
    """
    stub_web.redirect("https://example.com/start", hop)
    stub_web.page(hop, "<h1>Final</h1>")

    with pytest.raises(ValueError, match="blocked_domains"):
        web_fetch_tool(blocked_domains=["blocked.com"]).execute(url="https://example.com/start")

    assert stub_web.requested == ["https://example.com/start"]


@pytest.mark.parametrize(
    ("blocked", "url"),
    [("blocked.com", "https://blocked.com./page"), ("blocked.com.", "https://blocked.com/page")],
    ids=["url", "list-entry"],
)
def test_web_fetch_tool_refuses_a_blocked_first_url_whatever_the_trailing_dot(
    stub_web: StubWeb, blocked: str, url: str
) -> None:
    """A host and a deny-list entry are matched without their trailing dot."""
    with pytest.raises(ValueError, match="blocked_domains"):
        web_fetch_tool(blocked_domains=[blocked]).execute(url=url)

    assert stub_web.requested == []


def test_web_fetch_tool_keeps_no_cookie_between_fetches(stub_web: StubWeb) -> None:
    """A cookie a fetched site sets is never sent on a later fetch, nor kept by the shared client."""
    stub_web.page("https://example.com/set", "<h1>Set</h1>", {"set-cookie": "track=abc; Path=/"})
    stub_web.page("https://example.com/docs", "<h1>Docs</h1>")

    web_fetch_tool().execute(url="https://example.com/set")
    web_fetch_tool().execute(url="https://example.com/docs")

    sent, shared_jar = stub_web.sent[1].headers, get_broker().get_client().cookies.jar
    assert ("cookie" in sent, len(shared_jar)) == (False, 0)


def test_web_fetch_tool_sends_its_own_headers_without_trace_context(stub_web: StubWeb) -> None:
    """A fetched page receives the tool's headers and never the caller's traceparent."""
    stub_web.page("https://example.com/docs", "<h1>Docs</h1>")
    span = {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "00f067aa0ba902b7"}

    with patch("devops_cli.telemetry.context.get_current_span_context", return_value=span):
        web_fetch_tool(headers={"Accept-Language": "en"}).execute(url="https://example.com/docs")

    sent = stub_web.sent[0].headers
    assert (sent.get("accept-language"), "traceparent" in sent) == ("en", False)


def test_web_fetch_tool_blocks_dns_rebinding() -> None:
    """Verify web_fetch_tool raises SSRFBlockedError if DNS resolves to a private IP (DNS rebinding)."""
    tool = web_fetch_tool()
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 443))]):
        with pytest.raises(SSRFBlockedError):
            tool.execute(url="https://example.com/sensitive")


def test_web_fetch_tool_non_2xx_raises_tool_failed(stub_web: StubWeb) -> None:
    """Non-2xx HTTP status raises ToolFailed and is never returned as page text."""
    from devops_cli.exceptions.ai import ToolFailed

    tool = web_fetch_tool()
    with pytest.raises(ToolFailed) as exc_info:
        tool.execute(url="https://example.com/missing")

    assert "404" in str(exc_info.value)


def test_web_fetch_tool_connection_failure_raises_tool_failed(
    monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Connection errors raise ToolFailed and are never returned as page text."""
    import httpx2

    from devops_cli.exceptions.ai import ToolFailed

    def fail_handler(_request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused by target host")

    transport = httpx2.MockTransport(fail_handler)

    class FailingClient(httpx2.Client):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx2, "Client", FailingClient)

    tool = web_fetch_tool()
    with pytest.raises(ToolFailed) as exc_info:
        tool.execute(url="https://example.com/unreachable")

    assert "Connection refused" in str(exc_info.value)


def test_web_fetch_tool_runner_dispatches_tool_failed_and_error(stub_web: StubWeb) -> None:
    """Runner maps ToolFailed to tool_failed status and SSRFBlockedError to error status."""
    from devops_cli.ai.agents.runner import _execute_single_tool

    tool = web_fetch_tool()

    # 1. Non-2xx response -> tool_failed
    status_404, _, res_404 = _execute_single_tool(
        tool, "web_fetch", {"url": "https://example.com/not_found"}, []
    )
    assert (status_404, "404" in str(res_404)) == ("tool_failed", True)

    # 2. SSRF block -> error
    status_ssrf, _, res_ssrf = _execute_single_tool(
        tool, "web_fetch", {"url": "http://127.0.0.1:8080/admin"}, []
    )
    assert (status_ssrf, "SSRF blocked" in str(res_ssrf)) == ("error", True)
