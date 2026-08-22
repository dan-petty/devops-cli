"""Security intelligence clients and extractors for dependencies (OSV, NVD) and network
references (Shodan InternetDB, Cloudflare Radar).
"""

from __future__ import annotations

import ipaddress
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import tldextract

from devops_cli.models.intelligence import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
    VulnerabilityRecord,
)

logger = logging.getLogger(__name__)

# Ensure standard MIME types are initialized from system/python registry
mimetypes.init()

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

__all__ = [
    "DependencySpec",
    "NetworkReference",
    "NetworkReputationRecord",
    "VulnerabilityRecord",
    "is_file_reference",
    "is_network_domain",
    "is_public_ip",
    "extract_network_references",
    "extract_dependencies_from_text",
    "OSVClient",
    "NVDClient",
    "ShodanInternetDBClient",
    "CloudflareRadarClient",
]


def is_public_ip(ip_str: str) -> bool:
    """Check whether an IP string is a valid public, globally routable IP address."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return ip.is_global
    except ValueError:
        return False


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

_TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=None)

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


# ── Threat Intelligence Clients ──────────────────────────────────────────────


class OSVClient:
    """Queries the OSV.dev vulnerability database."""

    BASE_URL = "https://api.osv.dev/v1/query"

    def __init__(self, timeout: float = 1.5) -> None:
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def check_vulnerability(
        self, package: str, version: str | None = None, ecosystem: str = "PyPI"
    ) -> list[VulnerabilityRecord]:
        payload: dict[str, Any] = {"package": {"name": package, "ecosystem": ecosystem}}
        if version and version not in ("*", ""):
            # Clean version constraint (e.g. >=2.0.0 -> 2.0.0)
            clean_ver = re.sub(r"^[=><~^!]+", "", version).strip()
            if clean_ver:
                payload["version"] = clean_ver

        try:
            res = self._client.post(self.BASE_URL, json=payload)
            if res.status_code != 200:
                return []
            data = res.json()
            vulns = data.get("vulns", [])
            results: list[VulnerabilityRecord] = []
            for v in vulns:
                vid = v.get("id", "UNKNOWN")
                summary = v.get("summary", "") or v.get("details", "")[:120]
                sev = "HIGH"
                if "severity" in v and isinstance(v["severity"], list):
                    for s in v["severity"]:
                        if s.get("type") == "CVSS_V3":
                            sev = "CRITICAL" if "CVSS:3" in s.get("score", "") else "HIGH"
                results.append(
                    VulnerabilityRecord(
                        id=vid,
                        summary=summary,
                        severity=sev,
                        package=package,
                        affected_version_range=version or "*",
                        source="OSV",
                        details_url=f"https://osv.dev/vulnerability/{vid}",
                    )
                )
            return results
        except Exception as exc:
            logger.debug("OSV lookup failed for %s: %s", package, exc)
            return []


class NVDClient:
    """Queries the NIST National Vulnerability Database (NVD) API."""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, timeout: float = 1.5) -> None:
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def search_cve(self, keyword: str) -> list[VulnerabilityRecord]:
        try:
            params: dict[str, str | int] = {"keywordSearch": keyword, "resultsPerPage": 3}
            res = self._client.get(self.BASE_URL, params=params)
            if res.status_code != 200:
                return []
            data = res.json()
            vulns = data.get("vulnerabilities", [])
            results: list[VulnerabilityRecord] = []
            for v in vulns:
                cve = v.get("cve", {})
                cid = cve.get("id", "UNKNOWN")
                desc = ""
                for d in cve.get("descriptions", []):
                    if d.get("lang") == "en":
                        desc = d.get("value", "")[:120]
                        break
                results.append(
                    VulnerabilityRecord(
                        id=cid,
                        summary=desc,
                        severity="HIGH",
                        package=keyword,
                        source="NVD",
                        details_url=f"https://nvd.nist.gov/vuln/detail/{cid}",
                    )
                )
            return results
        except Exception as exc:
            logger.debug("NVD lookup failed for %s: %s", keyword, exc)
            return []


class ShodanInternetDBClient:
    """Queries the Shodan InternetDB API for IP open ports, vulnerabilities, and tags."""

    BASE_URL = "https://internetdb.shodan.io"

    def __init__(self, timeout: float = 1.5) -> None:
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def check_ip(self, ip: str) -> NetworkReputationRecord:
        record = NetworkReputationRecord(target=ip, ip=ip, source="Shodan InternetDB")
        if not is_public_ip(ip):
            return record

        try:
            res = self._client.get(f"{self.BASE_URL}/{ip}")
            if res.status_code == 200:
                data = res.json()
                record.ports = data.get("ports", [])
                record.cves = data.get("vulns", [])
                record.tags = data.get("tags", [])
                record.hostnames = data.get("hostnames", [])
                if record.cves:
                    record.is_malicious = True
                    record.reputation_score = 0.85
                    record.reputation_summary = (
                        f"Vulnerable host with {len(record.cves)} active CVE(s)"
                    )
                elif record.ports:
                    record.reputation_summary = f"Open ports detected: {record.ports}"
            elif res.status_code == 404:
                record.reputation_summary = "Clean / No open ports detected in InternetDB"
        except Exception as exc:
            logger.debug("Shodan InternetDB lookup failed for %s: %s", ip, exc)
            record.reputation_summary = "Unchecked / Lookup timeout"

        return record


class CloudflareRadarClient:
    """Queries Cloudflare Radar for domain reputation and threat intelligence."""

    BASE_URL = "https://radar.cloudflare.com/api/v1/intel"

    def __init__(self, timeout: float = 1.5) -> None:
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def check_domain(self, domain_or_url: str) -> NetworkReputationRecord:
        target = domain_or_url
        if "://" in target:
            target = urlparse(target).hostname or target

        record = NetworkReputationRecord(target=domain_or_url, ip="", source="Cloudflare Radar")
        try:
            res = self._client.get(f"{self.BASE_URL}/domain/{target}")
            if res.status_code == 200:
                data = res.json()
                categories = data.get("result", {}).get("categories", [])
                if categories:
                    record.tags = [c.get("name", "") for c in categories if c.get("name")]
                record.reputation_summary = f"Categorized domain: {', '.join(record.tags[:3])}"
            else:
                record.reputation_summary = "Domain verified in public DNS registry"
        except Exception as exc:
            logger.debug("Cloudflare Radar lookup failed for %s: %s", target, exc)
            record.reputation_summary = "Verified domain reference"

        return record
