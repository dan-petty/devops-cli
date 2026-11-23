"""A 401 or 403 reply whose provider says the key reached its spend limit gives the spend-limit
error, not the credentials error (#6821). The bodies follow the gateway log of 2026-11-22: the
LiteLLM gateway passes the OpenRouter reply on as text in the `message` of its error."""

from __future__ import annotations

import json
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic_ai.exceptions import ModelHTTPError

from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.claude import _map_anthropic_errors
from devops_cli.ai.client.models import (
    AICredentialsError,
    AIKeySpendLimitError,
    spend_limit_error,
)
from devops_cli.ai.gateway import fetch_model_info
from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.agent_run import model_call_error
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import reply, serve_llm, sse_data

GATEWAY_URL = "http://gateway.example.com:4000/v1"
SPENT_TEXT = (
    "The provider key reached its spend limit (HTTP 403). A person raises the spend limit of the "
    "key at the provider, or changes the key."
)
OPENROUTER_BODY = (
    '{"error":{"message":"Key limit exceeded (total limit). Manage it using '
    'https://example.com/settings/keys","code":403,'
    '"metadata":{"usage":"$5.00 of $5.00 used; does not reset."}}}'
)
GATEWAY_ERROR: dict[str, Any] = {
    "message": f"litellm.APIError: APIError: OpenrouterException - {OPENROUTER_BODY}. "
    "Received Model Group=devops-coder",
    "type": None,
    "param": None,
    "code": "403",
}
GATEWAY_BODY: dict[str, Any] = {"error": GATEWAY_ERROR}
REFUSED_BODY: dict[str, Any] = {"error": {"message": "Authentication Error, No api key passed in."}}


@pytest.fixture(autouse=True)
def _public_endpoints(web: WebFake) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


@pytest.mark.parametrize(
    "body",
    [GATEWAY_ERROR, GATEWAY_BODY, json.dumps(GATEWAY_BODY), "KEY LIMIT EXCEEDED (total limit)"],
    ids=["sdk-error-object", "transport-body", "json-text", "plain-text"],
)
def test_a_body_that_says_the_key_limit_is_exceeded_gives_the_spend_limit_error(
    body: object,
) -> None:
    error = spend_limit_error(403, body)

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT)


def test_the_spend_limit_error_holds_no_amount_key_or_url_of_the_reply() -> None:
    error = spend_limit_error(403, GATEWAY_BODY)

    assert [part in str(error) for part in ("$", "http", "example.com", "Manage")] == [
        False,
        False,
        False,
        False,
    ]


def test_the_spend_limit_error_stops_a_run_as_a_refused_key_does() -> None:
    assert isinstance(spend_limit_error(401, GATEWAY_BODY), AICredentialsError)


@pytest.mark.parametrize(
    "body",
    [
        REFUSED_BODY,
        {"error": {"message": "Forbidden", "metadata": {"note": "Key limit exceeded"}}},
        None,
        "",
    ],
    ids=["refused-key", "other-field", "no-body", "empty"],
)
def test_a_body_with_no_key_limit_in_its_error_text_gives_no_spend_limit_error(
    body: object,
) -> None:
    assert spend_limit_error(403, body) is None


@pytest.mark.parametrize("body", [GATEWAY_ERROR, GATEWAY_BODY], ids=["sdk", "transport"])
def test_a_model_call_of_an_agent_run_on_a_spent_key_gives_the_spend_limit_error(
    body: object,
) -> None:
    error = model_call_error(ModelHTTPError(403, "devops-coder", body), "The stage's")

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT)


@pytest.mark.parametrize("status", [401, 403])
def test_a_model_call_with_a_refused_key_keeps_the_credentials_error(status: int) -> None:
    error = model_call_error(
        ModelHTTPError(status, "devops-coder", REFUSED_BODY["error"]), "The stage's"
    )

    assert (type(error), str(error)) == (
        AICredentialsError,
        f"The model refused the key (HTTP {status}).",
    )


def _gateway_client() -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="devops-coder", max_retries=3),
        api_key="sk-test",
        cache_enabled=False,
    )


def _failure(client: LLMClient, call: str) -> BaseException:
    with pytest.raises(AICredentialsError) as caught:
        if call == "stream":
            list(client.chat_stream("You are terse.", "Reply with OK."))
        else:
            client.chat("You are terse.", "Reply with OK.", use_cache=False)
    return caught.value


