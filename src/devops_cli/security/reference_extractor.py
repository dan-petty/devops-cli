"""Extractors for software dependencies (manifests) and network references (IPs, URLs, domains)."""

from __future__ import annotations

import ipaddress
import json
import logging
import mimetypes
import re
from pathlib import Path

import tldextract

from devops_cli.models.vulnerability import DependencySpec, NetworkReference

logger = logging.getLogger(__name__)

# Ensure standard MIME types are initialized from system/python registry
mimetypes.init()

_TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=None)

# Regular expressions for network reference extraction
_IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL_REGEX = re.compile(r"https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+(?::\d+)?(?:/[^\s\"'<>()]*)?")
_DOMAIN_REGEX = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")

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

_KNOWN_FILE_EXTENSIONS = {
    "in",
    "out",
    "lock",
    "env",
    "example",
    "sample",
    "template",
    "spec",
    "test",
    "log",
    "tmp",
    "bak",
    "py",
    "ts",
    "js",
    "json",
    "yaml",
    "yml",
    "toml",
    "md",
    "rst",
    "txt",
    "sh",
    "bash",
    "zsh",
    "c",
    "h",
    "cpp",
    "go",
    "rs",
    "java",
    "html",
    "css",
    "xml",
    "csv",
    "tsv",
    "svg",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "ico",
    "woff",
    "woff2",
    "ttf",
    "eot",
    "pdf",
    "zip",
    "tar",
    "gz",
    "tgz",
    "tf",
    "tfvars",
    "hcl",
    "proto",
    "sql",
    "graphql",
    "gql",
    "dockerfile",
    "containerfile",
}

# Common code methods, properties, and config keywords that collide with TLDs
_CODE_PROPERTY_SUFFIXES = {
    "run",
    "group",
    "host",
    "email",
    "in",
    "out",
    "get",
    "set",
    "main",
    "init",
    "start",
    "stop",
    "test",
    "mock",
    "patch",
    "runner",
    "pipeline",
    "agent",
    "agents",
    "command",
    "commands",
    "submodule",
    "module",
    "package",
    "class",
    "func",
    "function",
    "attr",
    "method",
    "coverage",
    "table",
    "record",
    "parser",
    "validator",
    "handler",
    "manager",
}

# Local variable, module, and runtime keywords that never start public domain hostnames
_LOCAL_VARIABLE_PREFIXES = {
    "self",
    "cls",
    "this",
    "m",
    "re",
    "os",
    "sys",
    "subprocess",
    "commands",
    "tool",
    "coverage",
    "user",
    "config",
    "git",
    "pytest",
    "unittest",
    "requirements",
    "temp",
    "args",
    "kwargs",
    "params",
}

# Programming language source code extensions where bare domain extraction
# requires string/comment context
_CODE_FILE_EXTENSIONS = {
    ".py",
    ".ts",
    ".js",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".rb",
    ".php",
    ".sh",
    ".bash",
    ".zsh",
    ".scala",
    ".kt",
    ".swift",
}

_STRING_OR_COMMENT_REGEX = re.compile(
    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\r\n]*|//[^\r\n]*|/\*[\s\S]*?\*/)"""
)

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
        return ip.is_global
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
            or src_name.endswith(".txt")
            or src_name in ("package-lock.json", "cargo.lock", "poetry.lock")
        ):
            return True

    suffix = Path(target_clean).suffix.lower().lstrip(".")
    if suffix in _KNOWN_FILE_EXTENSIONS:
        return True

    # If the target has a valid public suffix domain, it is a domain, not a file
    ext = _TLD_EXTRACTOR(target_clean)
    if ext.domain and ext.suffix and ext.suffix.lower() not in _KNOWN_FILE_EXTENSIONS:
        return False

    # Standard library mimetypes check
    mime, _ = mimetypes.guess_type(target_clean)
    if mime is not None and mime not in (
        "application/x-msdos-program",
        "application/x-msdownload",
        "application/x-sh",
    ):
        return True

    if f".{suffix}" in mimetypes.types_map and suffix not in ("com", "sh", "org", "net"):
        return True

    return False


