"""Unit tests for web search over a chain of providers (#3925).

`web_search` asks the providers of `search.providers` in order. A provider that is not configured is
skipped. A provider that fails, or returns no hit, passes the search on. The first provider with a
hit answers. Each attempt counts once in `devops_cli_web_searches_total`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from devops_cli.ai import web_search as chain
from devops_cli.ai.web_search import (
    DuckDuckGoProvider,
    FirecrawlProvider,
    SearchHit,
    configured_providers,
    web_search,
)
from devops_cli.config.defaults import (
    DEFAULT_DUCKDUCKGO_SEARCH_URL,
    DEFAULT_FIRECRAWL_SEARCH_URL,
    DEFAULT_WEB_SEARCH_LIMIT,
)
from devops_cli.config.settings import Settings
from devops_cli.exceptions.ai import SearchFailed, SearchQueryRefused
from devops_cli.telemetry.instruments import WEB_SEARCHES_TOTAL
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

_KEY = "fc-secret-key"
_QUERY = "private roadmap query"
_FIRECRAWL = DEFAULT_FIRECRAWL_SEARCH_URL
_DUCKDUCKGO = DEFAULT_DUCKDUCKGO_SEARCH_URL

_FIRECRAWL_WEB = [
    {"title": "Pydantic AI", "url": "https://example.com/pydantic-ai", "description": "Agents."},
    {"title": "Ruff", "url": "https://example.com/ruff", "description": "A linter."},
]
_DUCKDUCKGO_HITS = [
    ("Mypy", "https://example.com/mypy", "A type checker."),
    ("Pytest", "https://example.com/pytest", "A test runner."),
    ("Uv", "https://example.com/uv", "A package manager."),
]


def _hit(title: str, url: str, snippet: str, provider: str) -> SearchHit:
    return SearchHit(url=url, title=title, snippet=snippet, provider=provider)


_FROM_FIRECRAWL = [
    _hit("Pydantic AI", "https://example.com/pydantic-ai", "Agents.", "firecrawl"),
    _hit("Ruff", "https://example.com/ruff", "A linter.", "firecrawl"),
]
_FROM_DUCKDUCKGO = [_hit(*hit, "duckduckgo") for hit in _DUCKDUCKGO_HITS]


@pytest.fixture
def chain_of(config: Callable[..., Any]) -> Callable[..., None]:
    """Set the providers of the chain, and a Firecrawl key unless the test passes `key=None`."""

    def apply(*providers: str, key: str | None = _KEY) -> None:
        config(search={"providers": list(providers)}, firecrawl={"api_key": key})

    return apply


def _firecrawl_answers(web: WebFake, hits: list[dict[str, Any]]) -> None:
    web.content(_FIRECRAWL, json.dumps({"success": True, "data": {"web": hits}}).encode())


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


def _duckduckgo_answers(web: WebFake, hits: list[tuple[str, str, str]] | None = None) -> None:
    web.content(_DUCKDUCKGO, _duckduckgo_page(_DUCKDUCKGO_HITS if hits is None else hits))


def _points(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    return otlp.points(WEB_SEARCHES_TOTAL.name)


def _count(backend: str, result: str) -> tuple[dict[str, str], float]:
    return ({"backend": backend, "result": result}, 1.0)


def _lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.ai.web_search"
    ]


def test_the_first_provider_that_has_hits_answers_and_the_others_do_not_run(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo")
    _firecrawl_answers(web, _FIRECRAWL_WEB)
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, web.requested, _points(otlp)) == (
        _FROM_FIRECRAWL,
        [_FIRECRAWL],
        [_count("firecrawl", "ok")],
    )


def test_firecrawl_posts_the_query_with_its_key_and_the_cap(
    web: WebFake, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl")
    _firecrawl_answers(web, _FIRECRAWL_WEB)

    web_search("pydantic ai", limit=2)

    request = web.sent[0]
    assert (
        request.method,
        request.headers["Authorization"],
        request.headers["Accept-Language"],
        json.loads(request.content),
    ) == ("POST", f"Bearer {_KEY}", "en", {"query": "pydantic ai", "limit": 2})


def test_duckduckgo_posts_the_query_with_no_key_and_cuts_the_hits_to_the_cap(
    web: WebFake, chain_of: Callable[..., None]
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    hits = web_search(_QUERY, limit=2)

    request = web.sent[0]
    assert (
        hits,
        request.content.decode(),
        request.headers.get("Authorization"),
        request.headers["Accept-Language"],
    ) == (_FROM_DUCKDUCKGO[:2], "q=private+roadmap+query&b=&l=us-en", None, "en")


def test_the_search_language_is_the_accept_language_of_the_request(
    web: WebFake, config: Callable[..., Any]
) -> None:
    config(search={"providers": ["duckduckgo"], "language": "de"})
    _duckduckgo_answers(web)

    web_search(_QUERY)

    assert web.sent[0].headers["Accept-Language"] == "de"


def test_a_search_without_a_cap_asks_for_the_default_number_of_hits(
    web: WebFake, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl")
    _firecrawl_answers(web, [])

    web_search(_QUERY)

    assert json.loads(web.sent[0].content)["limit"] == DEFAULT_WEB_SEARCH_LIMIT


def test_the_duckduckgo_url_is_the_url_of_the_engine() -> None:
    from ddgs.engines.duckduckgo import Duckduckgo

    assert Duckduckgo.search_url == DEFAULT_DUCKDUCKGO_SEARCH_URL


@pytest.mark.parametrize("status", [401, 402, 403, 404, 429, 500, 503])
def test_a_provider_that_refuses_passes_the_search_on_and_counts_its_status(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None], status: int
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.respond("POST", _FIRECRAWL, status, {"success": False})
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, web.requested, _points(otlp)) == (
        _FROM_DUCKDUCKGO,
        [_FIRECRAWL, _DUCKDUCKGO],
        [_count("firecrawl", str(status)), _count("duckduckgo", "ok")],
    )


def test_a_provider_that_does_not_answer_passes_the_search_on_and_counts_error(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.fail(_FIRECRAWL, httpx2.ConnectTimeout("timed out"))
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, _points(otlp)) == (
        _FROM_DUCKDUCKGO,
        [_count("firecrawl", "error"), _count("duckduckgo", "ok")],
    )


@pytest.mark.parametrize(
    "reply",
    [
        b"not json",
        b'{"success": true}',
        b'{"success": true, "data": {"news": []}}',
        b'{"success": true, "data": {"web": "none"}}',
        b'["not", "an", "object"]',
    ],
    ids=["not-json", "no-data", "no-web-list", "web-not-a-list", "not-an-object"],
)
def test_a_reply_that_is_not_json_or_has_no_list_passes_the_search_on_and_counts_degraded(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None], reply: bytes
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.content(_FIRECRAWL, reply)
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, _points(otlp)) == (
        _FROM_DUCKDUCKGO,
        [_count("firecrawl", "degraded"), _count("duckduckgo", "ok")],
    )


def test_the_challenge_page_of_duckduckgo_counts_degraded(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    """DuckDuckGo answers a client that it takes for a bot with HTTP 202 and a page with no hit."""
    chain_of("duckduckgo", "firecrawl")
    web.respond("POST", _DUCKDUCKGO, 202, "<html>challenge</html>")
    _firecrawl_answers(web, _FIRECRAWL_WEB)

    hits = web_search(_QUERY)

    assert (hits, _points(otlp)) == (
        _FROM_FIRECRAWL,
        [_count("duckduckgo", "degraded"), _count("firecrawl", "ok")],
    )


def test_a_healthy_empty_reply_passes_the_search_on(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo")
    _firecrawl_answers(web, [])
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, web.requested, _points(otlp)) == (
        _FROM_DUCKDUCKGO,
        [_FIRECRAWL, _DUCKDUCKGO],
        [_count("firecrawl", "empty"), _count("duckduckgo", "ok")],
    )


def test_a_search_that_every_provider_fails_raises_search_failed(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.respond("POST", _FIRECRAWL, 402, {"success": False})
    web.respond("POST", _DUCKDUCKGO, 500, "<html>error</html>")

    with pytest.raises(SearchFailed) as raised:
        web_search(_QUERY)
    assert raised.value.error_code == "WEB_SEARCH_FAILED"

    assert _points(otlp) == [
        _count("firecrawl", "402"),
        _count("duckduckgo", "500"),
        _count("none", "exhausted"),
    ]


def test_a_search_that_one_provider_answered_empty_and_the_rest_failed_returns_no_hit(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo")
    _firecrawl_answers(web, [])
    web.respond("POST", _DUCKDUCKGO, 500, "<html>error</html>")

    assert (web_search(_QUERY), _points(otlp)) == (
        [],
        [_count("firecrawl", "empty"), _count("duckduckgo", "500")],
    )


def test_a_search_makes_no_retry_and_no_wait(
    web: WebFake, chain_of: Callable[..., None], clock: ClockFake
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.respond("POST", _FIRECRAWL, 429, {"success": False})
    _duckduckgo_answers(web)

    web_search(_QUERY)

    assert (web.requested, clock.waits) == ([_FIRECRAWL, _DUCKDUCKGO], [])


def test_a_provider_that_is_not_configured_is_skipped_and_not_counted(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo", key=None)
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, web.requested, _points(otlp)) == (
        _FROM_DUCKDUCKGO,
        [_DUCKDUCKGO],
        [_count("duckduckgo", "ok")],
    )


def test_the_default_chain_skips_searxng_and_asks_duckduckgo_before_firecrawl(
    web: WebFake, otlp: FakeCollector, config: Callable[..., Any]
) -> None:
    config(firecrawl={"api_key": _KEY})
    web.respond("POST", _DUCKDUCKGO, 500, "<html>error</html>")
    _firecrawl_answers(web, _FIRECRAWL_WEB)

    hits = web_search(_QUERY)

    assert (hits, web.requested, _points(otlp)) == (
        _FROM_FIRECRAWL,
        [_DUCKDUCKGO, _FIRECRAWL],
        [_count("duckduckgo", "500"), _count("firecrawl", "ok")],
    )


def test_a_search_with_no_configured_provider_raises_search_failed(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "searxng", key=None)

    with pytest.raises(SearchFailed) as raised:
        web_search(_QUERY)
    assert raised.value.error_code == "WEB_SEARCH_FAILED"

    assert (web.requested, _points(otlp)) == ([], [_count("none", "exhausted")])


def test_the_configured_providers_are_those_of_the_list_that_can_search(
    chain_of: Callable[..., None],
) -> None:
    chain_of("searxng", "firecrawl", "duckduckgo", key=None)
    without_key = [provider.name for provider in configured_providers()]
    chain_of("searxng", "firecrawl", "duckduckgo", key=_KEY)
    with_key = [provider.name for provider in configured_providers()]

    assert (without_key, with_key) == (["duckduckgo"], ["firecrawl", "duckduckgo"])


def test_a_settings_value_with_an_unknown_provider_is_a_validation_error() -> None:
    with pytest.raises(ValueError, match="providers"):
        Settings(search={"providers": ["duckduckgo", "bing"]})


def test_the_default_providers_name_searxng_first() -> None:
    assert Settings().search.providers == ["searxng", "duckduckgo", "firecrawl"]


def test_the_deadline_ends_the_chain(
    web: WebFake,
    otlp: FakeCollector,
    chain_of: Callable[..., None],
    clock: ClockFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider that takes 61 s leaves no time for the next one."""

    class Slow:
        name = "firecrawl"
        url = _FIRECRAWL

        def configured(self, settings: Settings) -> bool:
            return True

        def search(self, query: str, *, limit: int) -> list[SearchHit]:
            clock.shift(61)
            raise httpx2.ReadTimeout("timed out")

    chain_of("firecrawl", "duckduckgo")
    monkeypatch.setitem(chain.PROVIDERS, "firecrawl", Slow())
    _duckduckgo_answers(web)

    with pytest.raises(SearchFailed) as raised:
        web_search(_QUERY)
    assert raised.value.error_code == "WEB_SEARCH_FAILED"

    assert (web.requested, _points(otlp)) == (
        [],
        [_count("firecrawl", "error"), _count("none", "exhausted")],
    )


