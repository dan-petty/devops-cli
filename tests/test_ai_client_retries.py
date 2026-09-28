"""Unit tests for AI response validation and configurable request retry logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx2
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


def test_provider_http_error_informative_formatting() -> None:
    """Verify _provider_http_error distinguishes credentials, HTTP status codes, and network errors."""
    client = LLMClient(AIConfig(provider="openai", api_key="sk-test"))

    # 1. HTTP 504 Gateway Timeout with body
    req = httpx2.Request("POST", "https://example.com/v1/chat/completions")
    resp_504 = httpx2.Response(504, request=req, text="Gateway Timeout from upstream")
    err_504 = client._provider_http_error(
        httpx2.HTTPStatusError("504", request=req, response=resp_504), "Request failed"
    )
    assert (
        "HTTP 504" in str(err_504),
        "Gateway Timeout from upstream" in str(err_504),
    ) == (True, True)

    # 2. HTTP 429 Rate Limit with body
    resp_429 = httpx2.Response(429, request=req, text="Too Many Requests")
    err_429 = client._provider_http_error(
        httpx2.HTTPStatusError("429", request=req, response=resp_429), "Request failed"
    )
    assert ("HTTP 429" in str(err_429), "Too Many Requests" in str(err_429)) == (True, True)

    # 3. HTTP 401/403 credentials error
    resp_401 = httpx2.Response(401, request=req)
    err_401 = client._provider_http_error(
        httpx2.HTTPStatusError("401", request=req, response=resp_401), "Request failed"
    )
    assert "OpenAI" in str(err_401) or "openai" in str(err_401)

    # 4. Network error without response
    net_err = httpx2.ConnectError("Connection refused by peer")
    err_net = client._provider_http_error(net_err, "Fallback failure message")
    assert (
        "Fallback failure message" in str(err_net),
        "ConnectError" in str(err_net),
    ) == (True, True)


def test_provider_uses_shared_client_and_retry_transport() -> None:
    """Verify provider creates shared client with native retry transport."""
    client = LLMClient(AIConfig(provider="openai", api_key="sk-test", max_retries=3))
    transport = client._create_retry_transport()
    assert transport is not None

    shared = client._shared_client()
    assert (shared is not None, hasattr(shared, "post")) == (True, True)


def test_provider_http_error_sanitizes_html_error_response() -> None:
    """Verify _provider_http_error cleans HTML error responses to prevent HTML leakage."""
    client = LLMClient(AIConfig(provider="openai", api_key="sk-test"))
    req = httpx2.Request("POST", "https://example.com/v1/chat/completions")
    html_body = (
        "<!DOCTYPE html><!--[if IE 7]><html class='ie7'><![endif]-->"
        "<head><title>524: A timeout occurred</title></head>"
        "<body><h1>Error</h1><p>Cloudflare timeout</p></body></html>"
    )
    resp_524 = httpx2.Response(524, request=req, text=html_body)
    err = client._provider_http_error(
        httpx2.HTTPStatusError("524", request=req, response=resp_524), "Request failed"
    )
    err_str = str(err)
    assert (
        "524: A timeout occurred" in err_str,
        "<!DOCTYPE html>" not in err_str,
        "<html>" not in err_str,
        "<head>" not in err_str,
        "<body" not in err_str,
    ) == (True, True, True, True, True)
