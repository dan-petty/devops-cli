"""A reply names the server that it came from by the origin of the URL that the client called.

The origin holds the scheme, the host and the port, and never userinfo. Thus a password in a
configured AI URL stays out of the terminal output, the spend ledger, the metric labels, the
spans and the response cache, and the URL still sends it as Basic authentication. Every server
is a MockTransport, and `public_dns` answers each name, so no test opens a socket or sends a DNS
query.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry.tracer import get_recent_spans
from tests.llm_stream_fakes import NDJSON, ollama_line, reply, route_client
from tests.support.telemetry_capture import Captured

PASSWORD = "pw"
BASIC_USER_PW = "Basic dXNlcjpwdw=="

OLLAMA_REPLY = {
    "model": "test-model",
    "message": {"role": "assistant", "content": "OK"},
    "done": True,
    "done_reason": "stop",
    "prompt_eval_count": 12,
    "eval_count": 3,
}
COMPLETION = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 0,
    "model": "test-model",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
}
CLAUDE_MESSAGE = {
    "id": "msg_test",
    "type": "message",
    "role": "assistant",
    "model": "test-model",
    "content": [{"type": "text", "text": "OK"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 12, "output_tokens": 3},
}
NOT_FOUND = {"type": "error", "error": {"type": "not_found_error", "message": "not found"}}


@pytest.fixture(autouse=True)
def _public_endpoints(public_dns: str) -> None:
    """The configured hosts are example.com names, which resolve to a public address."""


def _serve(request: httpx2.Request) -> httpx2.Response:
    """Answer a chat request of each provider; refuse every other request, as a model lookup."""
    path = request.url.path
    if path.endswith("/api/chat"):
        return httpx2.Response(200, json=OLLAMA_REPLY)
    if path.endswith("/chat/completions"):
        return httpx2.Response(200, json=COMPLETION)
    if path.endswith("/v1/messages"):
        return httpx2.Response(200, json=CLAUDE_MESSAGE)
    return httpx2.Response(404, json=NOT_FOUND)


def _client(provider: str, settings: dict[str, Any]) -> LLMClient:
    return LLMClient(
        AIConfig(provider=provider, model="test-model", allow_private_network=True, **settings)
    )


def _ledger_rows(ledger: SpendLedger) -> list[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        return conn.execute(
            "SELECT server, backend_info FROM ai_spend_records ORDER BY id"
        ).fetchall()


def _counter_servers(captured: Captured) -> list[str]:
    return sorted(
        {attrs["server"] for attrs, _value in captured.points("devops_cli_ai_requests_total")}
    )


def _otlp_value(any_value: dict[str, Any]) -> Any:
    ((kind, raw),) = any_value.items()
    return int(raw) if kind == "intValue" else raw


def _server_attributes(span_name: str) -> dict[str, Any]:
    (span,) = [span for span in get_recent_spans() if span["name"] == span_name]
    attributes = {a["key"]: _otlp_value(a["value"]) for a in span.get("attributes", [])}
    return {key: value for key, value in attributes.items() if key.startswith("server.")}


def _cache_entries(data_dir: Path) -> list[str]:
    return [path.read_text(encoding="utf-8") for path in sorted(data_dir.rglob("llm_*.json"))]


ROWS = [
    pytest.param(
        "ollama",
        {"ollama_urls": ["http://user:pw@example.com:11434"]},
        "http://example.com:11434",
        "ollama (example.com:11434)",
        "example.com:11434",
        {"server.address": "example.com", "server.port": 11434},
        id="ollama-userinfo",
    ),
    pytest.param(
        "gateway",
        {"gateway_url": "http://user:pw@example.com:4000/v1"},
        "http://example.com:4000",
        "gateway (example.com:4000)",
        "example.com:4000",
        {"server.address": "example.com", "server.port": 4000},
        id="gateway-userinfo",
    ),
    pytest.param(
        "ollama",
        {"ollama_urls": ["http://[2001:db8::1]:11434"]},
        "http://[2001:db8::1]:11434",
        "ollama ([2001:db8::1]:11434)",
        "[2001:db8::1]:11434",
        {"server.address": "2001:db8::1", "server.port": 11434},
        id="ollama-ipv6",
    ),
    pytest.param(
        "ollama",
        {"ollama_urls": ["http://Example.COM:11434"]},
        "http://example.com:11434",
        "ollama (example.com:11434)",
        "example.com:11434",
        {"server.address": "example.com", "server.port": 11434},
        id="ollama-upper-case-host",
    ),
    pytest.param(
        "ollama",
        {"ollama_urls": ["http://example.com:80"]},
        "http://example.com:80",
        "ollama (example.com)",
        "example.com",
        {"server.address": "example.com", "server.port": 80},
        id="ollama-default-port",
    ),
    pytest.param(
        "claude",
        {},
        "https://api.anthropic.com",
        "claude (api.anthropic.com)",
        "api.anthropic.com",
        {"server.address": "api.anthropic.com", "server.port": 443},
        id="claude-default",
    ),
]


@pytest.mark.parametrize(
    ("provider", "settings", "origin_url", "backend", "server", "span_server"), ROWS
)
def test_a_reply_names_its_server_by_the_origin_of_the_url_called(
    monkeypatch: pytest.MonkeyPatch,
    captured: Captured,
    spend_ledger: SpendLedger,
    provider: str,
    settings: dict[str, Any],
    origin_url: str,
    backend: str,
    server: str,
    span_server: dict[str, Any],
) -> None:
    """The reply holds the origin of the URL called, and the display, the ledger, the counters
    and the span name the server as httpx2 reads it.

    The display, the ledger and the counters carry `host[:port]` as httpx2 writes it, so the
    host is lower case and a default port is left out. The span carries the port in all cases.
    """
    client = _client(provider, settings)
    route_client(client, monkeypatch, _serve)

    answer = client.chat("system instructions", "hello")

    assert (
        getattr(answer, "origin", None),
        client.backend_info,
        answer.backend_info,
        _ledger_rows(spend_ledger),
        _counter_servers(captured),
        _server_attributes("ai.llm.dispatch"),
    ) == (
        httpx2.URL(origin_url).origin,
        backend,
        backend,
        [(server, backend)],
        [server],
        span_server,
    )


@pytest.mark.parametrize(
    ("provider", "settings"),
    [
        pytest.param("ollama", {"ollama_urls": ["http://user:pw@example.com:11434"]}, id="ollama"),
        pytest.param(
            "gateway", {"gateway_url": "http://user:pw@example.com:4000/v1"}, id="gateway"
        ),
    ],
)
def test_a_password_in_a_configured_url_stays_out_of_every_record(
    monkeypatch: pytest.MonkeyPatch,
    captured: Captured,
    spend_ledger: SpendLedger,
    isolate_data_dir: Path,
    provider: str,
    settings: dict[str, Any],
) -> None:
    """The server gets the userinfo as Basic authentication, and no record holds the password."""
    client = _client(provider, settings)
    sent = route_client(client, monkeypatch, _serve)

    answer = client.chat("system instructions", "hello")

    chat_requests = [request for request in sent if request.method == "POST"]
    records = {
        "backend_info": [client.backend_info, answer.backend_info],
        "ledger": [str(value) for row in _ledger_rows(spend_ledger) for value in row],
        "counters": [
            str(value)
            for attrs, _value in captured.points("devops_cli_ai_requests_total")
            for value in attrs.values()
        ],
        "spans": [json.dumps(span) for span in get_recent_spans()],
        "cache": _cache_entries(isolate_data_dir),
    }
    assert (
        [request.headers.get("authorization") for request in chat_requests],
        {name: bool(values) for name, values in records.items()},
        {name: [v for v in values if PASSWORD in v] for name, values in records.items()},
    ) == (
        [BASIC_USER_PW],
        dict.fromkeys(records, True),
        {name: [] for name in records},
    )


def test_a_streamed_reply_names_its_leased_server_without_its_password(
    monkeypatch: pytest.MonkeyPatch, captured: Captured, spend_ledger: SpendLedger
) -> None:
    """A stream over two configured servers records the one that it leased, and no password.

    The stream span opens before a server is leased, so it names no server.
    """
    client = _client(
        "ollama",
        {"ollama_urls": ["http://user:pw@example.com:11434", "http://example.com:11435"]},
    )
    frames = [ollama_line("Hello "), ollama_line("world", done=True, eval_count=2)]
    route_client(client, monkeypatch, lambda request: reply(frames, NDJSON))

    chunks = list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    backend = "ollama (example.com:11434, example.com:11435)"
    assert (
        chunks,
        client.backend_info,
        _ledger_rows(spend_ledger),
        _counter_servers(captured),
        _server_attributes("ai.llm.stream"),
    ) == (["Hello ", "world"], backend, [("example.com:11434", backend)], ["example.com:11434"], {})


@pytest.mark.parametrize(
    ("settings", "backend"),
    [
        pytest.param({"api_base_url": "example.com:4000"}, "openai (unknown)", id="no-scheme"),
        pytest.param({"api_base_url": "http://[::1"}, "openai (unknown)", id="unreadable"),
    ],
)
def test_a_configured_url_with_no_origin_displays_unknown(
    settings: dict[str, Any], backend: str
) -> None:
    """A URL that httpx2 gives no origin for is shown as `unknown`, never as its own text.

    The settings refuse such a URL, so only a config built without validation holds one.
    """
    client = LLMClient(AIConfig.model_construct(provider="openai", model="test-model", **settings))

    assert (client.backend_host, client.backend_info) == ("unknown", backend)
