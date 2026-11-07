"""Unit tests for the web search of the roadmap jobs: `firecrawl_search` and its fallback.

Each Firecrawl search counts once by its result, and a failed search logs one warning that names the
result and never the key or the query (#2475). When Firecrawl fails, `web_search` asks DuckDuckGo
and counts that search in `devops_cli_web_search_fallbacks_total` (#3876).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx2
import pytest

from devops_cli.ai.common_tools import duckduckgo_search, firecrawl_search, web_search
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_LIMIT
from devops_cli.telemetry.instruments import FIRECRAWL_SEARCHES_TOTAL, WEB_SEARCH_FALLBACKS_TOTAL
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector

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


def _serve_firecrawl(web: WebFake, reply: Any) -> None:
    """Answer Firecrawl's search endpoint with `reply` serialised as JSON."""
    web.content(_FIRECRAWL_URL, json.dumps(reply).encode())


def test_firecrawl_search_posts_the_query_with_the_key_and_returns_the_web_results(
    web: WebFake,
) -> None:
    _serve_firecrawl(web, {"success": True, "data": {"web": _RESULTS}, "creditsUsed": 2})

    results = firecrawl_search("pydantic ai", api_key="fc-test")

    assert (
        results,
        [(request.method, str(request.url)) for request in web.sent],
        [request.headers["Authorization"] for request in web.sent],
        [json.loads(request.content) for request in web.sent],
    ) == (
        _RESULTS,
        [("POST", _FIRECRAWL_URL)],
        ["Bearer fc-test"],
        [{"query": "pydantic ai", "limit": DEFAULT_FIRECRAWL_SEARCH_LIMIT}],
    )


def test_firecrawl_search_sends_the_result_cap(web: WebFake) -> None:
    _serve_firecrawl(web, {"success": True, "data": {"web": []}})

    results = firecrawl_search("linters", api_key="fc-test", limit=2)

    assert (results, [json.loads(request.content)["limit"] for request in web.sent]) == (
        [],
        [2],
    )


def test_firecrawl_search_raises_on_http_error(web: WebFake) -> None:
    """A status the stub has no page for is a 404, which `raise_for_status` turns into an error."""
    with pytest.raises(httpx2.HTTPStatusError) as raised:
        firecrawl_search("test query", api_key="fc-test")
    assert raised.value is not None

    assert web.requested == [_FIRECRAWL_URL]


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
    web: WebFake, reply: Any
) -> None:
    _serve_firecrawl(web, reply)

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
    web: WebFake, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    _serve_firecrawl(web, {"success": True, "data": {"web": _RESULTS}})

    firecrawl_search(_QUERY, api_key=_KEY)

    assert (otlp.points(FIRECRAWL_SEARCHES_TOTAL.name), _warnings(caplog)) == (
        [({"result": "ok"}, 1.0)],
        [],
    )


@pytest.mark.parametrize("status", [401, 402, 429, 500])
def test_a_search_firecrawl_refuses_counts_its_status_and_logs_it_without_the_key_or_query(
    web: WebFake, otlp: FakeCollector, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    """A 402 says the account has no credits and a 429 that it reached its rate limit: both reach
    an alert, so each status counts as itself."""
    web.respond("POST", _FIRECRAWL_URL, status, {"success": False, "error": _QUERY})

    with pytest.raises(httpx2.HTTPStatusError) as raised:
        firecrawl_search(_QUERY, api_key=_KEY)
    assert raised.value is not None

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
    web: WebFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
    serve: Any,
    kind: str,
) -> None:
    serve(web)

    with pytest.raises((httpx2.HTTPError, ValueError)) as raised:
        firecrawl_search(_QUERY, api_key=_KEY)
    assert raised.value is not None

    assert (otlp.points(FIRECRAWL_SEARCHES_TOTAL.name), _warnings(caplog)) == (
        [({"result": "error"}, 1.0)],
        [f"A Firecrawl web search failed: {kind}."],
    )


_DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
_DUCKDUCKGO_HITS = [
    ("Pydantic AI", "https://example.com/pydantic-ai", "Agent framework for Python."),
    ("Ruff", "https://example.com/ruff", "A Python linter."),
    ("Mypy", "https://example.com/mypy", "A static type checker."),
]
_AS_FIRECRAWL = [
    {"title": title, "url": url, "description": body} for title, url, body in _DUCKDUCKGO_HITS
]


def _duckduckgo_page(hits: list[tuple[str, str, str]]) -> bytes:
    """The HTML page that DuckDuckGo answers a search with: one `result__body` block for each hit."""
    blocks = "".join(
        '<div class="result results_links web-result">'
        '<div class="links_main links_deep result__body">'
        f'<h2 class="result__title"><a rel="nofollow" class="result__a" href="{url}">{title}</a></h2>'
        f'<div class="result__extras"><a class="result__url" href="{url}">{url}</a></div>'
        f'<a class="result__snippet" href="{url}">{body}</a>'
        "</div></div>"
        for title, url, body in hits
    )
    return f"<html><body><div id='links'>{blocks}</div></body></html>".encode()


