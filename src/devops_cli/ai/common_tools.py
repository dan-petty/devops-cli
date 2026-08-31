"""Common tool factories for web search, URL fetching with SSRF protection, and search engines."""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

from devops_cli.ai.agents.tools import Tool
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.http.client import new_http_client


def _is_private_or_loopback(host: str) -> bool:
    """Validate if a hostname or IP address resolves to private/loopback space."""
    import ipaddress

    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass
    lower_host = host.lower()
    return lower_host in ("localhost", "127.0.0.1", "::1") or lower_host.endswith(".local")


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

        hostname = parsed.hostname or ""
        if _is_private_or_loopback(hostname):
            raise SSRFBlockedError(target_url=url)

        if allowed_domains and not any(
            hostname == d or hostname.endswith(f".{d}") for d in allowed_domains
        ):
            raise ValueError(f"Domain '{hostname}' is not in allowed_domains")

        if blocked_domains and any(
            hostname == d or hostname.endswith(f".{d}") for d in blocked_domains
        ):
            raise ValueError(f"Domain '{hostname}' is in blocked_domains")

        client = new_http_client(headers=headers or {})
        try:
            resp = client.get(url, follow_redirects=True, timeout=15.0)
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
                # Fallback pattern
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

    return Tool.from_function(
        search_tavily,
        name="tavily_search",
        description=f"Search Tavily search API (returns up to {max_results} results).",
        takes_ctx=False,
    )
