"""Core validation utilities for URLs, paths, Kubernetes identifiers, and versions."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import logging
import re
import socket
from pathlib import Path
from typing import Literal

import dns.exception
import dns.name
import httpx2
import typer
from pydantic_ai._ssrf import (
    _PRIVATE_NETWORKS,
    is_cloud_metadata_ip,
    is_private_ip,
)

from devops_cli.config.constants import (
    CONST_CLOUD_METADATA_DNS_HOSTNAMES,
    CONST_IPV4_EMBEDDING_IPV6_PREFIXES,
    CONST_K8S_LABEL_RE,
    CONST_K8S_SUBDOMAIN_RE,
    CONST_LOOPBACK_HOSTNAME,
)
from devops_cli.config.defaults import DEFAULT_DNS_TIMEOUT_SECONDS
from devops_cli.exceptions import (
    InvalidURLError,
    SSRFBlockedError,
    ValidationError,
)
from devops_cli.lang import MESSAGES
from devops_cli.output import print_error

logger = logging.getLogger(__name__)

PathKind = Literal["any", "dir", "file", "key"]

_LINK_LOCAL_IPV4_NETWORKS: tuple[ipaddress.IPv4Network, ...] = tuple(
    net for net in _PRIVATE_NETWORKS if isinstance(net, ipaddress.IPv4Network) and net.is_link_local
)
_LINK_LOCAL_IPV6_NETWORKS: tuple[ipaddress.IPv6Network, ...] = tuple(
    net for net in _PRIVATE_NETWORKS if isinstance(net, ipaddress.IPv6Network) and net.is_link_local
)
_LINK_LOCAL_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    _LINK_LOCAL_IPV4_NETWORKS + _LINK_LOCAL_IPV6_NETWORKS
)
# Every non-public block, with each private IPv4 block's NAT64 and IPv4-compatible images, which
# hold the addresses the classifier decodes to that block. A range overlapping one is non-public.
_NON_PUBLIC_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    *_PRIVATE_NETWORKS,
    *(
        ipaddress.IPv6Network(
            (int(prefix.network_address) + int(block.network_address), 96 + block.prefixlen)
        )
        for prefix in map(ipaddress.IPv6Network, CONST_IPV4_EMBEDDING_IPV6_PREFIXES)
        for block in _PRIVATE_NETWORKS
        if isinstance(block, ipaddress.IPv4Network)
    ),
)
_CLOUD_METADATA_DNS_NAMES: frozenset[dns.name.Name] = frozenset(
    dns.name.from_text(n) for n in CONST_CLOUD_METADATA_DNS_HOSTNAMES
)


def is_loopback_host(host: str) -> bool:
    """Whether a host is `localhost` or a loopback address, decided without a DNS query."""
    clean = str(host).strip().lower().removeprefix("[").removesuffix("]").rstrip(".")
    if clean == CONST_LOOPBACK_HOSTNAME:
        return True
    try:
        return ipaddress.ip_address(clean).is_loopback
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(clean, 0, flags=socket.AI_NUMERICHOST)
        return any(ipaddress.ip_address(info[4][0]).is_loopback for info in infos)
    except socket.gaierror, ValueError, OSError:
        return False


_is_loopback_host = is_loopback_host


def _is_cloud_metadata_addr(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return addr.is_link_local or is_cloud_metadata_ip(str(addr))


def _is_cloud_metadata_net(
    net: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> bool:
    if net.is_link_local:
        return True
    if net.num_addresses == 1:
        return _is_cloud_metadata_addr(net.network_address)
    if isinstance(net, ipaddress.IPv4Network):
        return any(net.subnet_of(ll) for ll in _LINK_LOCAL_IPV4_NETWORKS)
    try:
        nat64_net = ipaddress.IPv6Network("64:ff9b::a9fe:0/112")
        if net.subnet_of(nat64_net):
            return True
    except ValueError:
        pass
    return any(net.subnet_of(ll) for ll in _LINK_LOCAL_IPV6_NETWORKS)


def _check_numeric_metadata(host: str) -> bool | None:
    """Check if host is an IP literal or numeric representation, returning metadata status or None."""
    try:
        return _is_cloud_metadata_addr(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        h_parsed = httpx2.URL(scheme="http", host=host).host
        try:
            return _is_cloud_metadata_addr(ipaddress.ip_address(h_parsed))
        except ValueError:
            pass
        infos = socket.getaddrinfo(h_parsed, 0, flags=socket.AI_NUMERICHOST)
        return any(_is_cloud_metadata_addr(ipaddress.ip_address(info[4][0])) for info in infos)
    except Exception:
        pass
    try:
        infos = socket.getaddrinfo(host, 0, flags=socket.AI_NUMERICHOST)
        return any(_is_cloud_metadata_addr(ipaddress.ip_address(info[4][0])) for info in infos)
    except socket.gaierror, ValueError, OSError:
        return None


def is_cloud_metadata_name(host: str) -> bool:
    """Whether `host` names a cloud metadata service, compared as DNS compares names.

    Case and a trailing dot do not matter. A host that is not a DNS name is not one of them.
    """
    try:
        return dns.name.from_text(host) in _CLOUD_METADATA_DNS_NAMES
    except dns.exception.DNSException:
        return False


def is_cloud_metadata_host(
    host_or_ip: (
        str
        | ipaddress.IPv4Address
        | ipaddress.IPv6Address
        | ipaddress.IPv4Network
        | ipaddress.IPv6Network
    ),
    *,
    resolve_dns: bool = True,
) -> bool:
    """Return True if host, IP, or network matches cloud metadata or link-local endpoints."""
    if isinstance(host_or_ip, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return _is_cloud_metadata_addr(host_or_ip)
    if isinstance(host_or_ip, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        return _is_cloud_metadata_net(host_or_ip)

    clean = str(host_or_ip).strip().removeprefix("[").removesuffix("]")
    clean_nodot = clean.rstrip(".")
    if not clean_nodot:
        return False

    if "/" in clean_nodot:
        try:
            return _is_cloud_metadata_net(ipaddress.ip_network(clean_nodot, strict=False))
        except ValueError:
            pass

    numeric_res = _check_numeric_metadata(clean_nodot)
    if numeric_res is not None:
        return numeric_res

    try:
        dns.name.from_text(clean)
    except dns.exception.DNSException:
        return True

    if is_cloud_metadata_name(clean):
        return True

    if not resolve_dns:
        return False

    resolved_ips = _resolve_host_ips(clean_nodot)
    return any(_is_cloud_metadata_addr(ip) for ip in resolved_ips)


def is_non_public_ip(
    addr: (
        ipaddress.IPv4Address
        | ipaddress.IPv6Address
        | ipaddress.IPv4Network
        | ipaddress.IPv6Network
    ),
) -> bool:
    """Return True if the IP address or network is private, loopback, link-local, or non-global.

    A range is non-public when it is not global, when either end is non-public, or when it
    overlaps one of pydantic-ai's non-public blocks or a private IPv4 block's NAT64 or
    IPv4-compatible image, so `8.0.0.0/5` (which holds 10.0.0.0/8) and `64::/16` (which holds
    `64:ff9b::/96`) are refused. Space only Python's `is_global` treats as non-global, such as
    `3fff::/20`, is not looked for inside a wider range. An IPv4 range never overlaps an IPv6
    block. An ISATAP-style interface id, which the classifier also reads as an IPv4 address,
    occurs in every /64, so it is not taken to hide one inside a range: `2606:4700::/48` stays
    public.
    """
    if isinstance(addr, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        return (
            not addr.is_global
            or is_non_public_ip(addr.network_address)
            or is_non_public_ip(addr.broadcast_address)
            or any(addr.overlaps(net) for net in _NON_PUBLIC_NETWORKS)
        )
    return not addr.is_global or is_private_ip(str(addr))


def _resolve_host_ips(
    host: str,
    port: int | None = None,
    timeout: float = DEFAULT_DNS_TIMEOUT_SECONDS,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve hostname to IP addresses with bounded timeout without mutating global socket state."""
    effective_port = port or 0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                socket.getaddrinfo, host, effective_port, type=socket.SOCK_STREAM
            )
            addrinfos = future.result(timeout=timeout)
    except (
        socket.gaierror,
        socket.herror,
        TimeoutError,
        OSError,
        concurrent.futures.TimeoutError,
    ) as exc:
        logger.debug("DNS resolution failed for %s: %s", host, exc)
        return []

    resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for a in addrinfos:
        try:
            resolved.append(ipaddress.ip_address(a[4][0]))
        except ValueError, IndexError:
            continue
    return resolved


