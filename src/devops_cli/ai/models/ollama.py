"""Native Pydantic AI Ollama model and provider integration."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from pydantic_ai.models.ollama import OllamaModel
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers import Provider
    from pydantic_ai.providers.ollama import OllamaProvider

from pydantic_ai.profiles import ModelProfileSpec
from pydantic_ai.profiles.cohere import cohere_model_profile
from pydantic_ai.profiles.deepseek import deepseek_model_profile
from pydantic_ai.profiles.google import google_model_profile
from pydantic_ai.profiles.harmony import harmony_model_profile
from pydantic_ai.profiles.meta import meta_model_profile
from pydantic_ai.profiles.mistral import mistral_model_profile
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
from pydantic_ai.profiles.qwen import qwen_model_profile
from pydantic_ai.settings import ModelSettings, merge_model_settings

from devops_cli.ai.settings import create_model_settings
from devops_cli.exceptions import ConfigurationError, InvalidURLError, SSRFBlockedError


def _is_cloud_metadata_host(host: str) -> bool:
    from devops_cli.core.validation import is_cloud_metadata_host

    return is_cloud_metadata_host(host, resolve_dns=True)


def normalize_ollama_base_url(url: str, *, allow_private: bool = True) -> str:
    """Normalize Ollama base URL ensuring a clean /v1 endpoint path without duplicate segments.

    Examples:
        - http://localhost:11434 -> http://localhost:11434/v1
        - http://localhost:11434/v1/ -> http://localhost:11434/v1
        - https://ollama.com -> https://ollama.com/v1
    """
    clean_url = url.strip()
    if not clean_url:
        raise ConfigurationError(
            "No Ollama server URLs configured. Run: devops config set ai.ollama_urls <url>",
            key="ai.ollama_urls",
        )

    parsed = urlsplit(clean_url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise InvalidURLError(
            clean_url,
            reason=f"Invalid Ollama URL scheme '{parsed.scheme}': must be http or https",
        )
    if not parsed.netloc:
        raise InvalidURLError(
            clean_url,
            reason=f"Invalid Ollama URL '{clean_url}': missing host or authority",
        )

    host = (parsed.hostname or "").lower()
    if _is_cloud_metadata_host(host):
        raise SSRFBlockedError(
            clean_url,
            reason="Access to cloud instance metadata service is forbidden",
        )

    from devops_cli.core.validation import validate_url

    validate_url(
        clean_url,
        purpose="Ollama endpoint",
        allow_private=allow_private,
        schemes=("http", "https"),
    )

    raw_path = parsed.path.rstrip("/")
    if raw_path.endswith("/v1"):
        normalized_path = raw_path
    else:
        normalized_path = f"{raw_path}/v1" if raw_path else "/v1"

    return urlunsplit(
        (parsed.scheme, parsed.netloc, normalized_path, parsed.query, parsed.fragment)
    )


def create_ollama_provider(
    base_url: str | None = None,
    *,
    urls: list[str] | None = None,
    api_key: str | None = None,
    openai_client: AsyncOpenAI | None = None,
    http_client: Any | None = None,
    allow_private: bool = True,
) -> OllamaProvider:
    """Create a native pydantic_ai.providers.ollama.OllamaProvider with cluster and auth support.

    Args:
        base_url: Primary Ollama HTTP endpoint URL.
        urls: Sequence of Ollama cluster endpoint URLs for multi-node setups.
        api_key: Optional API key for authenticated gateways or Ollama Cloud.
        openai_client: Optional pre-configured AsyncOpenAI client instance.
        http_client: Optional custom HTTP client.
        allow_private: Whether private network/loopback endpoints are allowed.
    """
    raw_url: str | None = None
    if urls and len(urls) > 0:
        raw_url = urls[0]
    elif base_url:
        raw_url = base_url
    else:
        raw_url = os.environ.get("OLLAMA_BASE_URL")

    if not raw_url:
        raise ConfigurationError(
            "No Ollama server URLs configured. Run: devops config set ai.ollama_urls <url>",
            key="ai.ollama_urls",
        )

    normalized_url = normalize_ollama_base_url(raw_url, allow_private=allow_private)
    resolved_api_key = api_key or os.environ.get("OLLAMA_API_KEY")

    from pydantic_ai.providers.ollama import OllamaProvider

    return OllamaProvider(
        base_url=normalized_url,
        api_key=resolved_api_key,
        openai_client=openai_client,
        http_client=http_client,
    )


def create_ollama_model(
    model_name: str = "qwen2.5-coder",
    *,
    base_url: str | None = None,
    urls: list[str] | None = None,
    api_key: str | None = None,
    provider: Literal["ollama"] | Provider[AsyncOpenAI] | None = None,
    settings: ModelSettings | None = None,
    profile: ModelProfileSpec | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    reasoning_effort: str | None = None,
    timeout: float | None = None,
    openai_client: AsyncOpenAI | None = None,
    http_client: Any | None = None,
    **kwargs: Any,
) -> OllamaModel:
    """Factory creating and configuring a native Pydantic AI OllamaModel.

    Args:
        model_name: Target Ollama model identifier (e.g. 'qwen2.5-coder:14b', 'deepseek-r1:14b').
        base_url: Explicit base URL for the Ollama instance.
        urls: List of Ollama cluster URLs for multi-endpoint topologies.
        api_key: Optional API key for Ollama Cloud or authenticated reverse proxies.
        provider: Custom Provider instance or None to auto-create an OllamaProvider.
        settings: Existing native ModelSettings instance to augment.
        profile: Custom ModelProfileSpec for overriding model features.
        temperature: Model sampling temperature (0.0 - 2.0).
        max_tokens: Maximum output token budget.
        top_p: Nucleus sampling probability threshold.
        reasoning_effort: Reasoning effort mode ('low', 'medium', 'high') for thinking models.
        timeout: Network request timeout in seconds.
        openai_client: Optional custom AsyncOpenAI client.
        http_client: Optional custom HTTP client.
        **kwargs: Additional model settings forwarded to ModelSettings.
    """
    clean_model_name = model_name.removeprefix("ollama:").strip()

    resolved_provider: Literal["ollama"] | Provider[AsyncOpenAI]
    if provider is not None:
        resolved_provider = provider
    else:
        resolved_provider = create_ollama_provider(
            base_url=base_url,
            urls=urls,
            api_key=api_key,
            openai_client=openai_client,
            http_client=http_client,
        )

    explicit_settings = create_model_settings(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        timeout=timeout,
        **kwargs,
    )
    if reasoning_effort is not None:
        explicit_settings["reasoning_effort"] = reasoning_effort  # type: ignore[typeddict-unknown-key]
    model_settings = (
        merge_model_settings(settings, explicit_settings)
        if (settings or explicit_settings)
        else None
    )

    from pydantic_ai.models.ollama import OllamaModel

    return OllamaModel(
        clean_model_name,
        provider=resolved_provider,
        profile=profile,
        settings=model_settings,
    )


def __getattr__(name: str) -> Any:
    if name == "OllamaModel":
        from pydantic_ai.models.ollama import OllamaModel

        return OllamaModel
    if name == "OllamaProvider":
        from pydantic_ai.providers.ollama import OllamaProvider

        return OllamaProvider
    if name == "OpenAIChatModel":
        from pydantic_ai.models.openai import OpenAIChatModel

        return OpenAIChatModel
    if name == "Provider":
        from pydantic_ai.providers import Provider

        return Provider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ModelProfileSpec",
    "ModelSettings",
    "OllamaModel",
    "OllamaProvider",
    "OpenAIChatModel",
    "OpenAIJsonSchemaTransformer",
    "OpenAIModelProfile",
    "cohere_model_profile",
    "create_ollama_model",
    "create_ollama_provider",
    "deepseek_model_profile",
    "google_model_profile",
    "harmony_model_profile",
    "meta_model_profile",
    "mistral_model_profile",
    "normalize_ollama_base_url",
    "qwen_model_profile",
]
