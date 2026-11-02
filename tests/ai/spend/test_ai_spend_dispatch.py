"""Integration tests verifying automatic spend recording during LLMClient dispatches."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Iterator
from typing import Any

import httpx2
import pytest

import devops_cli.ai.spend as spend_mod
from devops_cli.ai import context_budget
from devops_cli.ai.client import AIClientError, LLMClient, LLMResponse, RequestPriority
from devops_cli.ai.client.models import CallSampling
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
    route_retrying_client,
    sse_data,
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


# ── Why a reply ended, from the provider to the ledger and its observers ──────────────────────


def _ledger_rows(ledger: SpendLedger) -> list[tuple[str, str | None]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
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
    sampling: CallSampling | None = None,
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

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute("SELECT request_type, cached FROM ai_spend_records").fetchall()
    assert (reply.cached, [call["cached"] for call in seen], rows) == (
        False,
        [False],
        [("chat_dispatch", 0)],
    )


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


def test_a_stream_refused_before_its_first_chunk_records_nothing(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify a stream that cannot open a connection writes no row and notifies no observer."""
    client = _stream_client(monkeypatch)
    route_retrying_client(client, monkeypatch, _refuse_connection)

    assert (_stream_reply(client), _ledger_rows(spend_ledger)) == (([], [], "AIClientError"), [])


