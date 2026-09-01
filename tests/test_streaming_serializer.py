"""Tests for streaming JSON, JSONL, and YAML serializers."""

from __future__ import annotations

import json

from pydantic import BaseModel

from devops_cli.output.streaming_serializer import (
    stream_json_array,
    stream_jsonl,
    stream_yaml_docs,
)


class ItemModel(BaseModel):
    id: int
    name: str


def test_stream_json_array() -> None:
    """Stream formatted JSON array chunks."""
    items = [ItemModel(id=1, name="a"), ItemModel(id=2, name="b")]
    chunks = list(stream_json_array(items))
    full_json = "".join(chunks)

    parsed = json.loads(full_json)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "a"
    assert parsed[1]["id"] == 2


def test_stream_jsonl() -> None:
    """Stream JSONL lines."""
    items = [{"key": "val1"}, {"key": "val2"}]
    lines = list(stream_jsonl(items))
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"key": "val1"}
    assert json.loads(lines[1]) == {"key": "val2"}


def test_stream_yaml_docs() -> None:
    """Stream multi-document YAML blocks."""
    items = [{"key": "val1"}, ItemModel(id=3, name="c")]
    blocks = list(stream_yaml_docs(items))
    assert len(blocks) == 2
    assert "---" in blocks[0]
    assert "key: val1" in blocks[0]
    assert "name: c" in blocks[1]
