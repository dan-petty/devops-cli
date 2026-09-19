"""Context-aware file classification, proper file type detection, and specialized review prompts."""

from __future__ import annotations

import ast
import json
import mimetypes
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Final

import yaml

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_CODE_EXTENSIONS,
    CONST_CONFIG_EXTENSIONS,
    CONST_CONFIG_FILENAMES,
    CONST_DOC_EXTENSIONS,
    CONST_DOC_FILENAMES,
)
from devops_cli.security.sanitizer import (
    mask_secrets,
    sanitize_prompt_boundary_tags,
)

_DOCS_REVIEW_TASK = load_task_prompt("docs_review_prompt.md")
_CONFIG_REVIEW_TASK = load_task_prompt("config_review_prompt.md")
_CODE_REVIEW_TASK = load_task_prompt("code_review_prompt.md")

_DOCS_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "text/markdown",
        "text/x-rst",
        "text/plain",
        "text/asciidoc",
        "text/x-tex",
        "text/html",
    }
)

_CONFIG_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/json",
        "application/yaml",
        "application/x-yaml",
        "application/toml",
        "application/x-toml",
        "application/xml",
        "text/yaml",
        "text/x-yaml",
        "text/xml",
    }
)

_CODE_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "text/x-python",
        "application/javascript",
        "text/javascript",
        "application/typescript",
        "text/x-go",
        "text/x-rust",
        "text/x-c",
        "text/x-c++",
        "text/x-java-source",
        "application/x-sh",
        "text/x-shellscript",
        "text/x-lua",
        "text/x-sql",
    }
)


class FileContextType(StrEnum):
    """Semantic context type of a file under review."""

    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    CODE = "code"


def _classify_by_shebang_and_header(content: str) -> FileContextType | None:
    """Inspect first lines for shebangs, XML headers, or markdown titles."""
    if not content:
        return None
    lines = content.splitlines()[:5]
    if not lines:
        return None

    first_lower = lines[0].strip().lower()
    if first_lower.startswith("#!"):
        return FileContextType.CODE

    if first_lower.startswith("<?xml"):
        return FileContextType.CONFIGURATION

    if first_lower.startswith("<!doctype html") or first_lower.startswith("<html"):
        return FileContextType.DOCUMENTATION

    if first_lower.startswith("---") or first_lower.startswith("# "):
        # Check if following lines are markdown-like or YAML frontmatter
        return FileContextType.DOCUMENTATION

    return None


def _classify_by_mime(file_path: Path) -> FileContextType | None:
    """Classify file context using Python's standard library mimetypes registry."""
    mime, _ = mimetypes.guess_type(str(file_path))
    if not mime:
        return None
    mime_clean = mime.lower().split(";")[0].strip()
    if mime_clean in _DOCS_MIME_TYPES:
        return FileContextType.DOCUMENTATION
    if mime_clean in _CONFIG_MIME_TYPES:
        return FileContextType.CONFIGURATION
    if mime_clean in _CODE_MIME_TYPES:
        return FileContextType.CODE
    return None


def _is_python_code(clean: str) -> bool:
    """Check if content can be parsed as Python code with structural definitions."""
    try:
        tree = ast.parse(clean)
        return any(
            isinstance(
                n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
            )
            for n in tree.body
        )
    except SyntaxError, ValueError:
        return False


def _is_json_config(clean: str) -> bool:
    """Check if content is valid JSON dictionary or list configuration."""
    if not (clean.startswith(("{", "[")) and clean.endswith(("}", "]"))):
        return False
    try:
        data = json.loads(clean)
        return isinstance(data, (dict, list))
    except json.JSONDecodeError, ValueError:
        return False


def _is_toml_config(clean: str) -> bool:
    """Check if content is valid TOML table configuration."""
    if "[" not in clean or "=" not in clean:
        return False
    try:
        data = tomllib.loads(clean)
        return isinstance(data, dict) and bool(data)
    except Exception:
        return False


def _is_yaml_config(clean: str) -> bool:
    """Check if content is valid YAML mapping or sequence configuration."""
    if ":" not in clean or clean.startswith("#"):
        return False
    try:
        data = yaml.safe_load(clean)
        return isinstance(data, (dict, list))
    except Exception:
        return False


