"""Extractors for software dependencies (manifests) and network references (IPs, URLs, domains)."""

from __future__ import annotations

import ast
import builtins
import functools
import importlib.util
import io
import ipaddress
import json
import keyword
import logging
import mimetypes
import os
import re
import socket
import sys
import textwrap
import tokenize
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any

import tldextract
import yaml
from packaging.requirements import InvalidRequirement, Requirement

from devops_cli.ai.analyze.scanner import detect_language
from devops_cli.config.constants import (
    CONST_CODE_CONFIG_PREFIXES,
    CONST_COMMON_PROPERTY_SUFFIXES,
    CONST_DEFAULT_LINE_NUMBER,
    CONST_EXCLUDED_FILE_MIME_TYPES,
    CONST_EXCLUDED_PUBLIC_REGISTRIES,
    CONST_RFC2606_RESERVED_DOMAINS,
    CONST_RFC2606_RESERVED_TLDS,
    CONST_SPECIAL_USE_TLDS,
    CONST_STANDARD_RECEIVER_IDENTIFIERS,
    CONST_TELEMETRY_CALL_NAMES,
)
from devops_cli.config.defaults import DEFAULT_FORMAT_TYPE
from devops_cli.core.repo import _get_pathspec_for_repo
from devops_cli.models.vulnerability import DependencySpec, NetworkReference

logger = logging.getLogger(__name__)

# Ensure standard MIME types are initialized from system registry
mimetypes.init()
mimetypes.add_type("text/x-template", ".in")
mimetypes.add_type("text/x-lock", ".lock")
mimetypes.add_type("text/x-terraform", ".tf")
mimetypes.add_type("text/x-terraform-vars", ".tfvars")
mimetypes.add_type("text/x-hcl", ".hcl")
mimetypes.add_type("application/x-wheel+zip", ".whl")
mimetypes.add_type("application/x-crate+tar", ".crate")
mimetypes.add_type("application/x-nupkg+zip", ".nupkg")
mimetypes.add_type("application/x-gem+tar", ".gem")
mimetypes.add_type("application/java-archive", ".war")
mimetypes.add_type("application/java-archive", ".ear")

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
    "is_code_or_config_reference",
    "is_example_ip",
    "is_example_or_invalid_domain",
    "is_example_or_invalid_network_target",
    "is_example_or_reserved_ip",
    "is_example_phone_number",
    "is_file_reference",
    "is_local_or_reserved_domain",
    "is_lockfile_or_ignore_file",
    "is_network_domain",
    "is_package_repository_asset",
    "is_private_or_local_ip",
    "is_public_ip",
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
def is_example_or_invalid_network_target(target: str) -> bool:
    """Check if any network target (URL, IP, domain, phone) is a documented example or invalid reference."""
    clean = target.strip().rstrip(".,;)>]\"'")
    if not clean:
        return False
    if clean.lower() == "localhost":
        return False
    if is_example_phone_number(clean):
        return True
    if clean.lower().startswith(("http://", "https://", "ftp://")):
        try:
            parsed = urllib.parse.urlsplit(clean)
            host = (parsed.hostname or "").lower()
            if not host:
                return False
            if host == "localhost":
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


@functools.lru_cache(maxsize=16)
def _get_workspace_filenames(root_dir_str: str = "") -> tuple[set[str], tuple[str, ...]]:
    """Recursively discover all file names and relative paths across the workspace respecting .gitignore."""
    root = Path(root_dir_str) if root_dir_str else Path.cwd()
    if not root.exists() or not root.is_dir():
        root = Path.cwd()
    exact_names: set[str] = set()
    all_paths: list[str] = []
    spec = _get_pathspec_for_repo(str(root.resolve()))
    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            pruned_dirs: list[str] = []
            for d in dirnames:
                if d == ".git":
                    continue
                if spec is not None:
                    try:
                        rel_d = (Path(dirpath) / d).relative_to(root).as_posix()
                        if spec.match_file(rel_d + "/") or spec.match_file(rel_d):
                            continue
                    except ValueError:
                        pass
                elif d.startswith(".") and d not in (".github", ".agents"):
                    continue
                pruned_dirs.append(d)
            dirnames[:] = pruned_dirs

            for fname in filenames:
                if spec is not None:
                    try:
                        rel_f = (Path(dirpath) / fname).relative_to(root).as_posix()
                        if spec.match_file(rel_f):
                            continue
                    except ValueError:
                        pass
                fname_lower = fname.lower()
                exact_names.add(fname_lower)
                all_paths.append(fname_lower)
                try:
                    full_p = Path(dirpath) / fname
                    rel = full_p.relative_to(root).as_posix().lower()
                    exact_names.add(rel)
                    all_paths.append(rel)
                except ValueError:
                    pass
    except Exception:
        pass
    return exact_names, tuple(all_paths)