def is_loopback_or_private_host(host_or_ip: str, *, resolve_dns: bool = True) -> bool:
    """Return True if host or IP string resolves to loopback, link-local, private, or non-global space."""
    clean = str(host_or_ip).strip().lower().removeprefix("[").removesuffix("]").rstrip(".")
    if not clean:
        return True
    if is_loopback_host(clean) or clean.endswith(".local"):
        return True
    if is_cloud_metadata_host(clean, resolve_dns=False):
        return True
    try:
        addr = ipaddress.ip_address(clean)
        return is_non_public_ip(addr)
    except ValueError:
        pass

    if not resolve_dns:
        return False

    resolved = _resolve_host_ips(clean)
    return bool(
        resolved
        and any(
            is_non_public_ip(ip) or is_cloud_metadata_host(ip, resolve_dns=False) for ip in resolved
        )
    )


def _is_numeric_host(host: str) -> bool:
    """Check whether host is a numeric IP representation."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, 0, flags=socket.AI_NUMERICHOST)
        return bool(infos)
    except socket.gaierror, ValueError, OSError:
        return False


def _validate_dns_name_syntax(
    host: str,
    url: str,
    purpose: str,
    error_cls: type[Exception],
) -> None:
    """Validate host DNS name syntax, raising on invalid RFC label structures."""
    clean = host.rstrip(".")
    if _is_numeric_host(clean):
        return
    try:
        dns.name.from_text(host)
    except dns.exception.DNSException as exc:
        msg = f"{purpose.capitalize()} URL '{url}' has invalid hostname '{host}'"
        if issubclass(error_cls, InvalidURLError):
            raise error_cls(url, reason=msg) from exc
        raise error_cls(msg) from exc


def _parse_and_validate_scheme(
    url: str,
    purpose: str,
    schemes: tuple[str, ...] | set[str],
    error_cls: type[Exception],
) -> tuple[str, str]:
    """Parse URL and validate its scheme and host presence."""
    clean_url = str(url).strip()
    try:
        parsed = httpx2.URL(clean_url)
    except Exception as exc:
        raise error_cls(f"Invalid {purpose} URL: {exc}") from exc

    if parsed.scheme not in schemes:
        schemes_str = " or ".join(sorted(schemes))
        raise error_cls(f"Invalid {purpose} URL scheme '{parsed.scheme}': must be {schemes_str}")
    host = parsed.host
    if not host:
        raise error_cls(f"Invalid {purpose} URL: missing valid hostname in '{url}'")
    return clean_url, host


def _enforce_ip_egress_safety(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    host: str,
    purpose: str,
    allow_private: bool,
    error_cls: type[Exception],
) -> None:
    """Enforce cloud metadata and private IP egress restrictions for an IP address."""
    if is_cloud_metadata_host(ip, resolve_dns=False):
        raise error_cls(f"Access to link-local or cloud metadata services ({host}) is prohibited.")
    if not allow_private and is_non_public_ip(ip):
        raise error_cls(f"{purpose.capitalize()} URL resolves to private or reserved IP: {host}")


def _validate_hostname_egress(
    host: str,
    purpose: str,
    allow_private: bool,
    error_cls: type[Exception],
) -> None:
    """Resolve and enforce egress safety for a non-IP hostname."""
    if is_loopback_host(host) or host.endswith(".local"):
        if not allow_private:
            raise error_cls(
                f"{purpose.capitalize()} URL resolves to private or reserved IP: {host}"
            )
        return

    resolved_ips = _resolve_host_ips(host)
    if not resolved_ips:
        if not allow_private:
            raise error_cls(f"DNS resolution failed or timed out for {purpose} URL: {host}")
        return

    for ip in resolved_ips:
        _enforce_ip_egress_safety(ip, host, purpose, allow_private, error_cls)


def validate_url_egress(
    url: str,
    purpose: str = "service",
    *,
    allow_private: bool = False,
    schemes: tuple[str, ...] | set[str] = ("http", "https"),
    error_cls: type[Exception] = SSRFBlockedError,
) -> str:
    """Validate URL egress safety against SSRF and non-permitted protocols.

    Args:
        url: Clean URL to validate.
        purpose: Human-readable service label for error reporting.
        allow_private: Whether private/loopback addresses are allowed.
        schemes: Allowed protocol schemes.
        error_cls: Custom exception class to raise on violation (defaults to SSRFBlockedError).

    Returns:
        The validated clean URL string.
    """
    clean_url, host = _parse_and_validate_scheme(url, purpose, schemes, error_cls)
    _validate_dns_name_syntax(host, clean_url, purpose, error_cls)

    if is_cloud_metadata_host(host, resolve_dns=False):
        raise error_cls(f"Access to link-local or cloud metadata services ({host}) is prohibited.")

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None

    if addr is not None:
        _enforce_ip_egress_safety(addr, host, purpose, allow_private, error_cls)
    else:
        _validate_hostname_egress(host, purpose, allow_private, error_cls)

    return clean_url


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
        if is_cloud_metadata_host(literal_ip, resolve_dns=False):
            raise SSRFBlockedError(
                url,
                reason=f"Access to link-local or cloud metadata services ({host}) is prohibited.",
            )
        if is_non_public_ip(literal_ip):
            raise SSRFBlockedError(
                url, reason=MESSAGES.messages.refusing_non_public_url.format(purpose=purpose)
            )
        return

    effective_port = port or (443 if scheme == "https" else 80)
    resolved_ips = _resolve_host_ips(host, port=effective_port)
    if not resolved_ips:
        raise SSRFBlockedError(
            url,
            reason=f"DNS resolution failed or timed out for {purpose} URL",
        )

    for ip in resolved_ips:
        if is_cloud_metadata_host(ip, resolve_dns=False):
            raise SSRFBlockedError(
                url,
                reason=f"Access to link-local or cloud metadata services ({host}) is prohibited.",
            )
        if is_non_public_ip(ip):
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
    try:
        parsed = httpx2.URL(clean_url)
    except Exception as exc:
        raise InvalidURLError(clean_url, reason=f"Invalid {purpose} URL: {exc}") from exc

    if parsed.scheme not in schemes:
        schemes_str = " or ".join(sorted(schemes))
        raise InvalidURLError(
            clean_url,
            reason=f"Invalid {purpose} URL scheme '{parsed.scheme}': must be {schemes_str}",
        )
    if require_hostname and not parsed.host:
        raise InvalidURLError(
            clean_url, reason=f"{purpose.capitalize()} URL '{url}' missing valid hostname"
        )

    if parsed.host:
        host = parsed.host
        _validate_dns_name_syntax(host, clean_url, purpose, InvalidURLError)

        if is_cloud_metadata_host(host, resolve_dns=False):
            raise SSRFBlockedError(
                clean_url,
                reason=f"Access to link-local or cloud metadata services ({host}) is prohibited.",
            )
        if not allow_private:
            _enforce_non_private_ssrf(clean_url, host, parsed.scheme, parsed.port, purpose)

    return clean_url


def validate_service_url(url: str, purpose: str = "service", *, allow: bool = False) -> None:
    """Raise ValidationError for non-http/https or unauthorized private-network URLs.

    Private-network targets are permitted when `allow` is True. A caller whose URL comes from the
    user's configuration passes `ai.allow_private_network`, which DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK
    sets; nothing here reads the environment.
    """
    validate_url(url, purpose=purpose, allow_private=allow)


def validate_configured_service_url(
    url: str, purpose: str = "service", *, allow_private: bool = False
) -> None:
    """Validate a service URL taken from the user's own configuration.

    Loopback (`localhost`, 127.0.0.0/8, ::1) is the workstation itself, so a configured local
    service, such as the example config's Qdrant and Ollama, is reached without
    `allow_private_network`. Every other non-public host, private ranges among them, is refused
    as `validate_service_url` refuses it unless `allow_private` permits it, and cloud metadata
    hosts always are. A client built by `devops_cli.http.client` makes the same decision at the
    connect, for the address it dials, at `devops_cli.http.egress.configured_level`.
    """
    clean_url = str(url).strip()
    try:
        host = httpx2.URL(clean_url).host
    except Exception:
        host = ""
    validate_url(url, purpose=purpose, allow_private=allow_private or is_loopback_host(host))


def validate_path(  # noqa: C901
    path: Path | str,
    *,
    must_exist: bool = True,
    kind: PathKind = "any",
    allow_traversal: bool = False,
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


def is_valid_k8s_name(value: str, *, namespace: bool = False) -> bool:
    """Check whether a string conforms to Kubernetes RFC 1123 label or DNS subdomain rules."""
    if not value or value.startswith("-"):
        return False
    pattern = CONST_K8S_LABEL_RE if namespace else CONST_K8S_SUBDOMAIN_RE
    return bool(pattern.fullmatch(value))


def validate_k8s_identifier(value: str, label: str = "resource", *, namespace: bool = False) -> str:
    """Validate Kubernetes resource identifier, raising ValidationError on failure."""
    if not is_valid_k8s_name(value, namespace=namespace):
        rule = (
            "RFC 1123 label (up to 63 chars)"
            if namespace
            else "RFC 1123 subdomain (up to 253 chars)"
        )
        raise ValidationError(
            f"Invalid Kubernetes {label} identifier '{value}'. Must match {rule}."
        )
    return value


def validate_k8s_name(value: str, label: str = "resource", *, namespace: bool = False) -> str:
    """Validate that a string conforms to Kubernetes RFC 1123 naming rules."""
    if not is_valid_k8s_name(value, namespace=namespace):
        print_error(f"Invalid {label}: {value!r}. Must be a valid RFC 1123 name.", prefix=False)
        raise typer.Exit(1)
    return value


def validate_k8s_context_name(value: str, label: str = "context name") -> str:
    """Validate that a kubeconfig context name is safe and non-empty.

    Allows letters, digits, '.', '-', '_', ':', '/', '@', matching standard kubeconfig
    naming patterns (including AWS EKS ARNs, GKE clusters, Docker Desktop, and user accounts)
    while rejecting empty strings, control characters, and shell injection tokens.
    """
    clean_val = value.strip()
    if not clean_val or not re.match(r"^[\w\.\:\-\/@]+$", clean_val):
        print_error(
            f"Invalid {label}: {value!r}. Must contain only alphanumeric, '.', '-', '_', ':', '/', or '@' characters.",
            prefix=False,
        )
        raise typer.Exit(1)
    return clean_val


def validate_session_id(session_id: str) -> str:
    """Validate that a review session ID conforms to safe alphanumeric identifier format."""
    clean_id = session_id.strip()
    if not clean_id or not re.match(r"^[A-Za-z0-9_-]+$", clean_id) or ".." in clean_id:
        raise ValidationError(
            f"Invalid review session identifier: {session_id!r}", field="session_id"
        )
    return clean_id
