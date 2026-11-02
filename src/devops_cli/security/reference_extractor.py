"""Extractors for network references (IPs and URLs) in source and configuration text."""

from __future__ import annotations

import ast
import functools
import io
import ipaddress
import json
import logging
import re
import textwrap
import tokenize
import tomllib
import urllib.parse
import warnings
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_DEFAULT_LINE_NUMBER,
    CONST_DOCUMENTATION_IP_NETWORKS,
    CONST_EXCLUDED_PUBLIC_REGISTRIES,
    CONST_NON_GLOBAL_NETWORKS_STDLIB_READS_GLOBAL,
    CONST_PROSE_TRAILING_PUNCTUATION,
    CONST_RFC2606_RESERVED_DOMAINS,
    CONST_RFC2606_RESERVED_TLDS,
    CONST_SPECIAL_USE_TLDS,
)
from devops_cli.config.defaults import DEFAULT_FORMAT_TYPE
from devops_cli.core.dns_names import get_tld_extractor
from devops_cli.core.validation import parse_numeric_ip
from devops_cli.http.urls import extract_domain_target
from devops_cli.models.vulnerability import NetworkReference, NetworkTargetClass

logger = logging.getLogger(__name__)

# Standard RFC 2606 and RFC 6761 reserved domain suffixes and TLDs
_RFC2606_RESERVED_TLDS = CONST_RFC2606_RESERVED_TLDS
_RFC2606_RESERVED_DOMAINS = CONST_RFC2606_RESERVED_DOMAINS
_SPECIAL_USE_TLDS = CONST_SPECIAL_USE_TLDS
_RESERVED_DOMAINS = _RFC2606_RESERVED_TLDS | _RFC2606_RESERVED_DOMAINS
_EXCLUDED_PUBLIC_REGISTRIES = CONST_EXCLUDED_PUBLIC_REGISTRIES

_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
_IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

_NANPA_EXAMPLE_PHONE_REGEX = re.compile(
    r"""^(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?555[-.\s]?01\d{2}$"""
)
_OFCOM_EXAMPLE_PHONE_REGEX = re.compile(
    r"""^(?:\+?44[-.\s]?|0)(?:1632[-.\s]?(?:960\d{3}|496\d{3,4}|\d{4,6})|20[-.\s]?7946[-.\s]?0\d{3}|7700[-.\s]?900\d{3}|8081[-.\s]?570\d{3}|909[-.\s]?879[-.\s]?0\d{3}|(?:\d{2,4}[-.\s]?)?496[-.\s]?(?:0\d{3}|\d{4}|\d{3}))(?:\s*#.*)?$"""
)


__all__ = [
    "classify_network_target",
    "deduplicate_network_references",
    "extract_network_references",
    "is_example_ip",
    "is_example_or_invalid_domain",
    "is_example_or_invalid_network_target",
    "is_example_phone_number",
    "is_local_or_reserved_domain",
    "is_lockfile_or_ignore_file",
    "is_private_or_local_ip",
    "is_public_ip",
    "is_trusted_registry_host",
    "network_target_address",
    "sort_network_references",
]


def _strip_prose_punctuation(target: str) -> str:
    """A target without surrounding whitespace and the punctuation prose leaves after it."""
    return target.strip().rstrip(CONST_PROSE_TRAILING_PUNCTUATION)


def _unmapped(ip: _IPAddress) -> _IPAddress:
    """The IPv4 address an IPv4-mapped IPv6 address (`::ffff:192.0.2.1`) carries, else `ip`."""
    mapped = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) else None
    return ip if mapped is None else mapped


