"""Serialization, structured data parsing, and markdown block extraction utilities."""

from __future__ import annotations

import json
import re
from typing import Any

_MARKDOWN_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```")
_JSON_UNSET = object()
_JSONC_STRING_OR_COMMENT = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.DOTALL)


def strip_json_comments(text: str) -> str:
    """Strip `//` and `/* */` comments from JSONC text, such as devcontainer.json.

    Strings are matched first and kept whole, so a `//` inside one -- every URL -- is not
    mistaken for the start of a comment.
    """
    return _JSONC_STRING_OR_COMMENT.sub(lambda match: match.group(1) or "", text)


def extract_json_block(text: str, *, default: Any = _JSON_UNSET) -> Any:
    """Extract and deserialize JSON from raw text, markdown code blocks, or conversational LLM output.

    Args:
        text: Raw input string containing JSON or markdown formatted JSON block.
        default: Fallback return value if JSON parsing fails.

    Returns:
        Deserialized Python structure (dict, list, etc.).

    Raises:
        ValueError: If JSON cannot be parsed and no default is provided.
    """
    clean_text = text.strip()
    if not clean_text:
        if default is not _JSON_UNSET:
            return default
        raise ValueError("Cannot extract JSON from empty string.")

    # 1. Check for markdown code fence blocks
    match = _MARKDOWN_CODEBLOCK_RE.search(clean_text)
    if match:
        block = match.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    # 2. Route through the unified repair_json seam (strict json.loads first, then json-repair)
    from devops_cli.ai.response_repair import repair_json
    from devops_cli.config.constants import CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK

    repaired, _ = repair_json(clean_text, source=CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK)
    if repaired != "" and repaired is not None and not isinstance(repaired, str):
        return repaired

    if default is not _JSON_UNSET:
        return default
    raise ValueError(f"Could not extract valid JSON from input text: {clean_text[:100]!r}")
