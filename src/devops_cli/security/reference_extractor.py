"""Extractors for software dependencies (manifests) and network references (IPs, URLs, domains)."""

from __future__ import annotations

import ast
import io
import ipaddress
import json
import logging
import mimetypes
import re
import textwrap
import tokenize
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any

import tldextract
import yaml
from packaging.requirements import InvalidRequirement, Requirement

from devops_cli.models.vulnerability import DependencySpec, NetworkReference

logger = logging.getLogger(__name__)

# Ensure standard MIME types are initialized from system/python registry
mimetypes.init()

_TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=None)

# Regular expressions for text token extraction
_IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL_REGEX = re.compile(r"https?://[^\s\"'<>`()\[\]{}]+", re.IGNORECASE)
_DOMAIN_REGEX = re.compile(
    r"(?<![a-zA-Z0-9_.@/\\-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?![a-zA-Z0-9_.@/\\-])"
)
_HOSTNAME_REGEX = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
_HCL_STRING_OR_COMMENT_REGEX = re.compile(
    r"""(?:"(?:\\.|[^"\\])*"|#[^\r\n]*|//[^\r\n]*|/\*[\s\S]*?\*/)"""
)

# Standard RFC 2606 and RFC 6761 reserved domain suffixes and public infra endpoints
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

_EXCLUDED_DOMAINS = {
    "schema.org",
    "w3.org",
    "json-schema.org",
    "github.com",
    "gitlab.com",
    "pypi.org",
    "npmjs.com",
    "crates.io",
    "golang.org",
    "google.com",
    "osv.dev",
    "nist.gov",
    "shodan.io",
    "cloudflare.com",
}

_PRIMARY_WEB_TLDS = {
    "com",
    "org",
    "net",
    "io",
    "co",
    "app",
    "dev",
    "cloud",
    "gov",
    "edu",
    "mil",
    "int",
    "ai",
}

_KNOWN_NON_DOMAIN_EXTENSIONS = {
    "in",
    "out",
    "lock",
    "env",
    "example",
    "sample",
    "template",
    "spec",
    "log",
    "tmp",
    "bak",
}

__all__ = [
    "extract_dependencies_from_text",
    "extract_network_references",
    "is_file_reference",
    "is_network_domain",
    "is_public_ip",
]


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


def is_file_reference(target: str, source_file: str = "") -> bool:
    """Check if target string represents a local file path, manifest item, or standard
    file format.
    """
    target_clean = target.strip()
    if "/" in target_clean or "\\" in target_clean:
        return True

    # Check local filesystem existence
    if Path(target_clean).exists() or (Path.cwd() / target_clean).exists():
        return True

    # Ignore and lock files context check
    if source_file:
        src_name = Path(source_file).name.lower()
        if (
            src_name.endswith("ignore")
            or src_name.endswith(".lock")
            or src_name in ("package-lock.json", "cargo.lock", "poetry.lock")
        ):
            return True

    suffix = Path(target_clean).suffix.lower().lstrip(".")
    if suffix in _KNOWN_NON_DOMAIN_EXTENSIONS:
        return True

    ext = _TLD_EXTRACTOR(target_clean)
    if not ext.domain or not ext.suffix:
        return True

    # Multi-level FQDN or primary web TLD indicates a domain, not a file
    if ext.subdomain or ext.suffix in _PRIMARY_WEB_TLDS:
        return False

    # Standard library mimetypes check
    mime, _ = mimetypes.guess_type(target_clean)
    if mime is not None and mime not in (
        "application/x-msdos-program",
        "application/x-msdownload",
        "application/x-sh",
    ):
        return True

    return False


def is_network_domain(target: str, source_file: str = "") -> bool:
    """Validate whether target string is a legitimate public network domain using tldextract,
    mimetypes, and ipaddress.
    """
    target_clean = target.strip().rstrip(".,;)>]\"'")
    if "_" in target_clean or not _HOSTNAME_REGEX.match(target_clean):
        return False

    if is_file_reference(target_clean, source_file=source_file):
        return False

    ext = _TLD_EXTRACTOR(target_clean)
    if not ext.domain or not ext.suffix:
        return False

    suffix = ext.suffix.lower()
    domain = ext.domain.lower()
    fqdn = ext.fqdn.lower()
    registered = f"{domain}.{suffix}"

    # Check against RFC reserved and excluded domains
    if (
        registered in _RESERVED_DOMAINS
        or registered in _EXCLUDED_DOMAINS
        or fqdn in _RESERVED_DOMAINS
        or fqdn in _EXCLUDED_DOMAINS
        or any(fqdn.endswith("." + exc) for exc in _RESERVED_DOMAINS | _EXCLUDED_DOMAINS)
    ):
        return False

    try:
        ip = ipaddress.ip_address(fqdn)
        return is_public_ip(str(ip))
    except ValueError:
        pass

    return True


