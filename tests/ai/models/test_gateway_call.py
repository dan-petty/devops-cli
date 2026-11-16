"""A model call to the LLM gateway has one retry layer, the gateway, and one deadline (#5965).

The client sends a call again only when the call did not reach the gateway, or when a streamed
reply failed before its first event, at most `ai.max_retries` + 1 times. A fake gateway answers
each call at httpx2's transport interface, so the real pydantic-ai OpenAI model and the OpenAI SDK
read each reply, and no socket is opened.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import anyio
import httpx2
import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import (
    ModelConnectionError,
    ModelHTTPError,
    ModelRequestTimeout,
)
from pydantic_ai.models.test import TestModel

from devops_cli.ai import pydantic_ai_bridge
from devops_cli.config.settings import Settings
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import OPENAI_DONE, SSE, openai_chunk, sse_data

GATEWAY = "http://example.com:4000/v1"
REPLY = "the reply"
KEEPALIVE = b": ping\n\n"
# The frame that LiteLLM writes into an open stream when OpenRouter times out (Loki, 2026-11-16).
TIMEOUT_FRAME = sse_data(
    {"error": {"message": "A Timeout Occurred", "type": "timeout", "code": "408"}}
)


def async_reply(frames: list[bytes], *, cut: bool = False) -> httpx2.Response:
    """An SSE response with status 200 for an async client, whose body comes frame by frame. With
    `cut`, the gateway closes the connection after the last frame, before the end of the body."""

    async def body() -> AsyncIterator[bytes]:
        for frame in frames:
            yield frame
        if cut:
            raise httpx2.RemoteProtocolError("peer closed connection without a complete body")

    return httpx2.Response(200, headers={"content-type": SSE}, content=body())


@pytest.fixture(autouse=True)
def _fixed_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bridge reads the gateway key from no keyring."""
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _settings: "sk-test")


def _settings(max_retries: int = 1, **ai_fields: Any) -> Settings:
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = GATEWAY
    settings.ai.max_retries = max_retries
    for field, value in ai_fields.items():
        setattr(settings.ai, field, value)
    return settings


def _reply() -> httpx2.Response:
    return async_reply([openai_chunk(REPLY), openai_chunk(finish_reason="stop"), OPENAI_DONE])


