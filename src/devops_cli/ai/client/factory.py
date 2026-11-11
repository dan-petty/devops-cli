"""Client factory building LLMClient instances per task with egress and settings integration (#1001)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from contextvars import ContextVar
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import httpx2

    from devops_cli.ai.client.unified import LLMClient
    from devops_cli.config.settings import AIConfig, Settings

from devops_cli.ai.client import unified as _unified

_client_override: Any | None = None


def set_llm_client_override(override: Any | None) -> None:
    """Set or clear a model client override for tests (#1001, ADR 0007)."""
    global _client_override
    _client_override = override


def reset_llm_client_override() -> None:
    """Clear any active model client override."""
    global _client_override
    _client_override = None


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


def _resolve_api_key(api_key: str | None, settings: Settings | None, cfg: AIConfig) -> str | None:
    """Resolve API key from explicit parameter, active settings, or config."""
    if api_key is not None:
        return api_key
    if settings is not None:
        from devops_cli.config.settings import get_ai_api_key

        return get_ai_api_key(settings)
    return getattr(cfg, "api_key", None)


def get_llm_client(
    task: str | None = None,
    *,
    config: AIConfig | None = None,
    settings: Settings | None = None,
    model: str | None = None,
    api_key: str | None = None,
    cache_enabled: bool | None = None,
    transport: httpx2.BaseTransport | None = None,
    http_client: httpx2.Client | None = None,
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
        transport: Optional HTTP transport override.
        http_client: Optional HTTP client override.
        **kwargs: Additional parameters passed through to LLMClient.

    Returns:
        Configured LLMClient instance.
    """
    if transport is not None:
        kwargs["transport"] = transport
    if http_client is not None:
        kwargs["http_client"] = http_client

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

    key = _resolve_api_key(api_key, active_settings, cfg)

    client_kwargs: dict[str, Any] = dict(kwargs)
    if cache_enabled is not None:
        client_kwargs["cache_enabled"] = cache_enabled

    return _unified.LLMClient(config=cfg, api_key=key, **client_kwargs)


build_llm_client = get_llm_client


def get_task_model(task: str, *, settings: Settings | None = None) -> Any:
    """The pydantic-ai model that serves `task` (#2398): the client override when it is a
    pydantic-ai `Model` (#1001, ADR 0007), else the task's model resolved with the task's own
    configuration, so its provider and gateway URL are the ones `get_llm_client(task)` uses."""
    from pydantic_ai.models import Model

    if isinstance(_client_override, Model):
        return _client_override

    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
    from devops_cli.config.settings import load_settings

    active_settings = settings or load_settings()
    task_config = active_settings.ai.for_task(task)
    task_settings = active_settings.model_copy(update={"ai": task_config})
    return resolve_pydantic_ai_model(task_config.model, settings=task_settings)


def get_tier_model(tier: str, *, settings: Settings | None = None) -> Any:
    """The pydantic-ai model that serves one tier of the implement ladder (#3060).

    A gateway group, local or hosted, is sent to the configured gateway whatever `ai.provider`
    is, so a local tier never reaches a hosted provider and a hosted group is reached only when
    the ladder names it. An `ollama:<tag>` tier is the local model of that tag. The client
    override of a test wins, as it does in `get_task_model`.
    """
    from pydantic_ai.models import Model

    if isinstance(_client_override, Model):
        return _client_override

    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
    from devops_cli.config.settings import load_settings

    active_settings = settings or load_settings()
    if tier.strip().startswith("ollama:"):
        return resolve_pydantic_ai_model(tier.strip(), settings=active_settings)
    gateway = active_settings.ai.gateway_provider
    return resolve_pydantic_ai_model(f"{gateway}:{tier.strip()}", settings=active_settings)


def _spend_capability(request_type: str, stage: str | None) -> Any:
    """The pydantic-ai hooks that write one spend record for each model request. The before hook
    keeps the monotonic start time of the request in a context variable, and the after hook
    writes the seconds since then (#4504). A request that raises runs no after hook, so it writes
    no record."""
    from pydantic_ai import RunContext
    from pydantic_ai.capabilities import Hooks
    from pydantic_ai.messages import ModelResponse
    from pydantic_ai.models import ModelRequestContext

    request_started: ContextVar[float | None] = ContextVar("request_started", default=None)

    async def _start_hook(
        ctx: RunContext[Any], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        request_started.set(monotonic())
        return request_context

    def _record(
        request_context: ModelRequestContext, response: ModelResponse, duration_seconds: float
    ) -> None:
        from urllib.parse import urlsplit

        from devops_cli.ai.spend.ledger import model_answer_labels, track_request_spend
        from devops_cli.config.constants import CONST_AI_GATEWAY_PROVIDER
        from devops_cli.telemetry.instruments import AI_MODEL_ANSWERS_TOTAL, emit

        m = request_context.model
        asked = str(getattr(m, "model_name", getattr(m, "model_id", "unknown")))
        served_by = getattr(m, "served_by", None)
        answered = response.model_name
        if answered:
            emit(AI_MODEL_ANSWERS_TOTAL, 1, model_answer_labels(asked, answered))
        track_request_spend(
            provider=CONST_AI_GATEWAY_PROVIDER
            if served_by
            else str(getattr(m, "system", "") or getattr(m, "provider", "") or "unknown"),
            model=asked,
            server=urlsplit(served_by).netloc if served_by else "unknown",
            served_model=answered,
            prompt_tokens=getattr(response.usage, "input_tokens", 0),
            completion_tokens=getattr(response.usage, "output_tokens", 0),
            reasoning_tokens=getattr(response.usage, "output_reasoning_tokens", 0),
            cache_read_tokens=getattr(response.usage, "cache_read_tokens", 0),
            request_type=request_type,
            duration_seconds=duration_seconds,
            stage=stage,
        )

    async def _spend_hook(
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        started = request_started.get()
        request_started.set(None)
        duration = 0.0 if started is None else monotonic() - started
        await asyncio.to_thread(_record, request_context, response, duration)
        return response

    return Hooks(before_model_request=_start_hook, after_model_request=_spend_hook)


def build_agent(
    model: Any = None,
    *,
    task: str | None = None,
    output_type: Any = str,
    instructions: str | Sequence[str] | None = None,
    system_prompt: str | Sequence[str] = (),
    tools: Sequence[Any] = (),
    toolsets: Sequence[Any] | None = None,
    retries: int | dict[str, int] | None = None,
    capabilities: Sequence[Any] | None = None,
    settings: Settings | None = None,
    request_type: str = "chat",
    stage: str | None = None,
    name: str | None = None,
    **kwargs: Any,
) -> Any:
    """Build a configured pydantic-ai Agent with per-request spend tracking (#2489). Each model
    request writes one spend record, with the seconds of the request (#4504) and the prompt tokens
    that the provider read from its cache, and a reply that names its model adds one count to
    `devops_cli_ai_model_answers_total`, as the run of an implement step does (#4475)."""
    from pydantic_ai import Agent
    from pydantic_ai.models import Model

    if model is None:
        model = get_task_model(task or "chat", settings=settings)
    elif isinstance(model, str):
        if isinstance(_client_override, Model):
            model = _client_override
        else:
            from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

            model = resolve_pydantic_ai_model(model, settings=settings)

    all_capabilities = [_spend_capability(request_type, stage), *(capabilities or ())]

    agent_kwargs: dict[str, Any] = {
        "output_type": output_type,
        "instructions": instructions,
        "tools": tools,
        "capabilities": all_capabilities,
        **kwargs,
    }
    if name is not None:
        agent_kwargs["name"] = name
    if system_prompt:
        agent_kwargs["system_prompt"] = system_prompt
    if toolsets is not None:
        agent_kwargs["toolsets"] = toolsets
    if retries is not None:
        agent_kwargs["retries"] = retries

    return Agent(model, **agent_kwargs)
