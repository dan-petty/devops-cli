"""Firecrawl web search for the roadmap refinement investigation (#2398)."""

from __future__ import annotations

from typing import Any, cast

from devops_cli.config.defaults import (
    DEFAULT_FIRECRAWL_SEARCH_LIMIT,
    DEFAULT_FIRECRAWL_SEARCH_URL,
    DEFAULT_FIRECRAWL_TIMEOUT_SECONDS,
)
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel


def firecrawl_search(
    query: str,
    api_key: str,
    *,
    limit: int = DEFAULT_FIRECRAWL_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Search the web with the hosted Firecrawl API and return its web results, each with a
    `url`, `title` and `description`. It asks for no page scrape, which costs a credit for each
    result.

    Raises on an HTTP error (`raise_for_status`) and on a reply with no `data.web` list.
    """
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


__all__ = ["firecrawl_search"]
