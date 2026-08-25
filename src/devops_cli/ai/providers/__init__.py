"""LLM Provider abstraction layer and factory registry for devops-cli."""

from __future__ import annotations

from devops_cli.ai.providers.anthropic import AnthropicProvider
from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.ai.providers.copilot import CopilotProvider
from devops_cli.ai.providers.mock import MockProvider
from devops_cli.ai.providers.ollama import OllamaProvider
from devops_cli.ai.providers.openai import OpenAIProvider
from devops_cli.config.settings import AIConfig

_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "claude": AnthropicProvider,
    "anthropic": AnthropicProvider,
    "copilot": CopilotProvider,
    "mock": MockProvider,
}


def get_provider(name: str, config: AIConfig) -> BaseLLMProvider:
    """Factory function retrieving an instantiated provider by canonical name."""
    provider_cls = _PROVIDERS.get(name.lower(), OllamaProvider)
    return provider_cls(config)


__all__ = [
    "AnthropicProvider",
    "BaseLLMProvider",
    "CopilotProvider",
    "MockProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "get_provider",
]
