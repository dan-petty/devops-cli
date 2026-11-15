"""Native Pydantic AI provider factory with SSRF-validated endpoints."""

from __future__ import annotations

import logging
from typing import Any, Final

logger = logging.getLogger(__name__)

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
    "system-one": ("pydantic_ai.providers.system_one", "SystemOneProvider"),
    "typesafe": ("pydantic_ai.providers.system_one", "SystemOneProvider"),
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


# The status codes of a TypeSafe Jev retry: a rate limit and a capacity limit (#5286).
_JEV_RETRY_STATUS: Final[frozenset[int]] = frozenset({429, 529})


def jev_retry_transport(
    wrapped: Any, *, wait: Any | None = None, attempts: int | None = None
) -> Any:
    """The transport of the Jev provider: retry a 429 or a 529 with backoff (#5286).

    `wait_retry_after` reads a `Retry-After` header, and its fallback is exponential. The attempt
    limit is low, so the timeout of the caller fires first and reports its own error.
    """
    import httpx2
    from pydantic_ai.retries import AsyncHTTPX2TenacityTransport, RetryConfig, wait_retry_after
    from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

    from devops_cli.config.constants import CONST_AI_JEV_RETRY_ATTEMPTS

    def validate(response: Any) -> Any:
        if response.status_code in _JEV_RETRY_STATUS:
            raise httpx2.HTTPStatusError(
                f"Jev answered {response.status_code}", request=response.request, response=response
            )
        return response

    def log_retry(state: Any) -> None:
        error = state.outcome.exception() if state.outcome is not None else None
        status = getattr(getattr(error, "response", None), "status_code", "?")
        logger.warning(
            "Jev answered %s on attempt %s; retry after the backoff", status, state.attempt_number
        )

    return AsyncHTTPX2TenacityTransport(
        RetryConfig(
            retry=retry_if_exception_type(httpx2.HTTPStatusError),
            wait=wait or wait_retry_after(wait_exponential(multiplier=0.5, max=10)),
            stop=stop_after_attempt(attempts or CONST_AI_JEV_RETRY_ATTEMPTS),
            before_sleep=log_retry,
            reraise=True,
        ),
        wrapped=wrapped,
        validate_response=validate,
    )


def create_pydantic_ai_provider(
    provider: str,
    base_url: str | None = None,
    api_key: str | None = None,
    *,
    allow_private_network: bool = False,
    gateway_caller: bool = False,
    **kwargs: Any,
) -> Any:
    """Create and configure a native Pydantic AI Provider instance.

    Configures endpoint URLs, API keys, and client parameters according to provider type.
    A provider that takes an ``http_client`` gets a client of the HTTP entry point at the configured level:
    loopback, or private with ``allow_private_network``. The connect checks each address.
    With ``gateway_caller``, each request of that client names devops-cli and its service as the
    caller, for the LLM gateway (#1668), and carries the trace context of its HTTP client span.
    """
    prov_name = provider.lower().strip()
    provider_cls: Any = _PYDANTIC_PROVIDERS.get(prov_name)
    if provider_cls is None:
        from pydantic_ai.providers import infer_provider_class

        provider_cls = infer_provider_class(provider)

    init_kwargs: dict[str, Any] = dict(kwargs)
    if prov_name in {"system-one", "typesafe"} and base_url is None:
        from devops_cli.config.constants import CONST_URL_TYPESAFE_API_BASE

        base_url = CONST_URL_TYPESAFE_API_BASE
    if base_url is not None and prov_name not in _EXCLUDE_BASE_URL_NAMES:
        init_kwargs["base_url"] = base_url
    if api_key is not None:
        init_kwargs["api_key"] = api_key

    import inspect

    sig = inspect.signature(provider_cls.__init__)
    if "http_client" in sig.parameters and "http_client" not in init_kwargs:
        from devops_cli.http.egress import EgressLevel
        from devops_cli.http.entry import async_http_client

        level = EgressLevel.PRIVATE if allow_private_network else EgressLevel.LOOPBACK
        if gateway_caller:
            from devops_cli.ai.client.network import name_gateway_caller
            from devops_cli.telemetry.library_spans import instrument_gateway_client

            gateway_client = async_http_client(
                level, event_hooks={"request": [name_gateway_caller]}, retries=3
            )
            instrument_gateway_client(gateway_client)
            init_kwargs["http_client"] = gateway_client
        elif prov_name in {"system-one", "typesafe"}:
            client = async_http_client(level, retries=3)
            client._transport = jev_retry_transport(client._transport)
            init_kwargs["http_client"] = client
        else:
            init_kwargs["http_client"] = async_http_client(level, retries=3)

    return provider_cls(**init_kwargs)


__all__ = [
    "create_pydantic_ai_provider",
    "is_pydantic_ai_provider",
    "jev_retry_transport",
]
