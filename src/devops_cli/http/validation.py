"""Network security and service URL validation helpers."""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

from devops_cli.config.defaults import DEFAULT_DNS_TIMEOUT_SECONDS
from devops_cli.lang import MESSAGES

_ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"


def _is_non_public_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not addr.is_global


# NOTE (Design Justification - AGENTS.md §7): Private/loopback network targets are blocked
# by default to prevent SSRF vulnerabilities, but explicitly permitted via
# DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true to support local model servers (e.g. Ollama).
def validate_service_url(url: str, purpose: str, *, allow: bool = False) -> None:
    """Raise ValueError for non-http/https or private-network URLs.

    Private-network targets are allowed when allow=True or
    DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true is set in the environment.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(MESSAGES.messages.invalid_url_scheme.format(purpose=purpose))

    allow = allow or os.environ.get(_ALLOW_PRIVATE_NETWORK_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    host = parsed.hostname

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_non_public_ip(literal_ip) and not allow:
            raise ValueError(MESSAGES.messages.refusing_non_public_url.format(purpose=purpose))
        return

    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(DEFAULT_DNS_TIMEOUT_SECONDS)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addrinfos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, TimeoutError, OSError):
        # Unable to resolve IP address (e.g., offline or unresolvable domain)
        return
    finally:
        socket.setdefaulttimeout(old_timeout)

    resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for addrinfo in addrinfos:
        try:
            resolved_ips.append(ipaddress.ip_address(addrinfo[4][0]))
        except ValueError:
            continue

    if resolved_ips and any(_is_non_public_ip(ip) for ip in resolved_ips) and not allow:
        raise ValueError(MESSAGES.messages.refusing_non_public_url.format(purpose=purpose))
