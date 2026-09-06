"""Unit tests for markdown JSON block extraction and deserialization (TDD Specification)."""

from __future__ import annotations

import pytest

from devops_cli.core.serialization import extract_json_block


def test_extract_json_block_raw_json() -> None:
    """Extracts raw JSON object."""
    raw = '{"name": "devops", "active": true, "count": 5}'
    res = extract_json_block(raw)
    assert res == {"name": "devops", "active": True, "count": 5}


def test_extract_json_block_markdown_fence_json() -> None:
    """Extracts JSON enclosed in markdown ```json code block."""
    raw = (
        "Here is the result:\n"
        "```json\n"
        '{\n  "status": "success",\n  "code": 200\n}\n'
        "```\n"
        "Hope this helps!"
    )
    res = extract_json_block(raw)
    assert res == {"status": "success", "code": 200}


def test_extract_json_block_markdown_fence_no_lang() -> None:
    """Extracts JSON enclosed in plain ``` code block."""
    raw = '```\n["item1", "item2", "item3"]\n```'
    res = extract_json_block(raw)
    assert res == ["item1", "item2", "item3"]


def test_extract_json_block_invalid_with_default() -> None:
    """Returns default value when JSON is invalid or missing."""
    raw = "Just a conversational sentence with no JSON."
    res = extract_json_block(raw, default={"fallback": True})
    assert res == {"fallback": True}


def test_extract_json_block_invalid_without_default() -> None:
    """Raises ValueError when JSON is invalid and no default is provided."""
    raw = "Invalid json content"
    with pytest.raises(ValueError):
        extract_json_block(raw)
