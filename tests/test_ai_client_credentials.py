"""A missing or rejected API key is reported as a credentials problem, not a network one."""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.config.settings import AIConfig
from tests.llm_stream_fakes import route_llm_clients

GATEWAY_URL = "http://gateway.example.com:4000/v1"


@pytest.fixture(autouse=True)
def _allow_private_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")


def _client(api_key: str) -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="devops-coder", max_retries=3),
        api_key=api_key,
        cache_enabled=False,
    )


def _serve(monkeypatch: pytest.MonkeyPatch, status: int) -> list[httpx2.Request]:
    """Answer every chat, stream and model-list request with ``status``; return the requests."""
    body: dict[str, Any] = (
        {"choices": [{"message": {"content": "OK"}}], "data": [{"id": "devops-coder"}]}
        if status == 200
        else {"error": {"message": "Authentication Error, No api key passed in."}}
    )
    return route_llm_clients(monkeypatch, lambda request: httpx2.Response(status, json=body))


def test_unset_key_sends_no_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an unset key omits Authorization rather than sending an empty bearer token."""
    sent = _serve(monkeypatch, 200)
    client = _client("")

    reply = client.chat("You are terse.", "Reply with OK.", use_cache=False)
    models = client.list_models()

    assert (str(reply), models, [request.headers.get("Authorization") for request in sent]) == (
        "OK",
        ["devops-coder"],
        [None, None],
    )


@pytest.mark.parametrize(
    ("api_key", "status", "expected"),
    [
        ("", 401, "no API key is configured"),
        ("sk-wrong", 401, "rejected the configured API key"),
        ("sk-limited", 403, "rejected the configured API key"),
    ],
)
def test_rejected_credentials_name_the_key_sources_without_retrying(
    monkeypatch: pytest.MonkeyPatch, api_key: str, status: int, expected: str
) -> None:
    """Verify 401/403 fail once with an error naming where the key comes from."""
    sent = _serve(monkeypatch, status)

    with pytest.raises(AIClientError) as exc_info:
        _client(api_key).chat("You are terse.", "Reply with OK.", use_cache=False)

    message = str(exc_info.value)
    assert (
        expected in message,
        "DEVOPS_CLI_AI_API_KEY" in message,
        "devops config set ai.api_key" in message,
        len(sent),
    ) == (True, True, True, 1)


def test_streaming_reports_rejected_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a streamed request without a key reports the missing key, not a stream failure."""
    sent: list[dict[str, str]] = []

    def fake_send(self: Any, request: httpx2.Request, **kwargs: Any) -> httpx2.Response:
        if str(request.url).startswith(GATEWAY_URL):
            sent.append(dict(request.headers))
        return httpx2.Response(401, json={"error": {"message": "No api key"}}, request=request)

    monkeypatch.setattr(httpx2.Client, "send", fake_send)

    with pytest.raises(AIClientError, match="no API key is configured"):
        list(_client("")._openai_compat_stream("You are terse.", []))

    assert [h.get("authorization") for h in sent] == [None]
