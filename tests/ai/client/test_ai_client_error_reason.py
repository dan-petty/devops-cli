"""An `AIClientError` states the HTTP status or the timeout of the call that failed (#2562).

The client reaches its gateway through the `web` fake of the HTTP entry point. The `reason` of an error is its
code and the cause, and it never holds the text of the provider's reply.
"""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from tests.llm_stream_fakes import reply, serve_llm, sse_data
from tests.support.fakes.http import WebFake

_MODEL_TEXT = "MODEL-TEXT"

pytestmark = pytest.mark.usefixtures("clock")


@pytest.fixture(autouse=True)
def _public_endpoints(web: WebFake) -> None:
    """The gateway is an example.com URL, which resolves to a public address."""


def _client() -> LLMClient:
    return LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-coder",
            max_retries=1,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )


def _failure(client: LLMClient) -> AIClientError:
    with pytest.raises(AIClientError) as caught:
        client.chat("You are terse.", "Reply with OK.", use_cache=False)
    return caught.value


@pytest.mark.parametrize(
    ("facts", "reason"),
    [
        ({"status": 408}, "LLM_INFERENCE_ERROR, timeout (HTTP 408 Request Timeout)"),
        ({"status": 599}, "LLM_INFERENCE_ERROR, HTTP 599"),
        ({"timed_out": True}, "LLM_INFERENCE_ERROR, timeout"),
        (
            {"status": 504, "timed_out": True},
            "LLM_INFERENCE_ERROR, timeout (HTTP 504 Gateway Timeout)",
        ),
        ({}, "LLM_INFERENCE_ERROR"),
    ],
    ids=["status", "status-with-no-phrase", "timeout", "timeout-and-status", "neither"],
)
def test_the_reason_is_the_code_then_the_status_or_the_timeout(
    facts: dict[str, Any], reason: str
) -> None:
    error = AIClientError(f"the reply said {_MODEL_TEXT}", **facts)

    assert error.reason == reason


def test_a_reply_with_a_status_gives_the_status_and_not_the_body(
    web: WebFake,
) -> None:
    serve_llm(
        web,
        lambda request: httpx2.Response(408, json={"error": {"message": _MODEL_TEXT}}),
    )

    error = _failure(_client())

    assert (error.status, error.timed_out, error.reason) == (
        408,
        False,
        "LLM_INFERENCE_ERROR, timeout (HTTP 408 Request Timeout)",
    )


def test_an_error_frame_with_a_status_gives_that_status(web: WebFake) -> None:
    """After a keepalive comment the gateway has sent its status line, so it writes its error
    reply into a frame whose code is the status."""
    frame = sse_data({"error": {"message": _MODEL_TEXT, "type": "Timeout", "code": "408"}})
    serve_llm(web, lambda request: reply([b": keepalive\n\n", frame]))

    error = _failure(_client())

    assert (error.status, error.reason) == (
        408,
        "LLM_INFERENCE_ERROR, timeout (HTTP 408 Request Timeout)",
    )


def test_a_call_that_times_out_says_so(web: WebFake) -> None:
    def time_out(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("read timed out", request=request)

    serve_llm(web, time_out)

    error = _failure(_client())

    assert (error.status, error.timed_out, error.reason) == (
        None,
        True,
        "LLM_INFERENCE_ERROR, timeout",
    )


def test_a_claude_reply_with_a_status_gives_the_status(web: WebFake) -> None:
    """The Anthropic SDK reads the status of a reply that a plain client returns; the client of
    this test has no retry transport, which raises before the SDK sees the reply."""
    client = LLMClient(
        AIConfig(
            provider="claude",
            model="claude-test",
            api_base_url="http://example.com",
            allow_private_network=True,
            max_retries=1,
        ),
        api_key="sk-test",
        cache_enabled=False,
        http_client=http_client(EgressLevel.PRIVATE),
    )
    serve_llm(
        web,
        lambda request: httpx2.Response(
            529,
            json={"type": "error", "error": {"type": "overloaded_error", "message": _MODEL_TEXT}},
        ),
    )

    error = _failure(client)

    assert (error.status, error.reason) == (529, "LLM_INFERENCE_ERROR, HTTP 529")


def test_a_transport_timeout_of_the_shared_client_says_so() -> None:
    client = LLMClient(AIConfig(provider="ollama", model="llama3"), cache_enabled=False)
    request = httpx2.Request("POST", "https://example.com/v1/chat")

    error = client._provider_http_error(
        httpx2.ReadTimeout("read timed out", request=request), "Request failed"
    )

    assert error.reason == "LLM_INFERENCE_ERROR, timeout"


def _claude_client() -> LLMClient:
    return LLMClient(
        AIConfig(
            provider="claude",
            model="claude-test",
            api_base_url="http://example.com",
            allow_private_network=True,
            max_retries=1,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )


def _ollama_client() -> LLMClient:
    return LLMClient(
        AIConfig(
            provider="ollama",
            model="llama3",
            ollama_urls=["http://ollama.example.com:11434"],
            max_retries=1,
        ),
        cache_enabled=False,
    )


def _time_out(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectTimeout("connect timed out", request=request)


@pytest.mark.parametrize(
    ("make_client", "handler", "status", "timed_out"),
    [
        (_claude_client, _time_out, None, True),
        (_ollama_client, _time_out, None, True),
        (_ollama_client, lambda request: httpx2.Response(500, text=_MODEL_TEXT), 500, False),
    ],
    ids=["claude-timeout", "ollama-timeout", "ollama-status"],
)
def test_a_provider_that_builds_its_own_error_gives_the_status_or_the_timeout(
    make_client: Any,
    handler: Any,
    status: int | None,
    timed_out: bool,
    web: WebFake,
) -> None:
    """The Claude and Ollama paths build their error without the gateway mixin."""
    client = make_client()
    serve_llm(web, handler)

    error = _failure(client)

    assert (error.status, error.timed_out, _MODEL_TEXT in error.reason) == (
        status,
        timed_out,
        False,
    )
