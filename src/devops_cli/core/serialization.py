"""Serialization, structured data parsing, and markdown block extraction utilities."""

from __future__ import annotations

import json
import re
from typing import Any

_MARKDOWN_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```")
_JSON_UNSET = object()


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

    # 2. Try direct JSON parsing
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # 3. Try bracket extraction heuristic ({...} or [...])
    start_brace = clean_text.find("{")
    end_brace = clean_text.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        candidate = clean_text[start_brace : end_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    start_bracket = clean_text.find("[")
    end_bracket = clean_text.rfind("]")
    if start_bracket != -1 and end_bracket > start_bracket:
        candidate = clean_text[start_bracket : end_bracket + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 4. Fallback to json_repair if available
    try:
        import json_repair

        repaired = json_repair.loads(clean_text)
        if repaired != "" and repaired is not None and not isinstance(repaired, str):
            return repaired
    except Exception:
        pass

    if default is not _JSON_UNSET:
        return default
    raise ValueError(f"Could not extract valid JSON from input text: {clean_text[:100]!r}")
