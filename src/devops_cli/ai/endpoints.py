"""AI endpoint resolver ensuring callers use only configured URLs (#1165)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
    CONST_URL_ANTHROPIC_API_BASE,
    CONST_URL_GITHUB_COPILOT_API_BASE,
)
from devops_cli.exceptions import ConfigurationError

if TYPE_CHECKING:
    from devops_cli.config.settings import AIConfig, Settings


@dataclass(frozen=True)
class ResolvedAIEndpoint:
    """Resolved endpoint URLs and model aliases for an AI provider."""

    provider: str
    urls: tuple[str, ...]
    models: tuple[str, ...] = ()

    @property
    def primary_url(self) -> str:
        """Return the primary endpoint URL."""
        if not self.urls:
            raise ConfigurationError("No endpoint URL available.", key="ai.provider")
        return self.urls[0]


def _resolve_gateway_endpoint(cfg: Any, settings: Settings | None) -> ResolvedAIEndpoint:
    gw_url = getattr(cfg, "gateway_url", None)
    if not gw_url and settings is not None:
        gw_url = getattr(settings.ai, "gateway_url", None)
    if not gw_url:
        gw_url = getattr(cfg, "api_base_url", None)
    if not gw_url:
        raise ConfigurationError(
            "No AI gateway URL configured for provider 'gateway'. "
            "Run: devops config set ai.gateway_url <url>",
            key="ai.gateway_url",
        )
    return ResolvedAIEndpoint(
        provider="gateway",
        urls=(str(gw_url).rstrip("/"),),
        models=CONST_AI_GATEWAY_VIRTUAL_MODELS,
    )


def _resolve_ollama_endpoint(cfg: Any) -> ResolvedAIEndpoint:
    urls = getattr(cfg, "ollama_urls", None)
    if not urls and hasattr(cfg, "get_ollama_urls"):
        urls = cfg.get_ollama_urls
    cleaned = [str(u).strip().rstrip("/") for u in (urls or []) if str(u).strip()]
    if not cleaned:
        raise ConfigurationError(
            "No Ollama server URLs configured for provider 'ollama'. "
            "Run: devops config set ai.ollama_urls <url>",
            key="ai.ollama_urls",
        )
    model = getattr(cfg, "model", "")
    models = (model,) if model else ()
    return ResolvedAIEndpoint(
        provider="ollama",
        urls=tuple(cleaned),
        models=models,
    )


def _resolve_cloud_or_custom_endpoint(provider: str, cfg: Any) -> ResolvedAIEndpoint:
    model = getattr(cfg, "model", "")
    models = (model,) if model else ()
    if provider in ("claude", "anthropic"):
        base_url = getattr(cfg, "api_base_url", None) or CONST_URL_ANTHROPIC_API_BASE
        return ResolvedAIEndpoint(
            provider="claude", urls=(str(base_url).rstrip("/"),), models=models
        )
    if provider in ("copilot", "github_copilot"):
        base_url = getattr(cfg, "api_base_url", None) or CONST_URL_GITHUB_COPILOT_API_BASE
        return ResolvedAIEndpoint(
            provider="copilot", urls=(str(base_url).rstrip("/"),), models=models
        )
    if provider == "openai":
        import openai

        base_url = getattr(cfg, "api_base_url", None) or str(
            openai.OpenAI(api_key="none").base_url
        ).rstrip("/")
        return ResolvedAIEndpoint(
            provider="openai", urls=(str(base_url).rstrip("/"),), models=models
        )

    base_url = getattr(cfg, "api_base_url", None)
    if base_url:
        return ResolvedAIEndpoint(
            provider=provider, urls=(str(base_url).rstrip("/"),), models=models
        )

    raise ConfigurationError(
        f"No endpoint configured for provider '{provider}'.",
        key="ai.api_base_url",
    )


def resolve_ai_endpoint(
    config: AIConfig | None = None,
    *,
    task: str | None = None,
    settings: Settings | None = None,
) -> ResolvedAIEndpoint:
    """Resolve active endpoint URLs and model aliases from configuration.

    Raises ConfigurationError naming the missing setting when no URL is configured.
    Never falls back to an unconfigured localhost default.
    """
    if config is None:
        if settings is None:
            from devops_cli.config.settings import load_settings

            settings = load_settings()
        cfg = settings.ai.for_task(task) if task else settings.ai
    else:
        cfg = config

    provider = (getattr(cfg, "provider", None) or "ollama").lower()
    if provider in (CONST_AI_GATEWAY_PROVIDER, "gateway"):
        return _resolve_gateway_endpoint(cfg, settings)
    if provider == "ollama":
        return _resolve_ollama_endpoint(cfg)
    return _resolve_cloud_or_custom_endpoint(provider, cfg)
