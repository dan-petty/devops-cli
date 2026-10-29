"""What devops-cli tells the LLM gateway about itself on each model call (#1668).

The gateway counts every caller's calls, but every caller sends the one master key, so its
series tell callers apart only by the end-user id that a request names and by its user agent.
devops-cli names its OTel `service.name` as the end-user id, and itself as the user agent, on
its chat calls, its embedding calls and the calls of a pydantic-ai agent. The gateway is faked
at the HTTP edge.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest
from pydantic_ai import Agent

from devops_cli import __version__
from devops_cli.ai.client import LLMClient
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.settings import AIConfig, Settings
from devops_cli.http.broker import HttpClientBroker
from tests.llm_stream_fakes import OPENAI_DONE, openai_chunk, reply, route_llm_clients
from tests.web_fakes import StubWeb

GATEWAY_URL = "http://example.com:4000/v1"
END_USER_HEADER = "x-litellm-end-user-id"
USER_AGENT = f"devops-cli/{__version__}"


@pytest.fixture(autouse=True)
def _public_endpoints(public_dns: str) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


@pytest.fixture(params=[None, "roadmap-service"], ids=["default-service", "named-service"])
def service_name(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """The OTel `service.name` of the process: devops-cli's own, or the one a workload sets."""
    if request.param is None:
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        return "devops-cli"
    monkeypatch.setenv("OTEL_SERVICE_NAME", request.param)
    return str(request.param)


def _caller(request: httpx2.Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.headers.get(END_USER_HEADER)


def _chat_reply(_request: httpx2.Request) -> httpx2.Response:
    return reply([openai_chunk("OK", finish_reason="stop"), OPENAI_DONE])


def test_a_gateway_chat_call_names_devops_cli_and_its_service(
    monkeypatch: pytest.MonkeyPatch, service_name: str
) -> None:
    """A chat call to the gateway names devops-cli as its user agent, not the OpenAI SDK, and
    the process's service as its end user."""
    sent = route_llm_clients(monkeypatch, _chat_reply)
    client = LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="devops-chat"),
        api_key="sk-gateway",
        cache_enabled=False,
    )

    client.chat("You are terse.", "Reply with OK.", use_cache=False)

    assert [_caller(request) for request in sent] == [(USER_AGENT, service_name)]


def test_a_chat_call_to_another_provider_names_no_end_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the gateway reads the end-user id, so no other endpoint gets it."""
    sent = route_llm_clients(monkeypatch, _chat_reply)
    client = LLMClient(
        AIConfig(provider="openai", api_base_url=GATEWAY_URL, model="gpt-4o"),
        api_key="sk-openai",
        cache_enabled=False,
    )

    client.chat("You are terse.", "Reply with OK.", use_cache=False)

    assert [request.headers.get(END_USER_HEADER) for request in sent] == [None]


def _embedding_reply(request: httpx2.Request) -> httpx2.Response:
    texts = json.loads(request.content)["input"]
    return httpx2.Response(
        200,
        json={
            "data": [{"index": i, "embedding": [0.5] * 4} for i in range(len(texts))],
            "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)},
        },
    )


def test_a_gateway_embedding_call_names_devops_cli_and_its_service(
    monkeypatch: pytest.MonkeyPatch, service_name: str, spend_ledger: Any
) -> None:
    """An embedding call to the gateway names devops-cli as its user agent, not httpx2, and the
    process's service as its end user."""
    sent: list[httpx2.Request] = []

    def answer(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return _embedding_reply(request)

    transport = httpx2.MockTransport(answer)
    monkeypatch.setattr(
        httpx2.HTTPTransport,
        "handle_request",
        lambda _self, request: transport.handle_request(request),
    )
    config = AIConfig(provider="gateway", gateway_url=GATEWAY_URL, allow_private_network=True)
    config.tasks.embedding.model = "qwen3-embedding:0.6b"

    EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=None).embed_texts(["chunk"])

    assert [_caller(request) for request in sent] == [(USER_AGENT, service_name)]


def _completion(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1,
            "model": "devops-chat",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "OK"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


def test_a_pydantic_ai_agent_call_to_the_gateway_names_devops_cli_and_its_service(
    monkeypatch: pytest.MonkeyPatch, service_name: str, stub_web: StubWeb
) -> None:
    """A call of a pydantic-ai agent on the gateway, as refine's investigation sends, names
    devops-cli as its user agent, not pydantic-ai, and the process's service as its end user."""
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "_is_testing_mode_active", lambda: False)
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _settings: "sk-gateway")
    stub_web.serve(_completion)
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = GATEWAY_URL
    model = pydantic_ai_bridge.resolve_pydantic_ai_model("devops-chat", settings=settings)

    Agent(model).run_sync("Reply with OK.")

    assert [_caller(request) for request in stub_web.sent] == [(USER_AGENT, service_name)]


def test_the_broker_names_this_release_of_devops_cli_as_its_user_agent() -> None:
    """The broker's user agent is the installed release, not a release named in the code."""
    assert HttpClientBroker().build_headers()["User-Agent"] == USER_AGENT
