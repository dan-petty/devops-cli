"""Mock LLM provider for deterministic unit testing and offline execution."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


class MockProvider(BaseLLMProvider):
    """Deterministic mock LLM provider for unit testing without network dependencies."""

    def __init__(self, config: AIConfig, default_response: str = '{"findings": []}') -> None:
        super().__init__(config)
        self.default_response = default_response
        self.invocations: list[list[ChatMessage]] = []

    @property
    def name(self) -> str:
        return "mock"

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        timeout: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> str:
        self.invocations.append(messages)
        return self.default_response

    def is_available(self) -> bool:
        return True
