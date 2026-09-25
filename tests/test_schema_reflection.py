"""Unit and integration tests for lossless structured schema error reflection."""

from __future__ import annotations

from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError

from devops_cli.ai.agents.agent import PydanticAgent
from devops_cli.ai.client.models import LLMResponse
from devops_cli.ai.client.unified import LLMClient
from devops_cli.ai.response_repair import fix_llm_response
from devops_cli.ai.schema_reflection import (
    SchemaReflectionReport,
    SchemaViolation,
    build_schema_reflection_message,
    extract_schema_reflection,
    format_field_path,
    synthesize_fix_hint,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import UnexpectedModelBehavior


class SampleDetail(BaseModel):
    """Nested item model for schema reflection testing."""

    code: str
    count: int = Field(ge=1, le=100)


class MultiErrorModel(BaseModel):
    """Schema model with multiple fields to test capped reflection."""

    title: str = Field(min_length=3, max_length=50)
    score: int = Field(ge=0, le=100)
    status: Literal["active", "inactive"]
    active: bool
    tags: list[str] = Field(min_length=1)
    details: list[SampleDetail]
    owner: str
    priority: int


def _create_mock_client() -> LLMClient:
    """Instantiate test LLMClient with standardized example.com hostname."""
    cfg = AIConfig(
        provider="ollama",
        model="demo-model",
        ollama_base_url="http://example.com:11434",
        max_retries=2,
    )
    return LLMClient(config=cfg, api_key="dummy-key")


def test_format_field_path_variants() -> None:
    """Verify conversion of location sequences into canonical dot-and-bracket notation."""
    cases = [
        ((), "root"),
        (("name",), "name"),
        (("user", "address", "city"), "user.address.city"),
        (("items", 0, "code"), "items[0].code"),
        ((2, "title"), "[2].title"),
    ]
    results = [format_field_path(loc) for loc, _ in cases]
    expected = [exp for _, exp in cases]
    assert results == expected


def test_synthesize_fix_hint_standard_types() -> None:
    """Verify deterministic prescriptive fix hints across standard Pydantic error types."""
    missing_hint = synthesize_fix_hint({"type": "missing", "msg": "Field required"})
    extra_hint = synthesize_fix_hint({"type": "extra_forbidden", "msg": "Extra inputs forbidden"})
    int_hint = synthesize_fix_hint(
        {"type": "int_parsing", "msg": "Input should be a valid integer"}
    )
    enum_hint = synthesize_fix_hint(
        {
            "type": "literal_error",
            "ctx": {"expected": "'active' or 'inactive'"},
            "msg": "Input error",
        }
    )
    ge_hint = synthesize_fix_hint(
        {"type": "greater_than_equal", "ctx": {"ge": 10}, "msg": "Value too small"}
    )
    custom_hint = synthesize_fix_hint({"type": "custom_rule", "msg": "Must start with prefix"})

    assert (
        "required" in missing_hint,
        "not permitted" in extra_hint,
        "valid integer" in int_hint,
        "'active' or 'inactive'" in enum_hint,
        "10" in ge_hint,
        "Must start with prefix" in custom_hint,
    ) == (True, True, True, True, True, True)


def test_extract_schema_reflection_preserves_up_to_five_errors() -> None:
    """Verify that extraction preserves at most 5 field paths with lossless error structures."""
    with pytest.raises(ValidationError) as exc_info:
        MultiErrorModel.model_validate({})

    report = extract_schema_reflection(exc_info.value, max_errors=5)
    assert (
        report.total_errors,
        len(report.violations),
        report.remaining_count,
    ) == (8, 5, 3)

    paths = [v.field_path for v in report.violations]
    assert (
        len(paths),
        all(isinstance(v, SchemaViolation) for v in report.violations),
        all(len(v.fix_hint) > 0 for v in report.violations),
    ) == (5, True, True)


def test_extract_schema_reflection_bounds_input_representations() -> None:
    """Verify that oversized erroneous input representations are bounded to prevent log bloat."""
    giant_string = "A" * 300
    with pytest.raises(ValidationError) as exc_info:
        MultiErrorModel.model_validate({"title": giant_string})

    report = extract_schema_reflection(exc_info.value, max_errors=5)
    title_violation = next(v for v in report.violations if v.field_path == "title")
    assert (
        title_violation.input_value is not None,
        len(title_violation.input_value or "") <= 60,
        (title_violation.input_value or "").endswith("..."),
    ) == (True, True, True)


def test_format_reflection_prompt_and_summary() -> None:
    """Verify markdown prompt and single-line summary formatting."""
    with pytest.raises(ValidationError) as exc_info:
        MultiErrorModel.model_validate({"title": "ok", "score": -5})

    report = extract_schema_reflection(exc_info.value, max_errors=5)
    prompt = report.format_reflection_prompt()
    summary = report.format_error_summary()

    assert (
        "Found 8 schema violation(s):" in prompt,
        "Field: `score`" in prompt,
        "Fix Hint:" in prompt,
        "... and 3 additional schema violation(s)." in prompt,
        "8 schema error(s):" in summary,
    ) == (True, True, True, True, True)


def test_build_schema_reflection_message() -> None:
    """Verify message synthesis from ValidationError, report, and fallback strings."""
    with pytest.raises(ValidationError) as exc_info:
        SampleDetail.model_validate({"count": 0})

    msg_from_exc = build_schema_reflection_message(exc_info.value)
    report = extract_schema_reflection(exc_info.value)
    msg_from_rep = build_schema_reflection_message(report)
    msg_from_str = build_schema_reflection_message("Syntax error in JSON")

    assert (
        msg_from_exc.role,
        "Field: `count`" in msg_from_exc.content,
        msg_from_rep.role,
        "Field: `count`" in msg_from_rep.content,
        msg_from_str.role,
        "Syntax error in JSON" in msg_from_str.content,
    ) == ("user", True, "user", True, "user", True)


def test_fix_llm_response_populates_schema_reflection() -> None:
    """Verify fix_llm_response captures schema validation errors and populates reflection."""
    raw_bad = '```json\n{"cluster_name": "prod"}\n```'
    fixed = fix_llm_response(raw_bad, schema=SampleDetail)

    assert (
        fixed.parsed_model is None,
        fixed.schema_reflection is not None,
        isinstance(fixed.schema_reflection, SchemaReflectionReport),
        fixed.validation_error is not None,
        len(fixed.repair_notes) > 0,
    ) == (True, True, True, True, True)


def test_chat_structured_single_turn_self_correction_with_reflection() -> None:
    """Verify chat_structured incorporates prescriptive reflection in retry turns."""
    client = _create_mock_client()
    bad_attempt = '{"code": "ERR_404"}'  # missing 'count'
    good_attempt = '{"code": "ERR_404", "count": 10}'

    with patch.object(
        client,
        "chat_messages",
        side_effect=[LLMResponse(bad_attempt), LLMResponse(good_attempt)],
    ) as mock_chat:
        res = client.chat_structured(
            system="System instructions",
            prompt="Generate error detail",
            schema=SampleDetail,
            backoff_seconds=0.001,
        )
        assert (mock_chat.call_count, res.code, res.count) == (2, "ERR_404", 10)

        retry_messages = mock_chat.call_args_list[1][0][1]
        reflection_content = retry_messages[2].content
        assert (
            retry_messages[2].role,
            "Field required" in reflection_content,
            "`count`" in reflection_content,
        ) == ("user", True, True)


def test_pydantic_agent_schema_retry_with_reflection() -> None:
    """Verify PydanticAgent triggers schema reflection retry and recovers in single turn."""
    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent[SampleDetail](
        client=mock_client,
        name="SchemaReflectionAgent",
        output_schema=SampleDetail,
    )

    bad_reply = '{"code": "OK"}'  # missing count
    good_reply = '{"code": "OK", "count": 42}'
    mock_client.chat_messages.side_effect = [bad_reply, good_reply]

    res = agent.run("Process sample", max_turns=3)
    assert (
        res.data is not None,
        res.turns,
        res.data.code if res.data else None,
        res.data.count if res.data else None,
    ) == (True, 2, "OK", 42)


def test_pydantic_agent_schema_retry_budget_exhaustion() -> None:
    """Verify PydanticAgent raises UnexpectedModelBehavior when schema retry budget is exceeded."""
    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = PydanticAgent[SampleDetail](
        client=mock_client,
        name="ExhaustionAgent",
        output_schema=SampleDetail,
    )

    bad_reply = '{"invalid_payload": true}'
    mock_client.chat_messages.side_effect = [bad_reply, bad_reply]

    with pytest.raises(
        UnexpectedModelBehavior, match="Output validation exceeded retry budget of 1"
    ):
        agent.run("Process sample", max_turns=3, retries=1)