@functools.lru_cache(maxsize=4096)
def network_target_address(target: str) -> _IPAddress | None:
    """The address a network target names, as a resolver dials it, or None when it names none.

    A URL or `host:port` names its host. The punctuation prose leaves after a target is not part
    of it, and a trailing dot ends a fully qualified host, never an address. The legacy numeric
    spellings `inet_aton` reads (`2130706433`, `127.1`, `0x7f.0.0.1`) name the address a resolver
    dials, and an IPv4-mapped IPv6 address names the IPv4 address it carries. A target holding
    whitespace names no address, though `inet_aton` reads one before trailing whitespace.
    No DNS query is made: the C library reads a legacy spelling with `AI_NUMERICHOST`.
    """
    clean = _strip_prose_punctuation(target)
    if not clean or any(char.isspace() for char in clean):
        return None
    ip = parse_numeric_ip(clean)
    if ip is None:
        ip = parse_numeric_ip((extract_domain_target(clean) or "").rstrip("."))
    return None if ip is None else _unmapped(ip)


def _parse_ip(ip_or_str: str | _IPAddress) -> _IPAddress | None:
    """The address a string names (`network_target_address`), or an address as itself."""
    if isinstance(ip_or_str, str):
        return network_target_address(ip_or_str)
    return _unmapped(ip_or_str)


def _in_any(ip: _IPAddress, networks: tuple[_IPNetwork, ...]) -> bool:
    """Whether an address lies in one of the networks; an address is never in the other family's."""
    return any(ip in net for net in networks)


def _is_documentation_address(ip: _IPAddress) -> bool:
    """Whether an address is set aside for documentation or benchmarking."""
    return _in_any(ip, CONST_DOCUMENTATION_IP_NETWORKS)


def _is_public_address(ip: _IPAddress) -> bool:
    """Whether an address is globally reachable: global, and neither reserved nor multicast.

    `is_global` alone admits reserved space such as `64:ff9b::c000:201`, the NAT64 form of
    192.0.2.1, and multicast such as 224.0.0.1, so both are excluded, as is the space the stdlib
    still reads as global against IANA (`CONST_NON_GLOBAL_NETWORKS_STDLIB_READS_GLOBAL`: 6to4
    relay anycast and deprecated site-local fec0::/10).
    """
    return (
        ip.is_global
        and not ip.is_reserved
        and not ip.is_multicast
        and not _in_any(ip, CONST_NON_GLOBAL_NETWORKS_STDLIB_READS_GLOBAL)
        and not _is_documentation_address(ip)
    )


def _address_class(ip: _IPAddress) -> NetworkTargetClass:
    """The one class an address is in: unspecified, documentation, public or local."""
    if ip.is_unspecified:
        return NetworkTargetClass.UNSPECIFIED_ADDRESS
    if _is_documentation_address(ip):
        return NetworkTargetClass.DOCUMENTATION_ADDRESS
    if _is_public_address(ip):
        return NetworkTargetClass.PUBLIC_ADDRESS
    return NetworkTargetClass.LOCAL_ADDRESS


def _is_address_in_class(ip_or_str: str | _IPAddress, address_class: NetworkTargetClass) -> bool:
    """Whether a target names an address (`network_target_address`) in `address_class`."""
    ip = _parse_ip(ip_or_str)
    return ip is not None and _address_class(ip) is address_class


@functools.lru_cache(maxsize=4096)
def is_example_ip(ip_or_str: str | _IPAddress) -> bool:
    """Whether an address is a documented example: documentation or benchmarking space.

    That is RFC 5737, RFC 3849 and RFC 9637 documentation space, and RFC 2544 and RFC 5180
    benchmarking space (`CONST_DOCUMENTATION_IP_NETWORKS`).
    """
    return _is_address_in_class(ip_or_str, NetworkTargetClass.DOCUMENTATION_ADDRESS)


