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

    def test_stream_retry_reset_before_first_chunk(self) -> None:
        """WHEN the first model request raises ConnectionResetError before it yields a chunk
        and the second attempt answers a complete reply
        THEN the agent run returns the second reply and raises no AIClientError."""
        from contextlib import asynccontextmanager

        from pydantic_ai import Agent, RunContext
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class FlakyStreamModel(TestModel):
            @asynccontextmanager
            async def request_stream(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise ConnectionResetError("Connection reset by peer")
                async with super().request_stream(*args, **kwargs) as s:
                    yield s

        model = wrap_stream_retry_model(FlakyStreamModel())
        agent = Agent(model)

        async def drain(_ctx: RunContext[None], events: object) -> None:
            async for _ in events:
                pass

        result = agent.run_sync("test request", event_stream_handler=drain)
        assert calls == 2
        assert result.output == "success (no tool calls)"

    def test_stream_retry_no_replay_after_first_chunk(self) -> None:
        """WHEN the model response yields one chunk and then raises ConnectionResetError
        THEN the run raises AIClientError and sends no second request."""
        from contextlib import asynccontextmanager

        from pydantic_ai import Agent, RunContext
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.client.models import AIClientError
        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class MidStreamFailModel(TestModel):
            @asynccontextmanager
            async def request_stream(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                async with super().request_stream(*args, **kwargs) as stream:

                    class FailingStream:
                        def __init__(self, inner: object) -> None:
                            self.inner = inner

                        def __getattr__(self, name: str) -> object:
                            return getattr(self.inner, name)

                        async def __aiter__(self):
                            count = 0
                            async for event in self.inner:
                                yield event
                                count += 1
                                if count == 1:
                                    raise ConnectionResetError("Connection reset mid-stream")

                    yield FailingStream(stream)

        model = wrap_stream_retry_model(MidStreamFailModel())
        agent = Agent(model)

        async def drain(_ctx: RunContext[None], events: object) -> None:
            async for _ in events:
                pass

        with pytest.raises(AIClientError) as exc_info:
            agent.run_sync("test request", event_stream_handler=drain)
        assert calls == 1
        assert "Connection reset mid-stream" in str(exc_info.value)

    def test_stream_retry_limit_reached(self) -> None:
        """WHEN each of three attempts raises ConnectionResetError before the first chunk
        THEN the client sends exactly three attempts, waits between them, and raises AIClientError."""
        from contextlib import asynccontextmanager

        from pydantic_ai import Agent, RunContext
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.client.models import AIClientError
        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class AlwaysFailModel(TestModel):
            @asynccontextmanager
            async def request_stream(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                raise ConnectionResetError("Connection reset by peer")
                yield

        model = wrap_stream_retry_model(AlwaysFailModel())
        agent = Agent(model)

        async def drain(_ctx: RunContext[None], events: object) -> None:
            async for _ in events:
                pass

        with pytest.raises(AIClientError) as exc_info:
            agent.run_sync("test request", event_stream_handler=drain)
        assert calls == 3
        assert "Connection reset by peer" in str(exc_info.value)

    def test_stream_retry_non_retryable_401_authentication_failure(self) -> None:
        """WHEN the model request returns HTTP 401 before any chunk
        THEN the client sends one request and raises AIClientError."""
        from contextlib import asynccontextmanager

        from pydantic_ai import Agent, RunContext
        from pydantic_ai.exceptions import ModelHTTPError
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.client.models import AIClientError
        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class AuthFailModel(TestModel):
            @asynccontextmanager
            async def request_stream(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                raise ModelHTTPError(status_code=401, model_name="test", body="Unauthorized")
                yield

        model = wrap_stream_retry_model(AuthFailModel())
        agent = Agent(model)

        async def drain(_ctx: RunContext[None], events: object) -> None:
            async for _ in events:
                pass

        with pytest.raises(AIClientError) as exc_info:
            agent.run_sync("test request", event_stream_handler=drain)
        assert calls == 1
        assert exc_info.value.status == 401

    def test_stream_retry_non_streaming_request_recovers(self) -> None:
        """Verify non-streaming request retries connection reset and recovers."""
        from pydantic_ai import Agent
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class FailOnceModel(TestModel):
            async def request(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise ConnectionResetError("Connection reset before output")
                return await super().request(*args, **kwargs)

        model = wrap_stream_retry_model(FailOnceModel())
        agent = Agent(model)
        result = agent.run_sync("non-streaming test")
        assert calls == 2
        assert result.output == "success (no tool calls)"

    def test_stream_retry_non_streaming_request_exhaustion(self) -> None:
        """Verify non-streaming request raises AIClientError when retries are exhausted."""
        from pydantic_ai import Agent
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.client.models import AIClientError
        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class AlwaysFailRequestModel(TestModel):
            async def request(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                raise ConnectionResetError("Reset always")

        model = wrap_stream_retry_model(AlwaysFailRequestModel())
        agent = Agent(model)
        with pytest.raises(AIClientError) as exc_info:
            agent.run_sync("exhaustion test")
        assert calls == 3
        assert "Reset always" in str(exc_info.value)

    def test_stream_retry_non_streaming_request_non_retryable(self) -> None:
        """Verify non-streaming request raises AIClientError immediately on 401 without retry."""
        from pydantic_ai import Agent
        from pydantic_ai.exceptions import ModelHTTPError
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.client.models import AIClientError
        from devops_cli.ai.pydantic_ai_bridge import wrap_stream_retry_model

        calls = 0

        class AuthFailRequestModel(TestModel):
            async def request(self, *args: object, **kwargs: object):
                nonlocal calls
                calls += 1
                raise ModelHTTPError(status_code=401, model_name="test", body="Unauthorized")

        model = wrap_stream_retry_model(AuthFailRequestModel())
        agent = Agent(model)
        with pytest.raises(AIClientError) as exc_info:
            agent.run_sync("auth fail test")
        assert calls == 1
        assert exc_info.value.status == 401

    def test_stream_retry_helper_functions_coverage(self) -> None:
        """Verify helper error inspection and wrapping logic."""
        from unittest.mock import MagicMock

        from pydantic_ai.exceptions import ModelConnectionError, ModelHTTPError
        from pydantic_ai.models.test import TestModel

        from devops_cli.ai.client.models import AIClientError
        from devops_cli.ai.pydantic_ai_bridge import (
            _is_retryable_error,
            _StreamRetryProxy,
            _to_ai_client_error,
            wrap_stream_retry_model,
        )

        req = httpx2.Request("GET", "https://example.com")
        resp_401 = httpx2.Response(401, request=req)
        assert not _is_retryable_error(
            httpx2.HTTPStatusError("401", request=req, response=resp_401)
        )
        assert not _is_retryable_error(
            ModelHTTPError(status_code=403, model_name="test", body="forbidden")
        )
        os_err = OSError("Reset")
        os_err.errno = 104
        assert _is_retryable_error(os_err)
        assert _is_retryable_error(httpx2.ReadTimeout("Timed out"))
        assert _is_retryable_error(ModelConnectionError(model_name="test", message="lost"))
        assert not _is_retryable_error(ValueError("generic error"))

        existing = AIClientError("already wrapped", status=400)
        assert _to_ai_client_error(existing) is existing

        class DummyResponseErr(Exception):
            def __init__(self) -> None:
                self.response = MagicMock(status_code=404)

        converted = _to_ai_client_error(DummyResponseErr())
        assert converted.status == 404

        timeout_err = _to_ai_client_error(httpx2.ReadTimeout("timed out"))
        assert timeout_err.timed_out

        assert wrap_stream_retry_model(None) is None
        wrapped = wrap_stream_retry_model(TestModel())
        assert wrap_stream_retry_model(wrapped) is wrapped

        proxy = _StreamRetryProxy(TestModel(), [], None, MagicMock(), None)
        with pytest.raises(AttributeError, match="non_existent_attribute"):
            _ = proxy.non_existent_attribute
        proxy._active_inner = MagicMock(custom_inner_attr=42)
        assert proxy.custom_inner_attr == 42

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
