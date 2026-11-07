"""Web search for the roadmap jobs: Firecrawl, and DuckDuckGo when Firecrawl fails (#2398, #3876)."""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx2

from devops_cli.config.constants import (
    CONST_FIRECRAWL_RESULT_ERROR,
    CONST_FIRECRAWL_RESULT_OK,
    CONST_WEB_SEARCH_BACKEND_DUCKDUCKGO,
)
from devops_cli.config.defaults import (
    DEFAULT_DUCKDUCKGO_REGION,
    DEFAULT_DUCKDUCKGO_SAFESEARCH,
    DEFAULT_DUCKDUCKGO_TIMEOUT_SECONDS,
    DEFAULT_FIRECRAWL_SEARCH_LIMIT,
    DEFAULT_FIRECRAWL_SEARCH_URL,
    DEFAULT_FIRECRAWL_TIMEOUT_SECONDS,
)
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.telemetry.instruments import (
    FIRECRAWL_SEARCHES_TOTAL,
    WEB_SEARCH_FALLBACKS_TOTAL,
    emit,
)

logger = logging.getLogger(__name__)


def web_search(
    query: str,
    api_key: str,
    *,
    limit: int = DEFAULT_FIRECRAWL_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Search the web with Firecrawl, and with DuckDuckGo when Firecrawl fails (#3876). Return the
    results in the form of Firecrawl: each with a `url`, `title` and `description`.

    A search that Firecrawl answered, also with no result, runs no fallback. A search that
    Firecrawl refused (HTTP 402, 429, 5xx), did not answer or answered with no `data.web` list logs
    one line with the reason, never the key or the query, and adds 1 to
    `devops_cli_web_search_fallbacks_total` by the backend and the result of the fallback.

    Raises what `firecrawl_search` raises when DuckDuckGo fails too: `httpx2.HTTPError` or
    `ValueError`, so a caller handles one failure.
    """
    try:
        return firecrawl_search(query, api_key, limit=limit)
    except (httpx2.HTTPError, ValueError) as exc:
        logger.warning("A web search fell back to DuckDuckGo: %s.", _reason(exc))
    try:
        results = duckduckgo_search(query, limit=limit)
    except httpx2.HTTPError, ValueError:
        _count_fallback(CONST_FIRECRAWL_RESULT_ERROR)
        raise
    _count_fallback(CONST_FIRECRAWL_RESULT_OK)
    return results


def duckduckgo_search(
    query: str,
    *,
    limit: int = DEFAULT_FIRECRAWL_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Search DuckDuckGo and return at most `limit` results in the form of Firecrawl results.

    The `ddgs` package builds the request and reads the HTML page of the DuckDuckGo engine. The
    request itself goes through the HTTP entry point at the public level, because the HTTP client
    of `ddgs` takes no transport and so skips the egress check (SECURITY.md).

    Raises on an HTTP error, and on an answer other than HTTP 200: DuckDuckGo answers a client that
    it takes for a bot with HTTP 202 and a page with no result.
    """
    # `ddgs` loads `lxml` and the code of all its engines, about 0.4 s: only a failed Firecrawl
    # search pays it.
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
            engine.search_url, data=payload, timeout=DEFAULT_DUCKDUCKGO_TIMEOUT_SECONDS
        )
    resp.raise_for_status()
    if resp.status_code != httpx2.codes.OK:
        raise ValueError(f"DuckDuckGo answered with HTTP {resp.status_code}")
    hits = engine.post_extract_results(engine.extract_results(resp.text))
    return [{"url": hit.href, "title": hit.title, "description": hit.body} for hit in hits[:limit]]


def firecrawl_search(
    query: str,
    api_key: str,
    *,
    limit: int = DEFAULT_FIRECRAWL_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Search the web with the hosted Firecrawl API and return its web results, each with a
    `url`, `title` and `description`. It asks for no page scrape, which costs a credit for each
    result.

    Each search adds 1 to `devops_cli_firecrawl_searches_total` by its result (#2475): `ok`, the
    HTTP status of a search that Firecrawl refused, or `error`. A failed search logs one warning
    that names the status or the error's class, and never the key or the query.

    Raises on an HTTP error (`raise_for_status`) and on a reply with no `data.web` list.
    """
    try:
        results = _search(query, api_key, limit)
    except httpx2.HTTPStatusError as exc:
        status = exc.response.status_code
        _failed(str(status), f"Firecrawl answered with HTTP {status}")
        raise
    except (httpx2.HTTPError, ValueError) as exc:
        _failed(CONST_FIRECRAWL_RESULT_ERROR, type(exc).__name__)
        raise
    emit(FIRECRAWL_SEARCHES_TOTAL, 1, {"result": CONST_FIRECRAWL_RESULT_OK})
    return results


def _search(query: str, api_key: str, limit: int) -> list[dict[str, Any]]:
    """One search request and its web results."""
    client = http_client(level=EgressLevel.PUBLIC)
    resp = client.post(
        DEFAULT_FIRECRAWL_SEARCH_URL,
        json={"query": query, "limit": limit},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=DEFAULT_FIRECRAWL_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    found = data.get("data") if isinstance(data, dict) else None
    results = found.get("web") if isinstance(found, dict) else None
    if not isinstance(results, list):
        raise ValueError("Firecrawl response missing 'data.web' list")
    return cast(list[dict[str, Any]], results)


def _reason(exc: Exception) -> str:
    """Why a Firecrawl search failed: its HTTP status, or the class of the error. Never the key."""
    if isinstance(exc, httpx2.HTTPStatusError):
        return f"Firecrawl answered with HTTP {exc.response.status_code}"
    return type(exc).__name__


def _count_fallback(result: str) -> None:
    """Count one search of the fallback backend by its `result`."""
    emit(
        WEB_SEARCH_FALLBACKS_TOTAL,
        1,
        {"backend": CONST_WEB_SEARCH_BACKEND_DUCKDUCKGO, "result": result},
    )


def _failed(result: str, reason: str) -> None:
    """Count a failed search by its result and log one warning with `reason`."""
    emit(FIRECRAWL_SEARCHES_TOTAL, 1, {"result": result})
    logger.warning("A Firecrawl web search failed: %s.", reason)


__all__ = ["duckduckgo_search", "firecrawl_search", "web_search"]
