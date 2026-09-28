"""Base provider mixin protocol and common interfaces."""

from __future__ import annotations

from typing import Any

import httpx2

from devops_cli.ai.client.models import AIClientError
from devops_cli.config.settings import AIConfig


class BaseLLMProviderMixin:
    """Base mixin declaring common client properties and methods for provider backends."""

    _config: AIConfig
    _api_key: str
    _ollama_thinking_supported: bool | None
    _request_timeout_seconds: float | None

    @property
    def backend_type(self) -> str:
        raise NotImplementedError

    @property
    def backend_host(self) -> str:
        raise NotImplementedError

    def _validate_base_url(
        self,
        base_url: str,
        purpose: str = "API",
        *,
        allow_loopback_for_local_tooling: bool = False,
    ) -> str:
        raise NotImplementedError

    def _request_timeout(self) -> httpx2.Timeout:
        raise NotImplementedError

    def _create_retry_transport(self) -> Any:
        """Create a native HTTPX2TenacityTransport with exponential backoff and Retry-After support."""
        from devops_cli.ai.retries import create_retry_transport
        from devops_cli.http.pool import connection_limits

        cfg = getattr(self, "_config", None)
        retries = getattr(cfg, "max_retries", None) if cfg is not None else None
        max_attempts = int(retries) if retries is not None and int(retries) > 0 else 3
        try:
            wrapped = httpx2.HTTPTransport(limits=connection_limits(), http2=True)
            return create_retry_transport(max_attempts=max_attempts, wrapped=wrapped)
        except Exception:
            return create_retry_transport(max_attempts=max_attempts)

    def _create_http_client(self, timeout: httpx2.Timeout | None = None) -> httpx2.Client:
        """Create an httpx2.Client with standard timeout and native retry transport."""
        req_timeout = timeout or self._request_timeout()
        try:
            transport = self._create_retry_transport()
            return httpx2.Client(timeout=req_timeout, transport=transport)
        except Exception:
            return httpx2.Client(timeout=req_timeout)

    def _shared_client(self) -> httpx2.Client:
        """Return the pooled HTTP client for this provider.

        Inference calls were each building their own connection pool, so every request
        paid for a fresh TCP handshake and TLS negotiation -- 247 ms per request against a
        remote endpoint, against 61 ms once the connection is reused.

        The client is shared and deliberately never closed by the caller; per-request
        concerns such as timeouts are passed to the request itself.
        """
        from devops_cli.http.pool import get_shared_client

        try:
            b_type = self.backend_type
        except Exception:
            b_type = "default"
        key = f"llm:{type(self).__name__}:{b_type}"
        try:
            transport = self._create_retry_transport()
            return get_shared_client(key, transport=transport)
        except Exception:
            return get_shared_client(key)

    def _format_status_error(self, exc: httpx2.HTTPError, status: int) -> AIClientError:
        """Extract response body preview for HTTP status errors."""
        detail = ""
        try:
            from devops_cli.security.sanitizer import mask_secrets

            resp = getattr(exc, "response", None)
            raw_body = (resp.text[:256].strip().replace("\n", " ")) if resp is not None else ""
            if raw_body:
                detail = f": {mask_secrets(raw_body)}"
        except Exception:
            pass
        return AIClientError(f"Provider request failed with HTTP {status}{detail}")

    def _format_network_error(self, exc: httpx2.HTTPError, failure: str) -> AIClientError:
        """Format network and transport errors with exception details."""
        from devops_cli.security.sanitizer import mask_secrets

        exc_msg = mask_secrets(str(exc)[:256])
        if exc_msg:
            return AIClientError(f"{failure} ({exc.__class__.__name__}: {exc_msg})")
        return AIClientError(failure)

    def _provider_http_error(self, exc: httpx2.HTTPError, failure: str) -> AIClientError:
        """Format informative provider HTTP error with status code and sanitized detail."""
        from devops_cli.ai.client.models import credentials_error

        status = exc.response.status_code if isinstance(exc, httpx2.HTTPStatusError) else None
        if status in (401, 403):
            provider_name = getattr(self._config, "provider", "AI")
            has_key = bool(getattr(self, "_api_key", None))
            return credentials_error(
                f"The {provider_name} provider", has_key=has_key, status=status
            )
        if status is not None:
            return self._format_status_error(exc, status)
        return self._format_network_error(exc, failure)

    def _connection_error(self, exc: Exception) -> AIClientError:
        raise NotImplementedError

    def _completion_limit(self) -> int | None:
        """Reply token limit: the smaller of the configured `max_tokens` and the call's cap."""
        from devops_cli.ai.client.network import completion_cap

        limits = [v for v in (getattr(self._config, "max_tokens", None), completion_cap.get()) if v]
        return int(min(limits)) if limits else None

    def _strip_think_blocks(self, text: str) -> str:
        raise NotImplementedError

    @classmethod
    def _load_and_increment_rr_index(cls, n: int) -> int:
        from devops_cli.ai.client.network import load_and_increment_rr_index

        return load_and_increment_rr_index(n)
