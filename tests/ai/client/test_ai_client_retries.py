"""Unit tests for AI response validation, configurable request retries and request timeouts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger

from devops_cli.ai.client import AIClientError, LLMClient, LLMResponse, ReplyRejectedError
from devops_cli.config.defaults import DEFAULT_AI_MAX_RETRIES, DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.config.settings import AIConfig, AITaskOverride
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.models.ai import ChatMessage
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import serve_llm


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


@pytest.mark.parametrize(
    ("content", "rejection"),
    [
        ("plain prose", ReplyRejectedError),
        ("", AIClientError),
        ('{"error": "down"}', AIClientError),
    ],
)
def test_a_reply_the_validator_refuses_comes_back_on_the_error(
    web: WebFake,
    content: str,
    rejection: type[Exception],
    spend_ledger: SpendLedger,
) -> None:
    """Verify a reply the caller's validator refuses raises ReplyRejectedError carrying it, with
    the message callers already match, while an empty reply or an error payload, which no
    validator saw, stays a plain AIClientError; none of them is cached."""
    client = LLMClient(
        AIConfig(provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1")
    )
    serve_llm(
        web,
        lambda request: httpx2.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        ),
    )

    key = client.cache.generate_key(
        "gateway",
        "demo-model",
        "sys",
        [ChatMessage(role="user", content="user")],
        {"enable_thinking": True},
    )

    with pytest.raises(AIClientError) as raised:
        client.chat("sys", "user", validator=lambda text: text.startswith("{"), max_retries=0)

    assert (
        type(raised.value),
        str(raised.value),
        getattr(raised.value, "reply", None),
        client.cache.get(key),
    ) == (
        rejection,
        "Response validation failed for model 'demo-model' (attempt 1/1).",
        content if rejection is ReplyRejectedError else None,
        None,
    )


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


def test_provider_client_retries_a_server_error(web: WebFake, clock: ClockFake) -> None:
    """Verify the shared client sends a request again after a 503, and waits between the two."""
    client = LLMClient(
        AIConfig(
            provider="ollama",
            ollama_urls=["http://example.com:11434"],
            max_retries=3,
        ),
        cache_enabled=False,
    )
    answers = [httpx2.Response(503), httpx2.Response(200, json={"message": {"content": "ok"}})]
    sent = serve_llm(web, lambda request: answers.pop(0))

    reply = client._ollama_messages("sys", [ChatMessage(role="user", content="hi")])

    assert (str(reply), len(sent), len(clock.waits)) == ("ok", 2, 1)


def _private_address_client(*, allow_private_network: bool) -> LLMClient:
    """An Ollama client for an address in a private range, without retries."""
    return LLMClient(
        AIConfig(
            provider="ollama",
            ollama_urls=["http://192.0.2.10:11434"],
            max_retries=0,
            allow_private_network=allow_private_network,
        ),
        cache_enabled=False,
    )


def test_provider_client_refuses_a_private_address_at_the_loopback_level(web: WebFake) -> None:
    """Verify the client refuses an address in a private range before it sends a request."""
    sent = serve_llm(web, lambda request: httpx2.Response(200, json={"message": {"content": "ok"}}))

    with pytest.raises(SSRFBlockedError) as raised:
        _private_address_client(allow_private_network=False)._ollama_messages(
            "sys", [ChatMessage(role="user", content="hi")]
        )

    assert (raised.value.error_code, sent) == ("SSRF_BLOCKED", [])


def test_provider_client_reaches_a_private_address_at_the_private_level(web: WebFake) -> None:
    """Verify `ai.allow_private_network` lets the client send to an address in a private range."""
    sent = serve_llm(web, lambda request: httpx2.Response(200, json={"message": {"content": "ok"}}))

    reply = _private_address_client(allow_private_network=True)._ollama_messages(
        "sys", [ChatMessage(role="user", content="hi")]
    )

    assert (str(reply), [str(request.url) for request in sent]) == (
        "ok",
        ["http://192.0.2.10:11434/api/chat"],
    )


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


@pytest.mark.parametrize(
    ("config", "constructor_timeout", "expected_read"),
    [
        (AIConfig(timeout=5.0).for_task("analysis"), None, 5.0),
        (AIConfig(tasks={"analysis": {"timeout": 7.0}}).for_task("analysis"), None, 7.0),
        (AIConfig(timeout=5.0, tasks={"chat": {"timeout": 7.0}}).for_task("analysis"), None, 5.0),
        (AIConfig(timeout=5.0), 9.0, 9.0),
        (AIConfig(), None, DEFAULT_HTTP_TIMEOUT_SECONDS),
    ],
    ids=["ai-timeout", "task-timeout", "other-task", "constructor-wins", "unset"],
)
def test_request_timeout_reads_the_configured_timeout(
    config: AIConfig, constructor_timeout: float | None, expected_read: float
) -> None:
    """Verify `ai.timeout` and `ai.tasks.<task>.timeout` set the read timeout, under the caller's."""
    client = LLMClient(
        config, api_key="x", request_timeout_seconds=constructor_timeout, cache_enabled=False
    )

    assert client._request_timeout().read == expected_read