@functools.lru_cache(maxsize=4096)
def is_example_or_invalid_domain(target: str) -> bool:
    """Check if domain is an RFC 2606 reserved TLD, example domain, or invalid namespace."""
    clean = _strip_prose_punctuation(target).lower()
    if not clean or clean.startswith("-") or clean.endswith("-") or "_" in clean:
        return False
    if clean == "localhost" or clean.endswith(".localhost"):
        return False
    if clean in _RFC2606_RESERVED_DOMAINS:
        return True
    if any(clean.endswith("." + d) for d in _RFC2606_RESERVED_DOMAINS):
        return True
    if clean in _RFC2606_RESERVED_TLDS:
        return True
    if any(clean.endswith("." + tld) for tld in _RFC2606_RESERVED_TLDS):
        return True
    ext = get_tld_extractor()(clean)
    if ext.suffix and ext.suffix.lower() in _RFC2606_RESERVED_TLDS:
        return True
    return False


@functools.lru_cache(maxsize=2048)
def is_example_phone_number(phone_str: str) -> bool:
    """Check if string matches ATIS-0300115 (NANPA 555-01xx) or UK Ofcom drama phone numbers."""
    clean = phone_str.strip()
    if not clean:
        return False
    return bool(_NANPA_EXAMPLE_PHONE_REGEX.match(clean) or _OFCOM_EXAMPLE_PHONE_REGEX.match(clean))


@functools.lru_cache(maxsize=4096)
def _is_unspecified_ip_host(target: str) -> bool:
    """Check if an IP address or host is an unspecified IP (e.g. 0.0.0.0 or ::)."""
    try:
        return ipaddress.ip_address(target.strip()).is_unspecified
    except ValueError:
        return False


# The classes of a documented example or an unspecified address, which
# `is_example_or_invalid_network_target` excludes.
_EXAMPLE_TARGET_CLASSES: frozenset[NetworkTargetClass] = frozenset(
    {
        NetworkTargetClass.DOCUMENTATION_ADDRESS,
        NetworkTargetClass.UNSPECIFIED_ADDRESS,
        NetworkTargetClass.EXAMPLE_PHONE_NUMBER,
        NetworkTargetClass.EXAMPLE_DOMAIN,
    }
)


@functools.lru_cache(maxsize=4096)
def classify_network_target(target: str) -> NetworkTargetClass:
    """What a network target (URL, `host:port`, address, domain or phone number) names.

    It is read without the punctuation prose leaves after it. A target that names an address
    (`network_target_address`) is in that address's class; a URL or `host:port` is otherwise
    in its host's. No DNS query is made.
    """
    clean = _strip_prose_punctuation(target)
    if is_example_phone_number(clean):
        return NetworkTargetClass.EXAMPLE_PHONE_NUMBER
    ip = network_target_address(clean)
    if ip is not None:
        return _address_class(ip)
    host = extract_domain_target(clean) or clean
    if is_example_or_invalid_domain(host):
        return NetworkTargetClass.EXAMPLE_DOMAIN
    if is_local_or_reserved_domain(host):
        return NetworkTargetClass.LOCAL_DOMAIN
    return NetworkTargetClass.DOMAIN


def is_example_or_invalid_network_target(target: str) -> bool:
    """Whether a network target is a documented example or an unspecified address.

    That is an example domain, a documentation or benchmarking address, a fictional phone
    number, or an unspecified address (`classify_network_target`).
    """
    return classify_network_target(target) in _EXAMPLE_TARGET_CLASSES


@functools.lru_cache(maxsize=4096)
def is_public_ip(ip_str: str) -> bool:
    """Whether a target names a globally reachable address, the only kind sent to Shodan.

    Every specified address is in exactly one of three classes: documented example
    (`is_example_ip`), public, or local (`is_private_or_local_ip`). A target is read as
    `network_target_address` reads it.
    """
    return _is_address_in_class(ip_str, NetworkTargetClass.PUBLIC_ADDRESS)


@functools.lru_cache(maxsize=4096)
def is_private_or_local_ip(ip_str: str) -> bool:
    """Whether a target names a local address: specified, and neither public nor an example.

    That holds private, loopback, link-local, site-local, shared, reserved and multicast space.
    An unspecified address (`0.0.0.0`, `::`) is in no class.
    """
    return _is_address_in_class(ip_str, NetworkTargetClass.LOCAL_ADDRESS)


