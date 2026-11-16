"""Unit tests for the native Pydantic AI Retries subsystem."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx2
import pytest
from pydantic_ai.retries import wait_retry_after
from tenacity import RetryCallState

from devops_cli.ai.retries import (
    create_retry_config,
    is_retryable_status_code,
)
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake


class TestPydanticAIRetriesSubsystem:
    """Validate native Pydantic AI retries integration and transports."""

    def test_is_retryable_status_code(self) -> None:
        """Test predicate identifying transient HTTP error codes including 524 Cloudflare timeouts."""
        statuses = (408, 429, 500, 502, 503, 504, 520, 524, 529, 200, 400, 401, 403, 404)
        results = tuple(is_retryable_status_code(code) for code in statuses)
        expected = (
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
        )
        assert results == expected

    def test_create_retry_config_defaults(self) -> None:
        """Verify default RetryConfig creation with exponential backoff and wait_retry_after."""
        config = create_retry_config(max_attempts=4)
        assert "stop" in config
        assert "wait" in config
        assert "retry" in config
        assert config.get("reraise") is True

    def test_wait_retry_after_numeric_header(self) -> None:
        """Verify wait_retry_after parses integer seconds from Retry-After header."""
        wait_fn = wait_retry_after(max_wait=60.0)
        req = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
        resp = httpx2.Response(429, headers={"retry-after": "12"}, request=req)
        exc = httpx2.HTTPStatusError("Rate limited", request=req, response=resp)

        mock_state = MagicMock(spec=RetryCallState)
        mock_outcome = MagicMock()
        mock_outcome.exception.return_value = exc
        mock_state.outcome = mock_outcome

        wait_seconds = wait_fn(mock_state)
        assert wait_seconds == 12.0

    def test_wait_retry_after_http_date_header(self) -> None:
        """Verify wait_retry_after parses HTTP date string and caps at max_wait."""
        wait_fn = wait_retry_after(max_wait=45.0)
        req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        resp = httpx2.Response(
            429,
            headers={"retry-after": "Fri, 31 Dec 2030 23:59:59 GMT"},
            request=req,
        )
        exc = httpx2.HTTPStatusError("Rate limited", request=req, response=resp)

        mock_state = MagicMock(spec=RetryCallState)
        mock_outcome = MagicMock()
        mock_outcome.exception.return_value = exc
        mock_state.outcome = mock_outcome

        wait_seconds = wait_fn(mock_state)
        assert wait_seconds == 45.0

    def test_wait_retry_after_fallback_strategy(self) -> None:
        """Verify wait_retry_after uses fallback strategy when header is absent."""
        fallback = MagicMock(return_value=2.5)
        wait_fn = wait_retry_after(fallback_strategy=fallback)

        req = httpx2.Request("POST", "https://api.ollama.com/api/generate")
        resp = httpx2.Response(500, headers={}, request=req)
        exc = httpx2.HTTPStatusError("Server error", request=req, response=resp)

        mock_state = MagicMock(spec=RetryCallState)
        mock_outcome = MagicMock()
        mock_outcome.exception.return_value = exc
        mock_state.outcome = mock_outcome

        wait_seconds = wait_fn(mock_state)
        assert wait_seconds == 2.5
        fallback.assert_called_once_with(mock_state)

    def test_httpx2_tenacity_transport_sync_retry(self, clock: ClockFake, web: WebFake) -> None:
        """Verify sync HTTPX2TenacityTransport retries and recovers on transient 503."""
        answers = [
            httpx2.Response(503),
            httpx2.Response(200, json={"result": "recovered"}),
        ]
        web.serve(lambda request: answers.pop(0))
        with http_client(EgressLevel.PUBLIC, retries=3) as client:
            resp = client.get("https://example.com/ai")
            attempts = len(web.sent)
            assert (resp.status_code, resp.json(), attempts, clock.waits) == (
                200,
                {"result": "recovered"},
                2,
                [1.0],
            )

    def test_httpx2_tenacity_transport_retries_on_http_524(
        self, clock: ClockFake, web: WebFake
    ) -> None:
        """Verify sync HTTPX2TenacityTransport retries and recovers on Cloudflare HTTP 524 gateway timeout."""
        html_error = "<!DOCTYPE html><html><head><title>524: A timeout occurred</title></head><body>error</body></html>"
        answers = [
            httpx2.Response(524, text=html_error),
            httpx2.Response(524, text=html_error),
            httpx2.Response(200, json={"status": "recovered"}),
        ]
        web.serve(lambda request: answers.pop(0))
        with http_client(EgressLevel.PUBLIC, retries=4) as client:
            resp = client.post("https://example.com/v1/chat/completions", json={"prompt": "hi"})
            attempts = len(web.sent)
            assert (resp.status_code, resp.json(), attempts, clock.waits) == (
                200,
                {"status": "recovered"},
                3,
                [1.0, 2.0],
            )

    def test_request_limited_json_rejects_4xx_and_5xx_responses(self, web: WebFake) -> None:
        """Verify request_limited_json raises for 4xx and 5xx replies and never parses them."""
        from devops_cli.ai.client.network import request_limited_json

        bodies = {
            524: "<!DOCTYPE html><html><title>524: A timeout occurred</title></html>",
            500: '{"error": "internal"}',
            404: '{"error": "not found"}',
        }
        web.serve(
            lambda request: httpx2.Response(
                int(request.url.path.strip("/")), text=bodies[int(request.url.path.strip("/"))]
            )
        )
        raised: list[tuple[int, str]] = []
        with http_client(EgressLevel.PUBLIC) as client:
            for status in bodies:
                with pytest.raises(httpx2.HTTPStatusError) as exc_info:
                    request_limited_json(client, "POST", f"https://example.com/{status}")
                raised.append((exc_info.value.response.status_code, exc_info.value.response.text))

        assert raised == list(bodies.items())

    @pytest.mark.asyncio
    async def test_httpx2_async_retry_transport(self, clock: ClockFake, web: WebFake) -> None:
        """Verify async client with retries retries and recovers on transient connect failure."""
        from devops_cli.http.entry import async_http_client

        answers: list[Exception | httpx2.Response] = [
            httpx2.ConnectError("Connection reset by peer"),
            httpx2.Response(200, json={"result": "recovered_async"}),
        ]

        def responder(request: httpx2.Request) -> httpx2.Response:
            item = answers.pop(0)
            if isinstance(item, Exception):
                item.request = request
                raise item
            return item

        web.serve(responder)
        async with async_http_client(EgressLevel.PUBLIC, retries=3) as client:
            resp = await client.get("https://example.com/ai-async")
            attempts = len(web.sent)
            assert (resp.status_code, resp.json(), attempts, clock.waits) == (
                200,
                {"result": "recovered_async"},
                2,
                [1.0],
            )

    def test_provider_uses_async_retry_transport_and_github_session_does_not(self) -> None:
        """Verify create_pydantic_ai_provider installs async retry transport and GitHub session does not."""
        from pydantic_ai.retries import AsyncHTTPX2TenacityTransport

        from devops_cli.ai.providers import create_pydantic_ai_provider
        from devops_cli.github.session_transport import session_client

        provider = create_pydantic_ai_provider(
            "openai", api_key="sk-test", base_url="https://api.openai.com/v1"
        )
        assert isinstance(provider._client._client._transport, AsyncHTTPX2TenacityTransport)

        github_client = session_client()
        assert not isinstance(github_client._transport, AsyncHTTPX2TenacityTransport)

    def test_the_client_of_a_gateway_chat_group_has_no_retry_transport(self) -> None:
        """Verify the HTTP client of a gateway chat group retries nothing: the gateway owns the
        retries, and `GatewayCallModel` sends a call again before it reaches the gateway (#5965)."""
        from devops_cli.ai.providers import create_pydantic_ai_provider

        chat = create_pydantic_ai_provider(
            "openai", api_key="sk-test", base_url="https://example.com/v1", gateway_caller=True
        )
        jev = create_pydantic_ai_provider(
            "system-one", api_key="sk-test", base_url="https://example.com/v1", gateway_caller=True
        )

        assert (
            type(chat._client._client._transport).__name__,
            type(jev.client._transport).__name__,
        ) == ("AsyncHTTPTransport", "AsyncHTTPX2TenacityTransport")

    def test_create_retry_config_should_retry_http_status_error(self) -> None:
        """Verify should_retry inspects HTTP status errors."""
        from unittest.mock import MagicMock

        from tenacity import RetryCallState

        from devops_cli.ai.retries import create_retry_config

        config = create_retry_config(retry_statuses=(503,))
        retry_fn = config["retry"]
        req = httpx2.Request("GET", "https://example.com")
        status_err = httpx2.HTTPStatusError(
            "503", request=req, response=httpx2.Response(503, request=req)
        )
        mock_state = MagicMock(spec=RetryCallState)
        mock_outcome = MagicMock()
        mock_outcome.exception.return_value = status_err
        mock_state.outcome = mock_outcome
        assert retry_fn(mock_state)
