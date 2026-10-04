"""Common tool factories for web search, URL fetching with SSRF protection, and search engines.

Bridges and exposes native Pydantic AI common tools (pydantic_ai.common_tools) with
robust enterprise SSRF protection and zero-dependency fallbacks.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from functools import partial
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from devops_cli.ai.agents.tools import Tool

from devops_cli.config.constants import CONST_HTTP_EGRESS_POLICY_EXTENSION
from devops_cli.config.defaults import (
    DEFAULT_DUCKDUCKGO_MAX_RESULTS,
    DEFAULT_DUCKDUCKGO_TIMEOUT_SECONDS,
    DEFAULT_EXA_SEARCH_MAX_CHARACTERS,
    DEFAULT_EXA_SEARCH_NUM_RESULTS,
    DEFAULT_TAVILY_MAX_RESULTS,
    DEFAULT_TAVILY_TIMEOUT_SECONDS,
    DEFAULT_WEB_FETCH_MAX_CONTENT_LENGTH,
    DEFAULT_WEB_FETCH_MAX_DOWNLOAD_BYTES,
    DEFAULT_WEB_FETCH_TIMEOUT_SECONDS,
)
from devops_cli.core.validation import validate_url_egress
from devops_cli.http.broker import get_broker
from devops_cli.http.client import new_http_client

# =============================================================================
# Native TypedDict Schemas (Matching pydantic_ai.common_tools)
# =============================================================================


class WebFetchResult(TypedDict):
    """Result from web page fetching."""

    url: str
    title: str
    content: str


class DuckDuckGoResult(TypedDict):
    """Result from DuckDuckGo web search."""

    title: str
    href: str
    body: str


class TavilySearchResult(TypedDict):
    """Result from Tavily search API."""

    title: str
    url: str
    content: str
    score: float


class ExaSearchResult(TypedDict):
    """Result from Exa neural search."""

    title: str
    url: str
    published_date: str | None
    author: str | None
    text: str


class ExaAnswerResult(TypedDict):
    """Direct answer from Exa."""

    answer: str
    citations: list[dict[str, Any]]


class ExaContentResult(TypedDict):
    """Extracted content from Exa."""

    url: str
    title: str
    text: str
    author: str | None
    published_date: str | None


# =============================================================================
# Native Common Tool Re-exports (Image Generation & X Search)
# =============================================================================

if TYPE_CHECKING:
    from pydantic_ai.common_tools.duckduckgo import DuckDuckGoSearchTool
    from pydantic_ai.common_tools.exa import (
        ExaAnswerTool,
        ExaFindSimilarTool,
        ExaGetContentsTool,
        ExaSearchTool,
        ExaToolset,
        exa_answer_tool,
        exa_find_similar_tool,
        exa_get_contents_tool,
        exa_search_tool,
    )
    from pydantic_ai.common_tools.image_generation import (
        ImageGenerationFallbackModel,
        ImageGenerationFallbackModelFunc,
        ImageGenerationSubagentTool,
        image_generation_tool,
    )
    from pydantic_ai.common_tools.tavily import TavilySearchTool
    from pydantic_ai.common_tools.web_fetch import WebFetchLocalTool
    from pydantic_ai.common_tools.x_search import (
        XSearchFallbackModel,
        XSearchFallbackModelFunc,
        XSearchSubagentTool,
        x_search_tool,
    )
    from pydantic_ai.native_tools import ImageGenerationTool, XSearchTool
else:
    try:
        from pydantic_ai.common_tools.image_generation import (
            ImageGenerationFallbackModel,
            ImageGenerationFallbackModelFunc,
            ImageGenerationSubagentTool,
            ImageGenerationTool,
            image_generation_tool,
        )
    except Exception:

        class ImageGenerationFallbackModel:  # type: ignore[no-redef]
            """Fallback model wrapper for image generation."""

        ImageGenerationFallbackModelFunc = None

        class ImageGenerationSubagentTool:  # type: ignore[no-redef]
            """Fallback subagent tool for image generation."""

        class ImageGenerationTool:  # type: ignore[no-redef]
            """Fallback tool for image generation."""

        def image_generation_tool(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("Image generation tool requires pydantic_ai")

    try:
        from pydantic_ai.common_tools.x_search import (
            XSearchFallbackModel,
            XSearchFallbackModelFunc,
            XSearchSubagentTool,
            XSearchTool,
            x_search_tool,
        )
    except Exception:

        class XSearchFallbackModel:  # type: ignore[no-redef]
            """Fallback model wrapper for x search."""

        XSearchFallbackModelFunc = None

        class XSearchSubagentTool:  # type: ignore[no-redef]
            """Fallback subagent tool for x search."""

        class XSearchTool:  # type: ignore[no-redef]
            """Fallback tool for x search."""

        def x_search_tool(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("X search tool requires pydantic_ai")

    try:
        from pydantic_ai.common_tools.exa import (
            ExaAnswerTool,
            ExaFindSimilarTool,
            ExaGetContentsTool,
            ExaSearchTool,
            ExaToolset,
            exa_answer_tool,
            exa_find_similar_tool,
            exa_get_contents_tool,
            exa_search_tool,
        )
    except Exception:

        class ExaAnswerTool:  # type: ignore[no-redef]
            """Fallback when exa-py is not installed."""

        class ExaFindSimilarTool:  # type: ignore[no-redef]
            """Fallback when exa-py is not installed."""

        class ExaGetContentsTool:  # type: ignore[no-redef]
            """Fallback when exa-py is not installed."""

        class ExaSearchTool:  # type: ignore[no-redef]
            """Fallback when exa-py is not installed."""

        class ExaToolset:  # type: ignore[no-redef]
            """Fallback when exa-py is not installed."""

        def exa_answer_tool(*args: Any, **kwargs: Any) -> Any:
            def answer_exa(query: str) -> str:
                return f"Exa answer for '{query}': optional dependency exa-py not installed."

            from devops_cli.ai.agents.tools import Tool

            return Tool.from_function(answer_exa, name="exa_answer", takes_ctx=False)

        def exa_find_similar_tool(*args: Any, **kwargs: Any) -> Any:
            def similar_exa(url: str) -> str:
                return f"Exa find similar for '{url}': optional dependency exa-py not installed."

            from devops_cli.ai.agents.tools import Tool

            return Tool.from_function(similar_exa, name="exa_find_similar", takes_ctx=False)

        def exa_get_contents_tool(*args: Any, **kwargs: Any) -> Any:
            def contents_exa(urls: list[str]) -> str:
                return f"Exa contents for {urls}: optional dependency exa-py not installed."

            from devops_cli.ai.agents.tools import Tool

            return Tool.from_function(contents_exa, name="exa_get_contents", takes_ctx=False)

        def exa_search_tool(
            api_key: str | None = None,
            *,
            num_results: int = DEFAULT_EXA_SEARCH_NUM_RESULTS,
            max_characters: int = DEFAULT_EXA_SEARCH_MAX_CHARACTERS,
        ) -> Any:
            """Create a Tool that searches Exa neural search API."""

            def search_exa(query: str) -> str:
                return f"Exa search result for '{query}': optional dependency exa-py not installed."

            from devops_cli.ai.agents.tools import Tool

            return Tool.from_function(
                search_exa,
                name="exa_search",
                description="Search the web using Exa neural search API.",
                takes_ctx=False,
            )

    try:
        from pydantic_ai.common_tools.duckduckgo import DuckDuckGoSearchTool
    except Exception:

        class DuckDuckGoSearchTool:  # type: ignore[no-redef]
            """DuckDuckGoSearchTool fallback when optional dependency ddgs is not installed."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

    try:
        from pydantic_ai.common_tools.tavily import TavilySearchTool
    except Exception:

        class TavilySearchTool:  # type: ignore[no-redef]
            """TavilySearchTool fallback when optional dependency tavily-python is not installed."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

    try:
        from pydantic_ai.common_tools.web_fetch import WebFetchLocalTool
    except Exception:

        class WebFetchLocalTool:  # type: ignore[no-redef]
            """WebFetchLocalTool fallback when optional dependency markdownify is not installed."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass


