"""LLM Provider abstraction layer, native Pydantic AI providers, and factory registry."""

from __future__ import annotations

from typing import Any

from pydantic_ai.providers import Provider, infer_provider, infer_provider_class
from pydantic_ai.providers.anthropic import AnthropicProvider as NativeAnthropicProvider
from pydantic_ai.providers.deepseek import DeepSeekProvider as NativeDeepSeekProvider
from pydantic_ai.providers.google import GoogleProvider as NativeGoogleProvider
from pydantic_ai.providers.ollama import OllamaProvider as NativeOllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider as NativeOpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider as NativeOpenRouterProvider

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
    """Factory function retrieving an instantiated legacy provider by canonical name."""
    provider_cls = _PROVIDERS.get(name.lower(), OllamaProvider)
    return provider_cls(config)


def create_pydantic_ai_provider(
    provider: str,
    base_url: str | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> Provider[Any]:
    """Create and configure a native Pydantic AI Provider instance.

    Configures endpoint URLs, API keys, and client parameters according to provider type.
    """
    prov_name = provider.lower().strip()
    if prov_name in ("ollama", "ollama-chat"):
        return NativeOllamaProvider(base_url=base_url, api_key=api_key, **kwargs)
    elif prov_name in ("openai", "openai-chat", "openai-responses"):
        return NativeOpenAIProvider(base_url=base_url, api_key=api_key, **kwargs)
    elif prov_name in ("anthropic", "claude"):
        return NativeAnthropicProvider(base_url=base_url, api_key=api_key, **kwargs)
    elif prov_name in ("google", "gemini"):
        init_google: dict[str, Any] = dict(kwargs)
        if api_key is not None:
            init_google["api_key"] = api_key
        if base_url is not None:
            init_google["base_url"] = base_url
        return NativeGoogleProvider(**init_google)
    elif prov_name == "deepseek":
        return NativeDeepSeekProvider(api_key=api_key, **kwargs)
    elif prov_name == "openrouter":
        init_openrouter: dict[str, Any] = dict(kwargs)
        if api_key is not None:
            init_openrouter["api_key"] = api_key
        return NativeOpenRouterProvider(**init_openrouter)

    provider_cls = infer_provider_class(provider)
    init_kwargs: dict[str, Any] = dict(kwargs)
    if base_url is not None:
        init_kwargs["base_url"] = base_url
    if api_key is not None:
        init_kwargs["api_key"] = api_key
    return provider_cls(**init_kwargs)


__all__ = [
    "AnthropicProvider",
    "BaseLLMProvider",
    "CopilotProvider",
    "MockProvider",
    "NativeAnthropicProvider",
    "NativeDeepSeekProvider",
    "NativeGoogleProvider",
    "NativeOllamaProvider",
    "NativeOpenAIProvider",
    "NativeOpenRouterProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "Provider",
    "create_pydantic_ai_provider",
    "get_provider",
    "infer_provider",
    "infer_provider_class",
]
