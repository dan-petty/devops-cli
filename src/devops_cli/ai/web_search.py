"""Web search over a chain of providers (#3925).

`web_search` asks the providers of `search.providers` in order and returns the hits of the first
one that has any. A provider that is not configured is skipped. A provider that fails, or returns no
hit, passes the search on at once, with no retry and no wait. Every request goes through the HTTP
entry point at the public level, so the egress check of SECURITY.md applies to each provider.

A new provider is a class with the members of `SearchProvider` and one entry in `PROVIDERS` and in
`SearchProviderName`.
"""

from __future__ import annotations

import ipaddress
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from email.errors import MessageError
from email.headerregistry import Address
from typing import Final, Protocol
from urllib.parse import urlsplit

import httpx2

from devops_cli.config.constants import (
    CONST_WEB_SEARCH_BACKEND_NONE,
    CONST_WEB_SEARCH_RESULT_DEGRADED,
    CONST_WEB_SEARCH_RESULT_EMPTY,
    CONST_WEB_SEARCH_RESULT_ERROR,
    CONST_WEB_SEARCH_RESULT_EXHAUSTED,
    CONST_WEB_SEARCH_RESULT_OK,
    CONST_WEB_SEARCH_RESULT_REFUSED,
)
from devops_cli.config.defaults import (
    DEFAULT_DUCKDUCKGO_REGION,
    DEFAULT_DUCKDUCKGO_SAFESEARCH,
    DEFAULT_DUCKDUCKGO_SEARCH_URL,
    DEFAULT_DUCKDUCKGO_TIMEOUT_SECONDS,
    DEFAULT_FIRECRAWL_SEARCH_URL,
    DEFAULT_FIRECRAWL_TIMEOUT_SECONDS,
    DEFAULT_SEARXNG_CATEGORIES,
    DEFAULT_SEARXNG_MAX_REPLY_BYTES,
    DEFAULT_SEARXNG_TIMEOUT_SECONDS,
    DEFAULT_WEB_SEARCH_DEADLINE_SECONDS,
    DEFAULT_WEB_SEARCH_LIMIT,
    DEFAULT_WEB_SEARCH_QUERY_MAX_CHARS,
    DEFAULT_WEB_SEARCH_QUERY_MAX_WORDS,
)
from devops_cli.config.settings import Settings, get_firecrawl_api_key, load_settings
from devops_cli.core import clock
from devops_cli.exceptions.ai import SearchFailed, SearchQueryRefused
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.http.egress import EgressLevel, configured_level
from devops_cli.http.entry import http_client
from devops_cli.http.urls import service_base_url
from devops_cli.security.reference_extractor import (
    is_local_or_reserved_domain,
    is_private_or_local_ip,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.instruments import WEB_SEARCHES_TOTAL, emit

logger = logging.getLogger(__name__)

_PROSE_EDGES: Final[str] = ".,;:!?\"'`(){}<>"
_HTTP_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
_SEARXNG_SETTING: Final[str] = "search.searxng_url"


@dataclass(frozen=True)
class SearchHit:
    """One result of a web search, and the provider that returned it."""

    url: str
    title: str
    snippet: str
    provider: str


class SearchProvider(Protocol):
    """One source of web search hits.

    `search` raises `httpx2.HTTPError` when the provider did not answer or refused, and
    `ValueError` when its reply is not readable. It makes no retry and no wait: `web_search`
    passes the search on.
    """

    @property
    def name(self) -> str:
        """The name that `search.providers` lists and the metric uses as its backend."""
        ...

    @property
    def method(self) -> str:
        """The HTTP method of a search request."""
        ...

    @property
    def url(self) -> str:
        """The URL of a search request."""
        ...

    def configured(self, settings: Settings) -> bool:
        """Whether the provider has what it needs to search, such as a key."""
        ...

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        """At most `limit` hits for `query`."""
        ...


class DuckDuckGoProvider:
    """DuckDuckGo through the HTML engine of the `ddgs` package (#3876). It needs no key.

    The `ddgs` package builds the payload and reads the page. The request itself goes through the
    HTTP entry point, because the HTTP client of `ddgs` takes no transport and so skips the egress
    check (SECURITY.md).
    """

    name = "duckduckgo"
    method = "POST"
    url = DEFAULT_DUCKDUCKGO_SEARCH_URL

    def configured(self, settings: Settings) -> bool:
        return True

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        """Raises on an HTTP error and on an answer other than HTTP 200: DuckDuckGo answers a
        client that it takes for a bot with HTTP 202 and a page with no hit."""
        # `ddgs` loads `lxml` and the code of all its engines, about 0.4 s: only a search that
        # reaches this provider pays it.
        from ddgs.engines.duckduckgo import Duckduckgo

        engine = Duckduckgo()
        payload = engine.build_payload(
            query,
            region=DEFAULT_DUCKDUCKGO_REGION,
            safesearch=DEFAULT_DUCKDUCKGO_SAFESEARCH,
            timelimit=None,
        )
        with http_client(level=EgressLevel.PUBLIC) as client:
            resp = client.post(
                engine.search_url,
                data=payload,
                headers=_language_headers(),
                timeout=DEFAULT_DUCKDUCKGO_TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        if resp.status_code != httpx2.codes.OK:
            raise ValueError(f"DuckDuckGo answered with HTTP {resp.status_code}")
        found = engine.post_extract_results(engine.extract_results(resp.text))
        return [
            SearchHit(url=hit.href, title=hit.title, snippet=hit.body, provider=self.name)
            for hit in found[:limit]
        ]


class FirecrawlProvider:
    """The hosted Firecrawl API. It reads its own key. It asks for no page scrape, which costs a
    credit for each result."""

    name = "firecrawl"
    method = "POST"
    url = DEFAULT_FIRECRAWL_SEARCH_URL

    def configured(self, settings: Settings) -> bool:
        return bool(get_firecrawl_api_key(settings))

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        """Raises on an HTTP error (`raise_for_status`) and on a reply with no `data.web` list."""
        client = http_client(level=EgressLevel.PUBLIC)
        resp = client.post(
            self.url,
            json={"query": query, "limit": limit},
            headers={"Authorization": f"Bearer {get_firecrawl_api_key()}", **_language_headers()},
            timeout=DEFAULT_FIRECRAWL_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise ValueError("Firecrawl reply is not JSON") from exc
        found = data.get("data") if isinstance(data, dict) else None
        results = found.get("web") if isinstance(found, dict) else None
        if not isinstance(results, list):
            raise ValueError("Firecrawl reply has no 'data.web' list")
        return [
            SearchHit(
                url=str(item.get("url") or ""),
                title=str(item.get("title") or ""),
                snippet=str(item.get("description") or ""),
                provider=self.name,
            )
            for item in results
            if isinstance(item, dict)
        ]


class SearxngProvider:
    """The SearXNG service of the cluster (#3927). It needs no key, only its address in
    `search.searxng_url`, which has no default.

    The request is `GET {address}/search` with `format=json`. A model chooses the query, and
    SearXNG reads a query that starts with `!` as an engine selector and answers it with a
    redirect, so the client follows no redirect: a redirect is a failure (the query guard refuses
    such a query first). The client dials a loopback address, and a private one when
    `ai.allow_private_network` is set, so a workstation reaches the service by
    `kubectl port-forward` and the Service pod by its cluster address. The client reads at most
    `DEFAULT_SEARXNG_MAX_REPLY_BYTES`. The title and the text of a hit are data from the web and
    untrusted: a caller must never run them as an instruction.
    """

    name = "searxng"
    method = "GET"

    @property
    def url(self) -> str:
        """The search endpoint of the configured service, or an empty string without an address."""
        address = load_settings().search.searxng_url
        return f"{service_base_url(address, _SEARXNG_SETTING)}/search" if address else ""

    def configured(self, settings: Settings) -> bool:
        return bool(settings.search.searxng_url)

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        """Raises `ConfigurationError` when `search.searxng_url` is not set, `SSRFBlockedError` when
        the egress check refuses the address, `httpx2.HTTPStatusError` for an answer other than
        HTTP 200 (a redirect included), and `ValueError` for a reply that is over the byte cap, is
        not a JSON object with a `results` list, or has no result while an engine did not
        answer."""
        settings = load_settings()
        if not settings.search.searxng_url:
            raise ConfigurationError(
                f"The setting {_SEARXNG_SETTING} is not set", key=_SEARXNG_SETTING
            )
        endpoint = f"{service_base_url(settings.search.searxng_url, _SEARXNG_SETTING)}/search"
        with (
            http_client(
                level=configured_level(settings.ai),
                timeout=DEFAULT_SEARXNG_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client,
            client.stream(
                "GET",
                endpoint,
                params={
                    "q": query,
                    "format": "json",
                    "language": settings.search.language,
                    "categories": DEFAULT_SEARXNG_CATEGORIES,
                    "pageno": "1",
                },
                headers={"Accept": "application/json", **_language_headers()},
            ) as response,
        ):
            response.raise_for_status()
            if response.status_code != httpx2.codes.OK:
                raise ValueError(f"SearXNG answered with HTTP {response.status_code}")
            body = _read_capped(response)
        reply = json.loads(body)
        results = reply.get("results") if isinstance(reply, dict) else None
        if not isinstance(results, list):
            raise ValueError("SearXNG reply has no 'results' list")
        if not results and reply.get("unresponsive_engines"):
            raise ValueError("SearXNG engines did not answer")
        return [
            SearchHit(
                url=str(item["url"]),
                title=str(item.get("title") or ""),
                snippet=str(item.get("content") or ""),
                provider=self.name,
            )
            for item in results[:limit]
            if isinstance(item, dict) and item.get("url")
        ]


def _read_capped(response: httpx2.Response) -> bytes:
    """The body of a streamed reply, refused as soon as it passes the byte cap."""
    body = bytearray()
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > DEFAULT_SEARXNG_MAX_REPLY_BYTES:
            raise ValueError("SearXNG reply is larger than the byte cap")
    return bytes(body)


# The providers that exist, by the name that `search.providers` lists.
PROVIDERS: Final[dict[str, SearchProvider]] = {
    provider.name: provider
    for provider in (SearxngProvider(), DuckDuckGoProvider(), FirecrawlProvider())
}


def iter_configured_providers(settings: Settings | None = None) -> Iterator[SearchProvider]:
    """The providers that a search asks, in order: those of `search.providers` that exist and are
    configured. A provider is checked only when the caller asks for it, so a search that the first
    provider answers reads no key of a later one."""
    active = settings or load_settings()
    for name in active.search.providers:
        provider = PROVIDERS.get(name)
        if provider and provider.configured(active):
            yield provider


def configured_providers(settings: Settings | None = None) -> list[SearchProvider]:
    """All the providers of `iter_configured_providers`."""
    return list(iter_configured_providers(settings))


def first_configured_provider(settings: Settings | None = None) -> SearchProvider | None:
    """The provider that a search asks first, or None. Web search is on when there is one."""
    return next(iter_configured_providers(settings), None)


def web_search(query: str, *, limit: int = DEFAULT_WEB_SEARCH_LIMIT) -> list[SearchHit]:
    """Search the web through the configured providers and return at most `limit` hits.

    The first provider with at least one hit answers. A provider that fails, or returns no hit,
    passes the search on. The chain starts no provider after `DEFAULT_WEB_SEARCH_DEADLINE_SECONDS`.
    Each attempt adds 1 to `devops_cli_web_searches_total` by its backend and its result, and a
    failed attempt logs one warning that names the backend and the HTTP status or the class of the
    error, never the key or the query.

    Raises `SearchQueryRefused` when the guard stops the query, before any request, and
    `SearchFailed` when no provider answered. When some provider answered with no hit and the rest
    failed, the result is an empty list.
    """
    try:
        _guard(query)
    except SearchQueryRefused:
        _count(CONST_WEB_SEARCH_BACKEND_NONE, CONST_WEB_SEARCH_RESULT_REFUSED)
        raise
    settings = load_settings()
    deadline = clock.monotonic() + DEFAULT_WEB_SEARCH_DEADLINE_SECONDS
    answered_empty = False
    for provider in iter_configured_providers(settings):
        if clock.monotonic() >= deadline:
            break
        try:
            found = provider.search(query, limit=limit)
        except httpx2.HTTPStatusError as exc:
            status = exc.response.status_code
            _failed(provider.name, str(status), f"HTTP {status}")
            continue
        except httpx2.HTTPError as exc:
            _failed(provider.name, CONST_WEB_SEARCH_RESULT_ERROR, type(exc).__name__)
            continue
        except SSRFBlockedError as exc:
            _failed(provider.name, CONST_WEB_SEARCH_RESULT_REFUSED, type(exc).__name__)
            continue
        except ValueError as exc:
            _failed(provider.name, CONST_WEB_SEARCH_RESULT_DEGRADED, type(exc).__name__)
            continue
        hits = _usable(found)[:limit]
        if hits:
            _count(provider.name, CONST_WEB_SEARCH_RESULT_OK)
            return hits
        _count(provider.name, CONST_WEB_SEARCH_RESULT_EMPTY)
        answered_empty = True
    if answered_empty:
        return []
    _count(CONST_WEB_SEARCH_BACKEND_NONE, CONST_WEB_SEARCH_RESULT_EXHAUSTED)
    raise SearchFailed("No search provider answered.")


def normalize_url(url: str) -> str:
    """`url` as the jobs compare it: a trailing slash does not make another URL."""
    return url.rstrip("/")


def _usable(hits: list[SearchHit]) -> list[SearchHit]:
    """The hits with an http or https URL, each URL once."""
    seen: set[str] = set()
    kept: list[SearchHit] = []
    for hit in hits:
        key = normalize_url(hit.url)
        if urlsplit(hit.url).scheme not in _HTTP_SCHEMES or key in seen:
            continue
        seen.add(key)
        kept.append(hit)
    return kept


def _language_headers() -> dict[str, str]:
    """The `Accept-Language` of a search request, from `search.language`."""
    return {"Accept-Language": load_settings().search.language}


def _count(backend: str, result: str) -> None:
    emit(WEB_SEARCHES_TOTAL, 1, {"backend": backend, "result": result})


def _failed(backend: str, result: str, reason: str) -> None:
    """Count a failed attempt and log one warning with `reason`: the status or the error class."""
    _count(backend, result)
    logger.warning("A web search failed on %s: %s.", backend, reason)


# ── The query guard ───────────────────────────────────────────────────────────


def _guard(query: str) -> None:
    """Refuse a query that must not leave the process, before any provider runs.

    The message names the rule and never holds the query.
    """
    text = query.strip()
    reason = (
        "the query is empty"
        if not text
        else "the query is over the character cap"
        if len(text) > DEFAULT_WEB_SEARCH_QUERY_MAX_CHARS
        else "the query is over the word cap"
        if len(text.split()) > DEFAULT_WEB_SEARCH_QUERY_MAX_WORDS
        else "the query starts with a bang or a command mark"
        if text[0] in "!:"
        else "the query holds a secret"
        if mask_secrets(text) != text
        else _private_part(text)
    )
    if reason:
        raise SearchQueryRefused(f"The search was refused: {reason}.")


def _private_part(text: str) -> str | None:
    """Why a token of `text` is private data: an e-mail address, a private address or an internal
    host name. None when no token is."""
    for token in text.split():
        word = token.strip(_PROSE_EDGES)
        host = _host_of(word)
        if _is_email(word):
            return "the query holds an e-mail address"
        if _is_private_address(host):
            return "the query holds a private address"
        if is_local_or_reserved_domain(host):
            return "the query holds an internal host name"
    return None


def _host_of(word: str) -> str:
    """The host of `word`, which may carry a port or brackets, or `word` when it names no host."""
    try:
        return urlsplit(f"//{word}").hostname or word
    except ValueError:
        return word


def _is_email(word: str) -> bool:
    """Whether `word` is an e-mail address, as the standard library reads one: a name, an `@` and
    a domain with a dot."""
    try:
        return "." in Address(addr_spec=word).domain
    except ValueError, MessageError:
        return False


def _is_private_address(host: str) -> bool:
    """Whether `host` is an IP address in private or local space. A version such as `10.15` is no
    address: only a full address counts."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return is_private_or_local_ip(str(address))


__all__ = [
    "PROVIDERS",
    "DuckDuckGoProvider",
    "FirecrawlProvider",
    "SearchHit",
    "SearchProvider",
    "SearxngProvider",
    "configured_providers",
    "first_configured_provider",
    "iter_configured_providers",
    "normalize_url",
    "web_search",
]
