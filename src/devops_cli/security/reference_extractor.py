"""Extractors for software dependencies (manifests) and network references (IPs and URLs)."""

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

import tldextract
import yaml
from packaging.requirements import InvalidRequirement, Requirement

from devops_cli.config.constants import (
    CONST_DEFAULT_LINE_NUMBER,
    CONST_EXCLUDED_PUBLIC_REGISTRIES,
    CONST_RFC2606_RESERVED_DOMAINS,
    CONST_RFC2606_RESERVED_TLDS,
    CONST_SPECIAL_USE_TLDS,
)
from devops_cli.config.defaults import DEFAULT_FORMAT_TYPE
from devops_cli.models.vulnerability import DependencySpec, NetworkReference

logger = logging.getLogger(__name__)

_TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)

# Standard RFC 2606 and RFC 6761 reserved domain suffixes and TLDs
_RFC2606_RESERVED_TLDS = CONST_RFC2606_RESERVED_TLDS
_RFC2606_RESERVED_DOMAINS = CONST_RFC2606_RESERVED_DOMAINS
_SPECIAL_USE_TLDS = CONST_SPECIAL_USE_TLDS
_RESERVED_DOMAINS = _RFC2606_RESERVED_TLDS | _RFC2606_RESERVED_DOMAINS
_EXCLUDED_PUBLIC_REGISTRIES = CONST_EXCLUDED_PUBLIC_REGISTRIES

# RFC 5737 and RFC 3849 documentation / example IP subnets
_RFC5737_IPV4_EXAMPLE_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3 (RFC 5737)
)
_RFC3849_IPV6_EXAMPLE_NETWORKS = (
    ipaddress.ip_network("2001:db8::/32"),  # Documentation (RFC 3849)
)

# RFC 6890 / RFC 2544 / RFC 5180 / RFC 6666 / RFC 6598 special-purpose networks
_RFC6890_IPV4_SPECIAL_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),  # "This host on this network" (RFC 1122)
    ipaddress.ip_network("100.64.0.0/10"),  # Shared Address Space / CGNAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments (RFC 6890)
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("192.88.99.0/24"),  # 6to4 Relay Anycast (RFC 3068 / RFC 7526)
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved for future use (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"),  # Limited Broadcast (RFC 919)
)
_RFC6890_IPV6_SPECIAL_NETWORKS = (
    ipaddress.ip_network("100::/64"),  # Discard-Only (RFC 6666)
    ipaddress.ip_network("2001::/23"),  # IETF Protocol Assignments (RFC 2928)
    ipaddress.ip_network("2001:2::/48"),  # Benchmarking (RFC 5180)
    ipaddress.ip_network("2001:db8::/32"),  # Documentation (RFC 3849)
    ipaddress.ip_network("2002::/16"),  # 6to4 (RFC 3056)
)

_NANPA_EXAMPLE_PHONE_REGEX = re.compile(
    r"""^(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?555[-.\s]?01\d{2}$"""
)
_OFCOM_EXAMPLE_PHONE_REGEX = re.compile(
    r"""^(?:\+?44[-.\s]?|0)(?:1632[-.\s]?(?:960\d{3}|496\d{3,4}|\d{4,6})|20[-.\s]?7946[-.\s]?0\d{3}|7700[-.\s]?900\d{3}|8081[-.\s]?570\d{3}|909[-.\s]?879[-.\s]?0\d{3}|(?:\d{2,4}[-.\s]?)?496[-.\s]?(?:0\d{3}|\d{4}|\d{3}))(?:\s*#.*)?$"""
)


__all__ = [
    "deduplicate_network_references",
    "extract_dependencies_from_text",
    "extract_network_references",
    "is_example_ip",
    "is_example_or_invalid_domain",
    "is_example_or_invalid_network_target",
    "is_example_or_reserved_ip",
    "is_example_phone_number",
    "is_local_or_reserved_domain",
    "is_lockfile_or_ignore_file",
    "is_private_or_local_ip",
    "is_public_ip",
    "is_trusted_registry_host",
    "sort_network_references",
]


