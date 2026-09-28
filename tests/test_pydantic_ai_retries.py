"""Unit tests for the native Pydantic AI Retries subsystem."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx2
import pytest
from tenacity import RetryCallState

from devops_cli.ai.retries import (
    AsyncHTTPX2TenacityTransport,
    AsyncTenacityTransport,
    HTTPX2TenacityTransport,
    TenacityTransport,
    create_async_retry_transport,
    create_retry_config,
    create_retry_transport,
    is_retryable_status_code,
    normalize_agent_retries,
    wait_retry_after,
)


class TestPydanticAIRetriesSubsystem:
    """Validate native Pydantic AI retries integration and transports."""

    def test_core_classes_and_function_exports(self) -> None:
        """Verify core types, classes, and aliases are exported correctly."""
        assert HTTPX2TenacityTransport is not None
        assert AsyncHTTPX2TenacityTransport is not None
        assert TenacityTransport is not None
        assert AsyncTenacityTransport is not None
        assert callable(wait_retry_after)
        assert callable(create_retry_config)
        assert callable(create_retry_transport)
        assert callable(create_async_retry_transport)

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

    def test_httpx2_tenacity_transport_sync_retry(self) -> None:
        """Verify sync HTTPX2TenacityTransport retries and recovers on transient 503."""
        attempts = 0

        class FlakyTransport(httpx2.BaseTransport):
            def handle_request(self, request: httpx2.Request) -> httpx2.Response:
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    return httpx2.Response(503, request=request)
                return httpx2.Response(200, json={"result": "recovered"}, request=request)

        transport = create_retry_transport(
            max_attempts=3,
            min_wait=0.001,
            max_wait=0.01,
            wrapped=FlakyTransport(),
        )
        with httpx2.Client(transport=transport) as client:
            resp = client.get("https://example.com/ai")
            assert resp.status_code == 200
            assert resp.json() == {"result": "recovered"}
            assert attempts == 2

    @pytest.mark.asyncio
    async def test_async_httpx2_tenacity_transport_retry(self) -> None:
        """Verify async AsyncHTTPX2TenacityTransport retries and recovers on transient 429."""
        attempts = 0

        class FlakyAsyncTransport(httpx2.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
                nonlocal attempts
                attempts += 1
                if attempts < 2:
                    return httpx2.Response(429, headers={"retry-after": "0"}, request=request)
                return httpx2.Response(200, json={"status": "ok"}, request=request)

        transport = create_async_retry_transport(
            max_attempts=3,
            min_wait=0.001,
            max_wait=0.01,
            wrapped=FlakyAsyncTransport(),
        )
        async with httpx2.AsyncClient(transport=transport) as client:
            resp = await client.get("https://example.com/ai/async")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
            assert attempts == 2

    def test_normalize_agent_retries(self) -> None:
        """Verify normalization of diverse retries configurations into standard AgentRetries."""
        from devops_cli.ai.agents.context import AgentRetries as ContextAgentRetries

        # None -> default (tools=1, output=1)
        r_none = normalize_agent_retries(None)
        assert r_none == {"tools": 1, "output": 1}

        # int -> uniform budget
        r_int = normalize_agent_retries(3)
        assert r_int == {"tools": 3, "output": 3}

        # dict -> custom budgets
        r_dict = normalize_agent_retries({"tools": 4, "output": 2})
        assert r_dict == {"tools": 4, "output": 2}

        # Pydantic BaseModel instance -> extracted dict
        model_retries = ContextAgentRetries(tools=5, output=3)
        r_model = normalize_agent_retries(model_retries)
        assert r_model == {"tools": 5, "output": 3}

    def test_package_reexports(self) -> None:
        """Verify retries symbols are re-exported across package tiers."""
        import devops_cli.ai
        import devops_cli.ai.agents
        import devops_cli.ai.agents.pydantic_agent

        expected_symbols = (
            "HTTPX2TenacityTransport",
            "AsyncHTTPX2TenacityTransport",
            "TenacityTransport",
            "AsyncTenacityTransport",
            "RetryConfig",
            "wait_retry_after",
            "create_retry_config",
            "create_retry_transport",
            "create_async_retry_transport",
            "normalize_agent_retries",
        )
        for pkg in (
            devops_cli.ai,
            devops_cli.ai.agents,
            devops_cli.ai.agents.pydantic_agent,
        ):
            assert all(hasattr(pkg, s) for s in expected_symbols)

    def test_httpx2_tenacity_transport_retries_on_http_524(self) -> None:
        """Verify sync HTTPX2TenacityTransport retries and recovers on Cloudflare HTTP 524 gateway timeout."""
        attempts = 0

        class CloudflareTimeoutTransport(httpx2.BaseTransport):
            def handle_request(self, request: httpx2.Request) -> httpx2.Response:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    html_error = "<!DOCTYPE html><html><head><title>524: A timeout occurred</title></head><body>error</body></html>"
                    return httpx2.Response(524, text=html_error, request=request)
                return httpx2.Response(200, json={"status": "recovered"}, request=request)

        transport = create_retry_transport(
            max_attempts=4,
            min_wait=0.001,
            max_wait=0.01,
            wrapped=CloudflareTimeoutTransport(),
        )
        with httpx2.Client(transport=transport) as client:
            resp = client.post("https://example.com/v1/chat/completions", json={"prompt": "hi"})
            assert (resp.status_code, resp.json(), attempts) == (200, {"status": "recovered"}, 3)

    def test_read_limited_json_rejects_4xx_and_5xx_responses(self) -> None:
        """Verify read_limited_json always treats 4xx and 5xx responses as HTTP errors and never parses them."""
        from devops_cli.ai.client.network import read_limited_json

        req = httpx2.Request("POST", "https://example.com/ai")
        resp_524 = httpx2.Response(
            524,
            text="<!DOCTYPE html><html><title>524: A timeout occurred</title></html>",
            request=req,
        )
        with pytest.raises(httpx2.HTTPStatusError) as exc_info_524:
            read_limited_json(resp_524)

        resp_500 = httpx2.Response(500, text='{"error": "internal"}', request=req)
        with pytest.raises(httpx2.HTTPStatusError) as exc_info_500:
            read_limited_json(resp_500)

        resp_404 = httpx2.Response(404, text='{"error": "not found"}', request=req)
        with pytest.raises(httpx2.HTTPStatusError) as exc_info_404:
            read_limited_json(resp_404)

        assert (
            exc_info_524.value.response.status_code,
            exc_info_500.value.response.status_code,
            exc_info_404.value.response.status_code,
        ) == (524, 500, 404)
