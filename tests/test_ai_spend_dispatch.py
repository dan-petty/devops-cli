"""Integration tests verifying automatic spend recording during LLMClient dispatches and direct requests."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx2
import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.usage import RequestUsage

import devops_cli.ai.spend as spend_mod
from devops_cli.ai.client import LLMClient
from devops_cli.ai.direct import direct_model_request, direct_model_request_sync
from devops_cli.ai.spend.models import SpendRecord
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


@pytest.fixture(autouse=True)
def _bypass_dns_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )


def test_llm_client_dispatch_records_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMClient chat dispatch triggers track_request_spend with prompt/completion tokens."""
    recorded: list[dict[str, Any]] = []

    def mock_track_spend(**kwargs: Any) -> SpendRecord:
        recorded.append(kwargs)
        return SpendRecord(
            timestamp="2026-01-01T00:00:00Z",
            provider=kwargs.get("provider", ""),
            model=kwargs.get("model", ""),
            server=kwargs.get("server", ""),
            prompt_tokens=kwargs.get("prompt_tokens", 0),
            completion_tokens=kwargs.get("completion_tokens", 0),
            total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
            cost_usd=0.001,
        )

    monkeypatch.setattr(spend_mod, "track_request_spend", mock_track_spend)

    req = httpx2.Request("POST", "http://localhost:11434")
    mock_resp = httpx2.Response(
        200,
        request=req,
        json={
            "message": {"content": "Test response"},
            "prompt_eval_count": 15,
            "eval_count": 25,
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_resp)

    cfg = AIConfig(
        provider="ollama",
        model="llama3:8b",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)
    resp = client.chat(system="system prompt", user="user message")

    assert (len(recorded), resp.content) == (1, "Test response")
    rec = recorded[0]
    assert (
        rec["provider"],
        rec["model"],
        rec["prompt_tokens"],
        rec["completion_tokens"],
    ) == (
        "ollama",
        "llama3:8b",
        15,
        25,
    )


def test_llm_client_streaming_records_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMClient streaming chat completes and records estimated/token spend."""
    recorded: list[dict[str, Any]] = []

    def mock_track_spend(**kwargs: Any) -> SpendRecord:
        recorded.append(kwargs)
        return SpendRecord(
            timestamp="2026-01-01T00:00:00Z",
            provider=kwargs.get("provider", ""),
            model=kwargs.get("model", ""),
            server=kwargs.get("server", ""),
            prompt_tokens=kwargs.get("prompt_tokens", 0),
            completion_tokens=kwargs.get("completion_tokens", 0),
            total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
            cost_usd=0.0005,
        )

    monkeypatch.setattr(spend_mod, "track_request_spend", mock_track_spend)

    # Mock streaming response from Ollama
    stream_lines = [
        b'{"message": {"content": "Hello "}, "done": false}\n',
        b'{"message": {"content": "world!"}, "done": true, "prompt_eval_count": 8, "eval_count": 4}\n',
    ]

    class MockStreamResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self) -> Any:
            for line in stream_lines:
                yield line.decode("utf-8")

        def __enter__(self) -> MockStreamResponse:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(httpx2.Client, "stream", lambda self, *args, **kwargs: MockStreamResponse())

    cfg = AIConfig(
        provider="ollama",
        model="llama3:8b",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)
    generator = client.chat_messages_stream(
        system="sys",
        messages=[ChatMessage(role="user", content="stream query")],
    )

    chunks = list(generator)
    assert (len(chunks), len(recorded)) == (2, 1)
    rec = recorded[0]
    assert (rec["provider"], rec["model"], rec["server"]) == (
        "ollama",
        "llama3:8b",
        "localhost:11434",
    )


def test_direct_model_request_records_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify direct_model_request_sync and direct_model_request invoke spend tracking."""
    recorded: list[dict[str, Any]] = []

    def mock_track_spend(**kwargs: Any) -> SpendRecord:
        recorded.append(kwargs)
        return SpendRecord(
            timestamp="2026-01-01T00:00:00Z",
            provider=kwargs.get("provider", ""),
            model=kwargs.get("model", ""),
            server=kwargs.get("server", ""),
            prompt_tokens=kwargs.get("prompt_tokens", 0),
            completion_tokens=kwargs.get("completion_tokens", 0),
            total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
            cost_usd=0.0002,
        )

    monkeypatch.setattr(spend_mod, "track_request_spend", mock_track_spend)

    mock_resp = ModelResponse(
        parts=[TextPart(content="Direct mock reply")],
        usage=RequestUsage(input_tokens=40, output_tokens=60),
    )

    monkeypatch.setattr(
        "devops_cli.ai.pydantic_ai_bridge.resolve_pydantic_ai_model",
        lambda m, **kwargs: "test-model",
    )
    monkeypatch.setattr(
        "devops_cli.ai.direct.model_request_sync", lambda *args, **kwargs: mock_resp
    )

    async def async_req(*args: Any, **kwargs: Any) -> Any:
        return mock_resp

    monkeypatch.setattr("devops_cli.ai.direct.model_request", async_req)

    # Test sync
    sync_resp = direct_model_request_sync(
        prompt_or_messages="Sync test prompt",
        model="test-model",
    )

    # Test async
    async_resp = asyncio.run(
        direct_model_request(
            prompt_or_messages="Async test prompt",
            model="test-model",
        )
    )

    assert (
        sync_resp.parts[0].content,
        async_resp.parts[0].content,
        len(recorded),
    ) == (
        "Direct mock reply",
        "Direct mock reply",
        2,
    )
    assert (
        recorded[0]["provider"],
        recorded[0]["model"],
        recorded[0]["prompt_tokens"],
        recorded[0]["completion_tokens"],
    ) == (
        "pydantic_ai_direct",
        "test-model",
        40,
        60,
    )
