"""Network security and service URL validation helpers."""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

_ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"


def _is_non_public_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not addr.is_global


def validate_service_url(url: str, purpose: str, *, allow: bool = False) -> None:
    """Raise ValueError for non-http/https or private-network URLs.

    Private-network targets are allowed when allow=True or
    DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true is set in the environment.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Invalid {purpose} URL: must use http:// or https:// with a hostname.")

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
            raise ValueError(
                f"Refusing non-public {purpose} URL. "
                f"Set {_ALLOW_PRIVATE_NETWORK_ENV}=true to override."
            )
        return

    try:
        addrinfos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return

    resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for addrinfo in addrinfos:
        try:
            resolved_ips.append(ipaddress.ip_address(addrinfo[4][0]))
        except ValueError:
            continue

    if resolved_ips and all(_is_non_public_ip(ip) for ip in resolved_ips) and not allow:
        raise ValueError(
            f"Refusing non-public {purpose} URL. Set {_ALLOW_PRIVATE_NETWORK_ENV}=true to override."
        )
