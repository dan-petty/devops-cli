"""Tests for Claude provider modernized with Anthropic SDK and dynamic capabilities."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import ConfigurationError
from tests.llm_stream_fakes import (
    anthropic_event,
    anthropic_text,
    make_anthropic_model_info_payload,
    reply,
    route_client,
)


@pytest.fixture(autouse=True)
def _clear_claude_capabilities():
    from devops_cli.ai.client.claude import _CLAUDE_MODEL_CAPABILITIES

    _CLAUDE_MODEL_CAPABILITIES.clear()
    yield
    _CLAUDE_MODEL_CAPABILITIES.clear()


_make_model_info_payload = make_anthropic_model_info_payload


def _make_messages_reply_payload(
    model_id: str,
    text: str = "Test response",
    *,
    thinking_text: str | None = None,
    stop_reason: str = "end_turn",
) -> dict[str, Any]:
    """Build a valid Anthropic Messages API response payload."""
    content: list[dict[str, Any]] = []
    if thinking_text:
        content.append({"type": "thinking", "thinking": thinking_text})
    content.append({"type": "text", "text": text})
    return {
        "id": "msg_test_123",
        "type": "message",
        "role": "assistant",
        "model": model_id,
        "content": content,
        "stop_reason": stop_reason,
        "usage": {"input_tokens": 20, "output_tokens": 40},
    }


def test_claude_empty_model_raises_configuration_error() -> None:
    """Provider claude with an empty ai.model raises ConfigurationError naming ai.model."""
    cfg = AIConfig(provider="claude", model="")
    with pytest.raises(ConfigurationError) as exc_info:
        LLMClient(cfg, api_key="sk-ant-test")
    err_text = str(exc_info.value).lower()
    assert "ai.model" in err_text or exc_info.value.key == "ai.model"


def test_claude_adaptive_thinking_and_no_sampling_request_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a recorded Models API reply that declares adaptive thinking and no sampling,

    the recorded messages request has thinking.type == 'adaptive', no budget_tokens,
    and neither temperature nor top_p.
    """
    model_name = "claude-sonnet-4-5"
    captured_messages_payload: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_path = request.url.path
        if url_path.endswith(f"/v1/models/{model_name}"):
            return httpx2.Response(
                200,
                json=_make_model_info_payload(model_name, adaptive_thinking=True, sampling=False),
            )
        if url_path.endswith("/v1/messages"):
            nonlocal captured_messages_payload
            captured_messages_payload = json.loads(request.content)
            return httpx2.Response(
                200,
                json=_make_messages_reply_payload(
                    model_name,
                    text="Analysis complete.",
                    thinking_text="Thinking adaptively...",
                ),
            )
        return httpx2.Response(404, json={"error": f"Unknown path: {url_path}"})

    cfg = AIConfig(
        provider="claude",
        model=model_name,
        temperature=0.7,
        top_p=0.9,
        reasoning_effort="high",
        allow_private_network=True,
    )
    client = LLMClient(cfg, api_key="sk-ant-test")
    route_client(client, monkeypatch, handler)

    res = client.chat("System instructions", "User prompt", enable_thinking=True)

    assert res.text == "Analysis complete."
    assert res.thinking == "Thinking adaptively..."
    assert captured_messages_payload.get("thinking") == {"type": "adaptive"}
    assert "budget_tokens" not in captured_messages_payload.get("thinking", {})
    assert "budget_tokens" not in captured_messages_payload
    assert "temperature" not in captured_messages_payload
    assert "top_p" not in captured_messages_payload
    assert captured_messages_payload.get("output_config", {}).get("effort") == "high"


