"""Firecrawl web search for the roadmap refinement investigation (#2398)."""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx2

from devops_cli.config.constants import CONST_FIRECRAWL_RESULT_ERROR, CONST_FIRECRAWL_RESULT_OK
from devops_cli.config.defaults import (
    DEFAULT_FIRECRAWL_SEARCH_LIMIT,
    DEFAULT_FIRECRAWL_SEARCH_URL,
    DEFAULT_FIRECRAWL_TIMEOUT_SECONDS,
)
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.telemetry.instruments import FIRECRAWL_SEARCHES_TOTAL, emit

logger = logging.getLogger(__name__)


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
    client = new_http_client(level=EgressLevel.PUBLIC)
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


def _failed(result: str, reason: str) -> None:
    """Count a failed search by its result and log one warning with `reason`."""
    emit(FIRECRAWL_SEARCHES_TOTAL, 1, {"result": result})
    logger.warning("A Firecrawl web search failed: %s.", reason)


__all__ = ["firecrawl_search"]