def is_network_domain(target: str, source_file: str = "") -> bool:
    """Validate whether target string is a legitimate public network domain using tldextract,
    urllib, and ipaddress.
    """
    if is_file_reference(target, source_file=source_file):
        return False

    if "/" in target or "\\" in target or ":" in target or "_" in target or " " in target:
        return False

    ext = _TLD_EXTRACTOR(target)
    if not ext.domain or not ext.suffix:
        return False

    suffix = ext.suffix.lower()
    domain = ext.domain.lower()
    fqdn = ext.fqdn.lower()
    registered = f"{domain}.{suffix}"

    # Reject code method / property suffix collisions (e.g. .run, .group, .host, .email, .in)
    if suffix in _CODE_PROPERTY_SUFFIXES:
        return False

    # Reject local variable prefixes on subdomain or domain
    subdomain_parts = [p.lower() for p in ext.subdomain.split(".") if p]
    if subdomain_parts and subdomain_parts[0] in _LOCAL_VARIABLE_PREFIXES:
        return False
    if not subdomain_parts and domain in _LOCAL_VARIABLE_PREFIXES:
        return False

    # Multi-segment code paths (e.g. commands.workspace.subprocess.run or ai.agents.pipeline)
    if subdomain_parts and any(p in _LOCAL_VARIABLE_PREFIXES for p in subdomain_parts):
        return False

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
        return ip.is_global
    except ValueError:
        pass

    return True


def extract_network_references(content: str, source_file: str = "") -> list[NetworkReference]:
    """Extract external IPs, URLs, and public domains from documentation or source code."""
    results: list[NetworkReference] = []
    seen: set[str] = set()
    src_suffix = Path(source_file).suffix.lower() if source_file else ""
    is_code_file = src_suffix in _CODE_FILE_EXTENSIONS

    for line_idx, line in enumerate(content.splitlines(), 1):
        stripped_line = line.strip()

        # Skip TOML section headers, e.g. [tool.coverage.run]
        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            continue

        # 1. Extract URLs
        for match in _URL_REGEX.finditer(line):
            url = match.group(0).rstrip(".,;)>]\"'")
            if url not in seen:
                seen.add(url)
                results.append(
                    NetworkReference(
                        target=url,
                        reference_type="url",
                        source_file=source_file,
                        line_number=line_idx,
                    )
                )

        # 2. Extract Public IPs
        for match in _IP_REGEX.finditer(line):
            ip = match.group(0)
            if is_public_ip(ip) and ip not in seen:
                seen.add(ip)
                results.append(
                    NetworkReference(
                        target=ip,
                        reference_type="ip",
                        source_file=source_file,
                        line_number=line_idx,
                    )
                )

        # 3. Extract External Domains
        # In code and config files, only search inside string literals or comments
        target_texts: list[str] = []
        if is_code_file:
            target_texts = [m.group(0) for m in _STRING_OR_COMMENT_REGEX.finditer(line)]
        else:
            target_texts = [line]

        for text_segment in target_texts:
            for match in _DOMAIN_REGEX.finditer(text_segment):
                # Disregard function / method calls followed immediately by parentheses
                if match.end() < len(text_segment) and text_segment[match.end()] == "(":
                    continue

                domain = match.group(0).lower().rstrip(".,;)>]\"'")
                if (
                    domain not in seen
                    and "/" not in text_segment[max(0, match.start() - 1) : match.end() + 1]
                    and "\\" not in text_segment[max(0, match.start() - 1) : match.end() + 1]
                    and is_network_domain(domain, source_file=source_file)
                ):
                    seen.add(domain)
                    results.append(
                        NetworkReference(
                            target=domain,
                            reference_type="domain",
                            source_file=source_file,
                            line_number=line_idx,
                        )
                    )

    return results


def extract_dependencies_from_text(content: str, file_name: str) -> list[DependencySpec]:
    """Extract dependency specifications from manifest file content."""
    deps: list[DependencySpec] = []
    name_lower = Path(file_name).name.lower()

    if name_lower in ("requirements.txt", "requirements-dev.txt", "requirements.in"):
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # e.g. pydantic>=2.0.0 or requests==2.31.0
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
            import tomllib

            data = tomllib.loads(content)
            proj_deps = data.get("project", {}).get("dependencies", [])
            for dep_str in proj_deps:
                parts = re.split(r"([=><~^!]+.*)", dep_str, maxsplit=1)
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
        except Exception:
            pass

    elif name_lower == "package.json":
        try:
            data = json.loads(content)
            all_deps: dict[str, str] = {}
            if "dependencies" in data and isinstance(data["dependencies"], dict):
                all_deps.update(data["dependencies"])
            if "devDependencies" in data and isinstance(data["devDependencies"], dict):
                all_deps.update(data["devDependencies"])
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
        # Basic Cargo.toml parser
        in_deps = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[dependencies]") or line.startswith("[dev-dependencies]"):
                in_deps = True
                continue
            if line.startswith("[") and in_deps:
                in_deps = False
                continue
            if in_deps and "=" in line and not line.startswith("#"):
                parts = line.split("=", 1)
                pkg = parts[0].strip()
                ver = parts[1].strip().strip('"').strip("'")
                deps.append(
                    DependencySpec(
                        name=pkg,
                        version_range=ver,
                        ecosystem="crates.io",
                        source_file=file_name,
                    )
                )

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
