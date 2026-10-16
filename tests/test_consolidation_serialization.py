"""Unit tests for markdown JSON block extraction and deserialization (TDD Specification)."""

from __future__ import annotations

import json
from typing import Any

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
    with pytest.raises(ValueError, match="Could not extract valid JSON from input text"):
        extract_json_block(raw)


_UNCLOSED_FENCE_ONE_ITEM_LIST = (
    "```json\n"
    "[\n"
    "  {\n"
    '    "index": 0,\n'
    '    "status": "INVALIDATED",\n'
    '    "citation_line": 24,\n'
    '    "reason": "_LAZY_OBJECT_MAPPING is a static literal table."\n'
    "  }\n"
    "]"
)


def test_extract_json_block_unclosed_fence_one_item_list_returns_list() -> None:
    """An unclosed ```json fence holding a one-item list of objects returns the list, not the inner dict (#875)."""
    parsed = extract_json_block(_UNCLOSED_FENCE_ONE_ITEM_LIST)
    assert (
        isinstance(parsed, list),
        len(parsed) if isinstance(parsed, list) else 0,
        parsed[0]["status"] if isinstance(parsed, list) and parsed else None,
        parsed[0]["citation_line"] if isinstance(parsed, list) and parsed else None,
    ) == (True, 1, "INVALIDATED", 24)


def test_extract_json_block_preserves_whole_answer_with_bracketed_prose() -> None:
    """Bracketed prose around fenced or unfenced replies yields each answer whole (#875)."""
    from tests.test_ai_fixer import _FINDINGS, _LINK, _REVIEW, _REVIEW_BLOCK

    cases = [
        ("Here is my review.\n\n" + _REVIEW_BLOCK, _REVIEW),
        (_LINK + _REVIEW_BLOCK, _REVIEW),
        (
            "The handler reads `items[0]` without a bounds check.\n\n" + _REVIEW_BLOCK,
            _REVIEW,
        ),
        (
            _REVIEW_BLOCK + '\n\nNote: `request.args["id"]` is user input.',
            _REVIEW,
        ),
        ("Here are my findings:\n" + json.dumps(_FINDINGS), _FINDINGS),
        (_LINK + json.dumps(_REVIEW), _REVIEW),
    ]
    actual = [extract_json_block(reply) for reply, _ in cases]
    expected = [target for _, target in cases]
    assert actual == expected


def test_each_entry_point_counts_repairs_once_and_valid_json_emits_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing-comma JSON repairs once per entry point with its source label; valid JSON emits 0 (#875)."""
    from devops_cli.ai.client.structured import _parse_json_payload
    from devops_cli.ai.response_repair import repair_json, repair_json_string
    from devops_cli.config.constants import (
        CONST_JSON_REPAIR_SOURCE_CHAT_STRUCTURED,
        CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK,
        CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING,
    )
    from devops_cli.telemetry import tracer as tracer_module
    from devops_cli.telemetry.instruments import AI_JSON_REPAIRS_TOTAL
    from devops_cli.telemetry.tracer import OTelTelemetryClient

    payloads: list[dict[str, Any]] = []
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    monkeypatch.setattr(client, "_send_payload", lambda _path, payload: payloads.append(payload))
    monkeypatch.setattr(tracer_module, "get_tracer", lambda: client)

    valid = '{"name": "devops", "count": 5}'
    trailing = '{"name": "devops", "count": 5,}'
    expected = {"name": "devops", "count": 5}

    valid_results = (
        repair_json(valid, source="direct"),
        repair_json_string(valid),
        extract_json_block(valid),
        _parse_json_payload(valid, valid),
    )
    counts_after_valid = len(payloads)

    repaired_results = (
        repair_json_string(trailing),
        extract_json_block(trailing),
        _parse_json_payload(trailing, trailing),
    )

    points = [
        (
            {a["key"]: next(iter(a["value"].values())) for a in pt["attributes"]},
            pt["asDouble"],
        )
        for p in payloads
        for rm in p.get("resourceMetrics", [])
        for sm in rm["scopeMetrics"]
        for m in sm["metrics"]
        if m["name"] == AI_JSON_REPAIRS_TOTAL.name
        for pt in m["sum"]["dataPoints"]
    ]

    assert (
        valid_results,
        counts_after_valid,
        repaired_results,
        points,
    ) == (
        ((expected, False), expected, expected, (expected, False, None)),
        0,
        (expected, expected, (expected, True, None)),
        [
            ({"source": CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING}, 1.0),
            ({"source": CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK}, 1.0),
            ({"source": CONST_JSON_REPAIR_SOURCE_CHAT_STRUCTURED}, 1.0),
        ],
    )
