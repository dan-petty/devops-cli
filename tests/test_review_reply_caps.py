"""Review replies are capped, so one runaway generation cannot stall a review."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.network import completion_cap, limit_completion_tokens
from devops_cli.ai.review.pipeline import _execute_page_review_steps
from devops_cli.config.defaults import (
    DEFAULT_REVIEW_PERSONA_REPLY_MAX_TOKENS,
)
from devops_cli.config.settings import AIConfig
from tests.llm_stream_fakes import route_llm_clients

GATEWAY_URL = "http://gateway.example.com:4000/v1"


@pytest.fixture(autouse=True)
def _public_endpoints(public_dns: str) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


def _capture_payloads(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []

    def answer(request: httpx2.Request) -> httpx2.Response:
        if str(request.url).startswith(GATEWAY_URL):
            payloads.append(json.loads(request.content))
        return httpx2.Response(200, json={"choices": [{"message": {"content": "[]"}}]})

    route_llm_clients(monkeypatch, answer)
    return payloads


def _client(max_tokens: int | None = None) -> LLMClient:
    return LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url=GATEWAY_URL,
            model="devops-review",
            max_tokens=max_tokens,
        ),
        api_key="sk",
        cache_enabled=False,
    )


def test_call_cap_limits_the_reply_and_config_still_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a call's cap sets max_tokens, the smaller limit wins, and nothing leaks past it."""
    payloads = _capture_payloads(monkeypatch)

    with limit_completion_tokens(500):
        _client().chat("s", "u", use_cache=False)
        _client(max_tokens=300).chat("s", "u", use_cache=False)
    _client().chat("s", "u", use_cache=False)

    assert [p.get("max_tokens") for p in payloads] == [500, 300, None]


def test_persona_review_replies_are_capped() -> None:
    """Verify persona review runs under the persona reply cap."""
    seen: list[int | None] = []
    pipeline = MagicMock()

    def run(*args: Any, **kwargs: Any) -> Any:
        seen.append(completion_cap.get())
        return MagicMock(steps=[])

    pipeline.run.side_effect = run

    _execute_page_review_steps(pipeline, "prompt", "src/app.py", 1, 1, {}, [], [], [])

    assert seen == [DEFAULT_REVIEW_PERSONA_REPLY_MAX_TOKENS]