def _extract_python_literals_and_comments(content: str) -> list[tuple[str, int]]:
    """Extract string constants and comments from Python source code via AST and tokenize."""
    literals: list[tuple[str, int]] = []
    source = textwrap.dedent(content)
    # 1. AST string constants & docstrings
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                line = getattr(node, "lineno", 1)
                literals.append((node.value, line))
    except (SyntaxError, IndentationError):
        pass

    # 2. Tokenize comments
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                comment_text = tok.string.lstrip("#").strip()
                if comment_text:
                    literals.append((comment_text, tok.start[0]))
    except (tokenize.TokenError, IndentationError):
        pass

    return literals


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
    data: Any, out: list[tuple[str, int]], default_line: int = 1, is_yaml: bool = False
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


def _extract_json_strings(content: str) -> list[tuple[str, int]]:
    """Extract all string scalar values from valid JSON content."""
    strings: list[tuple[str, int]] = []
    try:
        data = json.loads(content)
        _collect_scalar_strings(data, strings, is_yaml=False)
    except Exception:
        pass
    return strings


def _extract_toml_strings(content: str) -> list[tuple[str, int]]:
    """Extract all string scalar values from valid TOML content."""
    strings: list[tuple[str, int]] = []
    try:
        data = tomllib.loads(content)
        _collect_scalar_strings(data, strings, is_yaml=False)
    except Exception:
        pass
    return strings


def _extract_yaml_strings(content: str) -> list[tuple[str, int]]:
    """Extract all string scalar values from YAML content."""
    strings: list[tuple[str, int]] = []
    try:
        data = yaml.safe_load(content)
        _collect_scalar_strings(data, strings, is_yaml=True)
    except Exception:
        pass
    return strings


def _get_target_segments(content: str, source_file: str) -> list[tuple[str, int]]:
    """Determine text segments to analyze based on source file syntax."""
    suffix = Path(source_file).suffix.lower() if source_file else ""

    if suffix == ".py":
        return _extract_python_literals_and_comments(content)

    if suffix in (".tf", ".tfvars", ".hcl"):
        return _extract_hcl_literals_and_comments(content)

    if suffix == ".json":
        return _extract_json_strings(content)

    if suffix == ".toml":
        return _extract_toml_strings(content)

    if suffix in (".yaml", ".yml"):
        return _extract_yaml_strings(content)

    # Fallback to line-by-line scanning for markdown, text, or unparseable files
    return [(line, line_idx) for line_idx, line in enumerate(content.splitlines(), 1)]


def extract_network_references(content: str, source_file: str = "") -> list[NetworkReference]:
    """Extract external IPs, URLs, and public domains from documentation or source code."""
    results: list[NetworkReference] = []
    seen: set[str] = set()

    # Skip files that only list filenames or patterns
    if source_file:
        src_name = Path(source_file).name.lower()
        if src_name.endswith("ignore") or src_name in (
            "package-lock.json",
            "cargo.lock",
            "poetry.lock",
        ):
            return []

    target_segments = _get_target_segments(content, source_file)

    for text_segment, line_idx in target_segments:
        # 1. Extract URLs with RFC validation
        for match in _URL_REGEX.finditer(text_segment):
            raw_url = match.group(0).rstrip(".,;)>]\"'")
            try:
                parsed = urllib.parse.urlsplit(raw_url)
                if parsed.scheme in ("http", "https") and parsed.netloc and raw_url not in seen:
                    seen.add(raw_url)
                    results.append(
                        NetworkReference(
                            target=raw_url,
                            reference_type="url",
                            source_file=source_file,
                            line_number=line_idx,
                        )
                    )
            except ValueError:
                pass

        # 2. Extract Public IPs
        for match in _IP_REGEX.finditer(text_segment):
            ip_candidate = match.group(0)
            if is_public_ip(ip_candidate) and ip_candidate not in seen:
                seen.add(ip_candidate)
                results.append(
                    NetworkReference(
                        target=ip_candidate,
                        reference_type="ip",
                        source_file=source_file,
                        line_number=line_idx,
                    )
                )

        # 3. Extract External Domains
        for match in _DOMAIN_REGEX.finditer(text_segment):
            domain_candidate = match.group(0).lower().rstrip(".,;)>]\"'")
            if (
                domain_candidate not in seen
                and "/"
                not in text_segment[
                    max(0, match.start() - 1) : min(len(text_segment), match.end() + 1)
                ]
                and is_network_domain(domain_candidate, source_file=source_file)
            ):
                seen.add(domain_candidate)
                results.append(
                    NetworkReference(
                        target=domain_candidate,
                        reference_type="domain",
                        source_file=source_file,
                        line_number=line_idx,
                    )
                )

    return results


