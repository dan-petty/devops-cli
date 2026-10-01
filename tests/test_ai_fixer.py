"""Unit tests for AI/LLM response repair and formatter (devops_cli.ai.response_repair)."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pydantic import BaseModel
from pydantic_ai import RunContext

from devops_cli.ai.output import TextOutput
from devops_cli.ai.response_repair import (
    _JSON_FENCE,
    extract_tool_invocations,
    fix_llm_response,
    repair_json_string,
)
from devops_cli.ai.review_schema import ReviewResult, normalize_unicode_text, parse_review_response


class SampleModel(BaseModel):
    name: str
    count: int
    active: bool = True


def test_normalize_unicode_text_spaces_and_quotes() -> None:
    raw = "Hello\u202fworld\u00a0\u2018smart\u2019 \u201cquotes\u201d\u200b!"
    norm = normalize_unicode_text(raw)
    assert norm == "Hello world 'smart' \"quotes\"!"


def test_repair_json_string_python_constants_and_trailing_commas() -> None:
    malformed = """
    {
        'name': 'test-pkg',
        'count': 42,
        'active': True,
        'missing': None,
    """
    data = repair_json_string(malformed)
    assert isinstance(data, dict)
    assert data["name"] == "test-pkg"
    assert data["count"] == 42
    assert data["active"] is True
    assert data["missing"] is None


def test_repair_json_string_markdown_fences() -> None:
    raw = """
    Here is the response:
    ```json
    {
      "status": "success",
      "records": [1, 2, 3]
    }
    ```
    """
    data = repair_json_string(raw)
    assert isinstance(data, dict)
    assert data["status"] == "success"
    assert data["records"] == [1, 2, 3]


def test_extract_tool_invocations_json() -> None:
    raw = """
    <think>We need to scan the package</think>
    ```json
    {
      "tool": "security_intel_package",
      "arguments": {
        "package_name": "python-dotenv",
        "version": "1.0.0",
        "ecosystem": "PyPI"
      }
    }
    ```
    """
    calls = extract_tool_invocations(raw)
    assert len(calls) == 1
    assert calls[0].tool_name == "security_intel_package"
    assert calls[0].arguments["package_name"] == "python-dotenv"
    assert calls[0].arguments["version"] == "1.0.0"


def test_extract_tool_invocations_function_style_in_thinking() -> None:
    raw = """
    <think>
    Let's check the function signature:
    security_intel_package({"package_name":"python-dotenv","version":"1.0.0","ecosystem":"pypi"}).
    Let's invoke.
    </think>
    """
    fixed = fix_llm_response(raw, available_tools=["security_intel_package"])
    assert len(fixed.tool_calls) == 1
    assert fixed.tool_calls[0].tool_name == "security_intel_package"
    assert fixed.tool_calls[0].arguments.get("package_name") == "python-dotenv"
    assert fixed.was_repaired is True


def test_fix_llm_response_strict_thinking_isolation() -> None:
    raw = """
    <think>
    The user is asking about python-dotenv vulnerabilities.
    We inspected the database.
    Conclusion: The package python-dotenv 1.0.0 has zero known CVEs or high-severity flaws.
    </think>
    """
    fixed = fix_llm_response(raw)
    assert fixed.content == ""
    assert len(fixed.thoughts) == 1
    assert "Conclusion: The package python-dotenv" in fixed.thoughts[0]


def test_fix_llm_response_does_not_parse_json_from_thinking_for_schema() -> None:
    raw = """
    <think>
    ```json
    {
      "name": "InsideThinking",
      "count": 99,
      "active": true
    }
    ```
    </think>
    """
    fixed = fix_llm_response(raw, schema=SampleModel)
    assert fixed.parsed_model is None
    assert fixed.content == ""


def test_fix_llm_response_schema_validation() -> None:
    raw = """
    ```json
    {
      'name': 'DevOpsAgent',
      'count': 10,
      'active': True
    }
    ```
    """
    fixed = fix_llm_response(raw, schema=SampleModel)
    assert fixed.parsed_model is not None
    assert fixed.parsed_model.name == "DevOpsAgent"
    assert fixed.parsed_model.count == 10
    assert fixed.parsed_model.active is True


def test_repair_json_string_rejects_oversized_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify repair_json_string returns None when input exceeds max length."""
    assert repair_json_string('{"key": "value"}', max_length=5) is None

    monkeypatch.setattr("devops_cli.ai.response_repair.DEFAULT_JSON_REPAIR_MAX_LENGTH", 20)
    assert repair_json_string("{" + (" " * 30) + "}") is None


def _shout(text: str) -> str:
    return text.upper()


def _with_context(ctx: RunContext[Any], text: str) -> str:
    return text.upper()


async def _async_shout(text: str) -> str:
    return text.upper()


def test_text_output_functions_run_only_when_they_take_the_text_alone() -> None:
    """Verify a text-only function parses the reply, and context-taking or async ones are skipped."""
    results = [
        fix_llm_response("hello", schema=cast(Any, TextOutput(fn))).parsed_model
        for fn in (_shout, _with_context, _async_shout)
    ]

    assert results == ["HELLO", None, None]


# A review answer of three findings, and the replies a model wraps it in.
_FINDINGS = [
    {
        "severity": "HIGH",
        "location": f"src/app.py:{line}",
        "title": title,
        "description": "User input reaches the query unchecked.",
        "fix": "Bind the value as a query parameter.",
    }
    for line, title in (
        (10, "SQL injection in search"),
        (24, "Unbounded page size"),
        (31, "Stack trace in error page"),
    )
]
_TITLES = [finding["title"] for finding in _FINDINGS]
_REVIEW = {"findings": _FINDINGS}
_REVIEW_TEXT = json.dumps(_REVIEW, indent=2)
_REVIEW_BLOCK = "```json\n" + _REVIEW_TEXT + "\n```"
_LINK = "See [OWASP A03](https://example.com/owasp-a03) for context.\n\n"
# Cut off inside the third finding, as a reply that runs out of tokens is.
_TRUNCATED = _REVIEW_TEXT[: _REVIEW_TEXT.rindex('"description"')]


def _titles(reply: str) -> list[str] | None:
    """The titles of the findings a review reply parses to, or None when it does not parse."""
    review = parse_review_response(reply)
    return [finding.title for finding in review.findings] if review else None


def _with_raw_newlines(json_text: str) -> str:
    """JSON as a model may write it, with raw newlines inside its strings."""
    return json_text.replace("\\n", "\n")


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param("Here is my review.\n\n" + _REVIEW_BLOCK, id="prose-then-block"),
        pytest.param(_LINK + _REVIEW_BLOCK, id="markdown-link-before"),
        pytest.param(
            "The handler reads `items[0]` without a bounds check.\n\n" + _REVIEW_BLOCK,
            id="index-before",
        ),
        pytest.param(
            _REVIEW_BLOCK + '\n\nNote: `request.args["id"]` is user input.', id="subscript-after"
        ),
    ],
)
def test_brackets_in_the_prose_cost_a_review_no_finding(reply: str) -> None:
    """Verify a fenced review keeps all three findings when its prose holds brackets (#786).

    json-repair reads `[OWASP A03](...)`, `items[0]` or `args["id"]` as list items beside the
    answer, so the whole reply parsed to a list that neither the review parser nor the agent
    loop's schema validation could read.
    """
    structured = fix_llm_response(reply, schema=ReviewResult).parsed_model

    assert (
        _titles(reply),
        [finding.title for finding in structured.findings] if structured else None,
    ) == (_TITLES, _TITLES)


