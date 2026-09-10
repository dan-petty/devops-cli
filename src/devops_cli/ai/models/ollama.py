"""Native Pydantic AI Ollama model and provider integration."""

from __future__ import annotations

import ipaddress
import os
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from openai import AsyncOpenAI
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import ModelProfileSpec
from pydantic_ai.profiles.cohere import cohere_model_profile
from pydantic_ai.profiles.deepseek import deepseek_model_profile
from pydantic_ai.profiles.google import google_model_profile
from pydantic_ai.profiles.harmony import harmony_model_profile
from pydantic_ai.profiles.meta import meta_model_profile
from pydantic_ai.profiles.mistral import mistral_model_profile
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
from pydantic_ai.profiles.qwen import qwen_model_profile
from pydantic_ai.providers import Provider
from pydantic_ai.providers.ollama import OllamaProvider

from devops_cli.ai.settings import (
    ModelSettings,
    create_model_settings,
    merge_model_settings,
)
from devops_cli.exceptions import InvalidURLError, SSRFBlockedError

DEFAULT_OLLAMA_BASE_URL: str = "http://localhost:11434"


def _is_cloud_metadata_host(host: str) -> bool:
    clean = host.strip().lower().strip("[]").rstrip(".")
    if clean in ("169.254.169.254", "fd00:ec2::254", "metadata.google.internal", "metadata"):
        return True
    try:
        ip = ipaddress.ip_address(clean)
        return ip.is_link_local
    except ValueError:
        pass

    from devops_cli.core.validation import _resolve_host_ips

    resolved_ips = _resolve_host_ips(clean)
    return any(
        ip.is_link_local or str(ip) in ("169.254.169.254", "fd00:ec2::254") for ip in resolved_ips
    )


def normalize_ollama_base_url(url: str, *, allow_private: bool = True) -> str:
    """Normalize Ollama base URL ensuring a clean /v1 endpoint path without duplicate segments.

    Examples:
        - http://localhost:11434 -> http://localhost:11434/v1
        - http://localhost:11434/v1/ -> http://localhost:11434/v1
        - https://ollama.com -> https://ollama.com/v1
    """
    clean_url = url.strip()
    if not clean_url:
        clean_url = DEFAULT_OLLAMA_BASE_URL

    if "://" in clean_url:
        scheme = clean_url.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            raise InvalidURLError(
                clean_url,
                reason=f"Invalid Ollama URL scheme '{scheme}': must be http or https",
            )
    elif not clean_url.startswith(("http://", "https://")):
        clean_url = f"http://{clean_url}"

    parsed = urlsplit(clean_url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidURLError(
            clean_url,
            reason=f"Invalid Ollama URL scheme '{parsed.scheme}': must be http or https",
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


def is_ollama_cloud(base_url: str | None = None, model_name: str | None = None) -> bool:
    """Determine if a target Ollama endpoint or model name references Ollama Cloud.

    Ollama Cloud models ending in '-cloud' or hosted on 'ollama.com' do not yet enforce
    upstream JSON Schema grammar constraints at generation time.
    """
    if base_url:
        parsed = urlsplit(base_url.strip())
        hostname = (parsed.hostname or "").lower()
        if hostname == "ollama.com" or hostname.endswith(".ollama.com"):
            return True

    if model_name and model_name.strip().lower().endswith("-cloud"):
        return True

    return False


def get_recommended_output_mode(base_url: str | None = None, model_name: str | None = None) -> str:
    """Return recommended Pydantic AI output mode ('native' vs 'tool') for target model.

    Self-hosted Ollama (v0.5.0+) supports grammar-constrained JSON decoding ('native').
    Ollama Cloud endpoints/models recommend 'tool' output to avoid unconstrained output.
    """
    return "tool" if is_ollama_cloud(base_url=base_url, model_name=model_name) else "native"


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
        raw_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)

    normalized_url = normalize_ollama_base_url(raw_url, allow_private=allow_private)
    resolved_api_key = api_key or os.environ.get("OLLAMA_API_KEY")

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

    return OllamaModel(
        clean_model_name,
        provider=resolved_provider,
        profile=profile,
        settings=model_settings,
    )


__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
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
    "get_recommended_output_mode",
    "google_model_profile",
    "harmony_model_profile",
    "is_ollama_cloud",
    "meta_model_profile",
    "mistral_model_profile",
    "normalize_ollama_base_url",
    "qwen_model_profile",
]
