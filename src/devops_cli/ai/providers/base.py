"""Abstract base provider protocol and common models for LLM backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


class BaseLLMProvider(ABC):
    """Abstract interface for LLM model providers (Ollama, OpenAI, Anthropic, Copilot, Mock)."""

    def __init__(self, config: AIConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical provider name (e.g. 'ollama', 'openai', 'claude', 'copilot', 'mock')."""
        ...

    @abstractmethod
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        timeout: float | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Execute a synchronous LLM chat completion request."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether provider endpoint and credentials are configured and reachable."""
        ...