def _classify_by_parser(content: str) -> FileContextType | None:
    """Classify file context by attempting structural parsing (AST, JSON, YAML, TOML)."""
    clean = content.strip()
    if not clean or len(clean) > 500_000:
        return None

    if _is_python_code(clean):
        return FileContextType.CODE
    if _is_json_config(clean) or _is_toml_config(clean) or _is_yaml_config(clean):
        return FileContextType.CONFIGURATION

    return None


def _classify_by_filename_and_ext(file_path: Path) -> FileContextType:
    """Classify file context by canonical filename patterns and standard extensions."""
    name_lower = file_path.name.lower()
    suffix_lower = file_path.suffix.lower()

    if name_lower in CONST_DOC_FILENAMES or suffix_lower in CONST_DOC_EXTENSIONS:
        return FileContextType.DOCUMENTATION

    if (
        name_lower in CONST_CONFIG_FILENAMES
        or name_lower.startswith(".env")
        or suffix_lower in CONST_CONFIG_EXTENSIONS
    ):
        return FileContextType.CONFIGURATION

    if suffix_lower in CONST_CODE_EXTENSIONS:
        return FileContextType.CODE

    return FileContextType.CODE


def classify_file_context(file_path: str | Path, content: str = "") -> FileContextType:
    """Classify file into Documentation, Configuration, or Code using multi-layered detection.

    Applies shebang inspection, official MIME types, structural language parsers (Python AST,
    JSON, YAML, TOML), and canonical filename/extension mappings.
    """
    p = Path(file_path) if isinstance(file_path, str) else file_path

    by_shebang = _classify_by_shebang_and_header(content)
    if by_shebang is not None:
        return by_shebang

    by_mime = _classify_by_mime(p)
    if by_mime is not None:
        return by_mime

    by_parser = _classify_by_parser(content)
    if by_parser is not None:
        return by_parser

    return _classify_by_filename_and_ext(p)


def get_default_personas_for_context(context_type: FileContextType) -> list[str]:
    """Return specialized persona subset tailored to the file context type."""
    dispatch = {
        FileContextType.DOCUMENTATION: ["pm", "auditor"],
        FileContextType.CONFIGURATION: ["devsecops", "architect"],
        FileContextType.CODE: ["devsecops", "architect", "qa", "auditor", "pm"],
    }
    return dispatch.get(context_type, ["devsecops", "architect", "qa"])


def _escape_fences(text: str) -> str:
    """Escape triple backticks to prevent prompt injection."""
    return text.replace("```", r"\`\`\`")


def build_context_review_prompt(
    context_type: FileContextType,
    fpath: str,
    p_idx: int,
    total_pages: int,
    page_content: str,
    symbols: str = "",
    rag_context_str: str = "",
    contract_context_str: str = "",
    persona_title: str = "DevSecOps Specialist",
) -> str:
    """Construct sanitized, context-tailored review prompt for documentation, configs, or code."""
    masked = mask_secrets(page_content)
    clean = sanitize_prompt_boundary_tags(_escape_fences(masked))
    page_prefix = f" (Page {p_idx}/{total_pages})" if total_pages > 1 else ""

    if context_type == FileContextType.DOCUMENTATION:
        task_body = (
            _DOCS_REVIEW_TASK.format(target=fpath, persona=persona_title)
            if _DOCS_REVIEW_TASK
            else ""
        )
        return (
            f"Review File: {fpath} [Documentation]{page_prefix}\n\n"
            f"{task_body}\n\n"
            f"Documentation Content:\n{clean}"
        )

    if context_type == FileContextType.CONFIGURATION:
        task_body = (
            _CONFIG_REVIEW_TASK.format(target=fpath, persona=persona_title)
            if _CONFIG_REVIEW_TASK
            else ""
        )
        return (
            f"Review File: {fpath} [Configuration]{page_prefix}\n\n"
            f"{task_body}\n\n"
            f"Configuration Content:\n{clean}"
        )

    task_body = (
        _CODE_REVIEW_TASK.format(target=fpath, persona=persona_title) if _CODE_REVIEW_TASK else ""
    )
    symbols_prefix = f"Key Symbols: {symbols}\n" if symbols else ""
    return (
        f"Review File: {fpath}{page_prefix}\n"
        f"{task_body}\n\n"
        f"{symbols_prefix}{rag_context_str}{contract_context_str}\n\n"
        f"Code Content / Diff:\n{clean}"
    )
