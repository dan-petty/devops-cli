"""The AI client reads a reply's body only up to its size limit, through every provider.

Replies are answered by httpx2's own `MockTransport` with bodies that record how many of their
chunks were read, so no socket is opened. Hosts are `example.com`, as AGENTS.md requires.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient, network
from devops_cli.ai.client.network import request_limited_json, size_limit_text
from devops_cli.ai.client.streaming import StreamingTokenProcessor
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import RecordedBody, route_client

_LIMIT = 4096
_KIB = b"x" * 1024
_MESSAGES = [ChatMessage(role="user", content="hi")]
_OLLAMA = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
_CLAUDE = AIConfig(provider="claude", api_base_url="https://example.com")
_OPENAI = AIConfig(provider="openai", api_base_url="https://example.com/v1")

# Each provider call that reads a whole JSON reply: (its client's config, the call).
_PROVIDER_CALLS: dict[str, tuple[AIConfig, Callable[[LLMClient], Any]]] = {
    "ollama-chat": (_OLLAMA, lambda client: client._ollama_messages("sys", _MESSAGES)),
    "ollama-tags": (_OLLAMA, lambda client: client._ollama_models()),
    "claude-messages": (_CLAUDE, lambda client: client._claude_messages("sys", _MESSAGES)),
    "openai-chat": (_OPENAI, lambda client: client._openai_compat_messages("sys", _MESSAGES)),
    "openai-models": (_OPENAI, lambda client: client._openai_models()),
}


@pytest.fixture
def small_limit(monkeypatch: pytest.MonkeyPatch) -> int:
    """Lower the reply size limit every provider call reads under to 4 KiB."""
    monkeypatch.setattr(network, "DEFAULT_AI_MAX_RESPONSE_BYTES", _LIMIT)
    return _LIMIT


def _answer(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


@pytest.mark.parametrize("call", list(_PROVIDER_CALLS))
@pytest.mark.usefixtures("public_dns")
def test_post_limited_json_stops_reading_past_limit(
    call: str, small_limit: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a provider stops reading a 2 MB reply once it passes the 4 KiB limit."""
    config, invoke = _PROVIDER_CALLS[call]
    client = LLMClient(config, api_key="sk-test", cache_enabled=False)
    body = RecordedBody([_KIB] * 2000)
    route_client(client, monkeypatch, lambda request: httpx2.Response(200, content=iter(body)))

    with pytest.raises(AIClientError) as caught:
        invoke(client)

    assert (str(caught.value), body.read <= 5) == (
        "Response body exceeded maximum size (4KB).",
        True,
    )


def test_a_declared_length_past_the_limit_is_refused_unread() -> None:
    """Verify a Content-Length over the limit is refused before any of the body is read."""
    body = RecordedBody([_KIB] * 8)
    declared = {"content-length": str(8 * len(_KIB))}

    with (
        _answer(
            lambda request: httpx2.Response(200, headers=declared, content=iter(body))
        ) as client,
        pytest.raises(AIClientError, match=r"exceeded maximum size \(4KB\)"),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat", limit_bytes=_LIMIT)

    assert body.read == 0


def test_a_compressed_reply_counts_its_decoded_bytes() -> None:
    """Verify the limit bounds the decoded body, so a small gzip reply cannot inflate past it."""
    packed = gzip.compress(json.dumps({"content": "x" * 100_000}).encode())
    headers = {"content-encoding": "gzip"}

    with (
        _answer(lambda request: httpx2.Response(200, headers=headers, content=packed)) as client,
        pytest.raises(AIClientError, match=r"exceeded maximum size \(4KB\)"),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat", limit_bytes=_LIMIT)

    assert len(packed) < _LIMIT


def test_a_reply_within_the_limit_is_parsed_with_its_headers() -> None:
    """Verify a JSON object reply comes back parsed, with the headers it was sent with."""
    reply = httpx2.Response(200, headers={"x-served-by": "node-a"}, json={"model": "m"})

    with _answer(lambda request: reply) as client:
        payload, headers = request_limited_json(client, "GET", "http://example.com/v1/models")

    assert (payload, headers.get("x-served-by")) == ({"model": "m"}, "node-a")


def test_an_error_reply_raises_with_its_body_readable() -> None:
    """Verify a 4xx reply is never parsed and its body reaches the HTTPStatusError's response."""
    error = {"error": "model 'm' does not support thinking"}

    with (
        _answer(lambda request: httpx2.Response(400, json=error)) as client,
        pytest.raises(httpx2.HTTPStatusError) as caught,
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat")

    assert (caught.value.response.status_code, caught.value.response.json()) == (400, error)


def test_an_error_reply_past_the_limit_is_not_read_whole() -> None:
    """Verify a 5xx reply's body is bounded by the same limit as a success."""
    body = RecordedBody([_KIB] * 2000)

    with (
        _answer(lambda request: httpx2.Response(500, content=iter(body))) as client,
        pytest.raises(AIClientError, match=r"exceeded maximum size \(4KB\)"),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat", limit_bytes=_LIMIT)

    assert body.read <= 5


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not json", "Invalid JSON response payload from AI provider"),
        (b'["a", "b"]', "AI provider replied with a JSON list, not an object"),
    ],
)
def test_a_reply_that_is_not_a_json_object_is_refused(content: bytes, message: str) -> None:
    """Verify a body that is not JSON, or JSON that is not an object, raises AIClientError."""
    with (
        _answer(lambda request: httpx2.Response(200, content=content)) as client,
        pytest.raises(AIClientError, match=message),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat")


@pytest.mark.parametrize(
    ("limit_bytes", "text"),
    [
        (50 * 1024 * 1024, "50MB"),
        (1536 * 1024, "1.5MB"),
        (4096, "4KB"),
        (1536, "1.5KB"),
        (200, "200 bytes"),
    ],
)
def test_size_limit_text_names_the_largest_whole_unit(limit_bytes: int, text: str) -> None:
    """Verify a limit is named in MB, KB or bytes, never rounded down to 0MB."""
    assert size_limit_text(limit_bytes) == text


def test_the_stream_processor_names_its_limit_in_kb() -> None:
    """Verify the sanitizing stream processor's limit message names a sub-MB limit correctly."""
    processor = StreamingTokenProcessor(max_stream_bytes=_LIMIT)

    with pytest.raises(AIClientError) as caught:
        processor.feed("x" * (_LIMIT + 1))

    assert str(caught.value) == "Stream exceeded maximum size limit of 4KB."