def extract_dependencies_from_text(content: str, file_name: str) -> list[DependencySpec]:
    """Extract dependency specifications from manifest file content using standard parsers."""
    deps: list[DependencySpec] = []
    name_lower = Path(file_name).name.lower()

    if name_lower in ("requirements.txt", "requirements-dev.txt", "requirements.in"):
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
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
                    )
                )
            except InvalidRequirement:
                # Fallback to robust token split for non-standard legacy entries
                parts = re.split(r"([=><~^!]+.*)", line, maxsplit=1)
                pkg_name = parts[0].strip()
                version_spec = parts[1].strip() if len(parts) > 1 else "*"
                if pkg_name:
                    deps.append(
                        DependencySpec(
                            name=pkg_name,
                            version_range=version_spec,
                            ecosystem="PyPI",
                            source_file=file_name,
                        )
                    )

    elif name_lower == "pyproject.toml":
        try:
            data = tomllib.loads(content)
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

            for req_str in req_strings:
                try:
                    req = Requirement(req_str)
                    deps.append(
                        DependencySpec(
                            name=req.name,
                            version_range=str(req.specifier) if str(req.specifier) else "*",
                            ecosystem="PyPI",
                            source_file=file_name,
                        )
                    )
                except InvalidRequirement:
                    pass
        except Exception:
            pass

    elif name_lower == "package.json":
        try:
            data = json.loads(content)
            all_deps: dict[str, str] = {}
            for section in (
                "dependencies",
                "devDependencies",
                "peerDependencies",
                "optionalDependencies",
            ):
                if section in data and isinstance(data[section], dict):
                    all_deps.update(data[section])
            for pkg, ver in all_deps.items():
                deps.append(
                    DependencySpec(
                        name=pkg,
                        version_range=str(ver),
                        ecosystem="npm",
                        source_file=file_name,
                    )
                )
        except Exception:
            pass

    elif name_lower == "cargo.toml":
        try:
            data = tomllib.loads(content)
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                table = data.get(section, {})
                if isinstance(table, dict):
                    for pkg, ver_data in table.items():
                        ver_str = (
                            ver_data
                            if isinstance(ver_data, str)
                            else ver_data.get("version", "*")
                            if isinstance(ver_data, dict)
                            else "*"
                        )
                        deps.append(
                            DependencySpec(
                                name=pkg,
                                version_range=str(ver_str),
                                ecosystem="crates.io",
                                source_file=file_name,
                            )
                        )
        except Exception:
            pass

    elif name_lower == "go.mod":
        in_require = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("require ("):
                in_require = True
                continue
            if line == ")" and in_require:
                in_require = False
                continue
            if in_require and line and not line.startswith("//"):
                parts = line.split()
                if len(parts) >= 2:
                    deps.append(
                        DependencySpec(
                            name=parts[0],
                            version_range=parts[1],
                            ecosystem="Go",
                            source_file=file_name,
                        )
                    )
            elif line.startswith("require ") and not in_require:
                parts = line.removeprefix("require ").strip().split()
                if len(parts) >= 2:
                    deps.append(
                        DependencySpec(
                            name=parts[0],
                            version_range=parts[1],
                            ecosystem="Go",
                            source_file=file_name,
                        )
                    )

    return deps
