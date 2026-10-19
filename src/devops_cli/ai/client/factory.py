"""Client factory building LLMClient instances per task with egress and settings integration (#1001)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from devops_cli.ai.client.unified import LLMClient
    from devops_cli.config.settings import AIConfig, Settings

from devops_cli.ai.client import unified as _unified

_client_override: Any | None = None


def set_llm_client_override(override: Any | None) -> None:
    """Set or clear a model client override for tests (#1001, ADR 0007)."""
    global _client_override
    _client_override = override


def _handle_override(
    override: Any,
    task: str | None,
    config: AIConfig | None,
    settings: Settings | None,
    model: str | None,
    api_key: str | None,
    cache_enabled: bool | None,
    kwargs: dict[str, Any],
) -> LLMClient:
    """Dispatch to active client override or record factory invocation (#1001)."""
    if callable(override) and not hasattr(override, "chat"):
        res: Any = override(
            task=task,
            config=config,
            settings=settings,
            model=model,
            api_key=api_key,
            cache_enabled=cache_enabled,
            **kwargs,
        )
        return cast("LLMClient", res)
    if hasattr(override, "record_factory_call"):
        override.record_factory_call(
            task=task,
            config=config,
            settings=settings,
            model=model,
            api_key=api_key,
            cache_enabled=cache_enabled,
            **kwargs,
        )
    return cast("LLMClient", override)


def get_llm_client(
    task: str | None = None,
    *,
    config: AIConfig | None = None,
    settings: Settings | None = None,
    model: str | None = None,
    api_key: str | None = None,
    cache_enabled: bool | None = None,
    **kwargs: Any,
) -> LLMClient:
    """Build or retrieve a configured LLMClient instance based on task or configuration (#1001).

    Args:
        task: Optional task name (e.g. "chat", "analysis", "review", "research") used to look up task-specific AIConfig.
        config: Explicit AIConfig to use instead of looking up settings.ai.
        settings: Active application Settings. If None, loaded via load_settings().
        model: Optional model override.
        api_key: Optional explicit API key override. If None, resolved via get_ai_api_key(settings).
        cache_enabled: Optional boolean enabling or disabling response cache.
        **kwargs: Additional parameters passed through to LLMClient.

    Returns:
        Configured LLMClient instance.
    """
    if _client_override is not None:
        return _handle_override(
            _client_override, task, config, settings, model, api_key, cache_enabled, kwargs
        )
    active_settings: Settings | None = settings
    if config is not None:
        cfg = config
    else:
        if active_settings is None:
            from devops_cli.config.settings import load_settings

            active_settings = load_settings()
        cfg = active_settings.ai.for_task(task) if task else active_settings.ai

    if model:
        cfg = cfg.model_copy(update={"model": model})

    key = api_key
    if key is None:
        if active_settings is not None:
            from devops_cli.config.settings import get_ai_api_key

            key = get_ai_api_key(active_settings)
        elif getattr(cfg, "api_key", None):
            key = getattr(cfg, "api_key", None)

    client_kwargs: dict[str, Any] = dict(kwargs)
    if cache_enabled is not None:
        client_kwargs["cache_enabled"] = cache_enabled

    return _unified.LLMClient(config=cfg, api_key=key, **client_kwargs)


build_llm_client = get_llm_client
