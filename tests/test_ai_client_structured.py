"""Unit tests for LLM structured output, schema repair, and error reflection retry engine."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from devops_cli.ai.client.models import AIClientError, LLMResponse
from devops_cli.ai.client.structured import (
    StructuredOutputMixin,
    _build_reflection_message,
    _extract_candidate_json,
    _parse_json_payload,
    _prepare_structured_messages,
    _repair_and_validate_payload,
    _validate_schema_payload,
)
from devops_cli.ai.client.unified import LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


class DemoReport(BaseModel):
    """Test schema for structured generation."""

    title: str
    severity: str = "medium"
    score: int = Field(ge=0, le=100)
    tags: list[str] = Field(default_factory=list)


def _create_mock_client() -> LLMClient:
    """Helper to instantiate LLMClient with safe test configuration."""
    cfg = AIConfig(
        provider="ollama",
        model="demo-model",
        ollama_base_url="http://example.com:11434",
        max_retries=2,
    )
    return LLMClient(config=cfg, api_key="dummy-key")


def test_build_reflection_message() -> None:
    """Verify reflection message formatting and bounded role definition."""
    msg = _build_reflection_message("Field required: score")
    assert (msg.role, "Field required: score" in msg.content) == ("user", True)


def test_repair_and_validate_payload() -> None:
    """Verify end-to-end extraction, repair, and schema validation."""
    raw = "<think>notes</think>\n```json\n{'title': 'RepairMe', 'score': 50}\n```"
    model, was_repaired, err = _repair_and_validate_payload(raw, DemoReport)
    assert (model is not None, was_repaired, err) == (True, True, None)
    if model is not None:
        assert (model.title, model.score) == ("RepairMe", 50)


def test_llm_client_inherits_structured_mixin() -> None:
    """Verify LLMClient class is an instance of StructuredOutputMixin."""
    client = _create_mock_client()
    assert isinstance(client, StructuredOutputMixin)


def test_extract_candidate_json_handles_fences_and_thinking() -> None:
    """Verify thinking tags and markdown code blocks are cleanly stripped."""
    raw = (
        "<think>Examining the AST context</think>\n"
        "```json\n"
        '{"title": "BufferOverflow", "severity": "high", "score": 90}\n'
        "```"
    )
    candidate = _extract_candidate_json(raw)
    assert candidate == '{"title": "BufferOverflow", "severity": "high", "score": 90}'


def test_parse_json_payload_clean_and_repair() -> None:
    """Verify clean JSON passes directly and malformed JSON triggers json_repair."""
    clean_raw = '{"title": "Safe", "score": 10}'
    data_clean, repaired_clean, err_clean = _parse_json_payload(clean_raw, clean_raw)
    assert (repaired_clean, err_clean, data_clean["score"]) == (False, None, 10)

    malformed_raw = "{'title': 'Repaired', 'score': 20, }"
    data_rep, repaired_rep, err_rep = _parse_json_payload(malformed_raw, malformed_raw)
    assert (repaired_rep, err_rep, data_rep["title"], data_rep["score"]) == (
        True,
        None,
        "Repaired",
        20,
    )

    invalid_raw = "This is pure freeform text with no JSON."
    data_inv, repaired_inv, err_inv = _parse_json_payload(invalid_raw, invalid_raw)
    assert (data_inv, repaired_inv, err_inv is not None) == (None, False, True)


def test_validate_schema_payload_bounds_errors() -> None:
    """Verify valid payloads produce models and invalid payloads bound error lengths."""
    valid_data = {"title": "Valid", "severity": "low", "score": 42, "tags": ["test"]}
    model, err = _validate_schema_payload(valid_data, DemoReport)
    assert (err, model is not None) == (None, True)
    if model is not None:
        assert (model.title, model.score, model.severity) == ("Valid", 42, "low")

    invalid_data = {"title": "MissingScore"}
    model_inv, err_inv = _validate_schema_payload(invalid_data, DemoReport)
    assert (model_inv, err_inv is not None, len(err_inv or "") <= 256) == (None, True, True)


def test_prepare_structured_messages_variants() -> None:
    """Verify prompt and user arguments normalize cleanly to ChatMessage list."""
    msgs_from_prompt = _prepare_structured_messages("Audit report request", None)
    assert (len(msgs_from_prompt), msgs_from_prompt[0].role, msgs_from_prompt[0].content) == (
        1,
        "user",
        "Audit report request",
    )

    msgs_from_user = _prepare_structured_messages(None, "User param request")
    assert (len(msgs_from_user), msgs_from_user[0].content) == (1, "User param request")

    existing_msgs = [
        ChatMessage(role="system", content="init"),
        ChatMessage(role="user", content="req"),
    ]
    msgs_from_list = _prepare_structured_messages(existing_msgs, None)
    assert len(msgs_from_list) == 2

    with pytest.raises(ValueError, match="Either prompt or user text must be provided"):
        _prepare_structured_messages(None, None)


def test_chat_structured_immediate_success() -> None:
    """Verify chat_structured succeeds on first attempt with clean JSON."""
    client = _create_mock_client()
    raw_response = '{"title": "ZeroBug", "severity": "low", "score": 100, "tags": ["sec"]}'

    with patch.object(client, "chat_messages", return_value=LLMResponse(raw_response)) as mock_chat:
        report = client.chat_structured(
            system="You are a reviewer",
            prompt="Generate a report",
            schema=DemoReport,
        )
        assert (mock_chat.call_count, report.title, report.score) == (1, "ZeroBug", 100)


def test_chat_structured_local_repair_no_network_retry() -> None:
    """Verify malformed JSON is repaired locally without consuming extra retry turns."""
    client = _create_mock_client()
    malformed_response = (
        "```json\n{\n  'title': 'RepairedBug',\n  'severity': 'high',\n  'score': 75,\n}\n```"
    )

    with patch.object(
        client, "chat_messages", return_value=LLMResponse(malformed_response)
    ) as mock_chat:
        report = client.chat_structured(
            system="You are a reviewer",
            prompt="Generate a report",
            schema=DemoReport,
        )
        assert (mock_chat.call_count, report.title, report.score, report.severity) == (
            1,
            "RepairedBug",
            75,
            "high",
        )


def test_chat_structured_reflection_retry_succeeds_on_second_turn() -> None:
    """Verify validation error triggers reflection prompt and recovers on retry."""
    client = _create_mock_client()
    bad_attempt_1 = '{"title": "MissingRequiredScore"}'
    good_attempt_2 = '{"title": "FixedReport", "severity": "high", "score": 88}'

    with patch.object(
        client,
        "chat_messages",
        side_effect=[LLMResponse(bad_attempt_1), LLMResponse(good_attempt_2)],
    ) as mock_chat:
        report = client.chat_structured(
            system="System prompt",
            prompt="Initial request",
            schema=DemoReport,
            backoff_seconds=0.01,
        )
        assert (mock_chat.call_count, report.title, report.score) == (2, "FixedReport", 88)
        second_call_messages = mock_chat.call_args_list[1][0][1]
        assert len(second_call_messages) == 3
        assert (
            second_call_messages[0].role,
            second_call_messages[1].role,
            second_call_messages[2].role,
        ) == ("user", "assistant", "user")
        assert "Validation Error" in second_call_messages[2].content


def test_chat_structured_retry_exhaustion_raises_client_error() -> None:
    """Verify retry exhaustion after max_retries raises AIClientError with actionable context."""
    client = _create_mock_client()
    bad_payload = "Non-parseable unstructured output"

    with patch.object(
        client,
        "chat_messages",
        side_effect=[
            LLMResponse(bad_payload),
            LLMResponse(bad_payload),
            LLMResponse(bad_payload),
        ],
    ) as mock_chat:
        with pytest.raises(
            AIClientError,
            match="Response validation failed for model 'demo-model' after 3 attempts",
        ):
            client.chat_structured(
                system="System prompt",
                prompt="Initial prompt",
                schema=DemoReport,
                max_retries=2,
                backoff_seconds=0.01,
            )
        assert mock_chat.call_count == 3


def test_chat_structured_requires_schema() -> None:
    """Verify ValueError is raised if schema is omitted."""
    client = _create_mock_client()
    with pytest.raises(ValueError, match="A schema model class must be provided"):
        client.chat_structured(system="sys", prompt="req", schema=None)