def _gateway(web: WebFake, *answers: Callable[[httpx2.Request], httpx2.Response]) -> list[int]:
    """Serve the chat calls with `answers` in turn, the last one for every later call, and return
    the list that counts the calls."""
    calls: list[int] = []

    def serve(request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/chat/completions"):
            return None
        calls.append(1)
        return answers[min(len(calls), len(answers)) - 1](request)

    web.serve(serve)
    return calls


def _refuse(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("Connection refused", request=request)


async def _drain(_ctx: RunContext[None], events: AsyncIterable[Any]) -> None:
    async for _ in events:
        pass


def _stream_run(settings: Settings) -> str:
    """The output of one streamed agent run on the gateway's `devops-coder` group."""
    model = pydantic_ai_bridge.resolve_pydantic_ai_model("devops-coder", settings=settings)
    return Agent(model).run_sync("go", event_stream_handler=_drain).output


@pytest.mark.parametrize(
    "first",
    [
        pytest.param(lambda _r: async_reply([KEEPALIVE], cut=True), id="cut"),
        pytest.param(lambda _r: async_reply([KEEPALIVE, TIMEOUT_FRAME]), id="error-frame"),
        pytest.param(lambda _r: async_reply([KEEPALIVE, OPENAI_DONE]), id="empty"),
        pytest.param(_refuse, id="connect"),
    ],
)
def test_a_call_that_fails_before_its_first_event_is_sent_once_more(
    web: WebFake, first: Callable[[httpx2.Request], httpx2.Response]
) -> None:
    """A gateway that answers 200 and then ends the stream, writes an error frame or sends no
    content before the first event, or a connect that fails, gets one more call, and the run
    reads the reply of that call."""
    calls = _gateway(web, first, lambda _r: _reply())

    output = _stream_run(_settings(max_retries=1))

    assert (output, len(calls)) == (REPLY, 2)


def test_a_role_only_first_chunk_does_not_end_the_resend_window(web: WebFake) -> None:
    """LiteLLM sends a first chunk with the role and no text. A stream that fails after it and
    before the first token is sent again."""
    role_chunk = sse_data(
        {"choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}}]}
    )
    role_only = async_reply([role_chunk, TIMEOUT_FRAME])
    calls = _gateway(web, lambda _r: role_only, lambda _r: _reply())

    output = _stream_run(_settings(max_retries=1))

    assert (output, len(calls)) == (REPLY, 2)


def test_an_error_after_the_first_event_is_not_sent_again(web: WebFake) -> None:
    """A stream that failed after its first event fails the call once, inside the stream."""
    calls = _gateway(web, lambda _r: async_reply([openai_chunk("half a"), TIMEOUT_FRAME]))

    with pytest.raises(ModelHTTPError) as raised:
        _stream_run(_settings(max_retries=3))

    assert (raised.value.status_code, raised.value.in_stream, len(calls)) == (408, True, 1)


def test_a_stream_cut_after_the_first_event_is_not_sent_again(web: WebFake) -> None:
    """A stream that the gateway closed after its first event fails the call once, in the read
    phase."""
    calls = _gateway(web, lambda _r: async_reply([openai_chunk("half a")], cut=True))

    with pytest.raises(ModelConnectionError) as raised:
        _stream_run(_settings(max_retries=3))

    assert (raised.value.phase, len(calls)) == ("read", 1)


def test_each_failed_connect_is_sent_at_most_max_retries_plus_one_times(web: WebFake) -> None:
    """A call whose connect fails each time goes out `ai.max_retries` + 1 times, and the run
    raises the error of the last send, not a group of errors."""
    calls = _gateway(web, _refuse)

    with pytest.raises(ModelConnectionError) as raised:
        _stream_run(_settings(max_retries=2))

    assert (raised.value.phase, len(calls)) == ("connect", 3)


def test_each_stream_that_fails_before_its_first_event_is_sent_max_retries_plus_one_times(
    web: WebFake,
) -> None:
    """With `ai.max_retries` 1, as in the cluster, a call goes to the gateway at most two times."""
    calls = _gateway(web, lambda _r: async_reply([KEEPALIVE, TIMEOUT_FRAME]))

    with pytest.raises(ModelHTTPError) as raised:
        _stream_run(_settings(max_retries=1))

    assert (raised.value.status_code, len(calls)) == (408, 2)


@pytest.mark.parametrize("status", [503, 401])
def test_a_status_of_the_gateway_is_not_sent_again(web: WebFake, status: int) -> None:
    """The gateway retried a call already when it answers a status, so the client and its SDK
    send the call one time."""
    calls = _gateway(
        web, lambda _r: httpx2.Response(status, json={"error": {"message": "no deployment"}})
    )

    with pytest.raises(ModelHTTPError) as raised:
        _stream_run(_settings(max_retries=3))

    assert (raised.value.status_code, len(calls)) == (status, 1)


def test_a_gateway_chat_model_holds_the_call_deadline_and_no_sdk_retries() -> None:
    """The model of a gateway chat group sets the one deadline of a call from
    `ai.request_timeout_seconds`, and turns the retries of the OpenAI SDK off."""
    model = pydantic_ai_bridge.resolve_pydantic_ai_model(
        "devops-coder", settings=_settings(request_timeout_seconds=300)
    )

    settings = model.settings or {}

    assert (settings.get("request_timeout"), settings.get("max_retries")) == (300, 0)


def test_one_deadline_covers_every_send_of_a_call() -> None:
    """The deadline starts once for a call. The second send answers 0.3 s after it starts, which
    a new deadline for each send would allow, but the first send took 0.4 s of the one deadline of
    0.5 s already, so the call times out."""
    from devops_cli.ai.models.gateway import GatewayCallModel

    sends: list[int] = []

    class _SlowGateway(TestModel):
        @asynccontextmanager
        async def request_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            sends.append(1)
            if len(sends) == 1:
                await anyio.sleep(0.4)
                raise ModelHTTPError(408, self.model_name, in_stream=True)
            await anyio.sleep(0.3)
            async with super().request_stream(*args, **kwargs) as stream:
                yield stream

    model = GatewayCallModel(_SlowGateway(), max_retries=1, request_timeout=0.5)

    with pytest.raises(ModelRequestTimeout) as raised:
        Agent(model).run_sync("go", event_stream_handler=_drain)

    assert (raised.value.timeout, len(sends)) == (0.5, 2)
