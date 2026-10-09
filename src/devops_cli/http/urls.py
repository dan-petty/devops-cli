"""URL parsing and origin resolution using sending client parsers."""

from __future__ import annotations

import ipaddress
import urllib.parse
from typing import TYPE_CHECKING

import httpx2

if TYPE_CHECKING:
    from urllib.parse import SplitResult


def get_url_origin(value: str) -> httpx2.Origin | None:
    """Return the HTTP origin for a URL, or None if unparseable or not absolute."""
    clean = value.strip()
    try:
        return httpx2.URL(clean).origin
    except ValueError, httpx2.InvalidURL:
        return None


def _bracket_bare_ipv6(s: str) -> str:
    """Bracket bare IPv6 address literal if valid, else return unchanged."""
    try:
        ip = ipaddress.ip_address(s)
        if isinstance(ip, ipaddress.IPv6Address):
            return f"[{ip}]"
    except ValueError:
        pass
    return s


def _has_empty_port(netloc: str) -> bool:
    """Check if netloc ends with a colon or has an empty port component."""
    host_port = netloc.split("@")[-1]
    return host_port.endswith(":")


def _resolve_netloc_fallback(s: str, parsed: SplitResult) -> SplitResult:
    """Apply //netloc fallback when urlsplit(s) found no netloc."""
    fallback = urllib.parse.urlsplit(f"//{s}")
    if parsed.scheme:
        try:
            has_port = fallback.port is not None
        except ValueError:
            has_port = True
        if has_port:
            return fallback
        return parsed
    return fallback


def read_url_or_authority(s: str) -> SplitResult | None:
    """Parse a URL or bare authority (host[:port]) into a SplitResult with a valid host."""
    if not isinstance(s, str):
        return None
    try:
        clean = _bracket_bare_ipv6(s)
        parsed = urllib.parse.urlsplit(clean)

        if not parsed.netloc:
            parsed = _resolve_netloc_fallback(clean, parsed)

        if parsed.netloc and _has_empty_port(parsed.netloc):
            return None

        host = parsed.hostname
        if not host:
            return None
        return parsed
    except ValueError:
        return None


def extract_domain_target(s: str) -> str | None:
    """Extract the hostname from a URL or bare host:port string."""
    parsed = read_url_or_authority(s)
    if parsed is None:
        return None
    try:
        return parsed.hostname
    except ValueError:
        return None


def append_path(base: httpx2.URL | str, reference: str) -> httpx2.URL:
    """Append a relative path reference to a base URL without losing trailing path components."""
    url = httpx2.URL(base) if isinstance(base, str) else base
    if not reference:
        return url
    raw_path = url.raw_path
    if not raw_path.endswith(b"/"):
        raw_path = raw_path + b"/"
    base_with_slash = url.copy_with(raw_path=raw_path)
    rel = "./" + reference.lstrip("/")
    return base_with_slash.join(rel)


__all__ = [
    "append_path",
    "extract_domain_target",
    "get_url_origin",
    "read_url_or_authority",
]
