"""A missing or rejected API key is reported as a credentials problem, not a network one."""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.config.settings import AIConfig
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import serve_llm

GATEWAY_URL = "http://gateway.example.com:4000/v1"


@pytest.fixture(autouse=True)
def _public_endpoints(web: WebFake) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


def _client(api_key: str) -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="devops-coder", max_retries=3),
        api_key=api_key,
        cache_enabled=False,
    )


def _serve(web: WebFake, status: int) -> list[httpx2.Request]:
    """Answer every chat, stream and model-list request with ``status``; return the requests."""
    body: dict[str, Any] = (
        {"choices": [{"message": {"content": "OK"}}], "data": [{"id": "devops-coder"}]}
        if status == 200
        else {"error": {"message": "Authentication Error, No api key passed in."}}
    )
    return serve_llm(web, lambda request: httpx2.Response(status, json=body))


def test_unset_key_sends_no_authorization_header(web: WebFake) -> None:
    """Verify an unset key omits Authorization rather than sending an empty bearer token."""
    sent = _serve(web, 200)
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
    web: WebFake, api_key: str, status: int, expected: str
) -> None:
    """Verify 401/403 fail once with an error naming where the key comes from."""
    sent = _serve(web, status)

    with pytest.raises(AIClientError) as exc_info:
        _client(api_key).chat("You are terse.", "Reply with OK.", use_cache=False)

    message = str(exc_info.value)
    assert (
        expected in message,
        "DEVOPS_CLI_AI_API_KEY" in message,
        "devops config set ai.api_key" in message,
        len(sent),
    ) == (True, True, True, 1)


def test_streaming_reports_rejected_credentials(web: WebFake) -> None:
    """Verify a streamed request without a key reports the missing key, not a stream failure."""
    web.serve(lambda request: httpx2.Response(401, json={"error": {"message": "No api key"}}))

    with pytest.raises(AIClientError, match="no API key is configured"):
        list(_client("")._openai_compat_stream("You are terse.", []))

    assert [request.headers.get("authorization") for request in web.sent] == [None]
