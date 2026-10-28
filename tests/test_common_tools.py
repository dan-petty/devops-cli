"""Unit tests for `firecrawl_search`, the web search of the roadmap refinement investigation.

Each search counts once by its result, and a failed search logs one warning that names the
result and never the key or the query (#2475).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx2
import pytest

from devops_cli.ai.common_tools import firecrawl_search
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_LIMIT
from devops_cli.telemetry.instruments import FIRECRAWL_SEARCHES_TOTAL
from tests.support.fakes.otlp import FakeCollector
from tests.web_fakes import StubWeb

_KEY = "fc-secret-key"
_QUERY = "private roadmap query"

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


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The warning lines `firecrawl_search` logged."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.ai.common_tools" and record.levelno == logging.WARNING
    ]


def test_a_search_counts_ok_and_logs_nothing(
    stub_web: StubWeb, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    _serve_firecrawl(stub_web, {"success": True, "data": {"web": _RESULTS}})

    firecrawl_search(_QUERY, api_key=_KEY)

    assert (otlp.points(FIRECRAWL_SEARCHES_TOTAL.name), _warnings(caplog)) == (
        [({"result": "ok"}, 1.0)],
        [],
    )


@pytest.mark.parametrize("status", [401, 402, 429, 500])
def test_a_search_firecrawl_refuses_counts_its_status_and_logs_it_without_the_key_or_query(
    stub_web: StubWeb, otlp: FakeCollector, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    """A 402 says the account has no credits and a 429 that it reached its rate limit: both reach
    an alert, so each status counts as itself."""
    stub_web.respond("POST", _FIRECRAWL_URL, status, {"success": False, "error": _QUERY})

    with pytest.raises(httpx2.HTTPStatusError):
        firecrawl_search(_QUERY, api_key=_KEY)

    logged = _warnings(caplog)
    assert (
        otlp.points(FIRECRAWL_SEARCHES_TOTAL.name),
        logged,
        [line for line in logged if _KEY in line or _QUERY in line],
    ) == (
        [({"result": str(status)}, 1.0)],
        [f"A Firecrawl web search failed: Firecrawl answered with HTTP {status}."],
        [],
    )


@pytest.mark.parametrize(
    ("serve", "kind"),
    [
        (
            lambda web: web.fail(_FIRECRAWL_URL, httpx2.ConnectTimeout("timed out")),
            "ConnectTimeout",
        ),
        (lambda web: _serve_firecrawl(web, {"success": True}), "ValueError"),
    ],
    ids=["no-answer", "no-web-results"],
)
def test_a_search_with_no_answer_or_no_web_results_counts_error_and_logs_its_class(
    stub_web: StubWeb,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
    serve: Any,
    kind: str,
) -> None:
    serve(stub_web)

    with pytest.raises((httpx2.HTTPError, ValueError)):
        firecrawl_search(_QUERY, api_key=_KEY)

    assert (otlp.points(FIRECRAWL_SEARCHES_TOTAL.name), _warnings(caplog)) == (
        [({"result": "error"}, 1.0)],
        [f"A Firecrawl web search failed: {kind}."],
    )
