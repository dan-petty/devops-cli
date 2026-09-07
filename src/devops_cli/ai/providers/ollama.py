"""Ollama local model provider implementation."""

from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any

import httpx2

from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.config.defaults import (
    DEFAULT_AI_TIMEOUT_SECONDS,
    DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_HOST,
)
from devops_cli.config.env import ENV_AI_ALLOW_PRIVATE_NETWORK
from devops_cli.http.validation import validate_service_url
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_loopback_or_private_allowed(base_url: str, allow_private: bool = False) -> bool:
    """Check if base_url targets a loopback interface or private network egress is allowed."""
    if allow_private:
        return True
    parsed = urllib.parse.urlparse(base_url)
    hostname = (parsed.hostname or "").lower()
    if hostname in _LOOPBACK_HOSTS:
        return True
    return os.environ.get(ENV_AI_ALLOW_PRIVATE_NETWORK, "").lower() in ("1", "true", "yes")


def _validate_ollama_url(base_url: str, allow_private: bool = False) -> None:
    """Validate Ollama endpoint against SSRF while allowing loopback or authorized private networks."""
    permitted = _is_loopback_or_private_allowed(base_url, allow_private=allow_private)
    validate_service_url(base_url, purpose="ollama", allow=permitted)


class OllamaProvider(BaseLLMProvider):
    """Local Ollama REST API model provider."""

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        urls = self.config.get_ollama_urls
        if not urls:
            return False
        base_url = urls[0]
        allow_private = getattr(self.config, "allow_private_network", False)
        try:
            _validate_ollama_url(base_url, allow_private=allow_private)
            res = httpx2.get(
                f"{base_url.rstrip('/')}/api/tags", timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
            )
            return res.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        timeout: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        target_model = model or self.config.model
        urls = self.config.get_ollama_urls
        base_url = urls[0].rstrip("/") if urls else DEFAULT_OLLAMA_HOST
        allow_private = getattr(self.config, "allow_private_network", False)
        _validate_ollama_url(base_url, allow_private=allow_private)
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [m.model_dump() if hasattr(m, "model_dump") else m for m in messages],
            "stream": stream,
        }
        if getattr(self.config, "reasoning_effort", None):
            payload["reasoning_effort"] = self.config.reasoning_effort
        res = httpx2.post(
            f"{base_url}/api/chat", json=payload, timeout=timeout or DEFAULT_AI_TIMEOUT_SECONDS
        )
        res.raise_for_status()
        return res.json()
