"""Canned model streams for tests of the LLM client's stream readers, with no network.

Streams are answered by httpx2's own `MockTransport`, so a reply is read through the same
response, content decoders and event parser it would be against a real server, and no socket is
opened. Hosts are `example.com`, as docs/TESTING.md requires of fixtures.
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


def _asks_for_stream(request: httpx2.Request) -> bool:
    if request.method != "POST" or not request.url.path.endswith("/chat/completions"):
        return False
    try:
        body = json.loads(request.content or b"{}")
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("stream") is True


def completion_chunks(completion: dict[str, Any]) -> list[bytes]:
    """The SSE frames that an OpenAI-compatible server streams for `completion`, a chat
    completion body: one chunk for each choice, whose delta is the choice's message, then a
    usage chunk when the body has usage, then `[DONE]`. A body with no choices is sent as one
    frame, as a server sends an error object."""
    choices = completion.get("choices")
    if not isinstance(choices, list):
        return [sse_data(completion), OPENAI_DONE]
    top = {k: v for k, v in completion.items() if k not in ("choices", "usage", "object")}
    top = {"id": "chatcmpl-test", "created": 0, **top, "object": "chat.completion.chunk"}
    frames = []
    for position, choice in enumerate(choices):
        delta = dict(choice.get("message") or {})
        chunk_choice = {
            "index": choice.get("index", position),
            "delta": delta,
            "finish_reason": choice.get("finish_reason"),
        }
        frames.append(sse_data({**top, "choices": [chunk_choice]}))
    if completion.get("usage") is not None:
        frames.append(sse_data({**top, "choices": [], "usage": completion["usage"]}))
    frames.append(OPENAI_DONE)
    return frames


def as_requested(request: httpx2.Request, response: httpx2.Response) -> httpx2.Response:
    """`response` in the form that `request` asks for: a successful JSON chat completion to a
    request with `stream: true` is streamed as SSE frames with the same status and headers, as
    an OpenAI-compatible server streams it. Any other response is returned as it is."""
    content_type = response.headers.get("content-type", "")
    if not (response.is_success and content_type.startswith("application/json")):
        return response
    if not _asks_for_stream(request):
        return response
    completion = json.loads(response.read())
    headers = {k: v for k, v in response.headers.items() if k.lower() not in _BODY_HEADERS}
    return httpx2.Response(
        response.status_code,
        headers={**headers, "content-type": SSE},
        content=iter(completion_chunks(completion)),
        request=request,
    )


_BODY_HEADERS = frozenset({"content-type", "content-length", "content-encoding"})


def anthropic_event(event_type: str, **fields: Any) -> bytes:
    """One Anthropic Messages stream event, named in both its `event:` line and its data."""
    if event_type == "message_start":
        msg = fields.get("message")
        if isinstance(msg, dict) and "content" not in msg:
            fields["message"] = {"content": [], **msg}
    data = json.dumps({"type": event_type, **fields}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n".encode()


def anthropic_text(text: str, index: int = 0) -> bytes:
    """An Anthropic text delta."""
    return anthropic_event(
        "content_block_delta", index=index, delta={"type": "text_delta", "text": text}
    )


def anthropic_stream_frames(
    chunks: Sequence[str],
    *,
    input_tokens: int = 10,
    output_tokens: int = 20,
    stop_reason: str = "end_turn",
    thinking: str | None = None,
) -> list[bytes]:
    """Build a complete sequence of valid Anthropic Messages SSE frames."""
    frames = [
        anthropic_event(
            "message_start",
            message={"id": "msg_test", "content": [], "usage": {"input_tokens": input_tokens}},
        ),
    ]
    idx = 0
    if thinking:
        frames.extend(
            [
                anthropic_event(
                    "content_block_start",
                    index=idx,
                    content_block={"type": "thinking", "thinking": ""},
                ),
                anthropic_event(
                    "content_block_delta",
                    index=idx,
                    delta={"type": "thinking_delta", "thinking": thinking},
                ),
                anthropic_event("content_block_stop", index=idx),
            ]
        )
        idx += 1
    frames.append(
        anthropic_event(
            "content_block_start",
            index=idx,
            content_block={"type": "text", "text": ""},
        )
    )
    for chunk in chunks:
        frames.append(
            anthropic_event(
                "content_block_delta",
                index=idx,
                delta={"type": "text_delta", "text": chunk},
            )
        )
    frames.extend(
        [
            anthropic_event("content_block_stop", index=idx),
            anthropic_event(
                "message_delta",
                delta={"stop_reason": stop_reason},
                usage={"output_tokens": output_tokens},
            ),
            anthropic_event("message_stop"),
        ]
    )
    return frames


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
        return as_requested(request, handler(request))

    transport = httpx2.MockTransport(record)
    monkeypatch.setattr(client, "_shared_client", lambda: httpx2.Client(transport=transport))
    monkeypatch.setattr(
        client, "_create_http_client", lambda timeout=None: httpx2.Client(transport=transport)
    )
    monkeypatch.setattr("devops_cli.ai.gateway._query_model_info", lambda *a, **kw: None)
    return sent


def route_llm_clients(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> list[httpx2.Request]:
    """Send every request any LLMClient makes, including one built inside the code under test,
    to `handler`; return the requests, in order."""
    from devops_cli.ai.client import LLMClient

    sent: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return as_requested(request, handler(request))

    transport = httpx2.MockTransport(record)
    monkeypatch.setattr(
        LLMClient, "_shared_client", lambda self: httpx2.Client(transport=transport)
    )
    monkeypatch.setattr(
        LLMClient,
        "_create_http_client",
        lambda self, timeout=None: httpx2.Client(transport=transport),
    )
    monkeypatch.setattr("devops_cli.ai.gateway._query_model_info", lambda *a, **kw: None)
    return sent


def route_retrying_client(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> list[httpx2.Request]:
    """Send every request an LLMClient makes through its retry transport to `handler`,
    replacing only the innermost transport and patching retry waits to 0."""
    monkeypatch.setattr("devops_cli.core.clock.sleep", lambda *_: None)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    monkeypatch.setattr("devops_cli.ai.gateway._query_model_info", lambda *a, **kw: None)

    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.retries import create_retry_transport
    from devops_cli.ai.spend.transport import AttemptRecordingTransport

    sent: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return as_requested(request, handler(request))

    inner = httpx2.MockTransport(record)
    recording = AttemptRecordingTransport(inner)

    def _make_client(timeout: Any = None) -> httpx2.Client:
        retrying = create_retry_transport(
            max_attempts=client._max_attempts(),
            wrapped=recording,
            min_wait=0.0,
            max_wait=0.0,
        )
        return httpx2.Client(transport=retrying)

    monkeypatch.setattr(client, "_shared_client", lambda: _make_client())
    monkeypatch.setattr(client, "_create_http_client", _make_client)
    monkeypatch.setattr(LLMClient, "_shared_client", lambda self: _make_client())
    monkeypatch.setattr(
        LLMClient,
        "_create_http_client",
        lambda self, timeout=None: _make_client(timeout),
    )
    return sent


def make_anthropic_model_info_payload(
    model_id: str,
    *,
    adaptive_thinking: bool = True,
    sampling: bool = False,
) -> dict[str, Any]:
    """Build a valid Anthropic Models API response payload."""
    return {
        "id": model_id,
        "created_at": "2026-01-01T00:00:00Z",
        "type": "model",
        "display_name": f"Claude Model {model_id}",
        "lifecycle": "active",
        "capabilities": {
            "batch": {"supported": True},
            "citations": {"supported": True},
            "code_execution": {"supported": True},
            "context_management": {"supported": False},
            "effort": {
                "supported": adaptive_thinking,
                "low": {"supported": True},
                "medium": {"supported": True},
                "high": {"supported": True},
                "max": {"supported": True},
            },
            "image_input": {"supported": True},
            "pdf_input": {"supported": True},
            "server_tools": {
                "supported": False,
                "code_execution": {"supported": False},
                "web_search": {"supported": False},
            },
            "structured_outputs": {"supported": True},
            "thinking": {
                "supported": adaptive_thinking,
                "types": {
                    "adaptive": {"supported": adaptive_thinking},
                    "disabled": {"supported": True},
                    "enabled": {"supported": True},
                },
            },
            "sampling": {"supported": sampling},
        },
    }