class PythonSymbolContext:
    """Container for AST-extracted symbols, attribute chains, and telemetry keys."""

    __slots__ = ("symbols", "attribute_chains", "metric_keys", "dict_keys")

    def __init__(
        self,
        symbols: set[str] | None = None,
        attribute_chains: set[str] | None = None,
        metric_keys: set[str] | None = None,
        dict_keys: set[str] | None = None,
    ) -> None:
        self.symbols = symbols or set()
        self.attribute_chains = attribute_chains or set()
        self.metric_keys = metric_keys or set()
        self.dict_keys = dict_keys or set()


def _resolve_attribute_chain(node: ast.AST) -> str | None:
    """Recursively resolve attribute chain like self.host or ci.step.security."""
    parts: list[str] = []
    curr: ast.AST | None = node
    while isinstance(curr, ast.Attribute):
        parts.append(curr.attr)
        curr = curr.value
    if isinstance(curr, ast.Name):
        parts.append(curr.id)
        return ".".join(reversed(parts))
    return None


def _resolve_call_func(node: ast.AST) -> str:
    """Extract call target identifier or attribute chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _resolve_attribute_chain(node) or node.attr
    return ""


class PythonSymbolVisitor(ast.NodeVisitor):
    """AST visitor extracting declared symbols, attribute chains, and telemetry call literals."""

    def __init__(self) -> None:
        self.symbols: set[str] = set()
        self.attribute_chains: set[str] = set()
        self.metric_keys: set[str] = set()
        self.dict_keys: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.symbols.add(alias.name.split(".")[0].lower())
            self.symbols.add((alias.asname or alias.name).lower())
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.symbols.add(node.module.split(".")[0].lower())
            self.symbols.add(node.module.lower())
        for alias in node.names:
            self.symbols.add((alias.asname or alias.name).lower())
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.symbols.add(node.name.lower())
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            self.symbols.add(arg.arg.lower())
        if node.args.vararg:
            self.symbols.add(node.args.vararg.arg.lower())
        if node.args.kwarg:
            self.symbols.add(node.args.kwarg.arg.lower())
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.symbols.add(node.name.lower())
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            self.symbols.add(arg.arg.lower())
        if node.args.vararg:
            self.symbols.add(node.args.vararg.arg.lower())
        if node.args.kwarg:
            self.symbols.add(node.args.kwarg.arg.lower())
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.add(node.name.lower())
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self.symbols.add(node.id.lower())
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        chain = _resolve_attribute_chain(node)
        if chain:
            self.attribute_chains.add(chain.lower())
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _resolve_call_func(node.func).lower()
        if any(marker in call_name for marker in CONST_TELEMETRY_CALL_NAMES):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    self.metric_keys.add(arg.value.lower())
            for kw in node.keywords:
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    self.metric_keys.add(kw.value.value.lower())
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                self.dict_keys.add(k.value.lower())
        self.generic_visit(node)


@functools.lru_cache(maxsize=1024)
def _parse_python_file_symbols(source_file: str) -> PythonSymbolContext:
    """Parse source file using Python AST symbol parser to extract declarations and telemetry calls."""
    if not source_file:
        return PythonSymbolContext()
    p = Path(source_file)
    if not p.is_file():
        p = Path.cwd() / p
    if not p.is_file() or p.suffix.lower() != ".py":
        return PythonSymbolContext()
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(p))
        visitor = PythonSymbolVisitor()
        visitor.visit(tree)
        return PythonSymbolContext(
            symbols=visitor.symbols,
            attribute_chains=visitor.attribute_chains,
            metric_keys=visitor.metric_keys,
            dict_keys=visitor.dict_keys,
        )
    except Exception:
        return PythonSymbolContext()


def _is_routable_dns_ip(ip_text: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_text)
        return not (addr.is_unspecified or addr.is_loopback)
    except ValueError:
        return False


@functools.lru_cache(maxsize=2048)
def _is_resolvable_domain(hostname: str) -> bool:
    """Use system domain lookup tooling to check if hostname resolves via DNS to a routable IP."""
    try:
        results = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        return any(_is_routable_dns_ip(str(res[4][0])) for res in results)
    except socket.gaierror, OSError, TimeoutError:
        return False


def _is_metric_or_telemetry_context(
    target: str, text_segment: str, source_file: str, line_idx: int
) -> bool:
    """Dynamically determine if target is used as a telemetry metric, attribute, or code key."""
    target_lower = target.lower()
    if is_local_or_reserved_domain(target_lower):
        return False

    if source_file:
        context = _parse_python_file_symbols(source_file)
        if target_lower in context.metric_keys or target_lower in context.attribute_chains:
            return True

    if target_lower.startswith(CONST_CODE_CONFIG_PREFIXES):
        return True

    parts = target_lower.split(".")
    if len(parts) >= 2 and parts[-1] in CONST_COMMON_PROPERTY_SUFFIXES:
        ext = _TLD_EXTRACTOR(target_lower)
        psl_tlds = frozenset(_TLD_EXTRACTOR.tlds)
        if not ext.suffix or ext.suffix.lower() not in psl_tlds:
            return True

    return False


@functools.lru_cache(maxsize=1024)
def _is_known_python_module(name: str) -> bool:
    """Check if identifier maps to an installed Python distribution or standard library module."""
    if not name.isidentifier():
        return False
    try:
        return importlib.util.find_spec(name) is not None
    except ImportError, AttributeError, ValueError:
        return False


@functools.lru_cache(maxsize=4096)
def is_file_reference(target: str, source_file: str = "") -> bool:
    """Check if target string represents an existing file on disk, known extension,
    or search match.
    """
    clean = target.strip().rstrip(".,;)>]\"'").lower()
    if not clean:
        return False
    if "/" in clean or "\\" in clean or clean.startswith("."):
        return True

    target_path = Path(clean)

    # 1. Direct or cwd-relative filesystem existence
    if target_path.is_file() or (Path.cwd() / target_path).is_file():
        return True

    # 2. Source file relative existence
    if source_file:
        src = Path(source_file)
        if (src.parent / target_path).is_file():
            return True
        if src.parent.is_dir() and any(
            (sibling / target_path).is_file()
            for sibling in src.parent.iterdir()
            if sibling.is_dir() and not sibling.name.startswith(".")
        ):
            return True

    exact_names, all_paths = _get_workspace_filenames(str(Path.cwd().resolve()))

    # 3. Exact match against any filename or relative path across workspace
    if clean in exact_names:
        return True

    # 4. Match as a substring of a filename in workspace file tree
    for path_str in all_paths:
        if clean == path_str or clean in path_str.split("/"):
            return True
        if "." in clean and (path_str.endswith("/" + clean) or path_str.endswith(clean)):
            return True

    # 5. Standard MIME or recognized language file reference
    mime_type, encoding = mimetypes.guess_type(clean)
    if encoding or (mime_type and mime_type not in CONST_EXCLUDED_FILE_MIME_TYPES):
        return True
    if Path(clean).suffix and detect_language(clean) not in ("plaintext", "org"):
        return True

    # 6. Network domains and reserved hostnames without disk presence are not files
    if is_local_or_reserved_domain(clean):
        return False

    ext = _TLD_EXTRACTOR(clean)
    if ext.domain and ext.suffix:
        if (
            ext.subdomain
            or ext.suffix.lower() in frozenset(_TLD_EXTRACTOR.tlds)
            or is_local_or_reserved_domain(clean)
        ):
            return False

    return False


@functools.lru_cache(maxsize=4096)
def is_code_or_config_reference(target: str, source_file: str = "") -> bool:
    """Differentiate code identifiers, method chains, and config keys from network hosts."""
    clean = target.strip().rstrip(".,;)>]\"'")

    # Programmatic function calls like not.a.domain.com(...)
    if "(" in clean or ")" in clean or clean.endswith("()"):
        return True

    # Valid network hostnames cannot contain underscores (RFC 1123)
    if "_" in clean or clean.startswith("-") or clean.endswith("-"):
        return True

    if is_local_or_reserved_domain(clean):
        return False

    clean_lower = clean.lower()

    # Common code receiver or property prefixes (e.g. self.host, ci.step.security, host.name)
    if clean_lower.startswith(CONST_CODE_CONFIG_PREFIXES):
        return True

    parts = clean.split(".")
    if len(parts) < 2:
        return True

    first_seg = parts[0].lower()
    last_seg = parts[-1].lower()

    if first_seg in CONST_STANDARD_RECEIVER_IDENTIFIERS:
        return True

    # Standard Python keywords and builtins (e.g. dir(builtins))
    builtin_names = set(dir(builtins))
    stdlib_names = getattr(sys, "stdlib_module_names", set()) | set(sys.builtin_module_names)

    # Check against AST-parsed symbols in source file
    if source_file:
        context = _parse_python_file_symbols(source_file)
        if clean_lower in context.attribute_chains or clean_lower in context.metric_keys:
            return True
        if (first_seg in context.symbols or last_seg in context.symbols) and all(
            seg.isidentifier() for seg in parts
        ):
            return True

    # If first segment is a language keyword, stdlib root module, or installed package
    if (
        keyword.iskeyword(first_seg)
        or first_seg in stdlib_names
        or _is_known_python_module(first_seg)
    ):
        return True

    # If last segment is a keyword or builtin attribute in 2-segment expression
    if keyword.iskeyword(last_seg) or (len(parts) == 2 and last_seg in builtin_names):
        return True

    # Single-letter variable receiver (e.g. m.group, r.json, f.read)
    if len(first_seg) == 1 and len(parts) == 2:
        return True

    # Check if identifier path maps to a local directory, package, or python source module
    alt_path = Path(clean.replace(".", "/"))
    if (
        (Path.cwd() / alt_path).is_dir()
        or (Path.cwd() / (clean.replace(".", "/") + ".py")).is_file()
        or (Path.cwd() / "src" / (clean.replace(".", "/") + ".py")).is_file()
    ):
        return True

    exact_names, all_paths = _get_workspace_filenames(str(Path.cwd().resolve()))
    if clean.replace(".", "/") in exact_names or any(
        clean.replace(".", "/") in p for p in all_paths
    ):
        return True

    # Top-level workspace package matching (e.g. devops_cli.*, tests.*)
    if (Path.cwd() / first_seg).exists() or (Path.cwd() / "src" / first_seg).exists():
        return True

    ext = _TLD_EXTRACTOR(clean)
    if not ext.domain or not ext.suffix:
        return True

    # Domain lookup tooling: inspect authoritative PSL database
    suffix_lower = ext.suffix.lower()
    psl_tlds = frozenset(_TLD_EXTRACTOR.tlds)
    if suffix_lower not in psl_tlds and not is_local_or_reserved_domain(clean):
        return True

    if (
        suffix_lower in CONST_COMMON_PROPERTY_SUFFIXES or last_seg in CONST_COMMON_PROPERTY_SUFFIXES
    ) and not _is_resolvable_domain(clean):
        return True

    return False


@functools.lru_cache(maxsize=4096)
def is_network_domain(target: str, source_file: str = "") -> bool:
    """Validate whether target string is a legitimate public network domain using standard library
    parsers and the Public Suffix List (PSL).
    """
    clean = target.strip().rstrip(".,;)>]\"'")
    if not clean or "." not in clean or " " in clean or "/" in clean or "\\" in clean:
        return False

    try:
        parsed = urllib.parse.urlsplit(f"//{clean}")
        hostname = parsed.hostname
        if not hostname or hostname != clean.lower():
            return False
    except ValueError:
        return False

    # Check if target is an IP address
    try:
        ipaddress.ip_address(clean)
        return False
    except ValueError:
        pass

    # Check for programmatic function calls
    if "(" in clean or ")" in clean or clean.endswith("()"):
        return False

    if is_file_reference(clean, source_file=source_file):
        return False

    if is_code_or_config_reference(clean, source_file=source_file):
        return False

    ext = _TLD_EXTRACTOR(clean)
    if not ext.domain or not ext.suffix:
        return False

    registered = f"{ext.domain.lower()}.{ext.suffix.lower()}"
    fqdn = ext.fqdn.lower()

    # Exclude reserved RFC domains and common public tooling registries
    if (
        registered in _RESERVED_DOMAINS
        or fqdn in _RESERVED_DOMAINS
        or any(fqdn.endswith("." + exc) for exc in _RESERVED_DOMAINS)
    ):
        return False

    if not fqdn.startswith("api."):
        if (
            registered in _EXCLUDED_PUBLIC_REGISTRIES
            or fqdn in _EXCLUDED_PUBLIC_REGISTRIES
            or any(fqdn.endswith("." + exc) for exc in _EXCLUDED_PUBLIC_REGISTRIES)
        ):
            return False

    # Check if domain name or registered name matches a workspace file
    if is_file_reference(fqdn, source_file=source_file) or is_file_reference(
        registered, source_file=source_file
    ):
        return False

    try:
        ip = ipaddress.ip_address(fqdn)
        return is_public_ip(str(ip))
    except ValueError:
        pass

    return True


def _parse_python_token_string(tok_string: str) -> str | None:
    """Safely parse literal value or clean fallback from a Python string token."""
    try:
        val = ast.literal_eval(tok_string)
        if isinstance(val, str):
            return val
    except Exception:
        pass
    clean_str = tok_string.strip("\"'")
    return clean_str if clean_str else None


def _extract_python_literals_and_comments(source: str) -> list[tuple[str, int]]:
    """Extract string constants and comments from Python source code with line numbers."""
    literals: list[tuple[str, int]] = []
    source = textwrap.dedent(source)
    parsed_ast = False

    try:
        tree = ast.parse(source)
        parsed_ast = True
        visitor = PythonSymbolVisitor()
        visitor.visit(tree)
        metric_and_dict_keys = visitor.metric_keys | visitor.dict_keys

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                line = getattr(node, "lineno", 1)
                val = node.value.strip()
                val_lower = val.lower()
                if val_lower in metric_and_dict_keys and not val_lower.startswith(
                    ("http://", "https://", "ftp://")
                ):
                    continue
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
    """Strip template expressions and git config options from YAML command blocks."""
    cleaned = re.sub(r"\$\{\{[\s\S]*?\}\}", "", text)
    cleaned = re.sub(r"git\s+config(?:\s+--[\w-]+)*\s+[\w.-]+", "", cleaned)
    return cleaned


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
    except Exception:
        pass
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
def is_package_repository_asset(url: str, host: str = "") -> bool:
    """Check if a URL represents an individual package download asset from a package repository."""
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = (host or parsed.hostname or "").lower()
    except ValueError:
        return False

    if not hostname:
        return False

    # Check if host or registered domain is a package registry/distribution CDN
    if hostname in _EXCLUDED_PUBLIC_REGISTRIES or any(
        hostname.endswith("." + exc) for exc in _EXCLUDED_PUBLIC_REGISTRIES
    ):
        return True

    path_lower = parsed.path.lower()
    mime_type, encoding = mimetypes.guess_type(path_lower)
    if encoding in ("gzip", "bzip2", "xz") or (
        mime_type
        and any(
            arch in mime_type
            for arch in (
                "zip",
                "tar",
                "archive",
                "octet-stream",
                "java-archive",
                "x-wheel",
                "x-crate",
                "x-nupkg",
                "x-gem",
            )
        )
    ):
        return True

    if any(
        segment in path_lower
        for segment in (
            "/packages/",
            "/crates/",
            "/v3-flatcontainer/",
            "/downloads/",
            "/repository/",
        )
    ):
        return True

    return False


def _extract_url_reference(
    clean_token: str,
    source_file: str,
    line_idx: int,
    include_local: bool,
    exclude_examples: bool = True,
) -> NetworkReference | None:
    """Parse and validate URL network reference."""
    if not clean_token.lower().startswith(("http://", "https://", "ftp://")):
        return None
    if "\\" in clean_token or ".*" in clean_token:
        return None
    try:
        parsed = urllib.parse.urlsplit(clean_token)
        if not (parsed.scheme in ("http", "https") and parsed.netloc):
            return None
        host = (parsed.hostname or "").lower()
        if not host:
            return None
        try:
            if ipaddress.ip_address(host).is_unspecified:
                return None
        except ValueError:
            pass
        if is_package_repository_asset(clean_token, host):
            return None
        is_example = is_example_or_invalid_domain(host) or is_example_or_reserved_ip(host)
        if is_example and exclude_examples:
            return None
        is_local_host = (
            host == "localhost"
            or is_private_or_local_ip(host)
            or is_local_or_reserved_domain(host)
            or ("." not in host)
            or (is_example and not exclude_examples)
        )
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
    except ValueError:
        return None


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


def _extract_domain_reference(
    clean_token: str,
    text_segment: str,
    source_file: str,
    line_idx: int,
    include_local: bool,
    exclude_examples: bool = True,
) -> NetworkReference | None:
    """Parse and validate domain/hostname network reference."""
    if not (
        "." in clean_token
        and "/" not in clean_token
        and "\\" not in clean_token
        and "@" not in clean_token
        and "$" not in clean_token
        and "=" not in clean_token
        and "*" not in clean_token
    ):
        if clean_token.lower() == "localhost":
            if not include_local:
                return None
            return NetworkReference(
                target="localhost",
                reference_type="domain",
                source_file=source_file,
                line_number=line_idx,
                is_local=True,
                is_example=False,
                scope="local",
                security_status="✓ Safe (Local)",
            )
        return None

    domain_candidate = clean_token.lower()
    if domain_candidate in _SPECIAL_USE_TLDS or is_example_or_invalid_domain(domain_candidate):
        return None

    if domain_candidate.endswith((".example", ".sample")) and any(
        kw in domain_candidate
        for kw in (
            "tfvars",
            "env",
            "config",
            "yml",
            "yaml",
            "json",
            "toml",
            "ini",
            "conf",
            "template",
        )
    ):
        return None

    # Validate hostname format via standard library urllib.parse
    try:
        parsed = urllib.parse.urlsplit(f"//{domain_candidate}")
        hostname = parsed.hostname
        if not hostname or hostname != domain_candidate:
            return None
    except ValueError:
        return None

    # Check programmatic function call indicators in original text segment
    pos = text_segment.find(clean_token)
    if pos != -1:
        trailing = text_segment[pos + len(clean_token) :].lstrip()
        if trailing.startswith(("(", "[", "=")):
            return None
        if pos > 0 and text_segment[pos - 1] in (".", "$", ">", ":", "\\"):
            return None

    if is_file_reference(domain_candidate, source_file=source_file):
        return None

    if _is_metric_or_telemetry_context(domain_candidate, text_segment, source_file, line_idx):
        return None

    if is_code_or_config_reference(domain_candidate, source_file=source_file):
        return None

    if is_local_or_reserved_domain(domain_candidate):
        if not include_local:
            return None
        return NetworkReference(
            target=domain_candidate,
            reference_type="domain",
            source_file=source_file,
            line_number=line_idx,
            is_local=True,
            is_example=False,
            scope="local",
            security_status="✓ Safe (Local)",
        )

    if is_network_domain(domain_candidate, source_file=source_file):
        return NetworkReference(
            target=domain_candidate,
            reference_type="domain",
            source_file=source_file,
            line_number=line_idx,
            is_local=False,
            is_example=False,
            scope="external",
            security_status="✓ Safe",
        )

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


_REF_TYPE_RANKS = {"domain": 0, "url": 1, "ip": 2}


def _network_reference_sort_key(n: NetworkReference) -> tuple[int, int, int, str, str]:
    """Sort key tuple: Scope (external, local), Security (descending severity),
    Type (domain, url, ip), Target (ascending), Location (ascending)."""
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
    Type (domain, url, ip), Target (ascending), and Location (ascending)."""
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


