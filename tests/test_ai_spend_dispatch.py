"""Integration tests verifying automatic spend recording during LLMClient dispatches and direct requests."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

import httpx2
import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.usage import RequestUsage

import devops_cli.ai.spend as spend_mod
from devops_cli.ai import context_budget
from devops_cli.ai.client import AIClientError, LLMClient, LLMResponse, RequestPriority
from devops_cli.ai.direct import direct_model_request, direct_model_request_sync
from devops_cli.ai.spend.ledger import SpendLedger, observe_llm_calls
from devops_cli.ai.spend.models import SpendRecord
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import (
    NDJSON,
    OPENAI_DONE,
    openai_chunk,
    reply,
    route_client,
)


@pytest.fixture(autouse=True)
def _bypass_dns_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )


def test_llm_client_dispatch_records_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMClient chat dispatch triggers track_request_spend with prompt/completion tokens."""
    recorded: list[dict[str, Any]] = []

    def mock_track_spend(**kwargs: Any) -> SpendRecord:
        recorded.append(kwargs)
        return SpendRecord(
            timestamp="2026-01-01T00:00:00Z",
            provider=kwargs.get("provider", ""),
            model=kwargs.get("model", ""),
            server=kwargs.get("server", ""),
            prompt_tokens=kwargs.get("prompt_tokens", 0),
            completion_tokens=kwargs.get("completion_tokens", 0),
            total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
            cost_usd=0.001,
        )

    monkeypatch.setattr(spend_mod, "track_request_spend", mock_track_spend)

    cfg = AIConfig(
        provider="ollama",
        model="llama3:8b",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)
    route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            200,
            json={
                "message": {"content": "Test response"},
                "prompt_eval_count": 15,
                "eval_count": 25,
            },
        ),
    )
    resp = client.chat(system="system prompt", user="user message")

    assert (len(recorded), resp.content) == (1, "Test response")
    rec = recorded[0]
    assert (
        rec["provider"],
        rec["model"],
        rec["prompt_tokens"],
        rec["completion_tokens"],
    ) == (
        "ollama",
        "llama3:8b",
        15,
        25,
    )


def test_llm_client_streaming_records_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMClient streaming chat completes and records estimated/token spend."""
    recorded: list[dict[str, Any]] = []

    def mock_track_spend(**kwargs: Any) -> SpendRecord:
        recorded.append(kwargs)
        return SpendRecord(
            timestamp="2026-01-01T00:00:00Z",
            provider=kwargs.get("provider", ""),
            model=kwargs.get("model", ""),
            server=kwargs.get("server", ""),
            prompt_tokens=kwargs.get("prompt_tokens", 0),
            completion_tokens=kwargs.get("completion_tokens", 0),
            total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
            cost_usd=0.0005,
        )

    monkeypatch.setattr(spend_mod, "track_request_spend", mock_track_spend)

    # Streaming response from Ollama
    stream_lines = [
        b'{"message": {"content": "Hello "}, "done": false}\n',
        b'{"message": {"content": "world!"}, "done": true, "prompt_eval_count": 8, "eval_count": 4}\n',
    ]

    cfg = AIConfig(
        provider="ollama",
        model="llama3:8b",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)
    route_client(client, monkeypatch, lambda request: reply(stream_lines, NDJSON))
    generator = client.chat_messages_stream(
        system="sys",
        messages=[ChatMessage(role="user", content="stream query")],
    )

    chunks = list(generator)
    assert (len(chunks), len(recorded)) == (2, 1)
    rec = recorded[0]
    assert (rec["provider"], rec["model"], rec["server"]) == (
        "ollama",
        "llama3:8b",
        "localhost:11434",
    )


def test_direct_model_request_records_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify direct_model_request_sync and direct_model_request invoke spend tracking."""
    recorded: list[dict[str, Any]] = []

    def mock_track_spend(**kwargs: Any) -> SpendRecord:
        recorded.append(kwargs)
        return SpendRecord(
            timestamp="2026-01-01T00:00:00Z",
            provider=kwargs.get("provider", ""),
            model=kwargs.get("model", ""),
            server=kwargs.get("server", ""),
            prompt_tokens=kwargs.get("prompt_tokens", 0),
            completion_tokens=kwargs.get("completion_tokens", 0),
            total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
            cost_usd=0.0002,
        )

    monkeypatch.setattr(spend_mod, "track_request_spend", mock_track_spend)

    mock_resp = ModelResponse(
        parts=[TextPart(content="Direct mock reply")],
        usage=RequestUsage(input_tokens=40, output_tokens=60),
    )

    monkeypatch.setattr(
        "devops_cli.ai.pydantic_ai_bridge.resolve_pydantic_ai_model",
        lambda m, **kwargs: "test-model",
    )
    monkeypatch.setattr(
        "devops_cli.ai.direct.model_request_sync", lambda *args, **kwargs: mock_resp
    )

    async def async_req(*args: Any, **kwargs: Any) -> Any:
        return mock_resp

    monkeypatch.setattr("devops_cli.ai.direct.model_request", async_req)

    # Test sync
    sync_resp = direct_model_request_sync(
        prompt_or_messages="Sync test prompt",
        model="test-model",
    )

    # Test async
    async_resp = asyncio.run(
        direct_model_request(
            prompt_or_messages="Async test prompt",
            model="test-model",
        )
    )

    assert (
        sync_resp.parts[0].content,
        async_resp.parts[0].content,
        len(recorded),
    ) == (
        "Direct mock reply",
        "Direct mock reply",
        2,
    )
    assert (
        recorded[0]["provider"],
        recorded[0]["model"],
        recorded[0]["prompt_tokens"],
        recorded[0]["completion_tokens"],
    ) == (
        "pydantic_ai_direct",
        "test-model",
        40,
        60,
    )


