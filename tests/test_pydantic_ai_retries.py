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
        """Test predicate identifying transient HTTP error codes."""
        assert is_retryable_status_code(429) is True
        assert is_retryable_status_code(500) is True
        assert is_retryable_status_code(502) is True
        assert is_retryable_status_code(503) is True
        assert is_retryable_status_code(504) is True
        assert is_retryable_status_code(200) is False
        assert is_retryable_status_code(400) is False
        assert is_retryable_status_code(401) is False
        assert is_retryable_status_code(404) is False

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
            resp = client.get("https://test.local/ai")
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
            resp = await client.get("https://test.local/ai/async")
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

        for pkg in (
            devops_cli.ai,
            devops_cli.ai.agents,
            devops_cli.ai.agents.pydantic_agent,
        ):
            assert hasattr(pkg, "HTTPX2TenacityTransport")
            assert hasattr(pkg, "AsyncHTTPX2TenacityTransport")
            assert hasattr(pkg, "TenacityTransport")
            assert hasattr(pkg, "AsyncTenacityTransport")
            assert hasattr(pkg, "RetryConfig")
            assert hasattr(pkg, "wait_retry_after")
            assert hasattr(pkg, "create_retry_config")
            assert hasattr(pkg, "create_retry_transport")
            assert hasattr(pkg, "create_async_retry_transport")
            assert hasattr(pkg, "normalize_agent_retries")