def test_a_stream_failing_before_its_first_chunk_with_server_error_records_each_attempt(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify a stream that the server answers with 500 writes one error row per attempt."""
    client = _stream_client(monkeypatch)
    route_retrying_client(client, monkeypatch, _server_error)

    chunks, seen, error = _stream_reply(client)

    assert (chunks, [c["finish_reason"] for c in seen], error, _ledger_rows(spend_ledger)) == (
        [],
        ["error"] * 5,
        "AIClientError",
        [("stream", "error")] * 5,
    )


def _chat_client(monkeypatch: pytest.MonkeyPatch, model: str = "devops-review") -> LLMClient:
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    config = AIConfig(
        provider="openai",
        model=model,
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    return LLMClient(config, api_key="sk-test", cache_enabled=False)


def _ok_reply(model: str = "gpt-test") -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "model": model,
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )


def test_failed_chat_dispatch_attempts_are_recorded_in_spend_ledger(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify each attempt reaching the gateway and failing writes an error row in the ledger."""
    client = _chat_client(monkeypatch)

    def _ok(_request: httpx2.Request) -> httpx2.Response:
        return _ok_reply()

    # 1. 500 once then reply -> 2 rows: ("chat_dispatch", "error") and ("chat_dispatch", "stop")
    responses_500: list[Callable[[httpx2.Request], httpx2.Response]] = [_server_error, _ok]
    route_retrying_client(client, monkeypatch, lambda req: responses_500.pop(0)(req))
    reply_res = client.chat("system", "user", use_cache=False)
    assert reply_res.content == "ok"
    assert _ledger_rows(spend_ledger) == [("chat_dispatch", "error"), ("chat_dispatch", "stop")]

    # 2. Read timeout then reply -> 2 rows
    spend_ledger.reset()

    def _read_timeout(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timed out", request=request)

    responses_timeout: list[Callable[[httpx2.Request], httpx2.Response]] = [_read_timeout, _ok]
    route_retrying_client(client, monkeypatch, lambda req: responses_timeout.pop(0)(req))
    reply_res = client.chat("system", "user", use_cache=False)
    assert reply_res.content == "ok"
    assert _ledger_rows(spend_ledger) == [("chat_dispatch", "error"), ("chat_dispatch", "stop")]

    # 3. Connection refused then reply -> 1 row (ConnectError writes no row)
    spend_ledger.reset()
    responses_connect: list[Callable[[httpx2.Request], httpx2.Response]] = [_refuse_connection, _ok]
    route_retrying_client(client, monkeypatch, lambda req: responses_connect.pop(0)(req))
    reply_res = client.chat("system", "user", use_cache=False)
    assert reply_res.content == "ok"
    assert _ledger_rows(spend_ledger) == [("chat_dispatch", "stop")]

    # 4. 500 five times -> 5 error rows, call raises
    spend_ledger.reset()
    route_retrying_client(client, monkeypatch, _server_error)
    with pytest.raises(AIClientError) as raised:
        client.chat("system", "user", use_cache=False)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"
    assert _ledger_rows(spend_ledger) == [("chat_dispatch", "error")] * 5


def test_chat_dispatch_records_served_by_and_resolved_model(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify chat dispatch records both served_by header and resolved model from reply body."""
    client = _chat_client(monkeypatch, model="devops-review")
    backend_header = {"x-litellm-model-api-base": "http://ollama-16gib:11434"}

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            headers=backend_header,
            json={
                "model": "gpt-oss:20b",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    route_retrying_client(client, monkeypatch, handler)
    client.chat("sys", "user", use_cache=False)

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT model, served_by, served_model FROM ai_spend_records ORDER BY id"
        ).fetchall()
    assert rows == [("devops-review", "http://ollama-16gib:11434", "gpt-oss:20b")]


def test_stream_dispatch_records_served_by_and_resolved_model(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify stream dispatch records both served_by header and resolved model from stream frames."""
    client = _stream_client(monkeypatch)
    backend_header = {"x-litellm-model-api-base": "http://ollama-16gib:11434"}
    frames = [
        sse_data({"model": "gpt-oss:20b", "choices": [{"index": 0, "delta": {"content": "Hel"}}]}),
        sse_data(
            {
                "model": "gpt-oss:20b",
                "choices": [{"index": 0, "delta": {"content": "lo"}, "finish_reason": "stop"}],
            }
        ),
        OPENAI_DONE,
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            headers={**backend_header, "content-type": "text/event-stream"},
            content=iter(frames),
        )

    route_retrying_client(client, monkeypatch, handler)
    list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT model, served_by, served_model FROM ai_spend_records ORDER BY id"
        ).fetchall()
    assert rows == [("gpt-test", "http://ollama-16gib:11434", "gpt-oss:20b")]


def test_failed_attempt_records_served_by_and_served_model_when_error_names_them(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify a failed attempt records backend and model when the error response names them."""
    client = _chat_client(monkeypatch, model="devops-review")
    error_headers = {
        "x-litellm-model-api-base": "http://ollama-16gib:11434",
        "x-litellm-model-name": "gpt-oss:20b",
    }
    calls = [
        lambda req: httpx2.Response(
            500, headers=error_headers, json={"error": {"message": "failed"}}
        ),
        lambda req: _ok_reply(model="devops-review"),
    ]
    route_retrying_client(client, monkeypatch, lambda req: calls.pop(0)(req))
    client.chat("system", "user", use_cache=False)

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT finish_reason, served_by, served_model FROM ai_spend_records ORDER BY id"
        ).fetchall()
    assert rows == [
        ("error", "http://ollama-16gib:11434", "gpt-oss:20b"),
        ("stop", None, None),
    ]


def _ledger_tokens(ledger: SpendLedger) -> list[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        return conn.execute(
            "SELECT finish_reason, prompt_tokens, completion_tokens, served_model"
            " FROM ai_spend_records ORDER BY id"
        ).fetchall()


def test_a_failed_attempt_records_the_usage_and_model_that_its_error_body_names(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """With no serving-model header, the error body's model and usage go on the error row."""
    client = _chat_client(monkeypatch, model="devops-review")
    body = {
        "model": "gpt-oss:20b",
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        "error": {"message": "failed"},
    }
    calls = [lambda req: httpx2.Response(500, json=body), lambda req: _ok_reply()]
    route_retrying_client(client, monkeypatch, lambda req: calls.pop(0)(req))

    client.chat("system", "user", use_cache=False)

    assert _ledger_tokens(spend_ledger) == [
        ("error", 12, 3, "gpt-oss:20b"),
        ("stop", 10, 5, "gpt-test"),
    ]


def _body_cut_by_the_network() -> Iterator[bytes]:
    yield b'{"error": '
    raise httpx2.ReadError("connection reset")


@pytest.mark.parametrize(
    "failed",
    [
        lambda: httpx2.Response(502, text="<html><title>Bad gateway</title></html>"),
        lambda: httpx2.Response(
            500, headers={"content-type": "application/json"}, content=_body_cut_by_the_network()
        ),
    ],
    ids=["html-body", "body-cut-by-the-network"],
)
def test_a_failed_attempt_whose_body_cannot_be_read_as_json_records_no_tokens(
    monkeypatch: pytest.MonkeyPatch,
    spend_ledger: SpendLedger,
    failed: Callable[[], httpx2.Response],
) -> None:
    """A Cloudflare HTML page or a body that the network cut still writes its error row."""
    client = _chat_client(monkeypatch)
    calls = [lambda req: failed(), lambda req: _ok_reply()]
    route_retrying_client(client, monkeypatch, lambda req: calls.pop(0)(req))

    client.chat("system", "user", use_cache=False)

    assert _ledger_tokens(spend_ledger) == [("error", 0, 0, None), ("stop", 10, 5, "gpt-test")]
