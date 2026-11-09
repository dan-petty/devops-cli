"""A gateway model whose reply is cut by the output token limit (#4220).

The gateway answers each request with `finish_reason` `length` and no part, as it does when a
Claude group gets no `max_tokens` and the reply passes the default of 4096 tokens.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest

from devops_cli.ai import pydantic_ai_bridge
from devops_cli.config.settings import Settings
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import OPENAI_DONE, SSE, sse_data

_GATEWAY = "http://example.com:4000/v1"


def length_stopped_model(
    web: WebFake, monkeypatch: pytest.MonkeyPatch, model: str = "claude-sonnet-5-5"
) -> tuple[Any, list[httpx2.Request]]:
    """The pydantic-ai model of the gateway group `model`, and the requests that the fake
    gateway got. Every answer is cut at the output token limit, with no part."""
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _settings: "sk-test")
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = _GATEWAY
    sent: list[httpx2.Request] = []

    def serve(request: httpx2.Request) -> httpx2.Response | None:
        if not request.url.path.endswith("/chat/completions"):
            return None
        sent.append(request)
        return httpx2.Response(200, headers={"content-type": SSE}, content=_cut_frames(model))

    web.serve(serve)
    return pydantic_ai_bridge.resolve_pydantic_ai_model(model, settings=settings), sent


async def _cut_frames(model: str) -> AsyncIterator[bytes]:
    """The stream of a reply that holds no part and ends with the finish reason `length`."""
    yield sse_data(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": "length"}],
        }
    )
    yield OPENAI_DONE
