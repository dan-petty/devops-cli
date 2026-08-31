"""Extractors for software dependencies (manifests) and network references (IPs, URLs, domains)."""

from __future__ import annotations

import ast
import builtins
import functools
import io
import ipaddress
import json
import keyword
import logging
import mimetypes
import os
import re
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

from devops_cli.config.constants import CONST_DEFAULT_LINE_NUMBER
from devops_cli.config.defaults import DEFAULT_FORMAT_TYPE
from devops_cli.models.vulnerability import DependencySpec, NetworkReference

logger = logging.getLogger(__name__)

# Ensure standard MIME types are initialized from system registry
mimetypes.init()
mimetypes.add_type("text/x-template", ".in")
mimetypes.add_type("text/x-lock", ".lock")
mimetypes.add_type("text/x-terraform", ".tf")
mimetypes.add_type("text/x-terraform-vars", ".tfvars")
mimetypes.add_type("text/x-hcl", ".hcl")

_TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=None)

# Standard RFC 2606 and RFC 6761 reserved domain suffixes
_RESERVED_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "local",
    "test",
    "example",
    "invalid",
    "internal",
}

_EXCLUDED_PUBLIC_REGISTRIES = {
    "schema.org",
    "w3.org",
    "json-schema.org",
    "opencontainers.org",
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "pypi.org",
    "pypi.python.org",
    "pythonhosted.org",
    "files.pythonhosted.org",
    "npmjs.com",
    "npmjs.org",
    "registry.npmjs.org",
    "yarnpkg.com",
    "registry.yarnpkg.com",
    "crates.io",
    "static.crates.io",
    "golang.org",
    "pkg.go.dev",
    "proxy.golang.org",
    "sum.golang.org",
    "rubygems.org",
    "maven.org",
    "apache.org",
    "gradle.org",
    "packagist.org",
    "nuget.org",
    "google.com",
    "osv.dev",
    "nist.gov",
    "shodan.io",
    "cloudflare.com",
}

_PACKAGE_ARCHIVE_EXTENSIONS = (
    ".whl",
    ".tar.gz",
    ".tgz",
    ".crate",
    ".nupkg",
    ".gem",
    ".jar",
    ".war",
    ".ear",
)

_WORKSPACE_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".data",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".uv",
    ".tox",
    "repos",
    "target",
}

__all__ = [
    "extract_dependencies_from_text",
    "extract_network_references",
    "is_code_or_config_reference",
    "is_file_reference",
    "is_local_or_reserved_domain",
    "is_lockfile_or_ignore_file",
    "is_network_domain",
    "is_package_repository_asset",
    "is_private_or_local_ip",
    "is_public_ip",
]