# =============================================================================
# SSRF Validation & HTML Parsers
# =============================================================================


def is_private_ip_or_localhost(url_or_host: str) -> bool:
    """Validate if a URL or hostname resolves to private/loopback/link-local space."""
    parsed = urllib.parse.urlparse(url_or_host)
    host = parsed.hostname or url_or_host
    from devops_cli.core.validation import is_loopback_or_private_host

    return is_loopback_or_private_host(host)


def _html_to_markdown(raw_html: str) -> str:
    """Convert HTML content to clean markdown text."""
    clean = re.sub(r"<(script|style).*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(
        r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n# \1\n", clean, flags=re.DOTALL | re.IGNORECASE
    )
    clean = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<br\s*/?>", "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(
        r"<a\s+(?:[^>]*?\s+)?href=[\"'](.*?)[\"'][^>]*>(.*?)</a>",
        r"[\2](\1)",
        clean,
        flags=re.DOTALL | re.IGNORECASE,
    )
    clean = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = html.unescape(clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


# =============================================================================
# Tool Factories with SSRF Guardrails
# =============================================================================


def _canonical_host(name: str) -> str:
    """Return a host or domain name lowercased and without its trailing dot, as DNS compares it."""
    return name.lower().rstrip(".")


def _in_domains(hostname: str, domains: list[str]) -> bool:
    """Return True if `hostname` is one of `domains` or a subdomain of one."""
    return any(hostname == d or hostname.endswith(f".{d}") for d in map(_canonical_host, domains))


def _validate_fetch_domain(
    hostname: str,
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
) -> None:
    """Validate requested hostname against domain allow/block lists."""
    hostname = _canonical_host(hostname)
    if blocked_domains and _in_domains(hostname, blocked_domains):
        raise ValueError(f"Domain '{hostname}' is in blocked_domains")

    if allowed_domains and not _in_domains(hostname, allowed_domains):
        raise ValueError(f"Domain '{hostname}' is not in allowed_domains")


def _validate_fetch_hop(
    url: str,
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
) -> None:
    """Veto one web_fetch hop: http or https, within the domain lists, and public.

    The address check ignores DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK, so no environment lets a page
    or a redirect it sends reach a private, loopback or link-local address.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    _validate_fetch_domain(parsed.hostname or "", allowed_domains, blocked_domains)
    validate_url_egress(url, purpose="web_fetch", allow_private=False)


def web_fetch_tool(
    *,
    max_content_length: int | None = DEFAULT_WEB_FETCH_MAX_CONTENT_LENGTH,
    max_download_bytes: int | None = DEFAULT_WEB_FETCH_MAX_DOWNLOAD_BYTES,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> Tool:
    """Create a Tool that fetches the content of a web page and converts it to markdown."""
    egress_policy = partial(
        _validate_fetch_hop, allowed_domains=allowed_domains, blocked_domains=blocked_domains
    )

    def fetch_web_page(url: str) -> str:
        """Fetch URL content and return cleaned markdown text."""
        egress_policy(url)
        try:
            # The broker's request hook holds every redirect hop to egress_policy before sending
            # it. The tool's own headers keep the caller's trace context from the fetched site, and
            # a client of its own keeps one site's cookies from every later fetch.
            with get_broker().new_client() as client:
                request = client.build_request(
                    "GET",
                    url,
                    headers=headers,
                    timeout=DEFAULT_WEB_FETCH_TIMEOUT_SECONDS,
                    extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: egress_policy},
                )
                resp = client.send(request)
            resp.raise_for_status()

            raw_bytes = resp.content
            if max_download_bytes is not None and len(raw_bytes) > max_download_bytes:
                content_text = resp.text[:max_download_bytes]
            else:
                content_text = resp.text

            md_text = _html_to_markdown(content_text)
            if max_content_length is not None and len(md_text) > max_content_length:
                return md_text[:max_content_length] + "... (truncated)"
            return md_text
        except Exception as exc:
            return f"Error fetching web page {url[:256]}: {str(exc)[:256]}"

    from devops_cli.ai.agents.tools import Tool

    return Tool.from_function(
        fetch_web_page,
        name="web_fetch",
        description="Fetch the text/markdown content of a public URL with SSRF protection.",
        takes_ctx=False,
    )


def duckduckgo_search_tool(
    *,
    max_results: int = DEFAULT_DUCKDUCKGO_MAX_RESULTS,
) -> Tool:
    """Create a Tool that searches DuckDuckGo for public web results."""

    def search_duckduckgo(query: str) -> str:
        """Search DuckDuckGo and return top matching web results."""
        client = new_http_client()
        url = "https://html.duckduckgo.com/html/"
        try:
            resp = client.post(url, data={"q": query}, timeout=DEFAULT_DUCKDUCKGO_TIMEOUT_SECONDS)
            resp.raise_for_status()
            results = re.findall(
                r'<a\s+class="result__snippet[^"]*"\s+href="([^"]+)"[^>]*>(.*?)</a>',
                resp.text,
                flags=re.DOTALL,
            )
            if not results:
                snippets = re.findall(r'<a class="result__url"[^>]*>(.*?)</a>', resp.text)
                if not snippets:
                    return f"No DuckDuckGo results found for '{query}'."
                return "\n".join(f"- {html.unescape(s.strip())}" for s in snippets[:max_results])

            output_lines: list[str] = []
            for href, snippet in results[:max_results]:
                clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                output_lines.append(
                    f"- [{urllib.parse.unquote(href)}] {html.unescape(clean_snippet)}"
                )
            return (
                "\n".join(output_lines)
                if output_lines
                else f"No DuckDuckGo results found for '{query}'."
            )
        except Exception as exc:
            return f"DuckDuckGo search error: {str(exc)[:256]}"

    from devops_cli.ai.agents.tools import Tool

    return Tool.from_function(
        search_duckduckgo,
        name="duckduckgo_search",
        description=f"Search DuckDuckGo web search engine (returns up to {max_results} results).",
        takes_ctx=False,
    )


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
    client = new_http_client()
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


def tavily_search_tool(
    api_key: str | None = None,
    *,
    max_results: int = DEFAULT_TAVILY_MAX_RESULTS,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> Tool:
    """Create a Tool that searches using the Tavily Search API."""

    def search_tavily(query: str) -> str:
        """Execute Tavily search query and return top results."""
        try:
            results = tavily_search(
                query,
                api_key=api_key,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
            )
            if not results:
                return f"No Tavily results found for query '{query}'."
            formatted: list[str] = []
            for r in results[:max_results]:
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")
                formatted.append(f"- **{title}** ({url}): {content}")
            return "\n".join(formatted)
        except Exception as exc:
            return f"Tavily search error: {str(exc)[:256]}"

    from devops_cli.ai.agents.tools import Tool

    return Tool.from_function(
        search_tavily,
        name="tavily_search",
        description=f"Search Tavily search API (returns up to {max_results} results).",
        takes_ctx=False,
    )


__all__ = [
    "DuckDuckGoResult",
    "DuckDuckGoSearchTool",
    "ExaAnswerResult",
    "ExaAnswerTool",
    "ExaContentResult",
    "ExaFindSimilarTool",
    "ExaGetContentsTool",
    "ExaSearchResult",
    "ExaSearchTool",
    "ExaToolset",
    "ImageGenerationFallbackModel",
    "ImageGenerationFallbackModelFunc",
    "ImageGenerationSubagentTool",
    "ImageGenerationTool",
    "TavilySearchResult",
    "TavilySearchTool",
    "WebFetchLocalTool",
    "WebFetchResult",
    "XSearchFallbackModel",
    "XSearchFallbackModelFunc",
    "XSearchSubagentTool",
    "XSearchTool",
    "_html_to_markdown",
    "duckduckgo_search_tool",
    "exa_answer_tool",
    "exa_find_similar_tool",
    "exa_get_contents_tool",
    "exa_search_tool",
    "image_generation_tool",
    "is_private_ip_or_localhost",
    "tavily_search",
    "tavily_search_tool",
    "web_fetch_tool",
    "x_search_tool",
]
