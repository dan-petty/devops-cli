"""Tavily web search for the roadmap refinement research step."""

from __future__ import annotations

from typing import Any, cast

from devops_cli.config.defaults import DEFAULT_TAVILY_MAX_RESULTS, DEFAULT_TAVILY_TIMEOUT_SECONDS
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel


def tavily_search(
    query: str,
    api_key: str | None = None,
    *,
    max_results: int = DEFAULT_TAVILY_MAX_RESULTS,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Execute a Tavily search query and return raw results list.

    Raises on HTTP error (via raise_for_status) and on a reply with no 'results' list.
    """
    client = new_http_client(level=EgressLevel.PUBLIC)
    tavily_url = "https://api.tavily.com/search"
    payload: dict[str, Any] = {
        "api_key": api_key or "",
        "query": query,
        "max_results": max_results,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    resp = client.post(tavily_url, json=payload, timeout=DEFAULT_TAVILY_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or "results" not in data or not isinstance(data["results"], list):
        raise ValueError("Tavily response missing 'results' list")
    return cast(list[dict[str, Any]], data["results"])


__all__ = ["tavily_search"]