# ── Why a reply ended, from the provider to the ledger and its observers ──────────────────────


def _ledger_rows(ledger: SpendLedger) -> list[tuple[str, str | None]]:
    with sqlite3.connect(ledger.db_path) as conn:
        return conn.execute(
            "SELECT request_type, finish_reason FROM ai_spend_records ORDER BY id"
        ).fetchall()


def _cut_reply(
    _self: object,
    _system: str,
    _messages: list[ChatMessage],
    *,
    enable_thinking: bool = True,
    priority: RequestPriority | str | None = None,
) -> LLMResponse:
    return LLMResponse(
        "partial", prompt_tokens=12, completion_tokens=8, total_tokens=20, finish_reason="length"
    )


def test_a_chat_reply_reaches_observers_and_the_ledger_with_its_finish_reason(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify `LLMClient.chat` hands the reply's reason to the observer and the ledger row."""
    monkeypatch.setattr(LLMClient, "_ollama_messages", _cut_reply)
    client = LLMClient(AIConfig(provider="ollama", model="llama3:8b"), cache_enabled=False)
    seen: list[dict[str, Any]] = []

    with observe_llm_calls(seen.append):
        client.chat("system", "user", use_cache=False)

    assert ([call["finish_reason"] for call in seen], _ledger_rows(spend_ledger)) == (
        ["length"],
        [("chat_dispatch", "length")],
    )


@pytest.mark.parametrize(
    ("cached_content", "options"),
    [("", {}), ("an earlier reply", {"append_cache": True})],
    ids=["empty-entry", "append-cache"],
)
def test_a_cache_lookup_that_answers_nothing_is_recorded_once_as_a_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    spend_ledger: SpendLedger,
    cached_content: str,
    options: dict[str, Any],
) -> None:
    """Verify a cached entry the client rejects, and the cached starting point an append-cache
    call sends, are no hits: the call reaches the model and is recorded once, uncached (#816)."""
    monkeypatch.setattr(LLMClient, "_ollama_messages", _cut_reply)
    client = LLMClient(AIConfig(provider="ollama", model="llama3:8b"))
    messages = [ChatMessage(role="user", content="user")]
    key = client.cache.generate_key(
        "ollama", "llama3:8b", "system", messages, options={"enable_thinking": True}
    )
    client.cache.set(key, "ollama", "llama3:8b", "system", "user", cached_content)
    seen: list[dict[str, Any]] = []

    with observe_llm_calls(seen.append):
        reply = client.chat("system", "user", use_cache=True, **options)

    with sqlite3.connect(spend_ledger.db_path) as conn:
        rows = conn.execute("SELECT request_type, cached FROM ai_spend_records").fetchall()
    assert (reply.cached, [call["cached"] for call in seen], rows) == (
        False,
        [False],
        [("chat_dispatch", 0)],
    )