@functools.lru_cache(maxsize=4096)
def is_example_ip(ip_or_str: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to RFC 5737 or RFC 3849 documentation/example subnets."""
    try:
        ip = ipaddress.ip_address(ip_or_str) if isinstance(ip_or_str, str) else ip_or_str
        if ip.version == 4:
            return any(ip in net for net in _RFC5737_IPV4_EXAMPLE_NETWORKS)
        return any(ip in net for net in _RFC3849_IPV6_EXAMPLE_NETWORKS)
    except ValueError:
        return False


@functools.lru_cache(maxsize=4096)
def is_example_or_reserved_ip(
    ip_or_str: str | ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Check if an IP address belongs to RFC 6890 special-purpose, example, or benchmarking subnets."""
    try:
        ip = ipaddress.ip_address(ip_or_str) if isinstance(ip_or_str, str) else ip_or_str
        if ip.version == 4:
            return any(ip in net for net in _RFC6890_IPV4_SPECIAL_NETWORKS)
        return any(ip in net for net in _RFC6890_IPV6_SPECIAL_NETWORKS)
    except ValueError:
        return False


@functools.lru_cache(maxsize=4096)
def is_example_or_invalid_domain(target: str) -> bool:
    """Check if domain is an RFC 2606 reserved TLD, example domain, or invalid namespace."""
    clean = target.strip().rstrip(".,;)>]\"'").lower()
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
    ext = _TLD_EXTRACTOR(clean)
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


@functools.lru_cache(maxsize=4096)
def is_example_or_invalid_network_target(target: str) -> bool:  # noqa: C901
    """Check if any network target (URL, IP, domain, phone) is a documented example or invalid reference."""
    clean = target.strip().rstrip(".,;)>]\"'")
    if not clean:
        return False
    if clean.lower() == "localhost":
        return False
    if is_example_phone_number(clean):
        return True
    if "://" in clean:
        try:
            parsed = urllib.parse.urlsplit(clean)
            if not (parsed.scheme and parsed.netloc):
                return False
            host = (parsed.hostname or "").lower()
            if not host or host == "localhost":
                return False
            if _is_unspecified_ip_host(host):
                return True
            return is_example_or_reserved_ip(host) or is_example_or_invalid_domain(host)
        except ValueError:
            return False
    if _is_unspecified_ip_host(clean):
        return True
    if is_example_or_reserved_ip(clean):
        return True
    return is_example_or_invalid_domain(clean)


@functools.lru_cache(maxsize=4096)
def is_public_ip(ip_str: str) -> bool:
    """Check whether an IP string is a valid public, globally routable IP address."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        if is_example_or_reserved_ip(ip):
            return False
        return (
            ip.is_global
            and not ip.is_private
            and not ip.is_loopback
            and not ip.is_reserved
            and not ip.is_multicast
            and not ip.is_unspecified
            and not ip.is_link_local
        )
    except ValueError:
        return False


@functools.lru_cache(maxsize=4096)
def is_private_or_local_ip(ip_str: str) -> bool:
    """Check whether an IP string is a private, loopback, link-local, or reserved IP address."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        if ip.is_unspecified:
            return False
        if is_example_or_reserved_ip(ip) or is_example_ip(ip):
            return False
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


@functools.lru_cache(maxsize=4096)
def is_local_or_reserved_domain(target: str) -> bool:
    """Check if domain or hostname is an RFC reserved, internal, or local network hostname."""
    clean = target.strip().rstrip(".,;)>]\"'").lower()
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
    ext = _TLD_EXTRACTOR(clean)
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


def _is_url_local_host(host: str, is_example: bool, exclude_examples: bool) -> bool:
    """Determine whether a URL's host represents a local, private, or loopback endpoint."""
    if host == "localhost" or "." not in host:
        return True
    if is_private_or_local_ip(host) or is_local_or_reserved_domain(host):
        return True
    return bool(is_example and not exclude_examples)


def _is_valid_url_target(clean_token: str) -> tuple[urllib.parse.SplitResult, str] | None:
    """Validate URL syntax and extract parsed result and lowercased hostname."""
    if "://" not in clean_token or "\\" in clean_token or ".*" in clean_token:
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
    is_example = is_example_or_invalid_domain(host) or is_example_or_reserved_ip(host)
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
        is_example = is_example_or_reserved_ip(ip) or is_example_ip(ip)
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
    if "LOW" in s:
        return 3
    if "SAFE" in s or "CLEAN" in s:
        return 4
    return 5


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


def _find_package_line(lines: list[str], pkg_token: str) -> int | None:
    token_lower = pkg_token.lower()
    for idx, line in enumerate(lines, start=1):
        if token_lower in line.lower():
            return idx
    return None


def _extract_pip_dependencies(content_lines: list[str], file_name: str) -> list[DependencySpec]:
    """Parse dependencies from requirements.txt format."""
    deps: list[DependencySpec] = []
    for line_idx, line in enumerate(content_lines, start=1):
        line = line.strip()
        if not line or line.startswith(("#", "-", "--")):
            continue
        try:
            req = Requirement(line)
            version_spec = str(req.specifier) if str(req.specifier) else "*"
            deps.append(
                DependencySpec(
                    name=req.name,
                    version_range=version_spec,
                    ecosystem="PyPI",
                    source_file=file_name,
                    line_number=line_idx,
                )
            )
        except InvalidRequirement:
            pass
    return deps


def _extract_pyproject_dependencies(  # noqa: C901
    content: str, content_lines: list[str], file_name: str
) -> list[DependencySpec]:
    """Parse dependencies from pyproject.toml format."""
    try:
        data = tomllib.loads(content)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        logger.warning("Failed to parse pyproject.toml %s: %s", file_name, exc)
        return []

    req_strings: list[str] = []

    # Standard PEP 621 project.dependencies
    proj_deps = data.get("project", {}).get("dependencies", [])
    if isinstance(proj_deps, list):
        req_strings.extend(d for d in proj_deps if isinstance(d, str))

    # Standard PEP 621 project.optional-dependencies
    opt_deps = data.get("project", {}).get("optional-dependencies", {})
    if isinstance(opt_deps, dict):
        for opt_list in opt_deps.values():
            if isinstance(opt_list, list):
                req_strings.extend(d for d in opt_list if isinstance(d, str))

    # PEP 735 dependency-groups
    dep_groups = data.get("dependency-groups", {})
    if isinstance(dep_groups, dict):
        for grp_list in dep_groups.values():
            if isinstance(grp_list, list):
                req_strings.extend(d for d in grp_list if isinstance(d, str))

    deps: list[DependencySpec] = []
    for req_str in req_strings:
        try:
            req = Requirement(req_str)
            line_no = _find_package_line(content_lines, req.name)
            version_spec = str(req.specifier) if str(req.specifier) else "*"
            deps.append(
                DependencySpec(
                    name=req.name,
                    version_range=version_spec,
                    ecosystem="PyPI",
                    source_file=file_name,
                    line_number=line_no,
                )
            )
        except InvalidRequirement:
            pass
    return deps


def _extract_package_json_dependencies(
    content: str, content_lines: list[str], file_name: str
) -> list[DependencySpec]:
    """Parse dependencies from package.json format."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse package.json %s: %s", file_name, exc)
        return []

    all_deps: dict[str, str] = {}
    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        if section in data and isinstance(data[section], dict):
            all_deps.update(data[section])

    deps: list[DependencySpec] = []
    for pkg, ver in all_deps.items():
        line_no = _find_package_line(content_lines, f'"{pkg}"') or _find_package_line(
            content_lines, pkg
        )
        deps.append(
            DependencySpec(
                name=pkg,
                version_range=str(ver),
                ecosystem="npm",
                source_file=file_name,
                line_number=line_no,
            )
        )
    return deps


def _extract_cargo_dependencies(
    content: str, content_lines: list[str], file_name: str
) -> list[DependencySpec]:
    """Parse dependencies from Cargo.toml or Cargo.lock format."""
    try:
        data = tomllib.loads(content)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        logger.warning("Failed to parse Cargo file %s: %s", file_name, exc)
        return []

    cargo_deps = data.get("dependencies", {})
    if not isinstance(cargo_deps, dict):
        return []

    deps: list[DependencySpec] = []
    for pkg, ver in cargo_deps.items():
        ver_str = ver if isinstance(ver, str) else ver.get("version", "*")
        line_no = _find_package_line(content_lines, pkg)
        deps.append(
            DependencySpec(
                name=pkg,
                version_range=str(ver_str),
                ecosystem="crates.io",
                source_file=file_name,
                line_number=line_no,
            )
        )
    return deps


def _extract_go_mod_dependencies(content_lines: list[str], file_name: str) -> list[DependencySpec]:
    """Parse dependencies from go.mod format."""
    deps: list[DependencySpec] = []
    in_require_block = False
    for line_idx, line in enumerate(content_lines, start=1):
        line = line.strip()
        if line.startswith("require ("):
            in_require_block = True
            continue
        if in_require_block and line == ")":
            in_require_block = False
            continue
        if not (in_require_block or line.startswith("require ")):
            continue
        raw = line.removeprefix("require").strip()
        parts = raw.split()
        if len(parts) >= 2:
            deps.append(
                DependencySpec(
                    name=parts[0],
                    version_range=parts[1],
                    ecosystem="Go",
                    source_file=file_name,
                    line_number=line_idx,
                )
            )
    return deps


def extract_dependencies_from_text(content: str, file_name: str) -> list[DependencySpec]:
    """Extract dependency specifications from manifest file content using standard parsers."""
    name_lower = Path(file_name).name.lower()
    content_lines = content.splitlines()

    if name_lower in ("requirements.txt", "requirements-dev.txt", "requirements.in"):
        return _extract_pip_dependencies(content_lines, file_name)
    if name_lower == "pyproject.toml":
        return _extract_pyproject_dependencies(content, content_lines, file_name)
    if name_lower == "package.json":
        return _extract_package_json_dependencies(content, content_lines, file_name)
    if name_lower in ("cargo.toml", "cargo.lock"):
        return _extract_cargo_dependencies(content, content_lines, file_name)
    if name_lower == "go.mod":
        return _extract_go_mod_dependencies(content_lines, file_name)

    return []
