"""Anthropic Claude REST API model provider implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx2

from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.config.defaults import (
    DEFAULT_AI_TIMEOUT_SECONDS,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_LLM_MAX_TOKENS,
)
from devops_cli.http.validation import validate_service_url
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    @property
    def name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        return bool(self.config.api_base_url or self.config.provider == "claude")

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        timeout: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        target_model = model or self.config.model or DEFAULT_ANTHROPIC_MODEL
        base_url = (self.config.api_base_url or "https://api.anthropic.com/v1").rstrip("/")
        validate_service_url(
            base_url,
            purpose="ai",
            allow=bool(getattr(self.config, "allow_private_network", False)),
        )
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        system_prompt = ""
        claude_messages: list[dict[str, str]] = []
        for m in messages:
            role = getattr(m, "role", "user")
            content = getattr(m, "content", str(m))
            if role == "system":
                system_prompt += f"{content}\n"
            else:
                claude_messages.append({"role": role, "content": content})

        payload = {
            "model": target_model,
            "system": system_prompt.strip(),
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", DEFAULT_LLM_MAX_TOKENS),
        }
        res = httpx2.post(
            f"{base_url}/messages",
            json=payload,
            headers=headers,
            timeout=timeout or DEFAULT_AI_TIMEOUT_SECONDS,
        )
        res.raise_for_status()
        return res.json()
