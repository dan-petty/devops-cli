"""LLM spans carry the GenAI attributes the pinned semantic conventions define, once each, and a
gateway call's wait for a backend slot is a span and a metric of its own, outside the call's
inference time."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator, Iterator
from typing import Any

import httpx2
import pytest

from devops_cli.ai import context_budget
from devops_cli.ai.client import network
from devops_cli.ai.client import openai as openai_client
from devops_cli.ai.client import unified as unified_client
from devops_cli.ai.client.models import (
    CallSampling,
    LLMResponse,
    RequestPriority,
    genai_provider_name,
)
from devops_cli.ai.client.unified import LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry.instruments import AI_GATEWAY_SLOT_WAIT, Instrument
from devops_cli.telemetry.semconv import load_genai_snapshot
from devops_cli.telemetry.tracer import get_tracer, reset_tracer
from tests.llm_stream_fakes import (
    NDJSON,
    OPENAI_DONE,
    ollama_line,
    openai_chunk,
    reply,
    route_client,
)

INFERENCE_REQUIRED = load_genai_snapshot()["spans"]["gen_ai.inference.client"]["required"]


@pytest.fixture
def sent_spans(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
) -> Iterator[list[dict[str, Any]]]:
    """Capture every OTLP payload the tracer sends."""
    config(telemetry={"enabled": True})
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
    sampling: CallSampling | None = None,
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
    sampling: CallSampling | None = None,
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
    _self: object,
    _system: str,
    _messages: list[Any],
    *,
    enable_thinking: bool = True,
    sampling: CallSampling | None = None,
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


OLLAMA_CHAT_REPLY = {
    "model": "test-model",
    "message": {"role": "assistant", "content": "OK"},
    "done": True,
    "done_reason": "stop",
    "prompt_eval_count": 12,
    "eval_count": 3,
}
REFUSED_PORT = 11434


def _ollama_server(request: httpx2.Request) -> httpx2.Response:
    """An Ollama that refuses each connection to port 11434 and answers a chat call on others.

    It streams the reply when the request asks for a stream.
    """
    if request.url.port == REFUSED_PORT:
        raise httpx2.ConnectError("connection refused", request=request)
    if not request.url.path.endswith("/api/chat"):
        return httpx2.Response(404, json={"error": "not found"})
    if json.loads(request.content).get("stream"):
        return reply([ollama_line("O"), ollama_line("K", done=True, eval_count=1)], NDJSON)
    return httpx2.Response(200, json=OLLAMA_CHAT_REPLY)


def _chat(client: LLMClient) -> None:
    client.chat("system instructions", "hello", use_cache=False)


def _stream(client: LLMClient) -> None:
    list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize(
    ("call", "span_name", "ollama_urls", "server"),
    [
        pytest.param(
            _chat,
            "ai.llm.dispatch",
            ["http://example.com:11434", "http://example.com:11435"],
            {"server.address": "example.com", "server.port": 11435},
            id="dispatch-server-that-answered",
        ),
        pytest.param(
            _chat,
            "ai.llm.dispatch",
            ["https://example.com"],
            {"server.address": "example.com", "server.port": 443},
            id="dispatch-scheme-default-port",
        ),
        pytest.param(
            _stream,
            "ai.llm.stream",
            ["http://example.com:11435"],
            {"server.address": "example.com", "server.port": 11435},
            id="stream-one-host",
        ),
        pytest.param(
            _stream,
            "ai.llm.stream",
            ["http://example.com:11434", "http://example.com:11435"],
            {},
            id="stream-host-list",
        ),
    ],
)
def test_server_attributes_come_from_the_origin_of_the_url_called(
    sent_spans: list[dict[str, Any]],
    call: Callable[[LLMClient], None],
    span_name: str,
    ollama_urls: list[str],
    server: dict[str, Any],
) -> None:
    """The dispatch span names the server that answered, by the origin of the URL called.

    `server.port` is the default port of the scheme when the URL has none. The stream span opens
    before the client leases a server, so it names a server only when one server is configured.
    """
    cfg = AIConfig(provider="ollama", model="test-model", ollama_urls=ollama_urls)
    client = LLMClient(cfg, transport=httpx2.MockTransport(_ollama_server))

    call(client)

    (span,) = _spans(sent_spans, span_name)
    attrs = _attributes(span)
    assert {key: value for key, value in attrs.items() if key.startswith("server.")} == server


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


@pytest.mark.parametrize(("reason", "expected"), [("length", ["length"]), (None, None)])
def test_the_dispatch_span_names_the_reason_the_reply_ended(
    monkeypatch: pytest.MonkeyPatch,
    sent_spans: list[dict[str, Any]],
    reason: str | None,
    expected: list[str] | None,
) -> None:
    """A reply's reason is on ai.llm.dispatch only; an unknown one sets no attribute."""

    def cut_reply(*args: Any, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            "OK",
            backend_info="ollama (example.com:11434)",
            prompt_tokens=12,
            completion_tokens=3,
            finish_reason=reason,
        )

    monkeypatch.setattr(LLMClient, "_ollama_messages", cut_reply)
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    cfg = AIConfig(provider="ollama", model="test-model", ollama_urls=["http://example.com:11434"])

    LLMClient(cfg).chat("system instructions", "hello", use_cache=False)

    (dispatch,) = _spans(sent_spans, "ai.llm.dispatch")
    (chat,) = _spans(sent_spans, "ai.llm.chat")
    key = "gen_ai.response.finish_reasons"
    assert (_attributes(dispatch).get(key), key in _attributes(chat)) == (expected, False)