def test_claude_sampling_parity_when_model_declares_sampling_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a model that declares sampling support, streamed and unstreamed requests

    carry the same temperature and top_p.
    """
    model_name = "claude-haiku-4"
    captured_requests: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_path = request.url.path
        if url_path.endswith(f"/v1/models/{model_name}"):
            return httpx2.Response(
                200,
                json=_make_model_info_payload(model_name, adaptive_thinking=False, sampling=True),
            )
        if url_path.endswith("/v1/messages"):
            payload = json.loads(request.content)
            captured_requests.append(payload)
            if payload.get("stream"):
                frames = [
                    anthropic_event(
                        "message_start",
                        message={"id": "msg_1", "content": [], "usage": {"input_tokens": 10}},
                    ),
                    anthropic_event(
                        "content_block_start",
                        index=0,
                        content_block={"type": "text", "text": ""},
                    ),
                    anthropic_text("Streamed "),
                    anthropic_text("response"),
                    anthropic_event("content_block_stop", index=0),
                    anthropic_event(
                        "message_delta",
                        delta={"stop_reason": "end_turn"},
                        usage={"output_tokens": 20},
                    ),
                    anthropic_event("message_stop"),
                ]
                return reply(frames)
            return httpx2.Response(
                200,
                json=_make_messages_reply_payload(model_name, text="Unstreamed response"),
            )
        return httpx2.Response(404, json={"error": f"Unknown path: {url_path}"})

    cfg = AIConfig(
        provider="claude",
        model=model_name,
        temperature=0.7,
        top_p=0.9,
        allow_private_network=True,
    )
    client = LLMClient(cfg, api_key="sk-ant-test")
    route_client(client, monkeypatch, handler)

    unstreamed_res = client.chat("System", "Hello unstreamed", enable_thinking=False)
    assert unstreamed_res.text == "Unstreamed response"

    streamed_chunks = list(client.chat_stream("System", "Hello streamed", enable_thinking=False))
    assert "".join(streamed_chunks) == "Streamed response"

    assert len(captured_requests) == 2
    unstreamed_payload, streamed_payload = captured_requests

    assert unstreamed_payload.get("temperature") == 0.7
    assert unstreamed_payload.get("top_p") == 0.9
    assert streamed_payload.get("temperature") == 0.7
    assert streamed_payload.get("top_p") == 0.9


def _claude_sampling_client(
    monkeypatch: pytest.MonkeyPatch, *, sampling: bool = True, **config: Any
) -> tuple[LLMClient, list[dict[str, Any]]]:
    """A Claude client whose fake model declares `sampling`; it records each Messages body."""
    model_name = "claude-haiku-4"
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith(f"/v1/models/{model_name}"):
            return httpx2.Response(
                200,
                json=_make_model_info_payload(
                    model_name, adaptive_thinking=False, sampling=sampling
                ),
            )
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json=_make_messages_reply_payload(model_name))

    cfg = AIConfig(
        provider="claude", model=model_name, temperature=0.7, allow_private_network=True, **config
    )
    client = LLMClient(cfg, api_key="sk-ant-test", cache_enabled=False)
    route_client(client, monkeypatch, handler)
    return client, bodies


def test_claude_request_carries_per_call_sampling_and_no_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, bodies = _claude_sampling_client(monkeypatch)
    client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7, enable_thinking=False)
    assert [(body.get("temperature"), body.get("top_p"), "seed" in body) for body in bodies] == [
        (0.9, 0.8, False)
    ]


def test_claude_omitted_temperature_keeps_the_configured_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, bodies = _claude_sampling_client(monkeypatch)
    client.chat("sys", "user", enable_thinking=False)
    assert [body.get("temperature") for body in bodies] == [0.7]


@pytest.mark.parametrize(
    ("sampling", "config"),
    [(True, {"use_model_sampling": True}), (False, {})],
    ids=["use-model-sampling", "model-without-sampling"],
)
def test_claude_sampling_gate_wins_over_per_call_sampling(
    monkeypatch: pytest.MonkeyPatch, sampling: bool, config: dict[str, Any]
) -> None:
    client, bodies = _claude_sampling_client(monkeypatch, sampling=sampling, **config)
    client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7, enable_thinking=False)
    assert [sorted({"temperature", "top_p", "seed"} & body.keys()) for body in bodies] == [[]]


def test_claude_sdk_client_http_client_is_factory_built() -> None:
    """The SDK client's HTTP client is the factory-built one (an identity check)."""
    cfg = AIConfig(provider="claude", model="claude-sonnet-4", allow_private_network=True)
    client = LLMClient(cfg, api_key="sk-ant-test")
    assert hasattr(client, "_anthropic_client")
    sdk_client = client._anthropic_client
    assert sdk_client._client is client._shared_client()
