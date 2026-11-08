"""Unit tests for the SearXNG provider of the web search chain (#3927).

The provider sends `GET {search.searxng_url}/search` with `format=json` and reads the `results` of
the reply. The address comes from the setting only, and the client dials a loopback address, or a
private one when `ai.allow_private_network` is set. A reply with a redirect is a failure: SearXNG
answers a query that starts with `!` with a redirect. The reply fixture holds the shape that the
SearXNG search API documents; the live check of #3929 holds the provider to a reply of the pinned
image.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from devops_cli.ai.web_search import PROVIDERS, SearchHit, SearxngProvider, web_search
from devops_cli.config.defaults import DEFAULT_SEARXNG_MAX_REPLY_BYTES
from devops_cli.config.settings import Settings
from devops_cli.exceptions.ai import SearchFailed
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.telemetry.instruments import WEB_SEARCHES_TOTAL
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.paths import FIXTURES

pytestmark = pytest.mark.usefixtures("keyring_store")

_REPLY = FIXTURES / "searxng" / "search_reply.json"
_LOOPBACK = "http://127.0.0.1:8080"
_SERVICE = "http://searxng.devops.svc.cluster.local:8080"
_SERVICE_ADDRESS = "10.0.0.5"
_QUERY = "private roadmap query"
_FROM_FIXTURE = [
    SearchHit(
        "https://developer.mozilla.org/en-US/docs/Glossary/Python",
        "Python",
        "Python is a high-level general-purpose programming language. It uses a multi-paradigm "
        "approach, meaning it supports procedural, object-oriented, and some functional "
        "programming constructs.",
        "searxng",
    ),
    SearchHit(
        "https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Server-side/Django",
        "Django Web Framework (Python)",
        "Django is an extremely popular and fully featured server-side web framework, written in "
        "Python. This module shows you why Django is one of the most popular web server "
        "frameworks, how to set up a development environment, and how to start using it to "
        "create your own web applications.",
        "searxng",
    ),
    SearchHit(
        "https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model",
        "Document Object Model (DOM)",
        "The Document Object Model (DOM) connects web pages to scripts or programming languages "
        "by representing the structure of a document\u2014such as the HTML representing a web "
        "page\u2014in memory. Usually it refers to JavaScript, even though modeling HTML, SVG, or "
        "XML documents as objects are not part of the core JavaScript language.",
        "searxng",
    ),
]
_DUCKDUCKGO = "https://html.duckduckgo.com/html/"


def _reply(**changes: Any) -> bytes:
    return json.dumps({**json.loads(_REPLY.read_text(encoding="utf-8")), **changes}).encode()


def _answers(web: WebFake, status: int = 200, body: bytes | None = None) -> None:
    """Answer every `GET /search` with `status` and `body`, the fixture by default."""
    content = _reply() if body is None else body

    def serve(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path != "/search":
            return None
        return httpx2.Response(
            status, headers={"content-type": "application/json"}, content=content
        )

    web.serve(serve)


def _search_fails() -> None:
    """Run the search and check that it raised `SearchFailed`, which no provider answered."""
    with pytest.raises(SearchFailed) as raised:
        web_search(_QUERY)
    assert raised.value.error_code == "WEB_SEARCH_FAILED"


def _points(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    return otlp.points(WEB_SEARCHES_TOTAL.name)


def _count(backend: str, result: str) -> tuple[dict[str, str], float]:
    return ({"backend": backend, "result": result}, 1.0)


@pytest.fixture
def searxng(config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Make `searxng` the first provider, at `url`. The test floor sets `ai.allow_private_network`
    through its variable; the fixture clears it unless the test passes `private`."""

    def apply(
        url: str | None = _LOOPBACK, *, then: tuple[str, ...] = (), private: bool = False
    ) -> None:
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", str(private).lower())
        config(
            search={"providers": ["searxng", *then], "searxng_url": url},
            firecrawl={"api_key": None},
        )

    return apply