_FENCED_FIX = "Bind the term as a parameter:\n```python\ncursor.execute(sql, (term,))\n```\nRerun."
_REVIEW_WITH_A_FENCED_FIX = {"findings": [{**_FINDINGS[0], "fix": _FENCED_FIX}, *_FINDINGS[1:]]}


@pytest.mark.parametrize("prose", ["", _LINK], ids=["block-only", "link-before"])
@pytest.mark.parametrize("raw_newlines", [False, True], ids=["escaped-newlines", "raw-newlines"])
def test_a_fence_inside_a_fix_keeps_every_finding_whole(prose: str, raw_newlines: bool) -> None:
    """Verify a ```python block inside a fix neither ends the json block nor costs a finding.

    With escaped newlines this is the reply #656 cut short. With raw ones the inner fences sit
    on lines of their own, where a fence pattern alone would close the json block early.
    """
    answer = json.dumps(_REVIEW_WITH_A_FENCED_FIX)
    reply = prose + "```json\n" + (_with_raw_newlines(answer) if raw_newlines else answer) + "\n```"

    assert repair_json_string(reply) == _REVIEW_WITH_A_FENCED_FIX


@pytest.mark.parametrize(
    "example",
    [
        pytest.param('params = {"id": user_id}\ncursor.execute(sql, params)', id="dict-literal"),
        pytest.param("first = rows[0]", id="subscript"),
    ],
)
def test_a_json_block_followed_by_a_python_example_parses_the_json_block(example: str) -> None:
    """Verify a ```python example after the answer is not read into the answer."""
    reply = _REVIEW_BLOCK + "\n\nFor example:\n```python\n" + example + "\n```"

    assert repair_json_string(reply) == _REVIEW


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(json.dumps(_REVIEW), id="bare-object"),
        pytest.param(json.dumps(_FINDINGS), id="bare-list"),
        pytest.param("Here are my findings:\n" + json.dumps(_FINDINGS), id="list-after-prose"),
        pytest.param(_LINK + json.dumps(_REVIEW), id="object-after-a-link"),
        pytest.param(_TRUNCATED, id="truncated"),
        pytest.param("```json\n" + _TRUNCATED, id="truncated-block"),
        pytest.param(_LINK + "```json\n" + _TRUNCATED, id="truncated-block-after-a-link"),
        pytest.param(str(_REVIEW), id="single-quoted"),
        pytest.param("```json\n" + str(_REVIEW) + "\n```", id="single-quoted-block"),
    ],
)
def test_bare_truncated_or_malformed_replies_still_yield_every_finding(reply: str) -> None:
    """Verify bare JSON, as an object or a list of findings, and replies json-repair mends parse."""
    assert _titles(reply) == _TITLES


