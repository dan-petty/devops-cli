"""Core validation utilities for URLs, paths, Kubernetes identifiers, and versions."""

from __future__ import annotations

import functools
import ipaddress
import logging
import re
import socket
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import dns.exception
import dns.name
import httpx2
import typer

from devops_cli.config.constants import (
    CONST_ALL_EMBEDDED_OFFSETS,
    CONST_CLOUD_METADATA_DNS_HOSTNAMES,
    CONST_CLOUD_METADATA_IPV4,
    CONST_CLOUD_METADATA_IPV6,
    CONST_IPV4_EMBEDDING_IPV6_PREFIXES,
    CONST_ISATAP_INTERFACE_IDS,
    CONST_K8S_LABEL_RE,
    CONST_K8S_SUBDOMAIN_RE,
    CONST_LOOPBACK_HOSTNAME,
    CONST_LOW32_OFFSETS,
    CONST_NAT64_PREFIXES,
    CONST_PRIVATE_NETWORKS,
    CONST_TEREDO_PREFIX,
)
from devops_cli.exceptions import (
    InvalidURLError,
    ValidationError,
)

logger = logging.getLogger(__name__)

PathKind = Literal["any", "dir", "file", "key"]


@functools.cache
def _private_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return CONST_PRIVATE_NETWORKS


@functools.cache
def _link_local_ipv4_networks() -> tuple[ipaddress.IPv4Network, ...]:
    return tuple(
        net
        for net in _private_networks()
        if isinstance(net, ipaddress.IPv4Network) and net.is_link_local
    )


@functools.cache
def _link_local_ipv6_networks() -> tuple[ipaddress.IPv6Network, ...]:
    return tuple(
        net
        for net in _private_networks()
        if isinstance(net, ipaddress.IPv6Network) and net.is_link_local
    )


@functools.cache
def _link_local_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return _link_local_ipv4_networks() + _link_local_ipv6_networks()


@functools.cache
def _non_public_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    priv = _private_networks()
    return (
        *priv,
        *(
            ipaddress.IPv6Network(
                (int(prefix.network_address) + int(block.network_address), 96 + block.prefixlen)
            )
            for prefix in map(ipaddress.IPv6Network, CONST_IPV4_EMBEDDING_IPV6_PREFIXES)
            for block in priv
            if isinstance(block, ipaddress.IPv4Network)
        ),
    )


def reset_network_caches() -> None:
    """Clear the cached private, link-local, and non-public network tuples."""
    _private_networks.cache_clear()
    _link_local_ipv4_networks.cache_clear()
    _link_local_ipv6_networks.cache_clear()
    _link_local_networks.cache_clear()
    _non_public_networks.cache_clear()


def _exhaustive_embedded_ipv4s(ip: ipaddress.IPv6Address) -> set[ipaddress.IPv4Address]:
    """Decode every standardized embedding position unconditionally."""
    packed = ip.packed
    candidates = {
        ipaddress.IPv4Address(bytes(packed[i] for i in offsets))
        for offsets in CONST_ALL_EMBEDDED_OFFSETS
    }
    if ip in CONST_TEREDO_PREFIX:
        candidates.add(ipaddress.IPv4Address(int.from_bytes(packed[12:16], "big") ^ 0xFFFFFFFF))
    return candidates


def _standard_embedded_ipv4s(ip: ipaddress.IPv6Address) -> set[ipaddress.IPv4Address]:
    """Decode well-recognized transition contexts (mapped, 6to4, NAT64, ISATAP)."""
    packed = ip.packed

    def at(offsets: tuple[int, int, int, int]) -> ipaddress.IPv4Address:
        return ipaddress.IPv4Address(bytes(packed[i] for i in offsets))

    candidates: set[ipaddress.IPv4Address] = set()
    if ip.ipv4_mapped is not None:
        candidates.add(ip.ipv4_mapped)
    if ip.sixtofour is not None:
        candidates.add(ip.sixtofour)
    for prefix, offsets_list in CONST_NAT64_PREFIXES:
        if ip in prefix:
            candidates.update(at(offsets) for offsets in offsets_list)
    if int(ip) >> 32 == 0 and not ip.is_loopback and not ip.is_unspecified:
        candidates.add(at(CONST_LOW32_OFFSETS))
    if packed[8:12] in CONST_ISATAP_INTERFACE_IDS:
        candidates.add(at(CONST_LOW32_OFFSETS))
    return candidates


