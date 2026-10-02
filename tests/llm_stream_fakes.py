"""Canned model streams for tests of the LLM client's stream readers, with no network.

Streams are answered by httpx2's own `MockTransport`, so a reply is read through the same
response, content decoders and event parser it would be against a real server, and no socket is
opened. Hosts are `example.com`, as AGENTS.md requires of fixtures.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import httpx2
import pytest

SSE = "text/event-stream"
NDJSON = "application/x-ndjson"


def sse_data(payload: object) -> bytes:
    """One server-sent event whose data is `payload`, as JSON unless it is a string."""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return f"data: {text}\n\n".encode()


OPENAI_DONE = sse_data("[DONE]")


def openai_chunk(content: str | None = None, finish_reason: str | None = None) -> bytes:
    """An OpenAI-compatible chat completion chunk with one choice."""
    delta = {"content": content} if content is not None else {}
    return sse_data({"choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]})


def anthropic_event(event_type: str, **fields: Any) -> bytes:
    """One Anthropic Messages stream event, named in both its `event:` line and its data."""
    data = json.dumps({"type": event_type, **fields}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n".encode()


def anthropic_text(text: str) -> bytes:
    """An Anthropic text delta."""
    return anthropic_event(
        "content_block_delta", index=0, delta={"type": "text_delta", "text": text}
    )


def ollama_line(content: str = "", **fields: Any) -> bytes:
    """One line of an Ollama chat stream; `done` is false unless a field says otherwise."""
    payload = {"message": {"role": "assistant", "content": content}, "done": False, **fields}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode()


class RecordedBody:
    """A response body that records how many of its frames have been read."""

    def __init__(self, frames: Sequence[bytes]) -> None:
        self.frames = frames
        self.read = 0

    def __iter__(self) -> Iterator[bytes]:
        for frame in self.frames:
            self.read += 1
            yield frame


def reply(frames: Iterable[bytes], content_type: str = SSE, status: int = 200) -> httpx2.Response:
    """A response whose body is produced frame by frame, as a server streams it."""
    return httpx2.Response(status, headers={"content-type": content_type}, content=iter(frames))


@contextmanager
def streamed(frames: Iterable[bytes], content_type: str = SSE) -> Iterator[httpx2.Response]:
    """An open streamed response to a POST, served by a MockTransport."""
    transport = httpx2.MockTransport(lambda request: reply(frames, content_type))
    with (
        httpx2.Client(transport=transport) as http_client,
        http_client.stream("POST", "http://example.com/v1/chat/completions") as response,
    ):
        yield response


def route_client(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> list[httpx2.Request]:
    """Send every request an LLMClient makes to `handler`; return the requests, in order."""
    sent: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return handler(request)

    transport = httpx2.MockTransport(record)
    monkeypatch.setattr(client, "_shared_client", lambda: httpx2.Client(transport=transport))
    monkeypatch.setattr(
        client, "_create_http_client", lambda timeout=None: httpx2.Client(transport=transport)
    )
    return sent
