"""Common tool factories for web search, URL fetching with SSRF protection, and search engines.

Bridges and exposes native Pydantic AI common tools (pydantic_ai.common_tools) with
robust enterprise SSRF protection and zero-dependency fallbacks.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from devops_cli.ai.agents.tools import Tool

from devops_cli.exceptions.security import SSRFBlockedError
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
            num_results: int = 5,
            max_characters: int = 1000,
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


def _is_private_or_loopback(host: str) -> bool:
    """Validate if a hostname or IP address resolves to private/loopback space."""
    import ipaddress
    import socket

    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass

    lower_host = host.lower()
    if lower_host in ("localhost", "127.0.0.1", "::1") or lower_host.endswith(".local"):
        return True

    try:
        resolved_addrs = socket.getaddrinfo(host, None)
        for _, _, _, _, sockaddr in resolved_addrs:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return True
            except ValueError:
                continue
    except socket.gaierror, OSError:
        pass

    return False


def is_private_ip_or_localhost(url_or_host: str) -> bool:
    """Validate if a URL or hostname resolves to private/loopback/link-local space."""
    parsed = urllib.parse.urlparse(url_or_host)
    host = parsed.hostname or url_or_host
    return _is_private_or_loopback(host)


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


def web_fetch_tool(
    *,
    max_content_length: int | None = 50000,
    max_download_bytes: int | None = 52428800,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> Tool:
    """Create a Tool that fetches the content of a web page and converts it to markdown."""

    def fetch_web_page(url: str) -> str:
        """Fetch URL content and return cleaned markdown text."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        hostname = (parsed.hostname or "").lower()
        if blocked_domains and any(
            hostname == d.lower() or hostname.endswith(f".{d.lower()}") for d in blocked_domains
        ):
            raise ValueError(f"Domain '{hostname}' is in blocked_domains")

        if allowed_domains and not any(
            hostname == d.lower() or hostname.endswith(f".{d.lower()}") for d in allowed_domains
        ):
            raise ValueError(f"Domain '{hostname}' is not in allowed_domains")

        if _is_private_or_loopback(hostname):
            raise SSRFBlockedError(target_url=url)

        client = new_http_client(headers=headers or {})
        try:
            resp = client.get(url, follow_redirects=True, timeout=15.0)
            final_host = ""
            if hasattr(resp, "url"):
                final_host = (
                    getattr(resp.url, "host", None) or getattr(resp.url, "hostname", None) or ""
                )
                if not final_host:
                    final_host = urllib.parse.urlparse(str(resp.url)).hostname or ""
            if final_host and _is_private_or_loopback(str(final_host)):
                raise SSRFBlockedError(target_url=str(getattr(resp, "url", url)))
            if not final_host and _is_private_or_loopback(hostname):
                raise SSRFBlockedError(target_url=url)

            resp.raise_for_status()
            if max_download_bytes is not None and len(resp.content) > max_download_bytes:
                content_text = resp.text[:max_download_bytes]
            else:
                content_text = resp.text

            md_text = _html_to_markdown(content_text)
            if max_content_length is not None and len(md_text) > max_content_length:
                return md_text[:max_content_length] + "... (truncated)"
            return md_text
        except Exception as exc:
            return f"Error fetching web page {url}: {exc}"

    from devops_cli.ai.agents.tools import Tool

    return Tool.from_function(
        fetch_web_page,
        name="web_fetch",
        description="Fetch the text/markdown content of a public URL with SSRF protection.",
        takes_ctx=False,
    )


def duckduckgo_search_tool(
    *,
    max_results: int = 5,
) -> Tool:
    """Create a Tool that searches DuckDuckGo for public web results."""

    def search_duckduckgo(query: str) -> str:
        """Search DuckDuckGo and return top matching web results."""
        client = new_http_client()
        url = "https://html.duckduckgo.com/html/"
        try:
            resp = client.post(url, data={"q": query}, timeout=10.0)
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
            return f"DuckDuckGo search error: {exc}"

    from devops_cli.ai.agents.tools import Tool

    return Tool.from_function(
        search_duckduckgo,
        name="duckduckgo_search",
        description=f"Search DuckDuckGo web search engine (returns up to {max_results} results).",
        takes_ctx=False,
    )


def tavily_search_tool(
    api_key: str | None = None,
    *,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> Tool:
    """Create a Tool that searches using the Tavily Search API."""

    def search_tavily(query: str) -> str:
        """Execute Tavily search query and return top results."""
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

        try:
            resp = client.post(tavily_url, json=payload, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
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
            return f"Tavily search error: {exc}"

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
    "_is_private_or_loopback",
    "duckduckgo_search_tool",
    "exa_answer_tool",
    "exa_find_similar_tool",
    "exa_get_contents_tool",
    "exa_search_tool",
    "image_generation_tool",
    "is_private_ip_or_localhost",
    "tavily_search_tool",
    "web_fetch_tool",
    "x_search_tool",
]