def _embedded_ipv4s(ip: ipaddress.IPv6Address, *, exhaustive: bool) -> set[ipaddress.IPv4Address]:
    """Return the IPv4 addresses `ip` may route to via an IPv6 transition mechanism."""
    return _exhaustive_embedded_ipv4s(ip) if exhaustive else _standard_embedded_ipv4s(ip)


def _parse_ip(ip_str: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an IP address for blocklist comparison, dropping IPv6 zone identifiers."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.scope_id is not None:
        ip = ipaddress.IPv6Address(ip.packed)
    return ip


def is_cloud_metadata_ip(
    ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Classify if an IP address belongs to known cloud provider instance metadata endpoints."""
    parsed = _parse_ip(str(ip))
    if parsed is None:
        return False
    if isinstance(parsed, ipaddress.IPv4Address):
        return parsed in CONST_CLOUD_METADATA_IPV4
    if parsed in CONST_CLOUD_METADATA_IPV6:
        return True
    return any(
        candidate in CONST_CLOUD_METADATA_IPV4
        for candidate in _embedded_ipv4s(parsed, exhaustive=True)
    )


def is_private_ip(
    ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Classify if an IP address belongs to RFC 1918 / non-globally routable networks."""
    parsed = _parse_ip(str(ip))
    if parsed is None:
        return True
    targets: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [parsed]
    if isinstance(parsed, ipaddress.IPv6Address):
        targets.extend(_embedded_ipv4s(parsed, exhaustive=False))
    return any(target in network for target in targets for network in CONST_PRIVATE_NETWORKS)


def __getattr__(name: str) -> Any:
    if name == "_LINK_LOCAL_NETWORKS":
        return _link_local_networks()
    if name == "_LINK_LOCAL_IPV4_NETWORKS":
        return _link_local_ipv4_networks()
    if name == "_LINK_LOCAL_IPV6_NETWORKS":
        return _link_local_ipv6_networks()
    if name == "_NON_PUBLIC_NETWORKS":
        return _non_public_networks()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_CLOUD_METADATA_DNS_NAMES: frozenset[dns.name.Name] = frozenset(
    dns.name.from_text(n) for n in CONST_CLOUD_METADATA_DNS_HOSTNAMES
)


def parse_numeric_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an IPv4 or IPv6 literal, or a legacy IPv4 spelling such as `0177.0.0.1` or `127.1`.

    `ipaddress` reads a literal, an IPv6 zone ID included. The C library reads a legacy spelling
    through `getaddrinfo` with `AI_NUMERICHOST`, by the rules of the resolver, and makes no DNS
    query (#2152).
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        answers = socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)
        return ipaddress.ip_address(answers[0][4][0])
    except OSError, UnicodeError:
        return None


def _normalize_host_or_ip(raw_host: str) -> str:
    """Canonicalise a host or IP string, stripping brackets and trailing dots."""
    s = str(raw_host).strip()
    if not s:
        return ""
    try:
        return str(ipaddress.ip_address(s))
    except ValueError:
        pass
    parsed = urlsplit(f"//{s}")
    h = parsed.hostname or s
    return h.rstrip(".").lower()


def is_loopback_host(host: str) -> bool:
    """Whether a host is `localhost` or a loopback address, decided without a DNS query."""
    clean = _normalize_host_or_ip(host)
    if clean == CONST_LOOPBACK_HOSTNAME:
        return True
    addr = parse_numeric_ip(clean)
    return addr is not None and addr.is_loopback


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
        return any(net.subnet_of(ll) for ll in _link_local_ipv4_networks())
    try:
        nat64_net = ipaddress.IPv6Network("64:ff9b::a9fe:0/112")
        if net.subnet_of(nat64_net):
            return True
    except ValueError:
        pass
    return any(net.subnet_of(ll) for ll in _link_local_ipv6_networks())


def _check_numeric_metadata(host: str) -> bool | None:
    """Check if host is an IP literal or numeric representation, returning metadata status or None."""
    addr = parse_numeric_ip(host)
    if addr is not None:
        return _is_cloud_metadata_addr(addr)
    try:
        h_parsed = httpx2.URL(scheme="http", host=host).host
        parsed_addr = parse_numeric_ip(h_parsed)
        if parsed_addr is not None:
            return _is_cloud_metadata_addr(parsed_addr)
    except Exception:
        pass
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

    return is_cloud_metadata_name(clean)


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
            or any(addr.overlaps(net) for net in _non_public_networks())
        )
    return not addr.is_global or is_private_ip(str(addr))


def is_loopback_or_private_host(host_or_ip: str) -> bool:
    """Return True if host or IP string is loopback, link-local, private, or non-global space."""
    from devops_cli.core.dns_names import is_public_dns_name

    clean = _normalize_host_or_ip(host_or_ip)
    if not clean:
        return True
    if is_loopback_host(clean):
        return True
    if is_cloud_metadata_host(clean):
        return True
    try:
        addr = ipaddress.ip_address(clean)
        return is_non_public_ip(addr)
    except ValueError:
        pass
    if not is_public_dns_name(clean):
        return True

    return False


def _is_numeric_host(host: str) -> bool:
    """Check whether host is a numeric IP representation."""
    return parse_numeric_ip(host) is not None


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
        msg = f"{purpose.capitalize()} URL has invalid hostname '{host}'"
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


def _fail_cli(message: str) -> None:
    from devops_cli.output import print_error

    print_error(message, prefix=False)
    raise typer.Exit(1)


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
        _fail_cli(f"{label} cannot be empty.")

    if not allow_traversal and ".." in raw_str:
        if kind == "key":
            raise ValidationError(f"Invalid SSH key path: {path}", field="key_path")
        _fail_cli(f"Path traversal ('..') is not permitted in {label.lower()}: '{path}'.")

    p = Path(path)
    resolved = p.resolve() if ".." in raw_str else p

    if kind == "key":
        if ".." in raw_str or not p.name.strip():
            raise ValidationError(f"Invalid SSH key path: {path}", field="key_path")
        return p

    if must_exist and not resolved.exists():
        _fail_cli(f"{label} '{path}' does not exist.")

    if must_exist:
        if kind == "dir" and not resolved.is_dir():
            _fail_cli(f"{label} '{path}' is not a directory.")
        if kind == "file" and not resolved.is_file():
            _fail_cli(f"{label} '{path}' is not a file.")

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
        _fail_cli(f"Invalid {label}: {value!r}. Must be a valid RFC 1123 name.")
    return value


def validate_k8s_context_name(value: str, label: str = "context name") -> str:
    """Validate that a kubeconfig context name is safe and non-empty.

    Allows letters, digits, '.', '-', '_', ':', '/', '@', matching standard kubeconfig
    naming patterns (including AWS EKS ARNs, GKE clusters, Docker Desktop, and user accounts)
    while rejecting empty strings, control characters, and shell injection tokens.
    """
    clean_val = value.strip()
    if not clean_val or not re.fullmatch(r"^[\w\.\:\-\/@]+$", clean_val):
        _fail_cli(
            f"Invalid {label}: {value!r}. Must contain only alphanumeric, '.', '-', '_', ':', '/', or '@' characters."
        )
    return clean_val


def validate_session_id(session_id: str) -> str:
    """Validate that a review session ID conforms to safe alphanumeric identifier format."""
    clean_id = session_id.strip()
    if not clean_id or not re.fullmatch(r"^[A-Za-z0-9_-]+$", clean_id) or ".." in clean_id:
        raise ValidationError(
            f"Invalid review session identifier: {session_id!r}", field="session_id"
        )
    return clean_id