def test_a_reply_an_open_bracket_swallowed_never_reads_as_a_review_without_findings() -> None:
    """Verify a reply json-repair cannot take apart yields its finding or nothing at all.

    An open `[` in the prose makes json-repair read the rest of the reply as one list of
    fragments, here holding the lone finding. Taking that fragment for the answer would pass
    for a review that found nothing, which the review runner accepts where it would
    otherwise ask the model again.
    """
    single_quoted = str({"findings": _FINDINGS[:1]})
    reply = "The pattern `[a-z` is unterminated.\n```json\n" + single_quoted + "\n```"

    assert _titles(reply) in (None, _TITLES[:1])


_GUIDE = "# Build\n\n```bash\nmake test\n```\n\nRun it before every push.\n"
_WRITE_GUIDE = {"path": "BUILD.md", "content": _GUIDE}


@pytest.mark.parametrize(
    "prose",
    [
        pytest.param("", id="block-only"),
        pytest.param(
            "Per the [style guide](https://example.com/guide), I'll write it.\n", id="link-before"
        ),
        pytest.param(
            "The pattern `[a-z` is unterminated, so I'll rewrite the guide.\n",
            id="open-bracket-before",
        ),
    ],
)
@pytest.mark.parametrize("raw_newlines", [False, True], ids=["escaped-newlines", "raw-newlines"])
def test_a_fenced_write_file_call_arrives_whole(prose: str, raw_newlines: bool) -> None:
    """Verify file content keeps its own fences and final newline, whatever prose leads the call."""
    call = json.dumps({"tool": "write_file", "arguments": _WRITE_GUIDE}, indent=2)
    reply = prose + "```json\n" + (_with_raw_newlines(call) if raw_newlines else call) + "\n```"

    fixed = fix_llm_response(reply, available_tools={"read_file", "write_file"})

    assert [(tool_call.tool_name, tool_call.arguments) for tool_call in fixed.tool_calls] == [
        ("write_file", _WRITE_GUIDE)
    ]


@pytest.mark.parametrize(
    ("reply", "blocks"),
    [
        pytest.param('```json\n{"a": 1}\n```', ['{"a": 1}'], id="fences-on-their-own-lines"),
        pytest.param('  ```JSON\r\n  {"a": 1}\r\n  ```  \r\n', ['{"a": 1}'], id="indented-crlf"),
        pytest.param('Wrap it in ```json\n{"a": 1}\n```', [], id="opening-mid-line"),
        pytest.param(
            '```json\n{"fix": "Use:\n```python\nmain()"}\n```',
            ['{"fix": "Use:\n```python\nmain()"}'],
            id="language-fence-inside",
        ),
    ],
)
def test_a_fence_opens_at_a_line_start_and_closes_on_a_line_of_its_own(
    reply: str, blocks: list[str]
) -> None:
    """Verify a ``` mid-line opens no block, and a fence naming a language closes none."""
    assert [block.strip() for block in _JSON_FENCE.findall(reply)] == blocks
