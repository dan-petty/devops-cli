"""Core validation utilities for URLs, paths, Kubernetes identifiers, and versions."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import typer

from devops_cli.config.constants import (
    CONST_K8S_LABEL_RE,
    CONST_K8S_SUBDOMAIN_RE,
)
from devops_cli.config.defaults import DEFAULT_DNS_TIMEOUT_SECONDS
from devops_cli.exceptions import (
    InvalidURLError,
    InvalidVersionError,
    SSRFBlockedError,
    ValidationError,
)
from devops_cli.lang import MESSAGES
from devops_cli.output import print_error

_ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"


PathKind = Literal["any", "dir", "file", "key"]


def is_non_public_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP address is private, loopback, link-local, or non-global."""
    return not addr.is_global


def _enforce_non_private_ssrf(
    url: str,
    host: str,
    scheme: str,
    port: int | None,
    purpose: str,
) -> None:
    """Resolve hostname and raise SSRFBlockedError if destination targets non-public/private IPs."""
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if is_non_public_ip(literal_ip):
            raise SSRFBlockedError(
                url, reason=MESSAGES.messages.refusing_non_public_url.format(purpose=purpose)
            )
        return

    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(DEFAULT_DNS_TIMEOUT_SECONDS)
        effective_port = port or (443 if scheme == "https" else 80)
        addrinfos = socket.getaddrinfo(host, effective_port, type=socket.SOCK_STREAM)
    except socket.gaierror, TimeoutError, OSError:
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

    if resolved_ips and any(is_non_public_ip(ip) for ip in resolved_ips):
        raise SSRFBlockedError(
            url, reason=MESSAGES.messages.refusing_non_public_url.format(purpose=purpose)
        )