@functools.lru_cache(maxsize=4096)
def is_local_or_reserved_domain(target: str) -> bool:
    """Check if domain or hostname is an RFC reserved, internal, or local network hostname."""
    clean = _strip_prose_punctuation(target).lower()
    if not clean or clean.startswith("-") or clean.endswith("-") or "_" in clean:
        return False
    if clean == "localhost":
        return True
    if is_example_or_invalid_domain(clean):
        return False
    if clean in _SPECIAL_USE_TLDS:
        return False
    if any(clean.endswith("." + d) for d in _SPECIAL_USE_TLDS):
        return True
    ext = get_tld_extractor()(clean)
    if ext.suffix and ext.suffix.lower() in _SPECIAL_USE_TLDS:
        return True
    return False


def _parse_python_token_string(tok_string: str) -> str | None:
    """Safely parse literal value or clean fallback from a Python string token."""
    try:
        val = ast.literal_eval(tok_string)
        if isinstance(val, str):
            return val
    except ValueError, SyntaxError:
        pass
    clean_str = tok_string.strip("\"'")
    return clean_str if clean_str else None


def _extract_python_literals_and_comments(source: str) -> list[tuple[str, int]]:
    """Extract string constants and comments from Python source code with line numbers."""
    literals: list[tuple[str, int]] = []
    source = textwrap.dedent(source)
    parsed_ast = False

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
        parsed_ast = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                line = getattr(node, "lineno", 1)
                literals.append((node.value, line))
    except SyntaxError, IndentationError:
        pass

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                comment_text = tok.string.lstrip("#").strip()
                if comment_text:
                    literals.append((comment_text, tok.start[0]))
            elif tok.type == tokenize.STRING and not parsed_ast:
                parsed_str = _parse_python_token_string(tok.string)
                if parsed_str:
                    literals.append((parsed_str, tok.start[0]))
    except tokenize.TokenError, IndentationError:
        pass

    return literals


_HCL_STRING_OR_COMMENT_REGEX = re.compile(
    r"""(?:"(?:\\.|[^"\\])*"|#[^\r\n]*|//[^\r\n]*|/\*[\s\S]*?\*/)"""
)


def _extract_hcl_literals_and_comments(content: str) -> list[tuple[str, int]]:
    """Extract string constants and comments from Terraform/HCL source code."""
    literals: list[tuple[str, int]] = []
    for line_idx, line in enumerate(content.splitlines(), 1):
        for match in _HCL_STRING_OR_COMMENT_REGEX.finditer(line):
            text = match.group(0).strip("\"'").strip()
            if text:
                literals.append((text, line_idx))
    return literals


def _clean_yaml_scalar(text: str) -> str:
    """Strip template expressions from YAML command blocks."""
    return re.sub(r"\$\{\{[\s\S]*?\}\}", "", text)


def _collect_scalar_strings(
    data: Any,
    out: list[tuple[str, int]],
    default_line: int = CONST_DEFAULT_LINE_NUMBER,
    is_yaml: bool = False,
) -> None:
    """Recursively collect string values from parsed structured data."""
    if isinstance(data, str):
        cleaned = _clean_yaml_scalar(data) if is_yaml else data
        out.append((cleaned, default_line))
    elif isinstance(data, dict):
        for val in data.values():
            _collect_scalar_strings(val, out, default_line, is_yaml=is_yaml)
    elif isinstance(data, list | tuple | set):
        for item in data:
            _collect_scalar_strings(item, out, default_line, is_yaml=is_yaml)


