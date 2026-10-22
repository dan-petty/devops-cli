"""Unit tests for `tavily_search`, the one search call the roadmap refinement research step makes."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.common_tools import tavily_search
from devops_cli.config.defaults import DEFAULT_TAVILY_MAX_RESULTS
from tests.web_fakes import StubWeb

_TAVILY_URL = "https://api.tavily.com/search"
_RESULTS = [
    {
        "title": "Pydantic AI",
        "url": "https://example.com/pydantic-ai",
        "content": "Agent framework for Python.",
    },
    {"title": "Ruff", "url": "https://example.com/ruff", "content": "A Python linter."},
]


def _serve_tavily(stub_web: StubWeb, reply: Any) -> None:
    """Answer Tavily's search endpoint with `reply` serialised as JSON."""
    stub_web.content(_TAVILY_URL, json.dumps(reply).encode())


def test_tavily_search_posts_the_query_and_returns_the_results(stub_web: StubWeb) -> None:
    _serve_tavily(stub_web, {"query": "pydantic ai", "results": _RESULTS})

    results = tavily_search("pydantic ai", api_key="test-key")

    assert (
        results,
        [(request.method, str(request.url)) for request in stub_web.sent],
        [json.loads(request.content) for request in stub_web.sent],
    ) == (
        _RESULTS,
        [("POST", _TAVILY_URL)],
        [
            {
                "api_key": "test-key",
                "query": "pydantic ai",
                "max_results": DEFAULT_TAVILY_MAX_RESULTS,
            }
        ],
    )


def test_tavily_search_sends_the_result_cap_and_both_domain_filters(stub_web: StubWeb) -> None:
    _serve_tavily(stub_web, {"results": []})

    results = tavily_search(
        "linters",
        api_key="test-key",
        max_results=2,
        include_domains=["example.com"],
        exclude_domains=["example.org"],
    )

    assert (results, [json.loads(request.content) for request in stub_web.sent]) == (
        [],
        [
            {
                "api_key": "test-key",
                "query": "linters",
                "max_results": 2,
                "include_domains": ["example.com"],
                "exclude_domains": ["example.org"],
            }
        ],
    )


def test_tavily_search_without_a_key_sends_an_empty_one(stub_web: StubWeb) -> None:
    _serve_tavily(stub_web, {"results": []})

    tavily_search("linters")

    assert [json.loads(request.content)["api_key"] for request in stub_web.sent] == [""]


def test_tavily_search_raises_on_http_error(stub_web: StubWeb) -> None:
    """A status the stub has no page for is a 404, which `raise_for_status` turns into an error."""
    with pytest.raises(httpx2.HTTPStatusError):
        tavily_search("test query", api_key="test-key")

    assert stub_web.requested == [_TAVILY_URL]


@pytest.mark.parametrize(
    "reply",
    [{"query": "test query"}, {"results": "none"}, ["not", "an", "object"]],
    ids=["no-results-key", "results-not-a-list", "reply-not-an-object"],
)
def test_tavily_search_raises_on_a_reply_without_a_results_list(
    stub_web: StubWeb, reply: Any
) -> None:
    _serve_tavily(stub_web, reply)

    with pytest.raises(ValueError, match="results"):
        tavily_search("test query", api_key="test-key")