def test_a_good_reply_gives_hits_with_the_provider_tag(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    searxng()
    _answers(web)

    hits = web_search(_QUERY)

    assert (hits, _points(otlp)) == (_FROM_FIXTURE, [_count("searxng", "ok")])


def test_the_request_is_a_get_of_the_search_path_with_the_json_format(
    web: WebFake, searxng: Callable[..., None], config: Callable[..., Any]
) -> None:
    searxng()
    config(search={"language": "de"})
    _answers(web)

    web_search(_QUERY)

    request = web.sent[0]
    assert (request.method, request.url.path, dict(request.url.params), request.content) == (
        "GET",
        "/search",
        {
            "q": _QUERY,
            "format": "json",
            "language": "de",
            "categories": "general,it,science",
            "pageno": "1",
        },
        b"",
    )


def test_the_hits_are_cut_to_the_cap(web: WebFake, searxng: Callable[..., None]) -> None:
    searxng()
    _answers(web)

    assert web_search(_QUERY, limit=2) == _FROM_FIXTURE[:2]


def test_a_result_with_no_url_or_not_an_object_is_dropped(
    web: WebFake, searxng: Callable[..., None]
) -> None:
    searxng()
    results = [
        "text",
        {"title": "No URL", "content": "None."},
        {"url": "https://example.com/a", "title": "A", "content": "First."},
        {"url": "https://example.com/b"},
    ]
    _answers(web, body=_reply(results=results))

    assert web_search(_QUERY) == [
        SearchHit("https://example.com/a", "A", "First.", "searxng"),
        SearchHit("https://example.com/b", "", "", "searxng"),
    ]


@pytest.mark.parametrize("status", [403, 429, 500, 503])
def test_a_status_other_than_200_is_a_failure_with_the_status_as_the_result(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None], status: int
) -> None:
    searxng()
    _answers(web, status=status, body=b"<html>no</html>")

    _search_fails()

    assert _points(otlp) == [_count("searxng", str(status)), _count("none", "exhausted")]


