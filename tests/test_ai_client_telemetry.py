"""LLM spans carry the GenAI attributes the pinned semantic conventions define, once each."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any

import pytest

from devops_cli.ai import context_budget
from devops_cli.ai.client.models import LLMResponse, RequestPriority, genai_provider_name
from devops_cli.ai.client.unified import LLMClient, _server_span_attributes
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry.semconv import load_genai_snapshot
from devops_cli.telemetry.tracer import get_tracer, reset_tracer

INFERENCE_REQUIRED = load_genai_snapshot()["spans"]["gen_ai.inference.client"]["required"]


@pytest.fixture
def sent_spans(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture every OTLP payload the tracer sends."""
    reset_tracer()
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(get_tracer(), "_send_payload", lambda path, p: payloads.append(p))
    yield payloads
    reset_tracer()


def _spans(payloads: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [
        span
        for payload in payloads
        for resource in payload.get("resourceSpans", [])
        for scope in resource.get("scopeSpans", [])
        for span in scope.get("spans", [])
        if span.get("name") == name
    ]


def _value(any_value: dict[str, Any]) -> Any:
    """Decode an OTLP AnyValue; integers travel as strings."""
    ((kind, raw),) = any_value.items()
    if kind == "intValue":
        return int(raw)
    if kind == "arrayValue":
        return [_value(item) for item in raw["values"]]
    return raw


def _attributes(span: dict[str, Any]) -> dict[str, Any]:
    return {attr["key"]: _value(attr["value"]) for attr in span.get("attributes", [])}


def _reply(
    _self: object,
    _system: str,
    _messages: list[Any],
    *,
    enable_thinking: bool = True,
    priority: RequestPriority | str | None = None,
) -> LLMResponse:
    return LLMResponse(
        "OK",
        backend_info="ollama (example.com:11434)",
        model="test-model",
        prompt_tokens=12,
        completion_tokens=3,
        total_tokens=15,
    )


def _two_chunks(
    _self: object,
    _system: str,
    _messages: list[ChatMessage],
    *,
    enable_thinking: bool = True,
    priority: RequestPriority | str | None = None,
) -> Generator[str]:
    yield "Hello "
    yield "world"


def test_chat_dispatch_is_the_one_inference_span(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """ai.llm.dispatch is a CLIENT inference span with usage; the ai.llm.chat wrapper has none."""
    monkeypatch.setattr(LLMClient, "_ollama_messages", _reply)
    cfg = AIConfig(provider="ollama", model="test-model", ollama_urls=["http://example.com:11434"])

    LLMClient(cfg).chat("system instructions", "hello", use_cache=False)

    (dispatch,) = _spans(sent_spans, "ai.llm.dispatch")
    (chat,) = _spans(sent_spans, "ai.llm.chat")
    dispatch_attrs, chat_attrs = _attributes(dispatch), _attributes(chat)
    reply_keys = (
        "server.address",
        "server.port",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.response.model",
    )
    assert (
        dispatch["kind"],
        [key for key in INFERENCE_REQUIRED if key not in dispatch_attrs],
        (dispatch_attrs["gen_ai.operation.name"], dispatch_attrs["gen_ai.provider.name"]),
        tuple(dispatch_attrs.get(key) for key in reply_keys),
        chat["kind"],
        sorted(key for key in chat_attrs if key.startswith(("gen_ai.usage.", "gen_ai.response."))),
    ) == (
        "SPAN_KIND_CLIENT",
        [],
        ("chat", "ollama"),
        ("example.com", 11434, 12, 3, "test-model"),
        "SPAN_KIND_INTERNAL",
        [],
    )


def test_cached_chat_names_no_response_model(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """A cache hit opens no inference span and leaves the response model unset."""
    monkeypatch.setattr(LLMClient, "_ollama_messages", _reply)
    client = LLMClient(
        AIConfig(provider="ollama", model="test-model", ollama_urls=["http://example.com:11434"])
    )

    client.chat("system instructions", "hello")
    client.chat("system instructions", "hello")

    cached = _attributes(_spans(sent_spans, "ai.llm.chat")[-1])
    assert (
        len(_spans(sent_spans, "ai.llm.dispatch")),
        cached.get("llm.cached"),
        sorted(key for key in cached if key.startswith(("gen_ai.usage.", "gen_ai.response."))),
    ) == (1, True, [])


@pytest.mark.parametrize(
    ("ollama_urls", "server_keys", "server"),
    [
        (["http://example.com:11434"], ["server.address", "server.port"], ("example.com", 11434)),
        (["http://example.com:11434", "http://example.com:11435"], [], (None, None)),
    ],
    ids=["one-host", "two-hosts"],
)
def test_stream_is_a_client_inference_span(
    monkeypatch: pytest.MonkeyPatch,
    sent_spans: list[dict[str, Any]],
    ollama_urls: list[str],
    server_keys: list[str],
    server: tuple[str | None, int | None],
) -> None:
    """ai.llm.stream is a CLIENT inference span; a host list names no single server."""
    monkeypatch.setattr(LLMClient, "_dispatch_stream", _two_chunks)
    # The stream's spend estimate counts tokens; loading the tokenizer is not under test.
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    client = LLMClient(AIConfig(provider="ollama", model="test-model", ollama_urls=ollama_urls))

    chunks = list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    (stream,) = _spans(sent_spans, "ai.llm.stream")
    attrs = _attributes(stream)
    assert (
        chunks,
        stream["kind"],
        [key for key in INFERENCE_REQUIRED if key not in attrs],
        sorted(key for key in attrs if key.startswith("server.")),
        (attrs.get("server.address"), attrs.get("server.port")),
        attrs.get("gen_ai.request.stream"),
        type(attrs.get("gen_ai.response.time_to_first_chunk")),
    ) == (["Hello ", "world"], "SPAN_KIND_CLIENT", [], server_keys, server, True, float)


def _claude_reply(
    _self: object, _system: str, _messages: list[Any], *, enable_thinking: bool = True
) -> LLMResponse:
    return LLMResponse("OK", backend_info="claude (api.anthropic.com)", model="claude-test")


def test_claude_spans_name_the_provider_anthropic(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """The dispatch, chat and stream spans of a claude request write the conventions' name."""
    monkeypatch.setattr(LLMClient, "_claude_messages", _claude_reply)
    monkeypatch.setattr(LLMClient, "_dispatch_stream", _two_chunks)
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    client = LLMClient(AIConfig(provider="claude", model="claude-test"))

    client.chat("system instructions", "hello", use_cache=False)
    list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    names = ("ai.llm.dispatch", "ai.llm.chat", "ai.llm.stream")
    assert [
        [_attributes(span).get("gen_ai.provider.name") for span in _spans(sent_spans, name)]
        for name in names
    ] == [["anthropic"], ["anthropic"], ["anthropic"]]


def test_server_attributes_come_from_one_backend_netloc() -> None:
    """The host becomes server.address, a port server.port, and a host list neither."""
    netlocs = (
        "example.com:11434",
        "example.com",
        "[::1]:11434",
        "example.com:11434, example.com:11435",
        "example.com:port",
        "",
        "unknown",
    )

    assert [_server_span_attributes(netloc) for netloc in netlocs] == [
        {"server.address": "example.com", "server.port": 11434},
        {"server.address": "example.com"},
        {"server.address": "::1", "server.port": 11434},
        {},
        {},
        {},
        {},
    ]


def test_provider_names_follow_the_conventions_well_known_values() -> None:
    """claude is written as anthropic; every other provider id is a custom value, unchanged."""
    providers = ("claude", "ollama", "openai", "gateway", "copilot", "github_copilot")

    assert [genai_provider_name(provider) for provider in providers] == [
        "anthropic",
        "ollama",
        "openai",
        "gateway",
        "copilot",
        "github_copilot",
    ]