def _extract_structured_strings(
    content: str, format_type: str = DEFAULT_FORMAT_TYPE
) -> list[tuple[str, int]]:
    """Extract all string scalar values from structured JSON, TOML, or YAML content."""
    strings: list[tuple[str, int]] = []
    try:
        fmt = format_type.lower()
        if fmt == "json":
            data = json.loads(content)
            is_yaml = False
        elif fmt == "toml":
            data = tomllib.loads(content)
            is_yaml = False
        elif fmt in ("yaml", "yml"):
            data = yaml.safe_load(content)
            is_yaml = True
        else:
            return strings
        _collect_scalar_strings(data, strings, is_yaml=is_yaml)
    except (
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        yaml.YAMLError,
        ValueError,
        TypeError,
    ) as exc:
        logger.debug("Failed to parse %s structured content: %s", fmt, exc)
    return strings


def _extract_json_strings(content: str) -> list[tuple[str, int]]:
    """Extract all string scalar values from valid JSON content."""
    return _extract_structured_strings(content, format_type="json")


def _extract_toml_strings(content: str) -> list[tuple[str, int]]:
    """Extract all string scalar values from valid TOML content."""
    return _extract_structured_strings(content, format_type="toml")


def _extract_yaml_strings(content: str) -> list[tuple[str, int]]:
    """Extract all string scalar values from YAML content."""
    return _extract_structured_strings(content, format_type="yaml")


def _get_target_segments(content: str, source_file: str) -> list[tuple[str, int]]:
    """Determine text segments to analyze based on source file syntax."""
    suffix = Path(source_file).suffix.lower() if source_file else ""

    if suffix == ".py":
        return _extract_python_literals_and_comments(content)

    if suffix in (".tf", ".tfvars", ".hcl"):
        return _extract_hcl_literals_and_comments(content)

    if suffix == ".json":
        return _extract_structured_strings(content, format_type="json")

    if suffix == ".toml":
        return _extract_structured_strings(content, format_type="toml")

    if suffix in (".yaml", ".yml"):
        return _extract_structured_strings(content, format_type="yaml")

    # Fallback to line-by-line scanning for markdown, text, or unparseable files
    return [(line, line_idx) for line_idx, line in enumerate(content.splitlines(), 1)]


@functools.lru_cache(maxsize=1024)
def is_lockfile_or_ignore_file(source_file: str) -> bool:
    """Check if file is a package manager lockfile or ignore pattern file."""
    if not source_file:
        return False
    src_name = Path(source_file).name.lower()
    if src_name.endswith("ignore"):
        return True
    if src_name.endswith((".lock", ".lockb", ".lock.json", ".lock.yaml", ".lock.yml", ".lock.hcl")):
        return True
    return src_name in (
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "cargo.lock",
        "poetry.lock",
        "uv.lock",
        "gemfile.lock",
        "composer.lock",
        "pipfile.lock",
        "packages.lock.json",
        "flake.lock",
        "go.sum",
        "shrinkwrap.json",
    )


@functools.lru_cache(maxsize=4096)
def is_trusted_registry_host(host: str) -> bool:
    """Check if a host is an excluded public package repository or distribution registry."""
    h = host.strip().lower()
    if not h:
        return False
    return h in _EXCLUDED_PUBLIC_REGISTRIES or any(
        h.endswith("." + exc) for exc in _EXCLUDED_PUBLIC_REGISTRIES
    )


def reset_reference_extractor_caches() -> None:
    """Clear all LRU caches on reference-extraction classifiers."""
    network_target_address.cache_clear()
    is_example_ip.cache_clear()
    is_example_or_invalid_domain.cache_clear()
    is_example_phone_number.cache_clear()
    _is_unspecified_ip_host.cache_clear()
    classify_network_target.cache_clear()
    is_public_ip.cache_clear()
    is_private_or_local_ip.cache_clear()
    is_local_or_reserved_domain.cache_clear()
    is_lockfile_or_ignore_file.cache_clear()
    is_trusted_registry_host.cache_clear()


