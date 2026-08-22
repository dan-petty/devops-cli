"""Core validation utilities for URLs, paths, Kubernetes identifiers, and versions."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich import print as rprint

from devops_cli.config.constants import (
    CONST_K8S_LABEL_RE,
    CONST_K8S_SUBDOMAIN_RE,
)
from devops_cli.config.defaults import DEFAULT_DNS_TIMEOUT_SECONDS
from devops_cli.lang import MESSAGES

_ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"
_VERSION_REGEX = re.compile(r"^v?\d+(\.\d+)*(-[a-zA-Z0-9_.]+)?$")


def is_non_public_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP address is private, loopback, link-local, or non-global."""
    return not addr.is_global


def validate_service_url(url: str, purpose: str = "service", *, allow: bool = False) -> None:
    """Raise ValueError for non-http/https or unauthorized private-network URLs.

    Private-network targets are permitted when allow=True or
    DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true is set in the environment.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(MESSAGES.messages.invalid_url_scheme.format(purpose=purpose))

    allow_private = allow or os.environ.get(_ALLOW_PRIVATE_NETWORK_ENV, "").strip().lower() in {
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
        if is_non_public_ip(literal_ip) and not allow_private:
            raise ValueError(MESSAGES.messages.refusing_non_public_url.format(purpose=purpose))
        return

    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(DEFAULT_DNS_TIMEOUT_SECONDS)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addrinfos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, TimeoutError, OSError):
        # Unable to resolve IP address (e.g. offline or unresolvable domain)
        return
    finally:
        socket.setdefaulttimeout(old_timeout)

    resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for addrinfo in addrinfos:
        try:
            resolved_ips.append(ipaddress.ip_address(addrinfo[4][0]))
        except ValueError:
            continue

    if resolved_ips and any(is_non_public_ip(ip) for ip in resolved_ips) and not allow_private:
        raise ValueError(MESSAGES.messages.refusing_non_public_url.format(purpose=purpose))


def validate_url(url: str, purpose: str = "service", *, allow_private: bool = True) -> str:
    """Validate that a URL has a valid http/https scheme and hostname.

    Returns the validated clean URL string.
    """
    clean_url = str(url).strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid {purpose} URL scheme '{parsed.scheme}': must be http or https")
    if not parsed.hostname:
        raise ValueError(f"{purpose.capitalize()} URL '{url}' missing valid hostname")
    if not allow_private:
        validate_service_url(clean_url, purpose, allow=False)
    return clean_url


def validate_path(path: Path | str, *, must_exist: bool = True) -> Path:
    """Resolve and validate that a filesystem path exists and has no traversal errors."""
    p = Path(path)
    if ".." in str(path):
        resolved = p.resolve()
    else:
        resolved = p
    if must_exist and not resolved.exists():
        rprint(f"[red]Path '{path}' does not exist.[/red]")
        raise typer.Exit(1)
    return resolved


def validate_dir(path: Path | str, *, must_exist: bool = True) -> Path:
    """Validate that a path resolves to an existing directory."""
    resolved = validate_path(path, must_exist=must_exist)
    if must_exist and not resolved.is_dir():
        rprint(f"[red]Path '{path}' is not a directory.[/red]")
        raise typer.Exit(1)
    return resolved


def validate_file(path: Path | str, *, must_exist: bool = True) -> Path:
    """Validate that a path resolves to an existing regular file."""
    resolved = validate_path(path, must_exist=must_exist)
    if must_exist and not resolved.is_file():
        rprint(f"[red]Path '{path}' is not a file.[/red]")
        raise typer.Exit(1)
    return resolved


def validate_safe_key_path(key_path: Path | str) -> Path:
    """Validate an SSH key path, preventing path traversal or blank names."""
    p = Path(key_path)
    if ".." in str(key_path) or not p.name.strip():
        raise ValueError(f"Invalid SSH key path: {key_path}")
    return p


def validate_k8s_name(value: str, label: str = "resource", *, namespace: bool = False) -> str:
    """Validate that a string conforms to Kubernetes RFC 1123 naming rules."""
    pattern = CONST_K8S_LABEL_RE if namespace else CONST_K8S_SUBDOMAIN_RE
    if not pattern.match(value):
        rprint(f"[red]Invalid {label}: {value!r}. Must be a valid RFC 1123 name.[/red]")
        raise typer.Exit(1)
    return value


def validate_version_str(version: str, tool_name: str = "tool") -> str:
    """Validate that a version string matches semantic version pattern."""
    v = version.strip()
    if not _VERSION_REGEX.match(v):
        msg = f"Invalid {tool_name} version string: {version!r}"
        raise ValueError(msg)
    return v.lstrip("v")
