"""An HTTP 402 of a model call says that the provider key has too few credits, so it gives the
spend-limit error and not a provider failure (#7261). The body follows the gateway log of
2026-11-25: the LiteLLM gateway passes the OpenRouter reply on with its status."""

from __future__ import annotations

import json
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic_ai.exceptions import ModelHTTPError, ModelQuotaExceededError

from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.claude import _map_anthropic_errors
from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    AIKeySpendLimitError,
    spend_limit_error,
)
from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.agent_run import model_call_error
from devops_cli.roadmap.failure import FailureClass, failure_class_of
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import serve_llm

GATEWAY_URL = "http://gateway.example.com:4000/v1"
SPENT_TEXT = (
    "The provider key reached its spend limit (HTTP 402). A person raises the spend limit of the "
    "key at the provider, or changes the key."
)
CREDITS_ERROR: dict[str, Any] = {
    "message": "litellm.APIError: APIError: OpenrouterException - "
    '{"error":{"message":"This request requires more credits, or fewer max_tokens. You requested '
    "up to 131072 tokens, but can only afford 118471. To increase, visit "
    'https://example.com/settings/keys and adjust the key\'s monthly limit","code":402}}',
    "type": None,
    "param": None,
    "code": "402",
}
CREDITS_BODY: dict[str, Any] = {"error": CREDITS_ERROR}


@pytest.fixture(autouse=True)
def _public_endpoints(web: WebFake) -> None:
    """The configured endpoints are example.com URLs, which resolve to a public address."""


@pytest.mark.parametrize(
    "body",
    [CREDITS_ERROR, CREDITS_BODY, json.dumps(CREDITS_BODY), "Insufficient Balance", None, ""],
    ids=["sdk-error-object", "transport-body", "json-text", "other-provider", "no-body", "empty"],
)
def test_an_http_402_gives_the_spend_limit_error_whatever_its_body_says(body: object) -> None:
    error = spend_limit_error(402, body)

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT)


def test_the_spend_limit_error_of_a_402_holds_no_amount_or_url_of_the_reply() -> None:
    error = spend_limit_error(402, CREDITS_BODY)

    assert [part in str(error) for part in ("118471", "http", "example.com", "max_tokens")] == [
        False,
        False,
        False,
        False,
    ]


@pytest.mark.parametrize(
    "body", [CREDITS_ERROR, CREDITS_BODY, None], ids=["sdk", "transport", "none"]
)
def test_a_model_call_of_an_agent_run_with_an_http_402_gives_the_spend_limit_error(
    body: object,
) -> None:
    error = model_call_error(ModelHTTPError(402, "devops-coder", body), "The refine's")

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT)


def test_a_quota_error_of_the_model_library_gives_the_spend_limit_error() -> None:
    """pydantic-ai raises `ModelQuotaExceededError` when a provider reports that its quota, its
    credits or its billing is exhausted, also inside a stream, where the reply has no status."""
    quota = ModelQuotaExceededError("devops-coder", "insufficient_quota")

    error = model_call_error(quota, "The refine's")

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT)


def test_a_quota_error_with_an_http_status_keeps_the_status_of_its_reply() -> None:
    """OpenAI reports an exhausted quota with HTTP 429 and the code `insufficient_quota`."""
    quota = ModelHTTPError.for_category(
        ModelQuotaExceededError,
        status_code=429,
        model_name="devops-coder",
        body={"message": "You exceeded your current quota.", "code": "insufficient_quota"},
    )

    error = model_call_error(quota, "The refine's")

    assert (type(error), str(error)) == (AIKeySpendLimitError, SPENT_TEXT.replace("402", "429"))


def test_the_failure_class_of_an_http_402_model_call_is_spend_limit() -> None:
    """A job stops its round for a credentials error, and the failure ledger of the Service waits
    for the class `spend_limit` before its next probe round."""
    error = model_call_error(ModelHTTPError(402, "devops-coder", CREDITS_BODY), "The refine's")

    assert (type(error).__mro__[:2], failure_class_of(error)) == (
        (AIKeySpendLimitError, AICredentialsError),
        FailureClass.SPEND_LIMIT,
    )


def test_a_rate_limit_of_a_model_call_stays_a_provider_failure() -> None:
    """The cooldown of the gateway answers HTTP 429 after a 402: it names no cause, so it keeps
    the class `provider`."""
    body = {"message": "No deployments available for selected model. Try again in 30 seconds."}

    error = model_call_error(ModelHTTPError(429, "devops-coder", body), "The refine's")

    assert (type(error), failure_class_of(error)) == (AIClientError, FailureClass.PROVIDER)


def _gateway_client() -> LLMClient:
    return LLMClient(
        AIConfig(provider="gateway", gateway_url=GATEWAY_URL, model="devops-coder", max_retries=3),
        api_key="sk-test",
        cache_enabled=False,
    )


@pytest.mark.parametrize("call", ["chat", "stream"])
def test_a_gateway_call_with_an_http_402_gives_the_spend_limit_error_after_one_request(
    call: str, web: WebFake
) -> None:
    sent = serve_llm(web, lambda request: httpx2.Response(402, json=CREDITS_BODY))
    client = _gateway_client()

    with pytest.raises(AICredentialsError) as caught:
        if call == "stream":
            list(client.chat_stream("You are terse.", "Reply with OK."))
        else:
            client.chat("You are terse.", "Reply with OK.", use_cache=False)

    assert (type(caught.value), str(caught.value), len(sent)) == (
        AIKeySpendLimitError,
        SPENT_TEXT,
        1,
    )


def test_a_claude_status_error_with_an_http_402_gives_the_spend_limit_error() -> None:
    body = {"type": "error", "error": {"type": "billing_error", "message": "Credit balance low."}}
    request = httpx2.Request("POST", "http://example.com/v1/messages")
    response = httpx2.Response(402, json=body, request=request)
    client = LLMClient(
        AIConfig(provider="claude", model="claude-test", api_base_url="http://example.com"),
        api_key="sk-test",
        cache_enabled=False,
    )

    with pytest.raises(AICredentialsError) as caught, _map_anthropic_errors(client, "failed"):
        raise anthropic.APIStatusError("Error code: 402", response=response, body=body)

    assert (type(caught.value), str(caught.value)) == (AIKeySpendLimitError, SPENT_TEXT)