def validate_url(
    url: str,
    purpose: str = "service",
    *,
    allow_private: bool = True,
    schemes: tuple[str, ...] | set[str] = ("http", "https"),
    require_hostname: bool = True,
) -> str:
    """Validate that a URL has valid scheme, hostname, and SSRF egress security constraints.

    Args:
        url: Clean URL string to validate.
        purpose: Descriptive label of the service or endpoint.
        allow_private: Whether private-network / loopback endpoints are authorized.
        schemes: Collection of allowed protocol schemes (default: http, https).
        require_hostname: Whether a valid hostname is mandatory.

    Returns:
        The validated clean URL string.
    """
    clean_url = str(url).strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in schemes:
        schemes_str = " or ".join(sorted(schemes))
        raise InvalidURLError(
            clean_url,
            reason=f"Invalid {purpose} URL scheme '{parsed.scheme}': must be {schemes_str}",
        )
    if require_hostname and not parsed.hostname:
        raise InvalidURLError(
            clean_url, reason=f"{purpose.capitalize()} URL '{url}' missing valid hostname"
        )

    allow_env = os.environ.get(_ALLOW_PRIVATE_NETWORK_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    permitted_private = allow_private or allow_env

    if not permitted_private and parsed.hostname:
        _enforce_non_private_ssrf(clean_url, parsed.hostname, parsed.scheme, parsed.port, purpose)

    return clean_url


def validate_service_url(url: str, purpose: str = "service", *, allow: bool = False) -> None:
    """Raise ValidationError for non-http/https or unauthorized private-network URLs.

    Private-network targets are permitted when allow=True or
    DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true is set in the environment.
    """
    validate_url(url, purpose=purpose, allow_private=allow)


def validate_path(
    path: Path | str,
    *,
    must_exist: bool = True,
    kind: PathKind = "any",
    allow_traversal: bool = True,
    label: str = "Path",
) -> Path:
    """Resolve and validate a filesystem path, directory, file, or key location.

    Args:
        path: Path string or Path object to validate.
        must_exist: Whether the target path must exist on the filesystem.
        kind: Expected path type ('any', 'dir', 'file', or 'key').
        allow_traversal: Whether to allow relative directory traversal ('..').
        label: Label name for human-readable error reporting.

    Returns:
        The validated and resolved Path object.
    """
    raw_str = str(path).strip()
    if not raw_str:
        if kind == "key":
            raise ValidationError(f"Invalid SSH key path: {path}", field="key_path")
        print_error(f"{label} cannot be empty.", prefix=False)
        raise typer.Exit(1)

    if not allow_traversal and ".." in raw_str:
        if kind == "key":
            raise ValidationError(f"Invalid SSH key path: {path}", field="key_path")
        print_error(
            f"Path traversal ('..') is not permitted in {label.lower()}: '{path}'.", prefix=False
        )
        raise typer.Exit(1)

    p = Path(path)
    resolved = p.resolve() if ".." in raw_str else p

    if kind == "key":
        if ".." in raw_str or not p.name.strip():
            raise ValidationError(f"Invalid SSH key path: {path}", field="key_path")
        return p

    if must_exist and not resolved.exists():
        print_error(f"{label} '{path}' does not exist.", prefix=False)
        raise typer.Exit(1)

    if must_exist:
        if kind == "dir" and not resolved.is_dir():
            print_error(f"{label} '{path}' is not a directory.", prefix=False)
            raise typer.Exit(1)
        if kind == "file" and not resolved.is_file():
            print_error(f"{label} '{path}' is not a file.", prefix=False)
            raise typer.Exit(1)

    return resolved


def validate_dir(path: Path | str, *, must_exist: bool = True, label: str = "Path") -> Path:
    """Validate that a path resolves to an existing directory."""
    return validate_path(path, must_exist=must_exist, kind="dir", label=label)


def validate_file(path: Path | str, *, must_exist: bool = True, label: str = "Path") -> Path:
    """Validate that a path resolves to an existing regular file."""
    return validate_path(path, must_exist=must_exist, kind="file", label=label)


def validate_safe_key_path(key_path: Path | str, *, label: str = "SSH key path") -> Path:
    """Validate an SSH key path, preventing path traversal or blank names."""
    return validate_path(key_path, must_exist=False, kind="key", allow_traversal=False, label=label)


def validate_safe_directory_path(dir_path: Path | str, *, label: str = "Directory path") -> Path:
    """Validate a directory path preventing relative path traversal or blank names."""
    raw_str = str(dir_path).strip()
    if not raw_str:
        raise ValidationError(f"Invalid directory path: {dir_path}", field="dir_path")
    if ".." in raw_str:
        raise ValidationError(
            f"Path traversal ('..') is not permitted in {label.lower()}: '{dir_path}'",
            field="dir_path",
        )
    return Path(dir_path)


def validate_k8s_name(value: str, label: str = "resource", *, namespace: bool = False) -> str:
    """Validate that a string conforms to Kubernetes RFC 1123 naming rules."""
    pattern = CONST_K8S_LABEL_RE if namespace else CONST_K8S_SUBDOMAIN_RE
    if not pattern.match(value):
        print_error(f"Invalid {label}: {value!r}. Must be a valid RFC 1123 name.", prefix=False)
        raise typer.Exit(1)
    return value


def validate_version_str(version: str, tool_name: str = "tool") -> str:
    """Validate that a version string matches standard PEP 440 / SemVer pattern."""
    clean_version = version.strip()
    if not clean_version:
        raise InvalidVersionError(version, tool_name=tool_name)
    try:
        from packaging.version import InvalidVersion, Version

        Version(clean_version.lstrip("v"))
    except (InvalidVersion, ValueError) as exc:
        raise InvalidVersionError(version, tool_name=tool_name) from exc
    return clean_version.lstrip("v")


def validate_session_id(session_id: str) -> str:
    """Validate that a review session ID conforms to safe alphanumeric identifier format."""
    clean_id = session_id.strip()
    if not clean_id or not re.match(r"^[A-Za-z0-9_-]+$", clean_id) or ".." in clean_id:
        raise ValidationError(
            f"Invalid review session identifier: {session_id!r}", field="session_id"
        )
    return clean_id