def test_a_direct_request_hands_its_finish_reason_to_observers(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify both direct requests record the `ModelResponse` finish reason."""
    cut = ModelResponse(
        parts=[TextPart(content="partial")],
        usage=RequestUsage(input_tokens=40, output_tokens=60),
        finish_reason="length",
    )

    async def async_request(*args: Any, **kwargs: Any) -> ModelResponse:
        return cut

    monkeypatch.setattr(
        "devops_cli.ai.pydantic_ai_bridge.resolve_pydantic_ai_model",
        lambda m, **kwargs: "test-model",
    )
    monkeypatch.setattr("devops_cli.ai.direct.model_request_sync", lambda *args, **kwargs: cut)
    monkeypatch.setattr("devops_cli.ai.direct.model_request", async_request)
    seen: list[dict[str, Any]] = []

    with observe_llm_calls(seen.append):
        direct_model_request_sync("Sync test prompt", model="test-model")
        asyncio.run(direct_model_request("Async test prompt", model="test-model"))

    assert [(call["request_type"], call["finish_reason"]) for call in seen] == [
        ("direct_sync", "length"),
        ("direct_async", "length"),
    ]


def _stream_client(monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    # The stream's spend estimate counts tokens; loading the tokenizer is not under test.
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    config = AIConfig(
        provider="openai",
        model="gpt-test",
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    return LLMClient(config, api_key="sk-test", cache_enabled=False)


def _stream_reply(client: LLMClient) -> tuple[list[str], list[dict[str, Any]], str | None]:
    """Stream one reply: the chunks it yielded, the calls observers saw and any error."""
    chunks: list[str] = []
    seen: list[dict[str, Any]] = []
    with observe_llm_calls(seen.append):
        try:
            for chunk in client.chat_messages_stream(
                "sys", [ChatMessage(role="user", content="hi")]
            ):
                chunks.append(chunk)
        except AIClientError as exc:
            return chunks, seen, type(exc).__name__
    return chunks, seen, None


def test_a_complete_stream_records_its_finish_reason(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify a stream that reaches its final frame writes one row with its reason."""
    client = _stream_client(monkeypatch)
    frames = [openai_chunk("Hel"), openai_chunk("lo", "length"), OPENAI_DONE]
    route_client(client, monkeypatch, lambda request: reply(frames))

    chunks, seen, error = _stream_reply(client)

    assert (chunks, [c["finish_reason"] for c in seen], error, _ledger_rows(spend_ledger)) == (
        ["Hel", "lo"],
        ["length"],
        None,
        [("stream", "length")],
    )


def test_a_stream_failing_after_output_records_its_spend_as_an_error(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify tokens yielded before a failure are recorded with reason `error`, then it raises."""
    client = _stream_client(monkeypatch)
    route_client(client, monkeypatch, lambda request: reply([openai_chunk("Hel")]))

    chunks, seen, error = _stream_reply(client)

    assert (chunks, [c["finish_reason"] for c in seen], error, _ledger_rows(spend_ledger)) == (
        ["Hel"],
        ["error"],
        "AIClientError",
        [("stream", "error")],
    )


def _refuse_connection(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("connection refused", request=request)


def _server_error(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(500, json={"error": {"message": "internal error"}})


@pytest.mark.parametrize(
    "handler", [_refuse_connection, _server_error], ids=["connect", "http-500"]
)
def test_a_stream_failing_before_its_first_chunk_records_nothing(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger, handler: Any
) -> None:
    """Verify a stream no provider served writes no row and notifies no observer."""
    client = _stream_client(monkeypatch)
    route_client(client, monkeypatch, handler)

    assert (_stream_reply(client), _ledger_rows(spend_ledger)) == (([], [], "AIClientError"), [])
