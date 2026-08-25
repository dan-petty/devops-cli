"""Unit tests for AI/LLM response repair and formatter (devops_cli.ai.response_repair)."""

from __future__ import annotations

from pydantic import BaseModel

from devops_cli.ai.response_repair import (
    extract_tool_invocations,
    fix_llm_response,
    repair_json_string,
)
from devops_cli.ai.review_schema import normalize_unicode_text


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


def test_fix_llm_response_recovers_answer_when_entirely_in_thinking() -> None:
    raw = """
    <think>
    The user is asking about python-dotenv vulnerabilities.
    We inspected the database.
    Conclusion: The package python-dotenv 1.0.0 has zero known CVEs or high-severity flaws.
    </think>
    """
    fixed = fix_llm_response(raw)
    assert "python-dotenv 1.0.0 has zero known CVEs" in fixed.content
    assert len(fixed.thoughts) == 1
    assert fixed.was_repaired is True


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
