"""Serialization, structured data parsing, and markdown block extraction utilities."""

from __future__ import annotations

import json
import re
from typing import Any, cast

import yaml

_MARKDOWN_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```")
_JSON_UNSET = object()
_JSONC_STRING_OR_COMMENT = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.DOTALL)
_YAML_VALUE_TAG = "tag:yaml.org,2002:value"


def _value_tag_as_string[LoaderT: (yaml.SafeLoader, yaml.CSafeLoader)](
    base: type[LoaderT],
) -> type[LoaderT]:
    """A subclass of the PyYAML loader `base` that reads a plain `=` as the string `"="`.

    PyYAML resolves a plain `=` to the YAML 1.1 tag `tag:yaml.org,2002:value` and has no
    constructor for it (yaml/pyyaml#89). YAML 1.2, and so Kubernetes, reads it as a string: the
    CRDs of prometheus-operator-crds hold the enum item `- =`. The constructor goes on a subclass,
    so `yaml.SafeLoader` and `yaml.CSafeLoader` stay as PyYAML ships them.
    """
    loader = cast("type[LoaderT]", type(f"ValueAsString{base.__name__}", (base,), {}))
    loader.add_constructor(_YAML_VALUE_TAG, _construct_value_as_string)
    return loader


def _construct_value_as_string(loader: yaml.SafeLoader | yaml.CSafeLoader, node: yaml.Node) -> str:
    """The text of a scalar of the value tag, as PyYAML constructs a `!!str` scalar."""
    return loader.construct_yaml_str(node)


# libyaml's loader composes several times faster than the pure-Python one, with the same nodes and
# line marks; PyYAML built without libyaml has only the latter.
YAML_SAFE_LOADER: type[yaml.SafeLoader] | type[yaml.CSafeLoader] = _value_tag_as_string(
    getattr(yaml, "CSafeLoader", yaml.SafeLoader)
)


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