def _is_url_local_host(host: str, is_example: bool, exclude_examples: bool) -> bool:
    """Determine whether a URL's host represents a local, private, or loopback endpoint."""
    if host == "localhost" or "." not in host:
        return True
    if is_private_or_local_ip(host) or is_local_or_reserved_domain(host):
        return True
    return bool(is_example and not exclude_examples)


def _is_valid_url_target(clean_token: str) -> tuple[urllib.parse.SplitResult, str] | None:
    """Validate URL syntax and extract parsed result and lowercased hostname."""
    if "\\" in clean_token or ".*" in clean_token:
        return None
    try:
        parsed = urllib.parse.urlsplit(clean_token)
        if not (parsed.scheme and parsed.netloc and parsed.hostname):
            return None
        host = parsed.hostname.lower()
        if _is_unspecified_ip_host(host) or is_trusted_registry_host(host):
            return None
        return parsed, host
    except ValueError:
        return None


def _extract_url_reference(
    clean_token: str,
    source_file: str,
    line_idx: int,
    include_local: bool,
    exclude_examples: bool = True,
) -> NetworkReference | None:
    """Parse and validate URL network reference."""
    valid_target = _is_valid_url_target(clean_token)
    if not valid_target:
        return None
    _parsed, host = valid_target
    is_example = is_example_or_invalid_domain(host) or is_example_ip(host)
    if is_example and exclude_examples:
        return None
    is_local_host = _is_url_local_host(host, is_example, exclude_examples)
    if is_local_host and not include_local:
        return None
    status = (
        "✓ Safe (Documented Example)"
        if is_example
        else ("✓ Safe (Local)" if is_local_host else "✓ Safe")
    )
    return NetworkReference(
        target=clean_token,
        reference_type="url",
        source_file=source_file,
        line_number=line_idx,
        is_local=is_local_host,
        is_example=is_example,
        scope="local" if is_local_host else "external",
        security_status=status,
    )


def _extract_ip_reference(
    clean_token: str,
    source_file: str,
    line_idx: int,
    include_local: bool,
    exclude_examples: bool = True,
) -> NetworkReference | None:
    """Parse and validate IP address network reference."""
    try:
        ip = ipaddress.ip_address(clean_token)
        ip_str = str(ip)
        if ip.is_unspecified:
            return None
        is_example = is_example_ip(ip)
        if is_example and exclude_examples:
            return None
        if is_public_ip(clean_token):
            return NetworkReference(
                target=ip_str,
                reference_type="ip",
                source_file=source_file,
                line_number=line_idx,
                is_local=False,
                is_example=False,
                scope="external",
                security_status="✓ Safe",
            )
        is_local = is_private_or_local_ip(clean_token) or (is_example and not exclude_examples)
        if is_local and include_local:
            status = "✓ Safe (Documented Example)" if is_example else "✓ Safe (Local)"
            return NetworkReference(
                target=ip_str,
                reference_type="ip",
                source_file=source_file,
                line_number=line_idx,
                is_local=True,
                is_example=is_example,
                scope="local",
                security_status=status,
            )
    except ValueError:
        return None
    return None


def _network_security_severity_rank(status: str) -> int:
    """Map security status string to numeric severity rank (0 is highest severity)."""
    s = status.upper()
    if "MALICIOUS" in s or "CRITICAL" in s:
        return 0
    if "⚠️" in s or "FLAGGED" in s or ("RISK" in s and "LOW" not in s) or "HIGH" in s:
        return 1
    if "MEDIUM" in s or "SUSPICIOUS" in s or "WARNING" in s:
        return 2
    # No lookup checked it, so it outranks every safe status (#2504).
    if "UNCHECKED" in s:
        return 3
    if "LOW" in s:
        return 4
    if "SAFE" in s or "CLEAN" in s:
        return 5
    return 6


_REF_TYPE_RANKS = {"url": 1, "ip": 2}