def test_a_configured_timeout_reaches_the_request(web: WebFake) -> None:
    """Verify an Ollama chat request is sent with the task's configured read timeout."""
    config = AIConfig(
        provider="ollama", ollama_urls=["http://example.com:11434"], timeout=5.0
    ).for_task("analysis")
    client = LLMClient(config, api_key="x", cache_enabled=False)
    sent = serve_llm(
        web,
        lambda request: httpx2.Response(200, json={"message": {"content": "ok"}, "done": True}),
    )

    reply = client._ollama_messages("sys", [ChatMessage(role="user", content="hi")])

    assert (str(reply), [request.extensions["timeout"]["read"] for request in sent]) == (
        "ok",
        [5.0],
    )


def test_dispatch_non_transport_exception_does_not_report_cannot_connect() -> None:
    """A non-transport exception raised during dispatch does not report 'Cannot connect' (#1609)."""
    client = LLMClient(AIConfig(provider="openai", api_key="sk-test"), cache_enabled=False)

    with patch.object(client, "_dispatch_messages", side_effect=KeyError("unexpected_key")):
        with pytest.raises(AIClientError) as exc_info:
            client.chat_messages(messages=[ChatMessage(role="user", content="hi")])

    err_msg = str(exc_info.value)
    assert ("Cannot connect" not in err_msg, "KeyError" in err_msg) == (True, True)


def test_dispatch_transport_error_reports_cannot_connect() -> None:
    """A transport exception raised during dispatch reports connection error."""
    client = LLMClient(AIConfig(provider="openai", api_key="sk-test"), cache_enabled=False)

    req = httpx2.Request("POST", "http://example.com/v1/chat/completions")
    with patch.object(
        client, "_dispatch_messages", side_effect=httpx2.ConnectError("boom", request=req)
    ):
        with pytest.raises(AIClientError) as exc_info:
            client.chat_messages(messages=[ChatMessage(role="user", content="hi")])

    assert "Cannot connect to AI provider API" in str(exc_info.value)


def test_six_connect_failures_then_a_reply(web: WebFake, clock: ClockFake) -> None:
    """The AI client transport sends a request again after connect errors up to 10 attempts (#4753)."""
    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            max_retries=1,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )
    attempts = [0]

    def handler(request: httpx2.Request) -> httpx2.Response:
        attempts[0] += 1
        if attempts[0] <= 6:
            raise httpx2.ConnectError("Connection refused", request=request)
        return httpx2.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "seventh reply"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    sent = serve_llm(web, handler)
    reply = client.chat("sys", "hi", use_cache=False)
    assert (str(reply), len(sent)) == ("seventh reply", 7)