def test_a_complete_stream_names_the_reason_on_the_stream_span(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """The reason in a stream's final frames is on ai.llm.stream."""
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    config = AIConfig(
        provider="openai",
        model="gpt-test",
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    client = LLMClient(config, api_key="sk-test")
    frames = [openai_chunk("Hel"), openai_chunk("lo", "length"), OPENAI_DONE]
    route_client(client, monkeypatch, lambda request: reply(frames))

    chunks = list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))

    (stream,) = _spans(sent_spans, "ai.llm.stream")
    assert (chunks, _attributes(stream).get("gen_ai.response.finish_reasons")) == (
        ["Hel", "lo"],
        ["length"],
    )


def test_stream_span_records_sanitizer_attributes_when_sanitize_is_enabled(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """Stream trace span ai.llm.stream records unopened_close_tags, unclosed_stream, and discarded_thought_chars when sanitize=True."""
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    config = AIConfig(
        provider="openai",
        model="gpt-test",
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    client = LLMClient(config, api_key="sk-test")
    frames = [
        openai_chunk("Clean prefix</think>"),
        openai_chunk("<think>unclosed thought"),
        OPENAI_DONE,
    ]
    route_client(client, monkeypatch, lambda request: reply(frames))

    chunks = list(
        client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")], sanitize=True)
    )

    (stream,) = _spans(sent_spans, "ai.llm.stream")
    attrs = _attributes(stream)
    assert "".join(chunks) == "Clean prefix"
    assert attrs.get("llm.stream.unopened_close_tags") == 1
    assert attrs.get("llm.stream.unclosed_stream") is True
    assert attrs.get("llm.stream.discarded_thought_chars") == 0


class _Clock:
    """A clock that moves only when told to, read as monotonic and as perf_counter time."""

    def __init__(self) -> None:
        self.now = 0.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def monotonic(self) -> float:
        return self.now

    def perf_counter(self) -> float:
        return self.now


class _SlotsFreeAfter:
    """Gateway slots that each take `wait` seconds of `clock` to come free."""

    def __init__(self, clock: _Clock, wait: float) -> None:
        self.clock, self.wait = clock, wait

    def acquire(self, timeout: float | None = None) -> bool:
        self.clock.advance(self.wait)
        return True

    def release(self) -> None:
        """A slot that was never held needs no release."""


_SLOT_WAIT_SECONDS, _REQUEST_SECONDS = 120.0, 2.0
_HI = [ChatMessage(role="user", content="hi")]

# Each gateway call: (its span, the call, the gateway's reply to it).
_TIMED_GATEWAY_CALLS: dict[
    str, tuple[str, Callable[[LLMClient], Any], Callable[[], httpx2.Response]]
] = {
    "plain": (
        "ai.llm.dispatch",
        lambda client: client._dispatch_messages("sys", _HI),
        lambda: httpx2.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
    ),
    "stream": (
        "ai.llm.stream",
        lambda client: list(client.chat_messages_stream("sys", _HI)),
        lambda: reply([openai_chunk("ok", "stop"), OPENAI_DONE]),
    ),
}


@pytest.mark.parametrize("call", list(_TIMED_GATEWAY_CALLS))
@pytest.mark.usefixtures("public_dns")
def test_a_gateway_call_is_timed_from_when_its_slot_is_held(
    call: str, monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """A call that waits 120 s for a gateway slot and 2 s for its reply records the wait as an
    `ai.llm.gateway_slot` span under the call's span and as one observation of the wait
    histogram, and records 2 s, not 122 s, as its wall time and its spend's duration, streamed
    or not."""
    span_name, invoke, gateway_reply = _TIMED_GATEWAY_CALLS[call]
    clock = _Clock()
    for module in (network, openai_client, unified_client):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(network, "gateway_slots", _SlotsFreeAfter(clock, _SLOT_WAIT_SECONDS))
    observed: list[tuple[str, float]] = []

    def observe(instrument: Instrument, value: float, attributes: Any = None) -> None:
        observed.append((instrument.name, value))

    monkeypatch.setattr(network, "emit", observe)
    durations: list[float] = []
    monkeypatch.setattr(
        "devops_cli.ai.spend.track_request_spend",
        lambda **kwargs: durations.append(kwargs["duration_seconds"]),
    )
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    client = LLMClient(
        AIConfig(
            provider="gateway", gateway_url="http://example.com/v1", allow_private_network=True
        ),
        api_key="sk-test",
        cache_enabled=False,
    )

    def answer(request: httpx2.Request) -> httpx2.Response:
        clock.advance(_REQUEST_SECONDS)
        return gateway_reply()

    route_client(client, monkeypatch, answer)

    invoke(client)

    (slot_span,) = _spans(sent_spans, "ai.llm.gateway_slot")
    (call_span,) = _spans(sent_spans, span_name)
    assert (
        observed,
        _attributes(slot_span).get("llm.gateway.slot_wait_seconds"),
        slot_span.get("parentSpanId") == call_span["spanId"],
        _attributes(call_span).get("llm.wall_seconds"),
        durations,
    ) == (
        [(AI_GATEWAY_SLOT_WAIT.name, _SLOT_WAIT_SECONDS)],
        _SLOT_WAIT_SECONDS,
        True,
        _REQUEST_SECONDS,
        [_REQUEST_SECONDS],
    )


def _gateway_client(monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    """A gateway client whose route is `devops-chat`, with spend tracking stubbed out."""
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    return LLMClient(
        AIConfig(
            provider="gateway",
            model="devops-chat",
            gateway_url="http://example.com/v1",
            allow_private_network=True,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )


def test_a_gateway_dispatch_span_names_the_deployment_model_that_served_the_call(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """A gateway reply naming its deployment model sets gen_ai.response.model to that model, not
    the route name the reply body gives, while gen_ai.request.model keeps the route name."""
    client = _gateway_client(monkeypatch)
    route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "model": "devops-chat"},
            headers={"x-litellm-model-name": "openai/gpt-4o"},
        ),
    )

    client._dispatch_messages("sys", _HI)

    (dispatch,) = _spans(sent_spans, "ai.llm.dispatch")
    attrs = _attributes(dispatch)
    assert (
        attrs.get("gen_ai.response.model"),
        attrs.get("gen_ai.request.model"),
    ) == ("openai/gpt-4o", "devops-chat")


def test_a_gateway_dispatch_span_keeps_the_body_model_when_the_gateway_names_none(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """A gateway reply naming no deployment model keeps the reply-body model in
    gen_ai.response.model, with gen_ai.request.model still the route name."""
    client = _gateway_client(monkeypatch)
    route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "model": "qwen3.8:27b"}
        ),
    )

    client._dispatch_messages("sys", _HI)

    (dispatch,) = _spans(sent_spans, "ai.llm.dispatch")
    attrs = _attributes(dispatch)
    assert (
        attrs.get("gen_ai.response.model"),
        attrs.get("gen_ai.request.model"),
    ) == ("qwen3.8:27b", "devops-chat")


def test_chat_dispatch_span_records_reasoning_tokens_attribute(
    monkeypatch: pytest.MonkeyPatch, sent_spans: list[dict[str, Any]]
) -> None:
    """The dispatch span sets gen_ai.usage.reasoning.output_tokens when reasoning tokens are present."""

    def reply_with_reasoning(*args: Any, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            "Final text",
            backend_info="openai (api.openai.com)",
            model="o1-preview",
            prompt_tokens=20,
            completion_tokens=50,
            total_tokens=70,
            reasoning_tokens=35,
        )

    monkeypatch.setattr(LLMClient, "_openai_compat_messages", reply_with_reasoning)
    client = LLMClient(
        AIConfig(provider="openai", model="o1-preview"),
        api_key="sk-test",
        cache_enabled=False,
    )
    client.chat("system instructions", "hello", use_cache=False)

    (dispatch,) = _spans(sent_spans, "ai.llm.dispatch")
    attrs = _attributes(dispatch)
    assert attrs.get("gen_ai.usage.input_tokens") == 20
    assert attrs.get("gen_ai.usage.output_tokens") == 50
    assert attrs.get("gen_ai.usage.reasoning.output_tokens") == 35