def test_a_hit_is_deduplicated_by_its_url_and_must_be_http_or_https(
    web: WebFake, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl")
    _firecrawl_answers(
        web,
        [
            {"title": "A", "url": "https://example.com/a", "description": "1"},
            {"title": "A again", "url": "https://example.com/a/", "description": "2"},
            {"title": "File", "url": "file:///etc/passwd", "description": "3"},
            {"title": "Script", "url": "javascript:alert(1)", "description": "4"},
            {"title": "No URL", "description": "5"},
            {"title": "B", "url": "http://example.com/b", "description": "6"},
        ],
    )

    hits = web_search(_QUERY)

    assert [(hit.title, hit.url) for hit in hits] == [
        ("A", "https://example.com/a"),
        ("B", "http://example.com/b"),
    ]


def test_an_answer_with_only_unusable_hits_is_empty_and_passes_the_search_on(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None]
) -> None:
    chain_of("firecrawl", "duckduckgo")
    _firecrawl_answers(web, [{"title": "File", "url": "file:///etc/hosts", "description": "x"}])
    _duckduckgo_answers(web)

    hits = web_search(_QUERY)

    assert (hits, _points(otlp)) == (
        _FROM_DUCKDUCKGO,
        [_count("firecrawl", "empty"), _count("duckduckgo", "ok")],
    )


