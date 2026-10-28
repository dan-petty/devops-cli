"""Unit tests for `firecrawl_search`, the web search of the roadmap refinement investigation."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.common_tools import firecrawl_search
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_LIMIT
from tests.web_fakes import StubWeb

_FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
_RESULTS = [
    {
        "title": "Pydantic AI",
        "url": "https://example.com/pydantic-ai",
        "description": "Agent framework for Python.",
        "position": 1,
    },
    {
        "title": "Ruff",
        "url": "https://example.com/ruff",
        "description": "A Python linter.",
        "position": 2,
    },
]


def _serve_firecrawl(stub_web: StubWeb, reply: Any) -> None:
    """Answer Firecrawl's search endpoint with `reply` serialised as JSON."""
    stub_web.content(_FIRECRAWL_URL, json.dumps(reply).encode())


def test_firecrawl_search_posts_the_query_with_the_key_and_returns_the_web_results(
    stub_web: StubWeb,
) -> None:
    _serve_firecrawl(stub_web, {"success": True, "data": {"web": _RESULTS}, "creditsUsed": 2})

    results = firecrawl_search("pydantic ai", api_key="fc-test")

    assert (
        results,
        [(request.method, str(request.url)) for request in stub_web.sent],
        [request.headers["Authorization"] for request in stub_web.sent],
        [json.loads(request.content) for request in stub_web.sent],
    ) == (
        _RESULTS,
        [("POST", _FIRECRAWL_URL)],
        ["Bearer fc-test"],
        [{"query": "pydantic ai", "limit": DEFAULT_FIRECRAWL_SEARCH_LIMIT}],
    )


def test_firecrawl_search_sends_the_result_cap(stub_web: StubWeb) -> None:
    _serve_firecrawl(stub_web, {"success": True, "data": {"web": []}})

    results = firecrawl_search("linters", api_key="fc-test", limit=2)

    assert (results, [json.loads(request.content)["limit"] for request in stub_web.sent]) == (
        [],
        [2],
    )


def test_firecrawl_search_raises_on_http_error(stub_web: StubWeb) -> None:
    """A status the stub has no page for is a 404, which `raise_for_status` turns into an error."""
    with pytest.raises(httpx2.HTTPStatusError):
        firecrawl_search("test query", api_key="fc-test")

    assert stub_web.requested == [_FIRECRAWL_URL]


@pytest.mark.parametrize(
    "reply",
    [
        {"success": True},
        {"success": True, "data": {"news": []}},
        {"success": True, "data": {"web": "none"}},
        ["not", "an", "object"],
    ],
    ids=["no-data", "no-web-results", "web-not-a-list", "reply-not-an-object"],
)
def test_firecrawl_search_raises_on_a_reply_without_a_web_results_list(
    stub_web: StubWeb, reply: Any
) -> None:
    _serve_firecrawl(stub_web, reply)

    with pytest.raises(ValueError, match=r"data\.web"):
        firecrawl_search("test query", api_key="fc-test")
