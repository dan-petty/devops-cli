"""Public Suffix List classification and DNS-label hierarchy comparison (#887).

`tldextract` and `dns.name` are imported on first use rather than at module import time.
"""

from __future__ import annotations

import functools
import ipaddress
from typing import TYPE_CHECKING, Annotated, Any, Final

from pydantic import AfterValidator, BeforeValidator, ValidationInfo

if TYPE_CHECKING:
    import dns.name
    import tldextract

__all__ = [
    "ConfiguredDomain",
    "OptionalConfiguredDomain",
    "blank_domain_to_none",
    "get_tld_extractor",
    "is_at_or_under",
    "is_public_dns_name",
    "validate_configured_domain",
]


@functools.lru_cache(maxsize=1)
def get_tld_extractor() -> tldextract.TLDExtract:
    """Return the shared offline Public Suffix List extractor (no network, no disk cache)."""
    import tldextract

    return tldextract.TLDExtract(
        suffix_list_urls=(),
        fallback_to_snapshot=True,
        cache_dir=None,
    )


@functools.lru_cache(maxsize=1)
def _special_use_psl_roots() -> tuple[dns.name.Name, dns.name.Name]:
    """Return the two IANA special-use domain roots listed in the Public Suffix List.

    - `arpa.` — Address and Routing Parameter Area (RFC 3172 / RFC 6761)
    - `onion.` — Tor Special-Use Domain Name (RFC 7686)
    """
    import dns.name

    arpa_dns_name: Final[dns.name.Name] = dns.name.from_text("arpa.")  # RFC 3172
    onion_dns_name: Final[dns.name.Name] = dns.name.from_text("onion.")  # RFC 7686
    return (arpa_dns_name, onion_dns_name)


def __getattr__(name: str) -> Any:
    """Lazily expose `ARPA_DNS_NAME` (RFC 3172) and `ONION_DNS_NAME` (RFC 7686) on first access."""
    if name == "ARPA_DNS_NAME":
        return _special_use_psl_roots()[0]
    if name == "ONION_DNS_NAME":
        return _special_use_psl_roots()[1]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _parse_ip_literal(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return a parsed IPv4 or IPv6 address when `value` is an IP literal, or `None`."""
    clean = str(value).strip().removeprefix("[").removesuffix("]")
    try:
        return ipaddress.ip_address(clean)
    except ValueError:
        return None


@functools.lru_cache(maxsize=512)
def _parse_non_root_dns_name(value: str) -> dns.name.Name:
    """Parse `value` with IDNA 2008 and raise `dns.name.EmptyLabel` if it is the root name."""
    import dns.name

    clean = str(value).strip()
    if not clean or clean.startswith("."):
        raise dns.name.EmptyLabel
    parsed = dns.name.from_unicode(clean, idna_codec=dns.name.IDNA_2008)
    if parsed == dns.name.root:
        raise dns.name.EmptyLabel
    return parsed


def is_public_dns_name(host: str) -> bool:
    """Return True when `host` is a valid DNS name with a registrable PSL domain outside `arpa.` and `onion.`."""
    import dns.exception

    clean = str(host).strip()
    if not clean or _parse_ip_literal(clean) is not None:
        return False
    try:
        parsed = _parse_non_root_dns_name(clean)
    except dns.exception.DNSException:
        return False
    extracted = get_tld_extractor()(clean.lower())
    if not extracted.top_domain_under_public_suffix:
        return False
    return not any(parsed.is_subdomain(root) for root in _special_use_psl_roots())


def is_at_or_under(host: str, domain: str) -> bool:
    """Return True when `host` is at or under `domain` on DNS label boundaries, or equal IPs."""
    host_ip = _parse_ip_literal(host)
    domain_ip = _parse_ip_literal(domain)
    if host_ip is not None or domain_ip is not None:
        if host_ip is None:
            _parse_non_root_dns_name(host)
        if domain_ip is None:
            _parse_non_root_dns_name(domain)
        return host_ip is not None and host_ip == domain_ip
    host_name = _parse_non_root_dns_name(host)
    domain_name = _parse_non_root_dns_name(domain)
    return host_name.is_subdomain(domain_name)


def _domain_field_label(info: ValidationInfo) -> str:
    """Resolve the qualified configuration field name for domain validation error messages."""
    title = (info.config or {}).get("title")
    field_name = info.field_name or "domain"
    if title == "KubernetesConfig" and field_name == "domain":
        return "k8s.domain"
    if title == "CloudflareConfig" and field_name == "domain":
        return "cloudflare.domain"
    return field_name


def validate_configured_domain(value: str, info: ValidationInfo) -> str:
    """Validate a configured domain or IP literal entry, refusing root, leading dot, and invalid DNS labels."""
    import dns.exception

    if _parse_ip_literal(value) is not None:
        return value
    field_label = _domain_field_label(info)
    try:
        _parse_non_root_dns_name(value)
    except dns.exception.DNSException as exc:
        raise ValueError(f"Invalid domain in {field_label}: {value!r}") from exc
    return value


def blank_domain_to_none(value: Any) -> Any:
    """Normalize blank or whitespace-only scalar domain strings to `None` before validation."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


ConfiguredDomain = Annotated[str, AfterValidator(validate_configured_domain)]
OptionalConfiguredDomain = Annotated[ConfiguredDomain | None, BeforeValidator(blank_domain_to_none)]