def test_reply_reset_before_first_chunk_retried(web: WebFake, clock: ClockFake) -> None:
    """The AI client replays when reply resets before the first chunk (#4753)."""
    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            max_retries=2,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )
    attempts = [0]

    def failing_stream() -> Any:
        raise httpx2.ReadError("connection reset by peer")
        yield b""

    def handler(request: httpx2.Request) -> httpx2.Response:
        attempts[0] += 1
        if attempts[0] == 1:
            return httpx2.Response(
                200, headers={"content-type": "text/event-stream"}, content=failing_stream()
            )
        return httpx2.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "second reply"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    sent = serve_llm(web, handler)
    reply = client.chat("sys", "hi", use_cache=False)
    assert (str(reply), len(sent)) == ("second reply", 2)


def test_reset_mid_stream_raises_and_no_replay(
    web: WebFake, clock: ClockFake, spend_ledger: SpendLedger
) -> None:
    """A stream that yielded at least one chunk must not be replayed when connection resets (#4753)."""
    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            max_retries=2,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )

    def mid_reset_stream() -> Any:
        from tests.support.llm_stream_fakes import openai_chunk

        yield openai_chunk("first chunk")
        raise httpx2.ReadError("connection reset mid-stream")

    sent = serve_llm(
        web,
        lambda request: httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=mid_reset_stream()
        ),
    )
    with pytest.raises(AIClientError) as exc_info:
        list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    assert "Cannot connect" in str(exc_info.value)
    assert len(sent) == 1
    import contextlib
    import sqlite3

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT request_type, finish_reason FROM ai_spend_records ORDER BY id"
        ).fetchall()
    assert rows == [("stream", "error")]


def test_connect_retries_bounded_by_read_timeout(web: WebFake, clock: ClockFake) -> None:
    """Connect retries stop before outer read timeout elapses and raise AIClientError within 60s (#4753)."""
    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            timeout=60.0,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )

    def timeout_handler(request: httpx2.Request) -> httpx2.Response:
        clock.shift(5.0)
        raise httpx2.ConnectTimeout("connect timed out", request=request)

    sent = serve_llm(web, timeout_handler)
    with pytest.raises(AIClientError) as exc_info:
        client.chat("sys", "hi", use_cache=False)

    assert "Cannot connect" in str(exc_info.value)
    assert len(sent) <= 10
    assert clock.monotonic() <= 60.0


def test_error_names_cause_and_host_without_api_key(web: WebFake, clock: ClockFake) -> None:
    """AIClientError of failed connect names error class, cause class, host, and no API key (#4753)."""
    import socket

    import httpcore2

    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            max_retries=0,
        ),
        api_key="sk-secret-key-that-must-never-leak",
        cache_enabled=False,
    )

    def dns_fail_handler(request: httpx2.Request) -> httpx2.Response:
        gai = socket.gaierror(-2, "Name or service not known")
        hcore = httpcore2.ConnectError("Failed to resolve")
        hcore.__cause__ = gai
        conn_err = httpx2.ConnectError("Failed to connect", request=request)
        conn_err.__cause__ = hcore
        raise conn_err

    serve_llm(web, dns_fail_handler)
    with pytest.raises(AIClientError) as exc_info:
        client.chat("sys", "hi", use_cache=False)

    msg = str(exc_info.value)
    assert "ConnectError" in msg
    assert "gaierror" in msg
    assert "gateway.example.com" in msg
    assert "sk-secret-key-that-must-never-leak" not in msg


def test_one_retry_layer_no_double_loop(web: WebFake, clock: ClockFake) -> None:
    """AI client sends exactly the policy's number of requests and dispatch does not double-loop (#4753)."""
    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            max_retries=1,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )

    def refuse_handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    sent = serve_llm(web, refuse_handler)
    with pytest.raises(AIClientError) as exc_info:
        client.chat("sys", "hi", use_cache=False)

    assert "Cannot connect" in str(exc_info.value)
    assert len(sent) == 10
