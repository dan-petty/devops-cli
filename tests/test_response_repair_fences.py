"""Regression tests for #786: brackets in a reply's prose must not cost its structured output."""

from __future__ import annotations

import json

import pytest

from devops_cli.ai.response_repair import repair_json_string
from devops_cli.ai.review_schema import parse_review_response

_FINDINGS = {
    "findings": [
        {"severity": "HIGH", "location": "app.py:10", "title": "SQL injection", "fix": "bind"},
        {"severity": "MEDIUM", "location": "app.py:20", "title": "Open redirect", "fix": "allow"},
        {"severity": "LOW", "location": "app.py:30", "title": "Verbose error", "fix": "hide"},
    ]
}
_BLOCK = "```json\n" + json.dumps(_FINDINGS, indent=2) + "\n```"


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(f"Here is the review.\n{_BLOCK}", id="prose-then-block"),
        pytest.param(
            f"See [OWASP A03](https://owasp.org/Top10/A03_2021-Injection/).\n{_BLOCK}",
            id="markdown-link-in-prose",
        ),
        pytest.param(f"The loop reads `items[0]` first.\n{_BLOCK}", id="index-in-prose"),
        pytest.param(f'{_BLOCK}\nAlso check `request.args["id"]`.', id="subscript-after-block"),
    ],
)
def test_bracketed_prose_keeps_every_finding(reply: str) -> None:
    """Each reply holds the same three findings, whatever brackets surround the block."""
    result = parse_review_response(reply)
    titles = [f.title for f in result.findings] if result else None
    assert titles == ["SQL injection", "Open redirect", "Verbose error"]


def test_a_fenced_block_keeps_fences_nested_in_its_string_values() -> None:
    """A code fence inside a string value must not end the block."""
    payload = {"findings": [{"title": "Bug", "fix": "```python\ndef foo():\n    pass\n```"}]}
    reply = "See [the docs](https://example.com).\n```json\n" + json.dumps(payload) + "\n```"
    assert repair_json_string(reply) == payload


def test_a_json_block_followed_by_a_python_example_yields_the_json() -> None:
    reply = f"{_BLOCK}\n\nFor example:\n```python\nrows = cursor.execute(q, [user_id])\n```"
    assert repair_json_string(reply) == _FINDINGS


def test_a_fenced_write_file_tool_call_keeps_its_content_whole() -> None:
    """Content holding its own fence reaches the file intact, not cut at the inner fence."""
    call = {"command": "write_file", "path": "docs/x.md", "content": "```yaml\nkey: value\n```\n"}
    reply = "Writing the file now [step 2].\n```json\n" + json.dumps(call) + "\n```"
    assert repair_json_string(reply) == call


def test_a_malformed_fenced_block_is_repaired_up_to_its_closing_line() -> None:
    """A block that needs repair stops at a line holding only the closing fence."""
    reply = 'Notes on `cfg["x"]`.\n```json\n{"findings": [{"title": "A",}]\n```\nThen `a[1]`.'
    assert repair_json_string(reply) == {"findings": [{"title": "A"}]}


def test_a_bare_json_reply_still_parses() -> None:
    assert repair_json_string(json.dumps(_FINDINGS)) == _FINDINGS