def test_a_failed_search_passes_on_to_the_next_provider(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    searxng(then=("duckduckgo",))
    _answers(web, status=429)
    web.respond("POST", _DUCKDUCKGO, 500, "<html>error</html>")

    _search_fails()

    assert _points(otlp) == [
        _count("searxng", "429"),
        _count("duckduckgo", "500"),
        _count("none", "exhausted"),
    ]


def test_an_empty_result_list_with_an_unresponsive_engine_is_degraded(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    searxng()
    _answers(web, body=_reply(results=[], unresponsive_engines=[["duckduckgo", "Suspended"]]))

    _search_fails()

    assert _points(otlp) == [_count("searxng", "degraded"), _count("none", "exhausted")]


def test_an_empty_result_list_with_no_unresponsive_engine_is_empty(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    searxng()
    _answers(web, body=_reply(results=[], unresponsive_engines=[]))

    assert (web_search(_QUERY), _points(otlp)) == ([], [_count("searxng", "empty")])


def test_a_result_list_with_an_unresponsive_engine_still_gives_its_hits(
    web: WebFake, searxng: Callable[..., None]
) -> None:
    searxng()
    _answers(web, body=_reply(unresponsive_engines=[["github", "HTTP error"]]))

    assert web_search(_QUERY) == _FROM_FIXTURE


@pytest.mark.parametrize(
    "body",
    [b"not json", b'["a", "list"]', b'{"query": "q"}', b'{"results": "none"}'],
    ids=["not-json", "not-an-object", "no-results", "results-not-a-list"],
)
def test_a_reply_that_is_not_a_result_object_is_degraded(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None], body: bytes
) -> None:
    searxng()
    _answers(web, body=body)

    _search_fails()

    assert _points(otlp) == [_count("searxng", "degraded"), _count("none", "exhausted")]


def test_a_reply_over_the_byte_cap_is_degraded(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    searxng()
    padding = "x" * DEFAULT_SEARXNG_MAX_REPLY_BYTES
    _answers(web, body=_reply(answers=[padding]))

    _search_fails()

    assert _points(otlp) == [_count("searxng", "degraded"), _count("none", "exhausted")]


def test_a_redirect_is_a_failure_and_no_second_request_is_sent(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    """SearXNG answers a query that starts with a bang with a redirect to the site of the bang."""
    searxng()
    web.serve(
        lambda request: httpx2.Response(302, headers={"location": "https://example.com/elsewhere"})
    )

    _search_fails()

    assert (len(web.sent), _points(otlp)) == (
        1,
        [_count("searxng", "302"), _count("none", "exhausted")],
    )


def test_a_failed_attempt_logs_the_status_and_never_the_query_or_the_address(
    web: WebFake, searxng: Callable[..., None], caplog: pytest.LogCaptureFixture
) -> None:
    searxng()
    _answers(web, status=503)

    with caplog.at_level(logging.WARNING, logger="devops_cli.ai.web_search"):
        _search_fails()

    assert [r.getMessage() for r in caplog.records if r.name == "devops_cli.ai.web_search"] == [
        "A web search failed on searxng: HTTP 503."
    ]


def test_a_service_that_does_not_answer_passes_the_search_on_and_counts_error(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    searxng()

    def refuse(request: httpx2.Request) -> httpx2.Response | None:
        raise httpx2.ConnectError("Connection refused", request=request)

    web.serve(refuse)

    _search_fails()

    assert _points(otlp) == [_count("searxng", "error"), _count("none", "exhausted")]


@pytest.mark.parametrize("url", [None])
def test_with_no_address_the_provider_is_not_configured_and_is_skipped(
    web: WebFake, otlp: FakeCollector, searxng: Callable[..., None], url: str | None
) -> None:
    searxng(url, then=("duckduckgo",))
    web.respond("POST", _DUCKDUCKGO, 500, "<html>error</html>")

    _search_fails()

    assert (web.requested, _points(otlp)) == (
        [_DUCKDUCKGO],
        [_count("duckduckgo", "500"), _count("none", "exhausted")],
    )
    assert SearxngProvider().configured(Settings(search={"searxng_url": url})) is False


def test_a_direct_call_with_no_address_names_the_setting(
    web: WebFake, searxng: Callable[..., None]
) -> None:
    searxng(None)

    with pytest.raises(ConfigurationError, match=r"search\.searxng_url") as raised:
        SearxngProvider().search(_QUERY, limit=5)

    assert (raised.value.key, web.sent) == ("search.searxng_url", [])


def test_a_workstation_address_on_loopback_needs_no_flag(
    web: WebFake, searxng: Callable[..., None]
) -> None:
    searxng("http://localhost:8080")
    _answers(web)

    assert web_search(_QUERY) == _FROM_FIXTURE


def test_a_cluster_service_address_needs_the_private_network_flag(
    web: WebFake, dns: DnsFake, searxng: Callable[..., None]
) -> None:
    dns.add("searxng.devops.svc.cluster.local", _SERVICE_ADDRESS)
    searxng(_SERVICE)
    _answers(web)

    with pytest.raises(SSRFBlockedError) as raised:
        SearxngProvider().search(_QUERY, limit=5)

    assert (raised.value.error_code, web.sent) == ("SSRF_BLOCKED", [])


def test_a_cluster_service_address_works_with_the_private_network_flag(
    web: WebFake, dns: DnsFake, searxng: Callable[..., None]
) -> None:
    dns.add("searxng.devops.svc.cluster.local", _SERVICE_ADDRESS)
    searxng(_SERVICE, private=True)
    _answers(web)

    assert web_search(_QUERY) == _FROM_FIXTURE


def test_an_address_that_the_egress_check_refuses_passes_the_search_on_and_counts_refused(
    web: WebFake, dns: DnsFake, otlp: FakeCollector, searxng: Callable[..., None]
) -> None:
    dns.add("searxng.devops.svc.cluster.local", _SERVICE_ADDRESS)
    searxng(_SERVICE, then=("duckduckgo",))
    web.respond("POST", _DUCKDUCKGO, 500, "<html>error</html>")

    _search_fails()

    assert _points(otlp) == [
        _count("searxng", "refused"),
        _count("duckduckgo", "500"),
        _count("none", "exhausted"),
    ]


def test_a_path_in_the_address_stays_and_an_end_slash_goes(
    web: WebFake, searxng: Callable[..., None]
) -> None:
    searxng(f"{_LOOPBACK}/")
    _answers(web)

    web_search(_QUERY)

    assert web.sent[0].url.path == "/search"


def test_the_provider_is_listed_and_its_url_is_the_search_endpoint_of_the_setting(
    searxng: Callable[..., None],
) -> None:
    searxng()

    provider = PROVIDERS["searxng"]

    assert (provider.name, provider.method, provider.url) == (
        "searxng",
        "GET",
        f"{_LOOPBACK}/search",
    )