@functools.lru_cache(maxsize=4096)
def is_public_ip(ip_str: str) -> bool:
    """Check whether an IP string is a valid public, globally routable IP address."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
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
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


@functools.lru_cache(maxsize=4096)
def is_local_or_reserved_domain(target: str) -> bool:
    """Check if domain or hostname is an RFC reserved, internal, or local network hostname."""
    clean = target.strip().rstrip(".,;)>]\"'").lower()
    if not clean or clean.startswith("-") or clean.endswith("-") or "_" in clean:
        return False
    if clean in _RESERVED_DOMAINS:
        return True
    if any(clean.endswith("." + d) for d in _RESERVED_DOMAINS):
        return True
    ext = _TLD_EXTRACTOR(clean)
    if ext.suffix and ext.suffix.lower() in _RESERVED_DOMAINS:
        return True
    if any(
        clean.endswith(ext_name)
        for ext_name in (
            ".local",
            ".internal",
            ".lan",
            ".home.arpa",
            ".cluster.local",
            ".localhost",
            ".localdomain",
            ".svc",
            ".corp",
            ".test",
            ".example",
            ".invalid",
        )
    ):
        return True
    return False


@functools.lru_cache(maxsize=16)
def _get_workspace_filenames(root_dir_str: str = "") -> tuple[set[str], tuple[str, ...]]:
    """Recursively discover all file names and relative paths across the workspace."""
    root = Path(root_dir_str) if root_dir_str else Path.cwd()
    if not root.exists() or not root.is_dir():
        root = Path.cwd()
    exact_names: set[str] = set()
    all_paths: list[str] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            # Prune skipped directory branches in-place for instant scanning
            dirnames[:] = [
                d
                for d in dirnames
                if d not in _WORKSPACE_SKIP_DIRS
                and (not d.startswith(".") or d in (".github", ".agents"))
            ]
            for fname in filenames:
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


_COMMON_FILE_EXTENSIONS = (
    ".py",
    ".pyi",
    ".pyx",
    ".md",
    ".markdown",
    ".rst",
    ".adoc",
    ".txt",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".bat",
    ".cmd",
    ".ps1",
    ".tf",
    ".tfvars",
    ".hcl",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".rs",
    ".go",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".xml",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".lock",
    ".lockb",
    ".pid",
    ".env",
    ".example",
    ".sample",
    ".template",
    ".sql",
    ".db",
    ".sqlite",
    ".log",
    ".out",
    ".err",
    ".bak",
    ".tmp",
)

_CODE_CONFIG_PREFIXES = (
    "self.",
    "cls.",
    "os.",
    "sys.",
    "process.",
    "ci.step.",
    "telemetry.",
    "logger.",
    "log.",
    "mcp.",
    "uvicorn.",
    "httpx.",
    "httpx2.",
)

_COMMON_PROPERTY_SUFFIXES = {
    "name",
    "email",
    "actor",
    "pid",
    "group",
    "security",
    "docs",
    "ping",
    "call",
    "run",
    "post",
    "collection",
    "sdk",
    "executable",
    "runtime",
}


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

    # 1. Standard source code, documentation, template, script, and config extensions
    if any(clean.endswith(ext) for ext in _COMMON_FILE_EXTENSIONS):
        return True

    exact_names, all_paths = _get_workspace_filenames(str(Path.cwd().resolve()))

    # 2. Exact match against any filename or relative path across workspace
    if clean in exact_names:
        return True

    # 3. Match as a substring of a filename in workspace file tree
    for path_str in all_paths:
        if clean == path_str or clean in path_str.split("/"):
            return True
        if "." in clean and (path_str.endswith("/" + clean) or path_str.endswith(clean)):
            return True

    target_path = Path(clean)

    # 4. Direct or cwd-relative filesystem existence
    if target_path.is_file() or (Path.cwd() / target_path).is_file():
        return True

    # 5. Source file relative existence
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
    if clean_lower.startswith(_CODE_CONFIG_PREFIXES):
        return True

    parts = clean.split(".")
    if len(parts) < 2:
        return True

    first_seg = parts[0].lower()
    last_seg = parts[-1].lower()

    # Standard Python keywords and builtins (e.g. dir(builtins))
    builtin_names = set(dir(builtins))
    stdlib_names = getattr(sys, "stdlib_module_names", set()) | set(sys.builtin_module_names)

    # If first segment is a language keyword or stdlib root module (e.g. subprocess.run, os.path)
    if keyword.iskeyword(first_seg) or first_seg in stdlib_names:
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

    # If the TLD suffix or domain is a programmatic identifier and not a standard web domain suffix
    if ext.suffix.lower() in _COMMON_PROPERTY_SUFFIXES and ext.suffix.lower() not in (
        "com",
        "org",
        "net",
        "io",
        "dev",
        "app",
        "gov",
        "edu",
        "info",
        "co",
        "me",
    ):
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
        or registered in _EXCLUDED_PUBLIC_REGISTRIES
        or fqdn in _RESERVED_DOMAINS
        or fqdn in _EXCLUDED_PUBLIC_REGISTRIES
        or any(fqdn.endswith("." + exc) for exc in _RESERVED_DOMAINS | _EXCLUDED_PUBLIC_REGISTRIES)
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
    if path_lower.endswith(_PACKAGE_ARCHIVE_EXTENSIONS):
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
    clean_token: str, source_file: str, line_idx: int, include_local: bool
) -> NetworkReference | None:
    """Parse and validate URL network reference."""
    if not clean_token.lower().startswith(("http://", "https://", "ftp://")):
        return None
    try:
        parsed = urllib.parse.urlsplit(clean_token)
        if not (parsed.scheme in ("http", "https") and parsed.netloc):
            return None
        host = (parsed.hostname or "").lower()
        if is_package_repository_asset(clean_token, host):
            return None
        is_local_host = is_private_or_local_ip(host) or is_local_or_reserved_domain(host)
        if is_local_host and not include_local:
            return None
        return NetworkReference(
            target=clean_token,
            reference_type="url",
            source_file=source_file,
            line_number=line_idx,
            is_local=is_local_host,
            scope="local" if is_local_host else "external",
            security_status="✓ Safe (Local)" if is_local_host else "✓ Safe",
        )
    except ValueError:
        return None


def _extract_ip_reference(
    clean_token: str, source_file: str, line_idx: int, include_local: bool
) -> NetworkReference | None:
    """Parse and validate IP address network reference."""
    try:
        ip = ipaddress.ip_address(clean_token)
        ip_str = str(ip)
        if is_public_ip(clean_token):
            return NetworkReference(
                target=ip_str,
                reference_type="ip",
                source_file=source_file,
                line_number=line_idx,
                is_local=False,
                scope="external",
                security_status="✓ Safe",
            )
        if is_private_or_local_ip(clean_token) and include_local:
            return NetworkReference(
                target=ip_str,
                reference_type="ip",
                source_file=source_file,
                line_number=line_idx,
                is_local=True,
                scope="local",
                security_status="✓ Safe (Local)",
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
) -> NetworkReference | None:
    """Parse and validate domain/hostname network reference."""
    if not (
        "." in clean_token
        and "/" not in clean_token
        and "\\" not in clean_token
        and "@" not in clean_token
        and "$" not in clean_token
        and "=" not in clean_token
    ):
        return None

    domain_candidate = clean_token.lower()

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
            scope="external",
            security_status="✓ Safe",
        )

    return None


def extract_network_references(
    content: str, source_file: str = "", include_local: bool = True
) -> list[NetworkReference]:
    """Extract external and local network references (IPs, URLs, and domains) from source code."""
    results: list[NetworkReference] = []
    seen: set[str] = set()

    # Skip lockfiles and ignore files whose packages are checked by dependency scans
    if is_lockfile_or_ignore_file(source_file):
        return []

    target_segments = _get_target_segments(content, source_file)

    for text_segment, line_idx in target_segments:
        tokens = re.split(r"""[\s"'`<>()[\]{}]+""", text_segment)

        for token in tokens:
            if not token:
                continue

            clean_token = token.strip(".,;:\"'`<>()[]{}")
            if not clean_token:
                continue

            # 1. URL Reference
            url_ref = _extract_url_reference(clean_token, source_file, line_idx, include_local)
            if url_ref:
                if url_ref.target not in seen:
                    seen.add(url_ref.target)
                    results.append(url_ref)
                continue

            # 2. IP Address Reference
            ip_ref = _extract_ip_reference(clean_token, source_file, line_idx, include_local)
            if ip_ref:
                if ip_ref.target not in seen:
                    seen.add(ip_ref.target)
                    results.append(ip_ref)
                continue

            # 3. Domain Reference
            dom_ref = _extract_domain_reference(
                clean_token, text_segment, source_file, line_idx, include_local
            )
            if dom_ref:
                if dom_ref.target not in seen:
                    seen.add(dom_ref.target)
                    results.append(dom_ref)

    return results


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