@pytest.mark.parametrize("call", ["chat", "stream"])
def test_a_gateway_call_on_a_spent_key_gives_the_spend_limit_error_after_one_request(
    call: str, web: WebFake
) -> None:
    sent = serve_llm(web, lambda request: httpx2.Response(403, json=GATEWAY_BODY))

    error = _failure(_gateway_client(), call)

    assert (type(error), str(error), len(sent)) == (AIKeySpendLimitError, SPENT_TEXT, 1)


def test_an_error_frame_of_a_spent_key_after_a_keepalive_gives_the_spend_limit_error(
    web: WebFake,
) -> None:
    """After a keepalive comment the gateway has sent its status line, so it writes its error
    reply into a frame whose code is the status."""
    frame = sse_data({"error": GATEWAY_ERROR})
    serve_llm(web, lambda request: reply([b": keepalive\n\n", frame]))

    error = _failure(_gateway_client(), "chat")

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT)


@pytest.mark.parametrize("call", ["chat", "stream"])
def test_a_gateway_call_with_a_refused_key_keeps_the_error_that_names_the_key_sources(
    call: str, web: WebFake
) -> None:
    serve_llm(web, lambda request: httpx2.Response(403, json=REFUSED_BODY))

    error = _failure(_gateway_client(), call)

    assert (type(error), "rejected the configured API key" in str(error)) == (
        AICredentialsError,
        True,
    )


@pytest.mark.parametrize("call", ["chat", "stream"])
def test_a_claude_call_on_a_spent_key_gives_the_spend_limit_error(call: str, web: WebFake) -> None:
    body = {
        "type": "error",
        "error": {"type": "permission_error", "message": "Key limit exceeded (total limit)."},
    }
    serve_llm(web, lambda request: httpx2.Response(403, json=body))
    client = LLMClient(
        AIConfig(
            provider="claude",
            model="claude-test",
            api_base_url="http://example.com",
            allow_private_network=True,
            max_retries=1,
        ),
        api_key="sk-test",
        cache_enabled=False,
    )

    error = _failure(client, call)

    assert type(error) is AIKeySpendLimitError


def test_a_refusal_that_the_transport_did_not_read_gives_the_credentials_error() -> None:
    request = httpx2.Request("POST", f"{GATEWAY_URL}/chat/completions")
    unread = httpx2.Response(403, stream=httpx2.ByteStream(json.dumps(GATEWAY_BODY).encode()))
    refusal = httpx2.HTTPStatusError("403", request=request, response=unread)

    error = _gateway_client()._provider_http_error(refusal, "Provider request failed.")

    assert (type(error), "rejected the configured API key" in str(error)) == (
        AICredentialsError,
        True,
    )


def test_the_model_list_of_a_gateway_on_a_spent_key_gives_the_spend_limit_error(
    web: WebFake,
) -> None:
    web.serve(lambda request: httpx2.Response(403, json=GATEWAY_BODY))
    config = AIConfig(provider="gateway", gateway_url=GATEWAY_URL, allow_private_network=True)

    with pytest.raises(AIKeySpendLimitError, match="reached its spend limit"):
        fetch_model_info(GATEWAY_URL, True, "sk-test", ai_config=config)


def _claude_status_error(body: dict[str, Any]) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "http://example.com/v1/messages")
    response = httpx2.Response(403, json=body, request=request)
    return anthropic.PermissionDeniedError("Error code: 403", response=response, body=body)


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("Key limit exceeded (total limit).", AIKeySpendLimitError),
        ("Your API key does not have permission.", AICredentialsError),
    ],
    ids=["spent-key", "refused-key"],
)
def test_a_claude_status_error_that_the_sdk_raises_reads_the_rule(
    message: str, kind: type[AICredentialsError]
) -> None:
    """A Claude client with its own transport has no retry transport, so the SDK raises the
    status error of the reply itself."""
    body = {"type": "error", "error": {"type": "permission_error", "message": message}}
    client = LLMClient(
        AIConfig(provider="claude", model="claude-test", api_base_url="http://example.com"),
        api_key="sk-test",
        cache_enabled=False,
    )

    with pytest.raises(AICredentialsError) as caught, _map_anthropic_errors(client, "failed"):
        raise _claude_status_error(body)

    assert type(caught.value) is kind