def _network_reference_sort_key(n: NetworkReference) -> tuple[int, int, int, str, str]:
    """Sort key tuple: Scope (external, local), Security (descending severity),
    Type (url, ip), Target (ascending), Location (ascending)."""
    scope_rank = (
        0
        if getattr(n, "scope", "").lower() == "external" or not getattr(n, "is_local", False)
        else 1
    )
    sec_rank = _network_security_severity_rank(str(getattr(n, "security_status", "")))
    type_rank = _REF_TYPE_RANKS.get(str(getattr(n, "reference_type", "")).lower(), 3)
    target_key = str(getattr(n, "target", "")).lower()
    loc_key = str(getattr(n, "location", "") or "").lower()
    return (scope_rank, sec_rank, type_rank, target_key, loc_key)


def sort_network_references(refs: list[NetworkReference]) -> list[NetworkReference]:
    """Sort network references by Scope (external, local), Security (descending severity),
    Type (url, ip), Target (ascending), and Location (ascending)."""
    return sorted(refs, key=_network_reference_sort_key)


def deduplicate_network_references(refs: list[NetworkReference]) -> list[NetworkReference]:
    """Deduplicate network references by target and type, consolidating locations and keeping highest severity."""
    groups: dict[tuple[str, str], list[NetworkReference]] = {}
    for r in refs:
        norm_target = r.target.strip().rstrip("/").lower()
        norm_type = r.reference_type.lower()
        groups.setdefault((norm_target, norm_type), []).append(r)

    deduped: list[NetworkReference] = []
    for group in groups.values():
        group_sorted = sorted(
            group, key=lambda x: _network_security_severity_rank(x.security_status)
        )
        primary = group_sorted[0]

        all_locs: list[str] = []
        for item in group:
            if item.locations:
                all_locs.extend(item.locations)
            elif item.source_file:
                loc = (
                    f"{item.source_file}:{item.line_number}"
                    if item.line_number
                    else f"{item.source_file}:1"
                )
                all_locs.append(loc)

        unique_locs = list(dict.fromkeys(all_locs))
        merged = primary.model_copy(deep=True)
        merged.locations = unique_locs
        deduped.append(merged)

    return sort_network_references(deduped)


def _extract_token_reference(
    clean_token: str,
    source_file: str,
    line_idx: int,
    include_local: bool,
    exclude_examples: bool,
) -> NetworkReference | None:
    """Attempt extracting a URL or IP reference from a single token."""
    url_ref = _extract_url_reference(
        clean_token,
        source_file,
        line_idx,
        include_local,
        exclude_examples=exclude_examples,
    )
    if url_ref:
        return url_ref
    return _extract_ip_reference(
        clean_token,
        source_file,
        line_idx,
        include_local,
        exclude_examples=exclude_examples,
    )


def extract_network_references(
    content: str,
    source_file: str = "",
    include_local: bool = True,
    exclude_examples: bool = True,
) -> list[NetworkReference]:
    """Extract external and local network references (IPs and URLs) from source code."""
    results: list[NetworkReference] = []
    seen: set[str] = set()

    # Skip lockfiles and ignore files whose packages are checked by dependency scans
    if is_lockfile_or_ignore_file(source_file):
        return []

    target_segments = _get_target_segments(content, source_file)

    for text_segment, line_idx in target_segments:
        tokens = re.split(r"""[\s,"'`<>()[\]{}]+""", text_segment)

        for token in tokens:
            if not token:
                continue

            clean_token = token.strip(".,;:\"'`<>()[]{}")
            if not clean_token:
                continue

            if exclude_examples and is_example_or_invalid_network_target(clean_token):
                continue

            ref = _extract_token_reference(
                clean_token,
                source_file,
                line_idx,
                include_local,
                exclude_examples,
            )
            if ref and ref.target not in seen:
                seen.add(ref.target)
                results.append(ref)

    return deduplicate_network_references(results)
