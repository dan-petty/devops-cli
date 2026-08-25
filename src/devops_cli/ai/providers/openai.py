"""OpenAI-compatible REST API model provider implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx2

from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI and OpenAI-compatible API provider (e.g. Azure OpenAI, Groq, vLLM)."""

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.config.api_base_url or self.config.provider == "openai")

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        timeout: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        target_model = model or self.config.model or "gpt-4o"
        base_url = (self.config.api_base_url or "https://api.openai.com/v1").rstrip("/")
        payload = {
            "model": target_model,
            "messages": [m.model_dump() if hasattr(m, "model_dump") else m for m in messages],
            "stream": stream,
        }
        res = httpx2.post(
            f"{base_url}/chat/completions",
            json=payload,
            timeout=timeout or 60.0,
        )
        res.raise_for_status()
        return res.json()