def _secret_query() -> str:
    return "how to use " + "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


_REFUSED = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="blank"),
    pytest.param("word " * 51, id="over-50-words"),
    pytest.param("x" * 401, id="over-400-characters"),
    pytest.param("!bang pydantic", id="leading-bang"),
    pytest.param(":help pydantic", id="leading-colon"),
    pytest.param(_secret_query(), id="secret"),
    pytest.param("who is dev@corp.test", id="email-address"),
    pytest.param("why does 192.168.49.2 refuse", id="private-address"),
    pytest.param("login to 100.64.0.5:8080", id="shared-address-with-port"),
    pytest.param("ping 169.254.10.5 now", id="link-local-address"),
    pytest.param("connect to [::1]:8080", id="loopback-v6-address"),
    pytest.param("open storage.internal share", id="internal-host-name"),
    pytest.param("open storage.home.arpa share", id="home-network-host-name"),
    pytest.param("ping localhost", id="localhost"),
]


@pytest.mark.parametrize("query", _REFUSED)
def test_a_query_the_guard_refuses_raises_and_sends_no_request(
    web: WebFake, otlp: FakeCollector, chain_of: Callable[..., None], query: str
) -> None:
    chain_of("firecrawl", "duckduckgo")

    with pytest.raises(SearchQueryRefused) as raised:
        web_search(query)

    assert (web.requested, _points(otlp), "a1B2c3" in str(raised.value)) == (
        [],
        [_count("none", "refused")],
        False,
    )


