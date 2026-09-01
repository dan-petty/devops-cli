"""High-performance streaming JSON, JSONL, and YAML serializers for large dataset outputs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from pydantic import BaseModel


def _dump_object(obj: Any) -> str:
    """Serialize a single object or Pydantic model to a JSON string."""
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
        return json.dumps(obj, default=str)
    return json.dumps(str(obj))


def stream_json_array(items: Iterable[Any]) -> Iterator[str]:
    """Yield formatted JSON array chunks with low memory overhead for large streams."""
    yield "[\n"
    first = True
    for item in items:
        if not first:
            yield ",\n"
        first = False
        rendered = _dump_object(item)
        # Indent object lines by 2 spaces
        indented = "\n".join(f"  {line}" for line in rendered.splitlines())
        yield indented
    yield "\n]"


def stream_jsonl(items: Iterable[Any]) -> Iterator[str]:
    """Yield line-delimited JSON (JSONL) strings one record per iteration."""
    for item in items:
        yield _dump_object(item) + "\n"


def stream_yaml_docs(items: Iterable[Any]) -> Iterator[str]:
    """Yield multi-document YAML stream blocks separated by document markers."""
    import yaml

    for item in items:
        data = item.model_dump() if isinstance(item, BaseModel) else item
        rendered = yaml.safe_dump(data, sort_keys=False)
        yield f"---\n{rendered}"
