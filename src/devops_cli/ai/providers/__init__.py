"""Native Pydantic AI provider factory with SSRF-validated endpoints."""

from __future__ import annotations

from typing import Any

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

    import inspect

    sig = inspect.signature(provider_cls.__init__)
    if "http_client" in sig.parameters and "http_client" not in init_kwargs:
        from devops_cli.http.client import new_async_http_client
        from devops_cli.http.egress import EgressLevel

        level = EgressLevel.PRIVATE if allow_private_network else EgressLevel.LOOPBACK
        init_kwargs["http_client"] = new_async_http_client(level=level)

    return provider_cls(**init_kwargs)


__all__ = [
    "create_pydantic_ai_provider",
    "is_pydantic_ai_provider",
]
