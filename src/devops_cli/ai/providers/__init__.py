"""LLM Provider abstraction layer, native Pydantic AI providers, and factory registry."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.providers.anthropic import AnthropicProvider
from devops_cli.ai.providers.base import BaseLLMProvider
from devops_cli.ai.providers.copilot import CopilotProvider
from devops_cli.ai.providers.ollama import OllamaProvider
from devops_cli.ai.providers.openai import OpenAIProvider
from devops_cli.config.settings import AIConfig

_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "claude": AnthropicProvider,
    "anthropic": AnthropicProvider,
    "copilot": CopilotProvider,
}


def register_provider(name: str, provider_cls: type[BaseLLMProvider]) -> None:
    """Register a custom or mock LLM provider class under the given canonical name."""
    _PROVIDERS[name.lower().strip()] = provider_cls


def get_provider(name: str, config: AIConfig) -> BaseLLMProvider:
    """Factory function retrieving an instantiated legacy provider by canonical name."""
    provider_cls = _PROVIDERS.get(name.lower(), OllamaProvider)
    return provider_cls(config)


_PYDANTIC_PROVIDER_SPECS: dict[str, tuple[str, str]] = {
    "ollama": ("pydantic_ai.providers.ollama", "OllamaProvider"),
    "ollama-chat": ("pydantic_ai.providers.ollama", "OllamaProvider"),
    "openai": ("pydantic_ai.providers.openai", "OpenAIProvider"),
    "openai-chat": ("pydantic_ai.providers.openai", "OpenAIProvider"),
    "openai-responses": ("pydantic_ai.providers.openai", "OpenAIProvider"),
    "anthropic": ("pydantic_ai.providers.anthropic", "AnthropicProvider"),
    "claude": ("pydantic_ai.providers.anthropic", "AnthropicProvider"),
    "google": ("pydantic_ai.providers.google", "GoogleProvider"),
    "gemini": ("pydantic_ai.providers.google", "GoogleProvider"),
    "deepseek": ("pydantic_ai.providers.deepseek", "DeepSeekProvider"),
    "openrouter": ("pydantic_ai.providers.openrouter", "OpenRouterProvider"),
}


class _LazyPydanticProviders(dict[str, Any]):
    """Mapping that lazily resolves native Pydantic AI provider classes on access."""

    def __getitem__(self, key: str) -> Any:
        val = super().get(key)
        if val is not None:
            return val
        norm_key = key.lower().strip()
        if norm_key in _PYDANTIC_PROVIDER_SPECS:
            mod_name, cls_name = _PYDANTIC_PROVIDER_SPECS[norm_key]
            import importlib

            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
            self[key] = cls
            return cls
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return key.lower().strip() in _PYDANTIC_PROVIDER_SPECS or super().__contains__(key)
        return False

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


_PYDANTIC_PROVIDERS = _LazyPydanticProviders()

_EXCLUDE_BASE_URL_NAMES: frozenset[str] = frozenset({"deepseek", "openrouter"})


def is_pydantic_ai_provider(name: str) -> bool:
    """Whether ``name`` names a provider: one registered here, or one pydantic-ai knows.

    A provider whose optional package is not installed still names one.
    """
    if name.lower().strip() in _PYDANTIC_PROVIDER_SPECS:
        return True
    try:
        from pydantic_ai.providers import infer_provider_class

        infer_provider_class(name)
    except ImportError:
        return True
    except ValueError:
        return False
    return True


def create_pydantic_ai_provider(
    provider: str,
    base_url: str | None = None,
    api_key: str | None = None,
    *,
    allow_private_network: bool = False,
    **kwargs: Any,
) -> Any:
    """Create and configure a native Pydantic AI Provider instance.

    Configures endpoint URLs, API keys, and client parameters according to provider type.
    ``base_url`` follows `validate_configured_service_url`: loopback is allowed, and any other
    non-public host needs ``allow_private_network``.
    """
    prov_name = provider.lower().strip()
    if base_url is not None:
        from devops_cli.core.validation import validate_configured_service_url

        validate_configured_service_url(
            base_url, purpose=prov_name, allow_private=allow_private_network
        )

    provider_cls: Any = _PYDANTIC_PROVIDERS.get(prov_name)
    if provider_cls is None:
        from pydantic_ai.providers import infer_provider_class

        provider_cls = infer_provider_class(provider)

    init_kwargs: dict[str, Any] = dict(kwargs)
    if base_url is not None and prov_name not in _EXCLUDE_BASE_URL_NAMES:
        init_kwargs["base_url"] = base_url
    if api_key is not None:
        init_kwargs["api_key"] = api_key

    return provider_cls(**init_kwargs)


def __getattr__(name: str) -> Any:
    _lazy_map: dict[str, tuple[str, str]] = {
        "Provider": ("pydantic_ai.providers", "Provider"),
        "infer_provider": ("pydantic_ai.providers", "infer_provider"),
        "infer_provider_class": ("pydantic_ai.providers", "infer_provider_class"),
        "NativeAnthropicProvider": ("pydantic_ai.providers.anthropic", "AnthropicProvider"),
        "NativeDeepSeekProvider": ("pydantic_ai.providers.deepseek", "DeepSeekProvider"),
        "NativeGoogleProvider": ("pydantic_ai.providers.google", "GoogleProvider"),
        "NativeOllamaProvider": ("pydantic_ai.providers.ollama", "OllamaProvider"),
        "NativeOpenAIProvider": ("pydantic_ai.providers.openai", "OpenAIProvider"),
        "NativeOpenRouterProvider": ("pydantic_ai.providers.openrouter", "OpenRouterProvider"),
    }
    if name in _lazy_map:
        mod_name, attr_name = _lazy_map[name]
        import importlib

        mod = importlib.import_module(mod_name)
        val = getattr(mod, attr_name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AnthropicProvider",
    "BaseLLMProvider",
    "CopilotProvider",
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
    "is_pydantic_ai_provider",
    "register_provider",
]
