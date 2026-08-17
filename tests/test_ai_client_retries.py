"""Unit tests for AI response validation and configurable request retry logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.client import AIClientError, LLMClient, LLMResponse
from devops_cli.config.defaults import DEFAULT_AI_MAX_RETRIES
from devops_cli.config.settings import AIConfig, AITaskOverride


def test_validate_response_text_valid() -> None:
    """_validate_response_text returns True for non-empty text."""
    assert LLMClient._validate_response_text("Valid AI output string") is True


def test_validate_response_text_empty_and_whitespace() -> None:
    """_validate_response_text returns False for empty or whitespace text."""
    assert LLMClient._validate_response_text("") is False
    assert LLMClient._validate_response_text("   \n\t ") is False


def test_validate_response_text_error_json_payload() -> None:
    """_validate_response_text returns False for raw API error JSON payloads."""
    assert LLMClient._validate_response_text('{"error": "Model not found"}') is False
    assert LLMClient._validate_response_text('{"error_code": 500, "message": "Failed"}') is False


def test_validate_response_text_custom_validator() -> None:
    """_validate_response_text enforces custom validator callbacks."""

    def validator(text: str) -> bool:
        return "required_keyword" in text

    assert LLMClient._validate_response_text("contains required_keyword here", validator) is True
    assert LLMClient._validate_response_text("missing key here", validator) is False


def test_ai_config_default_and_task_override_max_retries() -> None:
    """AIConfig provides default max_retries and supports task-level overrides."""
    cfg = AIConfig()
    assert cfg.max_retries == DEFAULT_AI_MAX_RETRIES

    cfg_override = AIConfig(
        max_retries=1,
        tasks=AIConfig().tasks.model_copy(update={"chat": AITaskOverride(max_retries=4)}),
    )
    assert cfg_override.for_task("chat").max_retries == 4
    assert cfg_override.for_task("metadata").max_retries == 1


@patch("time.sleep", return_value=None)
@patch.object(LLMClient, "_dispatch_messages")
def test_llm_client_chat_retries_on_validation_failure(
    mock_dispatch: MagicMock, mock_sleep: MagicMock
) -> None:
    """LLMClient chat retries requests when validation fails and succeeds on subsequent attempt."""
    mock_dispatch.side_effect = [
        LLMResponse(""),  # attempt 1: empty -> invalid
        LLMResponse("Successful response on retry"),  # attempt 2: valid
    ]
    cfg = AIConfig(max_retries=2)
    client = LLMClient(cfg)

    resp = client.chat(system="sys", user="user")
    assert resp == "Successful response on retry"
    assert mock_dispatch.call_count == 2


@patch("time.sleep", return_value=None)
@patch.object(LLMClient, "_dispatch_messages")
def test_llm_client_chat_exhausts_retries_and_raises(
    mock_dispatch: MagicMock, mock_sleep: MagicMock
) -> None:
    """LLMClient chat raises AIClientError after exhausting max_retries."""
    mock_dispatch.return_value = LLMResponse("")
    cfg = AIConfig(max_retries=1)
    client = LLMClient(cfg)

    with pytest.raises(AIClientError, match="Response validation failed"):
        client.chat(system="sys", user="user")

    assert mock_dispatch.call_count == 2  # initial + 1 retry
