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

    def _connection_error(self, exc: Exception) -> AIClientError:
        raise NotImplementedError

    def _strip_think_blocks(self, text: str) -> str:
        raise NotImplementedError

    @classmethod
    def _load_and_increment_rr_index(cls, n: int) -> int:
        from devops_cli.ai.client.network import load_and_increment_rr_index

        return load_and_increment_rr_index(n)
