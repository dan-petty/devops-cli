"""Structural metadata extraction for source code, configuration, and documentation."""

from __future__ import annotations

import ast
import re
from typing import Any

# Patterns indicating security-sensitive operations in code/manifests
_SECURITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "crypto": re.compile(
        r"(?:crypto|aes|rsa|ed25519|sha256|hmac|tls|ssl|certificate|cipher|encrypt|decrypt)",
        re.IGNORECASE,
    ),
    "network": re.compile(
        r"(?:httpx|requests|fetch|socket|grpc|websocket|listen|connect|bind|port|curl|endpoint)",
        re.IGNORECASE,
    ),
    "auth": re.compile(
        r"(?:jwt|token|bearer|oauth|password|authenticate|login|session|permission|role|rbac)",
        re.IGNORECASE,
    ),
    "secrets": re.compile(
        r"(?:keyring|secret|api_key|private_key|credential|vault)",
        re.IGNORECASE,
    ),
    "db": re.compile(
        r"(?:sql|select|insert|update|delete|database|postgres|mysql|sqlite|qdrant|redis|valkey|asyncpg|pg)",
        re.IGNORECASE,
    ),
    "fs": re.compile(
        r"(?:open|read_text|write_text|mkdir|unlink|rmdir|shutil|pathlib|os\.path)",
        re.IGNORECASE,
    ),
    "iam": re.compile(
        r"(?:ClusterRole|RoleBinding|ServiceAccount|Policy|Capability|Privileged|SecurityContext)",
        re.IGNORECASE,
    ),
}

_IMPORT_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))", re.MULTILINE
    ),
    "go": re.compile(r'^\s*(?:import\s+"([^"]+)"|"([^"]+)")', re.MULTILINE),
    "rust": re.compile(r"^use\s+([A-Za-z0-9_:]+)", re.MULTILINE),
    "typescript": re.compile(
        r'(?:import\s+.*?from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\))', re.MULTILINE
    ),
    "javascript": re.compile(
        r'(?:import\s+.*?from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\))', re.MULTILINE
    ),
    "java": re.compile(r"^import\s+([A-Za-z0-9_.]+);", re.MULTILINE),
    "cpp": re.compile(r'^#include\s+[<"]([^>"]+)[>"]', re.MULTILINE),
    "c": re.compile(r'^#include\s+[<"]([^>"]+)[>"]', re.MULTILINE),
    "terraform": re.compile(r'^\s*(?:source\s*=\s*"([^"]+)")', re.MULTILINE),
}


def extract_security_tags(content: str) -> list[str]:
    """Scan content and return matching security sensitivity tags."""
    tags: list[str] = []
    for tag_name, pattern in _SECURITY_PATTERNS.items():
        if pattern.search(content):
            tags.append(tag_name)
    return sorted(tags)


def extract_imports(content: str, language: str) -> list[str]:
    """Extract imported modules or dependencies from source code."""
    lang_key = language.lower()
    if lang_key.startswith("python") or lang_key == "py":
        try:
            tree = ast.parse(content)
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            return sorted(set(imports))
        except Exception:
            pass

    pattern = _IMPORT_PATTERNS.get(lang_key)
    if not pattern:
        return []

    results: set[str] = set()
    for match in pattern.finditer(content):
        for group in match.groups():
            if group:
                clean = group.strip()
                if clean:
                    results.add(clean)
    return sorted(results)


def extract_doc_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML/TOML frontmatter from Markdown or documentation files."""
    frontmatter: dict[str, Any] = {}
    if not content.startswith("---"):
        return frontmatter

    lines = content.splitlines()
    end_idx = -1
    for idx, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = idx
            break

    if end_idx > 0:
        f_lines = lines[1:end_idx]
        for line in f_lines:
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    frontmatter[k] = v

    return frontmatter


def extract_code_metadata(
    content: str,
    language: str,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Generate comprehensive structured metadata for a code chunk."""
    meta: dict[str, Any] = {
        "line_count": len(content.splitlines()),
        "char_count": len(content),
        "security_tags": extract_security_tags(content),
        "imports": extract_imports(content, language)[:15],
    }
    if symbols:
        meta["symbols_count"] = len(symbols)
    return meta


def extract_doc_metadata(
    content: str,
    section_path: list[str] | None = None,
) -> dict[str, Any]:
    """Generate comprehensive structured metadata for a documentation chunk."""
    frontmatter = extract_doc_frontmatter(content)
    meta: dict[str, Any] = {
        "line_count": len(content.splitlines()),
        "char_count": len(content),
        "security_tags": extract_security_tags(content),
        "frontmatter": frontmatter,
    }
    if section_path:
        meta["depth"] = len(section_path)
        meta["root_section"] = section_path[0]
        meta["leaf_section"] = section_path[-1]
    return meta