def _fallback_points(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    """The points of `devops_cli_web_search_fallbacks_total`."""
    return otlp.points(WEB_SEARCH_FALLBACKS_TOTAL.name)


def test_a_search_firecrawl_refuses_falls_back_to_duckduckgo_and_returns_the_form_of_firecrawl(
    web: WebFake, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    """The caller gets `url`, `title` and `description` for each result, as from Firecrawl. The
    fallback logs one line with the reason, and neither the key nor the query. The DuckDuckGo
    request holds the query and no key."""
    web.respond("POST", _FIRECRAWL_URL, 402, {"success": False})
    web.content(_DUCKDUCKGO_URL, _duckduckgo_page(_DUCKDUCKGO_HITS))

    results = web_search(_QUERY, _KEY)

    fallback_lines = [line for line in _all_lines(caplog) if "DuckDuckGo" in line]
    assert (
        results,
        web.requested,
        [request.headers.get("Authorization") for request in web.sent[1:]],
        [request.content.decode() for request in web.sent[1:]],
        otlp.points(FIRECRAWL_SEARCHES_TOTAL.name),
        _fallback_points(otlp),
        fallback_lines,
        [line for line in _all_lines(caplog) if _KEY in line or _QUERY in line],
    ) == (
        _AS_FIRECRAWL,
        [_FIRECRAWL_URL, _DUCKDUCKGO_URL],
        [None],
        ["q=private+roadmap+query&b=&l=us-en"],
        [({"result": "402"}, 1.0)],
        [({"backend": "duckduckgo", "result": "ok"}, 1.0)],
        ["A web search fell back to DuckDuckGo: Firecrawl answered with HTTP 402."],
        [],
    )


def _all_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Every line the logs of `devops_cli.ai.common_tools` hold."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.ai.common_tools"
    ]


def test_a_search_firecrawl_answers_does_not_run_the_fallback(
    web: WebFake, otlp: FakeCollector
) -> None:
    _serve_firecrawl(web, {"success": True, "data": {"web": _RESULTS}})

    results = web_search(_QUERY, _KEY)

    assert (results, web.requested, _fallback_points(otlp)) == (_RESULTS, [_FIRECRAWL_URL], [])


def test_a_firecrawl_search_with_no_result_is_an_answer_and_runs_no_fallback(
    web: WebFake,
) -> None:
    _serve_firecrawl(web, {"success": True, "data": {"web": []}})

    assert (web_search(_QUERY, _KEY), web.requested) == ([], [_FIRECRAWL_URL])


@pytest.mark.parametrize(
    ("serve", "reason"),
    [
        (lambda web: web.fail(_FIRECRAWL_URL, httpx2.ConnectTimeout("t")), "ConnectTimeout"),
        (lambda web: _serve_firecrawl(web, {"success": True}), "ValueError"),
    ],
    ids=["no-answer", "no-web-results"],
)
def test_a_search_with_no_answer_or_no_web_results_from_firecrawl_falls_back(
    web: WebFake,
    caplog: pytest.LogCaptureFixture,
    serve: Any,
    reason: str,
) -> None:
    serve(web)
    web.content(_DUCKDUCKGO_URL, _duckduckgo_page(_DUCKDUCKGO_HITS))

    results = web_search(_QUERY, _KEY)

    assert (results, [line for line in _all_lines(caplog) if "DuckDuckGo" in line]) == (
        _AS_FIRECRAWL,
        [f"A web search fell back to DuckDuckGo: {reason}."],
    )


def test_a_search_cuts_the_duckduckgo_results_to_the_limit(web: WebFake) -> None:
    web.respond("POST", _FIRECRAWL_URL, 429, {"success": False})
    web.content(_DUCKDUCKGO_URL, _duckduckgo_page(_DUCKDUCKGO_HITS))

    assert web_search(_QUERY, _KEY, limit=2) == _AS_FIRECRAWL[:2]


@pytest.mark.parametrize(
    ("status", "kind"),
    [(500, "HTTPStatusError"), (429, "HTTPStatusError"), (202, "ValueError")],
    ids=["server-error", "rate-limit", "challenge-page"],
)
def test_a_search_that_both_backends_fail_raises_like_a_firecrawl_failure_and_counts_error(
    web: WebFake, otlp: FakeCollector, status: int, kind: str
) -> None:
    """A caller already handles `httpx2.HTTPError` and `ValueError` from a failed search. DuckDuckGo
    answers a bot challenge with HTTP 202 and a page with no results: that is an error too."""
    web.respond("POST", _FIRECRAWL_URL, 402, {"success": False})
    web.respond("POST", _DUCKDUCKGO_URL, status, "<html>challenge</html>")

    with pytest.raises((httpx2.HTTPError, ValueError)) as raised:
        web_search(_QUERY, _KEY)

    assert (type(raised.value).__name__, _fallback_points(otlp)) == (
        kind,
        [({"backend": "duckduckgo", "result": "error"}, 1.0)],
    )


def test_a_duckduckgo_search_that_finds_nothing_returns_no_result(web: WebFake) -> None:
    web.content(_DUCKDUCKGO_URL, _duckduckgo_page([]))

    assert duckduckgo_search(_QUERY) == []
