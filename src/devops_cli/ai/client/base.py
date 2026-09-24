"""Base provider mixin protocol and common interfaces."""

from __future__ import annotations

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

    def _shared_client(self) -> httpx2.Client:
        """Return the pooled HTTP client for this provider.

        Inference calls were each building their own connection pool, so every request
        paid for a fresh TCP handshake and TLS negotiation -- 247 ms per request against a
        remote endpoint, against 61 ms once the connection is reused.

        The client is shared and deliberately never closed by the caller; per-request
        concerns such as timeouts are passed to the request itself.
        """
        from devops_cli.http.pool import get_shared_client

        return get_shared_client(f"llm:{type(self).__name__}")

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
