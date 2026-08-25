"""GitHub Copilot Chat API model provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)


class CopilotProvider(BaseLLMProvider):
    """GitHub Copilot Chat API provider."""

    @property
    def name(self) -> str:
        return "copilot"

    def is_available(self) -> bool:
        return bool(self.config.provider == "copilot")

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
        return {"model": target_model, "messages": messages}
