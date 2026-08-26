"""Ollama local model provider implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx2

from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.config.defaults import (
    DEFAULT_AI_TIMEOUT_SECONDS,
    DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_HOST,
)
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)


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
        try:
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
        payload = {
            "model": target_model,
            "messages": [m.model_dump() if hasattr(m, "model_dump") else m for m in messages],
            "stream": stream,
        }
        res = httpx2.post(
            f"{base_url}/api/chat", json=payload, timeout=timeout or DEFAULT_AI_TIMEOUT_SECONDS
        )
        res.raise_for_status()
        return res.json()
