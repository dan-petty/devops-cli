"""Per-call sampling of LLMClient.chat reaches the request body and the reply cache key."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig
from tests.llm_stream_fakes import route_client

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger

SAMPLING_KEYS = ("temperature", "top_p", "seed")


def _gateway_reply(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


def _ollama_reply(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json={"message": {"role": "assistant", "content": "OK"}})


def _gateway_client(
    monkeypatch: pytest.MonkeyPatch, **config: Any
) -> tuple[LLMClient, list[httpx2.Request]]:
    client = LLMClient(
        AIConfig(
            provider="gateway",
            model="demo-model",
            gateway_url="http://example.com:4000/v1",
            temperature=0.1,
            top_p=0.95,
            **config,
        ),
        cache_enabled=True,
    )
    return client, route_client(client, monkeypatch, _gateway_reply)


def _ollama_client(
    monkeypatch: pytest.MonkeyPatch, **config: Any
) -> tuple[LLMClient, list[httpx2.Request]]:
    client = LLMClient(
        AIConfig(
            provider="ollama",
            ollama_urls=["http://localhost:11434"],
            temperature=0.1,
            **config,
        ),
        cache_enabled=True,
    )
    return client, route_client(client, monkeypatch, _ollama_reply)


def _sampling(request: httpx2.Request) -> dict[str, Any]:
    body = json.loads(request.content)
    return {key: body.get(key) for key in SAMPLING_KEYS}


def _chat_requests(sent: list[httpx2.Request]) -> list[httpx2.Request]:
    return [r for r in sent if r.url.path.endswith("/chat/completions")]


def _ollama_options(sent: list[httpx2.Request]) -> list[dict[str, Any]]:
    options = [json.loads(r.content).get("options", {}) for r in sent if r.url.path == "/api/chat"]
    return [{key: opts.get(key) for key in SAMPLING_KEYS} for opts in options]


@pytest.mark.usefixtures("public_dns")
def test_gateway_request_carries_per_call_temperature_and_seed(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _gateway_client(monkeypatch)
    client.chat("sys", "user", temperature=0.9, seed=7)
    assert [_sampling(r) for r in _chat_requests(sent)] == [
        {"temperature": 0.9, "top_p": 0.95, "seed": 7}
    ]


@pytest.mark.usefixtures("public_dns")
def test_gateway_request_takes_per_call_top_p_and_configured_temperature(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _gateway_client(monkeypatch)
    client.chat("sys", "user", top_p=0.8)
    assert [_sampling(r) for r in _chat_requests(sent)] == [
        {"temperature": 0.1, "top_p": 0.8, "seed": None}
    ]


@pytest.mark.usefixtures("public_dns")
def test_omitted_parameters_keep_the_configured_values(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _gateway_client(monkeypatch)
    client.chat("sys", "user")
    bodies = [json.loads(r.content) for r in _chat_requests(sent)]
    assert [(b.get("temperature"), b.get("top_p"), "seed" in b) for b in bodies] == [
        (0.1, 0.95, False)
    ]


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize("gate", ["use_model_sampling", "supports_reasoning"])
def test_sampling_gate_wins_over_per_call_sampling(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger, gate: str
) -> None:
    client, sent = _gateway_client(monkeypatch, **{gate: True})
    client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7)
    bodies = [json.loads(r.content) for r in _chat_requests(sent)]
    assert [sorted(set(SAMPLING_KEYS) & b.keys()) for b in bodies] == [[]]


def test_unknown_keyword_raises_type_error_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sent = _gateway_client(monkeypatch)
    unknown: dict[str, Any] = {"unknown_param": 1}
    with pytest.raises(TypeError, match="unknown_param"):
        client.chat("sys", "user", **unknown)
    with pytest.raises(TypeError, match="unknown_param"):
        client.chat_messages("sys", [], **unknown)
    assert sent == []


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize(
    ("first", "second", "requests"),
    [
        ({"temperature": 0.1}, {"temperature": 0.9}, 2),
        ({"seed": 7}, {"seed": 42}, 2),
        ({"temperature": 0.9}, {"temperature": 0.9}, 1),
    ],
    ids=["temperatures-split", "seeds-split", "equal-sampling-hits"],
)
def test_cache_key_holds_per_call_sampling(
    monkeypatch: pytest.MonkeyPatch,
    spend_ledger: SpendLedger,
    first: dict[str, Any],
    second: dict[str, Any],
    requests: int,
) -> None:
    client, sent = _gateway_client(monkeypatch)
    client.chat("sys", "user", **first)
    client.chat("sys", "user", **second)
    assert len(_chat_requests(sent)) == requests


def test_ollama_request_carries_per_call_sampling(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _ollama_client(monkeypatch)
    client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7)
    assert _ollama_options(sent) == [{"temperature": 0.9, "top_p": 0.8, "seed": 7}]


def test_ollama_omitted_parameters_keep_the_configured_temperature(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _ollama_client(monkeypatch)
    client.chat("sys", "user")
    assert [opts["temperature"] for opts in _ollama_options(sent)] == [0.1]
    options = [json.loads(r.content).get("options", {}) for r in sent if r.url.path == "/api/chat"]
    assert ["seed" in opts for opts in options] == [False]


def test_ollama_use_model_sampling_ignores_per_call_sampling(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _ollama_client(monkeypatch, use_model_sampling=True)
    client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7)
    assert _ollama_options(sent) == [{"temperature": None, "top_p": None, "seed": None}]


def test_ollama_reasoning_model_cache_key_splits_per_call_temperatures(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    client, sent = _ollama_client(monkeypatch, supports_reasoning=True)
    client.chat("sys", "user", temperature=0.1)
    client.chat("sys", "user", temperature=0.9)
    assert [opts["temperature"] for opts in _ollama_options(sent)] == [0.1, 0.9]