def extract_network_references(
    content: str,
    source_file: str = "",
    include_local: bool = True,
    exclude_examples: bool = True,
) -> list[NetworkReference]:
    """Extract external and local network references (IPs, URLs, and domains) from source code."""
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

            # 1. URL Reference
            url_ref = _extract_url_reference(
                clean_token,
                source_file,
                line_idx,
                include_local,
                exclude_examples=exclude_examples,
            )
            if url_ref:
                if url_ref.target not in seen:
                    seen.add(url_ref.target)
                    results.append(url_ref)
                continue

            # 2. IP Address Reference
            ip_ref = _extract_ip_reference(
                clean_token,
                source_file,
                line_idx,
                include_local,
                exclude_examples=exclude_examples,
            )
            if ip_ref:
                if ip_ref.target not in seen:
                    seen.add(ip_ref.target)
                    results.append(ip_ref)
                continue

            # 3. Domain Reference
            dom_ref = _extract_domain_reference(
                clean_token,
                text_segment,
                source_file,
                line_idx,
                include_local,
                exclude_examples=exclude_examples,
            )
            if dom_ref:
                if dom_ref.target not in seen:
                    seen.add(dom_ref.target)
                    results.append(dom_ref)

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


def _extract_pyproject_dependencies(
    content: str, content_lines: list[str], file_name: str
) -> list[DependencySpec]:
    """Parse dependencies from pyproject.toml format."""
    try:
        data = tomllib.loads(content)
    except Exception:
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
    except Exception:
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
    except Exception:
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