@pytest.mark.parametrize(
    "query",
    [
        "pydantic ai agent framework",
        "x" * 400,
        "word " * 50,
        "python 3.14 release notes",
        "site reliability @scope/package",
        "example.com docs 192.0.2.1",
        "what is the c++ !important rule",
    ],
)
def test_a_query_the_guard_allows_reaches_the_provider(
    web: WebFake, chain_of: Callable[..., None], query: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    web_search(query)

    assert web.requested == [_DUCKDUCKGO]


# A host that the guard refuses, and the rule that the refusal names.
_REFUSED_HOSTS = [
    pytest.param("nas.lan", "an internal host name", id="lan-name"),
    pytest.param("printer.local", "an internal host name", id="local-name"),
    pytest.param("192.168.1.5", "a private address", id="v4-address"),
    pytest.param("10.0.0.7", "a private address", id="v4-address-class-a"),
    pytest.param("[fd00::1]", "a private address", id="v6-address"),
]
_PUBLIC_HOST = "docs.python.org"

# The forms of a word that names a host with no scheme.
_BARE_FORMS = [
    pytest.param("{host}", id="bare"),
    pytest.param("{host}:8080", id="port"),
    pytest.param("{host}/api", id="path"),
    pytest.param("{host}:8080/api", id="port-path"),
]

# The forms of a word that names a host in a URL.
_URL_FORMS = [
    pytest.param("https://{host}", id="scheme"),
    pytest.param("https://{host}/api", id="scheme-path"),
    pytest.param("http://{host}:8080", id="scheme-port"),
    pytest.param("http://{host}:8080/api", id="scheme-port-path"),
    pytest.param("https://{host}/api?x=1", id="scheme-path-query"),
    pytest.param("https://{host}?x=1", id="scheme-query"),
    pytest.param("https://{host}/api#part", id="scheme-path-fragment"),
    pytest.param("https://{host}#part", id="scheme-fragment"),
    pytest.param("HTTPS://{host}/api", id="upper-case-scheme"),
    pytest.param("ftp://{host}/api", id="other-scheme"),
    pytest.param("//{host}/api", id="scheme-relative"),
    pytest.param("(https://{host}/api)", id="in-parentheses"),
    pytest.param('"https://{host}/api"', id="in-double-quotes"),
    pytest.param("'https://{host}/api'", id="in-single-quotes"),
    pytest.param("<https://{host}/api>", id="in-angle-brackets"),
    pytest.param("[text](https://{host}/api)", id="markdown-link"),
    pytest.param("[text](https://{host})", id="markdown-link-no-path"),
    pytest.param("url=https://{host}/api", id="after-a-prefix"),
    pytest.param("https://web.example.com/save/http://{host}/api", id="in-a-path"),
    pytest.param("https://example.com/?u=http://{host}/api", id="in-a-query"),
    pytest.param("https://web.example.com/save/http%3A%2F%2F{host}%2Fapi", id="encoded-in-a-path"),
    pytest.param("https://example.com/?u=http%3A%2F%2F{host}%2Fapi", id="encoded-in-a-query"),
]


def _refusal(query: str) -> str | None:
    """The message of the refusal of `query`, or None when the guard allows the query."""
    try:
        web_search(query)
    except SearchQueryRefused as refused:
        return str(refused)
    return None


@pytest.mark.parametrize("form", _BARE_FORMS)
@pytest.mark.parametrize(("host", "rule"), _REFUSED_HOSTS)
def test_a_host_word_is_read_by_its_host(
    web: WebFake, chain_of: Callable[..., None], form: str, host: str, rule: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    refusal = _refusal(f"how to open {form.format(host=host)} now")

    assert (refusal, web.requested) == (f"The search was refused: the query holds {rule}.", [])


@pytest.mark.parametrize("form", _URL_FORMS)
@pytest.mark.parametrize(("host", "rule"), _REFUSED_HOSTS)
def test_a_url_word_is_read_by_its_host(
    web: WebFake, chain_of: Callable[..., None], form: str, host: str, rule: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    refusal = _refusal(f"how to open {form.format(host=host)} now")

    assert (refusal, web.requested) == (f"The search was refused: the query holds {rule}.", [])


@pytest.mark.parametrize(
    ("word", "rule"),
    [
        pytest.param("https://NAS.LAN/api", "an internal host name", id="upper-case-name"),
        pytest.param("HTTP://PRINTER.LOCAL:8080", "an internal host name", id="upper-case-url"),
        pytest.param("http://[FD00::1]/api", "a private address", id="upper-case-v6-address"),
        pytest.param("https://nas.lan./api", "an internal host name", id="name-with-a-dot"),
        pytest.param("http://printer.local.:8080", "an internal host name", id="dot-then-port"),
        pytest.param("http://192.168.1.5./api", "a private address", id="address-with-a-dot"),
        pytest.param("10.0.0.7.:8080", "a private address", id="bare-address-with-a-dot"),
        pytest.param("http://[fd00::1]", "a private address", id="v6-address-at-the-end"),
        pytest.param("url=http://[fd00::1]", "a private address", id="v6-address-after-a-prefix"),
        pytest.param("http://[fe80::1%25eth0]/api", "a private address", id="v6-address-zone"),
        pytest.param("http://localhost:8080/api", "an internal host name", id="localhost"),
    ],
)
def test_a_url_word_is_read_by_its_host_in_each_spelling_of_the_host(
    web: WebFake, chain_of: Callable[..., None], word: str, rule: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    refusal = _refusal(f"how to open {word} now")

    assert (refusal, web.requested) == (f"The search was refused: the query holds {rule}.", [])


@pytest.mark.parametrize("form", [*_BARE_FORMS, *_URL_FORMS])
def test_a_word_of_a_public_host_reaches_the_provider(
    web: WebFake, chain_of: Callable[..., None], form: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    refusal = _refusal(f"how to open {form.format(host=_PUBLIC_HOST)} now")

    assert (refusal, web.requested) == (None, [_DUCKDUCKGO])


@pytest.mark.parametrize(
    "word",
    [
        pytest.param("pydantic-ai", id="package-name"),
        pytest.param("v1.2.3", id="version-tag"),
        pytest.param("3.14", id="version-number"),
        pytest.param("foo/bar", id="path"),
        pytest.param("C:\\path", id="drive-path"),
        pytest.param("key=value", id="key-and-value"),
        pytest.param("list[int]", id="type-with-brackets"),
        pytest.param("https://example.com/docs/settings.local", id="url-path-like-a-name"),
        pytest.param("https://example.com/?next=http%3A%2F%2Fdocs.python.org", id="encoded-url"),
    ],
)
def test_a_word_with_no_refused_host_reaches_the_provider(
    web: WebFake, chain_of: Callable[..., None], word: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    refusal = _refusal(f"how to use {word} now")

    assert (refusal, web.requested) == (None, [_DUCKDUCKGO])


@pytest.mark.parametrize(
    ("word", "refusal"),
    [
        pytest.param("https://[name]:6443/healthz", None, id="name-in-brackets"),
        pytest.param(
            "https://[nas.lan]:6443/healthz",
            "The search was refused: the query holds an internal host name.",
            id="internal-name-in-brackets",
        ),
        pytest.param(
            "http://[192.168.1.5]/api",
            "The search was refused: the query holds a private address.",
            id="v4-address-in-brackets",
        ),
        pytest.param(
            "[a](https://nas.lan)[b](https://docs.python.org)",
            "The search was refused: the query holds an internal host name.",
            id="two-markdown-links",
        ),
        pytest.param(
            "http://nas.lan\uff0fapi",
            "The search was refused: the query holds an internal host name.",
            id="full-width-slash",
        ),
    ],
)
def test_a_text_that_the_url_parser_refuses_is_read_part_by_part(
    web: WebFake, chain_of: Callable[..., None], word: str, refusal: str | None
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    assert (_refusal(f"how to open {word} now"), web.requested) == (
        refusal,
        [] if refusal else [_DUCKDUCKGO],
    )


@pytest.mark.parametrize("host", ["nas.lan", "192.168.1.5", _PUBLIC_HOST])
def test_a_url_word_with_user_info_is_refused_by_the_secret_rule(
    web: WebFake, chain_of: Callable[..., None], host: str
) -> None:
    chain_of("duckduckgo")
    _duckduckgo_answers(web)

    refusal = _refusal(f"how to open https://user@{host}/api now")

    assert (refusal, web.requested) == ("The search was refused: the query holds a secret.", [])


def test_a_failed_attempt_logs_the_backend_and_the_status_and_never_the_key_or_the_query(
    web: WebFake, chain_of: Callable[..., None], caplog: pytest.LogCaptureFixture
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.respond("POST", _FIRECRAWL, 402, {"success": False, "error": _QUERY, "key": _KEY})
    web.fail(_DUCKDUCKGO, httpx2.ConnectTimeout(f"timed out for {_QUERY} {_KEY}"))

    with pytest.raises(SearchFailed) as raised:
        web_search(_QUERY)
    assert raised.value.error_code == "WEB_SEARCH_FAILED"

    logged = _lines(caplog)
    assert (logged, [line for line in logged if _KEY in line or _QUERY in line]) == (
        [
            "A web search failed on firecrawl: HTTP 402.",
            "A web search failed on duckduckgo: ConnectTimeout.",
        ],
        [],
    )


def test_a_search_that_succeeds_logs_nothing(
    web: WebFake, chain_of: Callable[..., None], caplog: pytest.LogCaptureFixture
) -> None:
    chain_of("firecrawl")
    _firecrawl_answers(web, _FIRECRAWL_WEB)

    web_search(_QUERY)

    assert _lines(caplog) == []


def test_each_provider_has_its_name_and_the_url_of_its_request() -> None:
    assert [
        (provider.name, provider.url) for provider in (FirecrawlProvider(), DuckDuckGoProvider())
    ] == [("firecrawl", _FIRECRAWL), ("duckduckgo", _DUCKDUCKGO)]


def test_the_registry_holds_a_provider_for_each_name_that_has_one() -> None:
    assert sorted(chain.PROVIDERS) == ["duckduckgo", "firecrawl", "searxng"]


def test_the_warning_level_is_the_only_level_of_a_failed_attempt(
    web: WebFake, chain_of: Callable[..., None], caplog: pytest.LogCaptureFixture
) -> None:
    chain_of("firecrawl", "duckduckgo")
    web.respond("POST", _FIRECRAWL, 429, {})
    _duckduckgo_answers(web)

    web_search(_QUERY)

    assert [
        record.levelno for record in caplog.records if record.name == "devops_cli.ai.web_search"
    ] == [logging.WARNING]
