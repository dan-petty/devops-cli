"""An OpenAI-compatible chat call reads its reply as a stream, which the gateway keeps open with
keepalive comments past the 125 s read timeout of the Cloudflare edge (#2365)."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterable
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.ai.client.network import DEFAULT_AI_MAX_RESPONSE_BYTES, size_limit_text
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.settings import AIConfig
from tests.llm_stream_fakes import OPENAI_DONE, SSE, openai_chunk, route_llm_clients, sse_data

GATEWAY_URL = "http://gateway.example.com:4000/v1"
OLLAMA = "http://ollama-0.example.com:11434"
SERVED_BY_HEADER = "x-litellm-model-api-base"
# What LiteLLM writes while the upstream call has no data yet (`open_sse_before_first_byte`).
PING = b": ping\n\n"


@pytest.fixture(autouse=True)
def _public_endpoints(public_dns: str) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


def _gateway_client() -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="qwen3.8:27b"),
        api_key="sk-gateway",
        cache_enabled=False,
    )


def _chunk(**fields: Any) -> bytes:
    """One chat completion chunk from the gateway, with `fields` on its one choice or itself."""
    choice = {"index": 0, "delta": fields.pop("delta", {}), "finish_reason": None, **fields}
    return sse_data(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "ollama_chat/qwen3.8:27b",
            "choices": [choice],
        }
    )


def _usage_chunk() -> bytes:
    return sse_data(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "ollama_chat/qwen3.8:27b",
            "choices": [],
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 5,
                "total_tokens": 12,
                "completion_tokens_details": {"reasoning_tokens": 3},
            },
        }
    )


def _error_frame(code: str) -> bytes:
    """The frame LiteLLM writes when a call fails after a ping committed the status line."""
    return sse_data({"error": _error_body(code)})


def _error_body(code: str) -> dict[str, Any]:
    return {"message": "backend failed", "type": "None", "param": None, "code": code}


def _streamed(frames: Iterable[bytes]) -> httpx2.Response:
    headers = {"content-type": SSE, SERVED_BY_HEADER: OLLAMA}
    return httpx2.Response(200, headers=headers, content=iter(frames))


def _failure(client: LLMClient) -> tuple[type[Exception], str]:
    with pytest.raises(AIClientError) as caught:
        client.chat("You are terse.", "Reply with OK.", use_cache=False)
    return type(caught.value), str(caught.value)


def test_a_reply_that_starts_with_keepalive_comments_is_joined_into_one_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pings carry no data; the reply holds the chunks' content, reasoning and usage."""
    frames = [
        PING,
        PING,
        _chunk(delta={"role": "assistant", "reasoning_content": "Let me "}),
        _chunk(delta={"reasoning_content": "think."}),
        _chunk(delta={"content": "O"}),
        _chunk(delta={"content": "K"}, finish_reason="stop"),
        _usage_chunk(),
        OPENAI_DONE,
    ]
    sent = route_llm_clients(monkeypatch, lambda request: _streamed(frames))

    reply = _gateway_client().chat("You are terse.", "Reply with OK.", use_cache=False)

    body = json.loads(sent[0].content)
    assert (body["stream"], body["stream_options"]) == (True, {"include_usage": True})
    assert (
        reply.content,
        reply.thinking,
        reply.finish_reason,
        reply.model,
        reply.prompt_tokens,
        reply.completion_tokens,
        reply.total_tokens,
        reply.reasoning_tokens,
        reply.served_by,
    ) == ("OK", "Let me think.", "stop", "ollama_chat/qwen3.8:27b", 7, 5, 12, 3, OLLAMA)


@pytest.mark.parametrize("code", ["500", "401"], ids=["server-error", "refused-key"])
def test_an_error_frame_fails_with_the_error_of_its_http_status(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    """After a ping, a failure can only come as a frame; it reads as the HTTP reply would."""
    route_llm_clients(
        monkeypatch, lambda request: _streamed([PING, _error_frame(code), OPENAI_DONE])
    )
    in_stream = _failure(_gateway_client())

    route_llm_clients(
        monkeypatch, lambda request: httpx2.Response(int(code), json={"error": _error_body(code)})
    )
    as_status = _failure(_gateway_client())

    assert in_stream == as_status


def test_a_stream_past_the_response_size_limit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The decoded data of the frames is counted, as the body of a blocking reply was."""
    oversized = _chunk(delta={"content": "x" * DEFAULT_AI_MAX_RESPONSE_BYTES})
    route_llm_clients(monkeypatch, lambda request: _streamed([PING, oversized, OPENAI_DONE]))

    assert _failure(_gateway_client()) == (
        AIClientError,
        f"Response body exceeded maximum size ({size_limit_text(DEFAULT_AI_MAX_RESPONSE_BYTES)}).",
    )


@pytest.mark.parametrize(
    "frames",
    [[PING, openai_chunk("Hel")], [PING, OPENAI_DONE]],
    ids=["cut-after-a-chunk", "no-chunk"],
)
def test_a_stream_that_stops_before_its_final_frame_fails(
    monkeypatch: pytest.MonkeyPatch, frames: list[bytes]
) -> None:
    """A stream cut after one chunk has no `[DONE]` and no finish reason, and a stream of
    pings and `[DONE]` has no chunk to make a reply of."""
    route_llm_clients(monkeypatch, lambda request: _streamed(frames))

    assert _failure(_gateway_client()) == (
        AIClientError,
        "Provider stream ended before its final frame.",
    )


def test_a_failure_in_the_stream_is_recorded_as_a_failed_attempt(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """The transport saw a 200, so the chat path records the failed attempt itself."""
    route_llm_clients(
        monkeypatch, lambda request: _streamed([PING, _error_frame("500"), OPENAI_DONE])
    )

    _failure(_gateway_client())

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT request_type, finish_reason, prompt_tokens, completion_tokens, served_by"
            " FROM ai_spend_records"
        ).fetchall()
    assert rows == [("chat_dispatch", "error", 0, 0, OLLAMA)]
