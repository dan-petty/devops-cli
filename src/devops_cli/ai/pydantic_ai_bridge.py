"""PydanticAI Standardized Agent Framework adapter and bridge."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import CachePoint
from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.agents.pydantic_agent import BaseCapability, PydanticAgent
from devops_cli.ai.client import LLMClient
from devops_cli.ai.concurrency import AnyConcurrencyLimit, limit_model_concurrency
from devops_cli.ai.governance import TokenBucketGovernance, TokenBudgetConfig
from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.config.constants import (
    CONST_AI_CASCADE_PROVIDERS,
    CONST_AI_DEFAULT_CACHE_MARKER_KIND,
    CONST_AI_PROMPT_CACHE_TTL_5M,
    CONST_AI_PROMPT_CACHE_TTLS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_AGENT_PERSONA,
    DEFAULT_AI_CONTEXT_TOKEN_BUDGET,
    DEFAULT_AI_END_STRATEGY,
    DEFAULT_AI_GATEWAY_URL,
    DEFAULT_CURRENT_PATH,
    DEFAULT_PORTKEY_GATEWAY_URL,
)
from devops_cli.config.settings import Settings, get_ai_api_key, load_settings

logger = logging.getLogger(__name__)


class DevOpsAgentContext(BaseModel):
    """Execution context and dependency container passed to PydanticAI agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    settings: Settings | None = None
    target_repo: str = str(DEFAULT_CURRENT_PATH)
    active_persona: str = DEFAULT_AI_AGENT_PERSONA
    context_tokens_budget: int = DEFAULT_AI_CONTEXT_TOKEN_BUDGET
    capabilities: list[BaseCapability] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)
    client: LLMClient | None = None
    governance: TokenBucketGovernance | None = None
    budget: TokenBudgetConfig | None = None


def is_pydantic_ai_available() -> bool:
    """Check if pydantic_ai library is installed and importable."""
    try:
        import pydantic_ai  # noqa: F401

        return True
    except ImportError:
        return False


def _extract_provider_and_target(model_str: str) -> tuple[str, str]:
    """Extract provider prefix and target model name."""
    if ":" in model_str:
        prov, target = model_str.split(":", 1)
        return prov, target
    return model_str, "devops-chat"


def _resolve_remote_provider_endpoint(
    model_str: str, active_settings: Settings
) -> tuple[str, str | None]:
    """Resolve target model string and base URL for remote gateway or inference providers."""
    prov, target = _extract_provider_and_target(model_str)
    ai_base = getattr(active_settings.ai, "api_base_url", None)
    if prov == "litellm":
        return target, ai_base or DEFAULT_AI_GATEWAY_URL
    if prov == "portkey":
        return target, DEFAULT_PORTKEY_GATEWAY_URL
    if prov == "lightllm":
        return target, "http://localhost:8000/v1"
    return model_str, ai_base


def _resolve_remote_inferred_model(model_str: str, active_settings: Settings) -> Any:
    """Infer model instance using configured remote provider endpoint."""
    from pydantic_ai.models import infer_model

    from devops_cli.ai.providers import create_pydantic_ai_provider

    target_name, base_url = _resolve_remote_provider_endpoint(model_str, active_settings)
    api_key = get_ai_api_key(active_settings) or getattr(active_settings.ai, "api_key", None)

    def _provider_factory(prov_name: str) -> Any:
        return create_pydantic_ai_provider(prov_name, base_url=base_url, api_key=api_key)

    return infer_model(target_name, provider_factory=_provider_factory)


def _resolve_ollama_model(model_str: str, active_settings: Settings) -> Any:
    """Resolve Ollama model instance with configured cluster URLs and parameters."""
    from devops_cli.ai.models.ollama import create_ollama_model

    ai_cfg = getattr(active_settings, "ai", None)
    urls = ai_cfg.get_ollama_urls if ai_cfg and hasattr(ai_cfg, "get_ollama_urls") else []
    return create_ollama_model(
        model_str,
        urls=urls,
        api_key=getattr(ai_cfg, "api_key", None) if ai_cfg else None,
        temperature=getattr(ai_cfg, "temperature", None) if ai_cfg else None,
        max_tokens=getattr(ai_cfg, "max_tokens", None) if ai_cfg else None,
        reasoning_effort=getattr(ai_cfg, "reasoning_effort", None) if ai_cfg else None,
    )


def _is_testing_mode_active() -> bool:
    """Check if model network requests are disabled for testing."""
    import devops_cli.ai.agents.agent as agent_module
    import devops_cli.ai.agents.testing as testing_module

    return not getattr(testing_module, "ALLOW_MODEL_REQUESTS", True) or not getattr(
        agent_module, "ALLOW_MODEL_REQUESTS", True
    )


def _resolve_string_model(model_str: str, active_settings: Settings) -> Any:
    """Resolve string model identifier into Ollama or remote inferred model."""
    provider = getattr(active_settings.ai, "provider", "ollama")
    if model_str.startswith("ollama:") or provider == "ollama":
        return _resolve_ollama_model(model_str, active_settings)
    try:
        return _resolve_remote_inferred_model(model_str, active_settings)
    except Exception:
        return model_str


def _wrap_model_concurrency(model_obj: Any, model_concurrency: AnyConcurrencyLimit) -> Any:
    """Optionally wrap model instance with concurrency limiting."""
    return limit_model_concurrency(model_obj, model_concurrency) if model_concurrency else model_obj


def resolve_pydantic_ai_model(
    model: str | Any | None = None,
    settings: Settings | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
) -> Any:
    """Resolve and configure native PydanticAI Model instance.

    Supports OllamaProvider with dynamic cluster URLs, TestModel for offline testing,
    fallback cascade models, and automatic model inference across providers.
    """
    if model is None:
        return None

    if isinstance(model, (list, tuple)) or model == "cascade":
        seq = model if isinstance(model, (list, tuple)) else CONST_AI_CASCADE_PROVIDERS
        return build_fallback_cascade_model(
            seq, settings=settings, model_concurrency=model_concurrency
        )

    if _is_testing_mode_active() or model == "test":
        from pydantic_ai.models.test import TestModel

        return _wrap_model_concurrency(TestModel(), model_concurrency)

    if not isinstance(model, str):
        return _wrap_model_concurrency(model, model_concurrency)

    active_settings = settings or load_settings()
    resolved = _resolve_string_model(model.strip(), active_settings)
    return _wrap_model_concurrency(resolved, model_concurrency)


def _resolve_result_model(output_type: Any, result_type: Any, output_mode: str | None) -> Any:
    """Resolve structured output result model."""
    res_model = output_type if output_type is not None else (result_type or ReviewResult)
    if output_mode is not None:
        from devops_cli.ai.output import build_output_spec

        return build_output_spec(res_model, mode=output_mode)  # type: ignore[arg-type]
    return res_model


def _populate_agent_optional_kwargs(
    kwargs: dict[str, Any],
    sig_params: Mapping[str, inspect.Parameter],
    active_caps: list[BaseCapability],
    active_tools: list[Any],
    active_toolsets: list[Any],
    max_concurrency: AnyConcurrencyLimit,
) -> None:
    """Populate optional capability, tool, and concurrency kwargs based on Agent signature."""
    if "capabilities" in sig_params and active_caps:
        kwargs["capabilities"] = active_caps
    if "tools" in sig_params and active_tools:
        kwargs["tools"] = active_tools
    if "toolsets" in sig_params and active_toolsets:
        kwargs["toolsets"] = active_toolsets
    if "max_concurrency" in sig_params and max_concurrency is not None:
        kwargs["max_concurrency"] = max_concurrency


def _fallback_pydantic_agent(
    client: LLMClient | None,
    settings: Settings,
    target_model: Any,
    system_prompt: str,
    active_tools: list[Any],
    active_toolsets: list[Any],
    active_caps: list[BaseCapability],
    res_model: Any,
    max_concurrency: AnyConcurrencyLimit,
) -> Any:
    """Construct fallback PydanticAgent when native PydanticAI Agent fails to initialize."""
    active_client = client or LLMClient(settings.ai, api_key=get_ai_api_key(settings))
    name_suffix = target_model if target_model else "default"
    return PydanticAgent(
        client=active_client,
        name=f"agent-{name_suffix}",
        system_prompt=system_prompt,
        tools=active_tools,
        toolsets=active_toolsets,
        capabilities=active_caps,
        output_type=res_model,
        max_concurrency=max_concurrency,
    )


def create_pydantic_ai_agent(
    model_name: str | Any | None = None,
    system_prompt: str = "",
    output_type: Any = None,
    result_type: Any = None,
    output_mode: str | None = None,
    deps_type: type[Any] = DevOpsAgentContext,
    capabilities: Sequence[BaseCapability] | None = None,
    tools: Sequence[Any] | None = None,
    client: LLMClient | None = None,
    end_strategy: str = DEFAULT_AI_END_STRATEGY,
    retries: int | None = None,
    max_concurrency: AnyConcurrencyLimit = None,
    model_concurrency: AnyConcurrencyLimit = None,
    toolsets: Sequence[Any] | None = None,
) -> Any:
    """Instantiate a standardized PydanticAI Agent with typed dependencies, capabilities, outputs, and concurrency limits."""
    settings: Settings = load_settings()
    target_model = model_name or getattr(getattr(settings, "ai", None), "model", None)
    res_model = _resolve_result_model(output_type, result_type, output_mode)
    active_caps = list(capabilities or [])
    active_tools = list(tools or [])
    active_toolsets = list(toolsets or [])

    try:
        from pydantic_ai import Agent

        resolved_model = resolve_pydantic_ai_model(
            target_model, settings=settings, model_concurrency=model_concurrency
        )
        kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "deps_type": deps_type,
            "end_strategy": end_strategy,
        }
        if retries is not None:
            kwargs["retries"] = retries
        sig = inspect.signature(Agent.__init__)
        res_key = "output_type" if "output_type" in sig.parameters else "result_type"
        kwargs[res_key] = res_model
        _populate_agent_optional_kwargs(
            kwargs, sig.parameters, active_caps, active_tools, active_toolsets, max_concurrency
        )
        if resolved_model is not None:
            kwargs["model"] = resolved_model
        return Agent(**kwargs)
    except Exception as exc:
        logger.debug("Native PydanticAI agent unavailable, creating PydanticAgent: %s", exc)
        return _fallback_pydantic_agent(
            client=client,
            settings=settings,
            target_model=target_model,
            system_prompt=system_prompt,
            active_tools=active_tools,
            active_toolsets=active_toolsets,
            active_caps=active_caps,
            res_model=res_model,
            max_concurrency=max_concurrency,
        )


def get_persona_pydantic_agent(
    persona: Persona | str = Persona.DEVSECOPS,
    settings: Settings | None = None,
    capabilities: Sequence[BaseCapability] | None = None,
    tools: Sequence[Any] | None = None,
    model_name: str | Any | None = None,
    max_concurrency: AnyConcurrencyLimit = None,
    model_concurrency: AnyConcurrencyLimit = None,
) -> Any:
    """Build a persona-specialized PydanticAI agent instance with optional concurrency limiting."""
    p_enum = Persona(persona) if isinstance(persona, str) else persona
    p_def = PERSONAS[p_enum]
    active_settings = settings or load_settings()
    target_model = model_name or active_settings.ai.model

    return create_pydantic_ai_agent(
        model_name=target_model,
        system_prompt=p_def.system_prompt,
        output_type=ReviewResult,
        deps_type=DevOpsAgentContext,
        capabilities=capabilities,
        tools=tools,
        max_concurrency=max_concurrency,
        model_concurrency=model_concurrency,
    )


def inject_prompt_cache_points(
    content: str | Sequence[Any],
    ttl: str = CONST_AI_PROMPT_CACHE_TTL_5M,
) -> list[Any]:
    """Inject CachePoint markers into prompt content for Anthropic/OpenAI prompt caching."""
    target_ttl: Any = ttl if ttl in CONST_AI_PROMPT_CACHE_TTLS else CONST_AI_PROMPT_CACHE_TTL_5M
    if isinstance(content, str):
        return [content, CachePoint(ttl=target_ttl)]

    parts = list(content)
    has_cache_point = any(
        getattr(part, "kind", None) == CONST_AI_DEFAULT_CACHE_MARKER_KIND for part in parts
    )
    if not has_cache_point:
        parts.append(CachePoint(ttl=target_ttl))
    return parts


def create_cached_user_prompt(
    prompt: str,
    preamble: str = "",
    ttl: str = CONST_AI_PROMPT_CACHE_TTL_5M,
) -> UserPromptPart:
    """Construct a UserPromptPart with embedded prompt caching boundaries."""
    target_ttl: Any = ttl if ttl in CONST_AI_PROMPT_CACHE_TTLS else CONST_AI_PROMPT_CACHE_TTL_5M
    if preamble:
        return UserPromptPart(content=[preamble, CachePoint(ttl=target_ttl), prompt])
    return UserPromptPart(content=[prompt, CachePoint(ttl=target_ttl)])


def build_fallback_cascade_model(
    models_or_providers: Sequence[str | Any] = CONST_AI_CASCADE_PROVIDERS,
    settings: Settings | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
) -> Any:
    """Build a FallbackModel cascading across multiple providers or models.

    Tries each resolved model in sequence upon errors (e.g. LiteLLM -> Portkey -> LightLLM -> Ollama).
    """
    active_settings = settings or load_settings()
    resolved_models: list[Any] = []
    for item in models_or_providers:
        m = resolve_pydantic_ai_model(item, settings=active_settings)
        if m is not None:
            resolved_models.append(m)

    if not resolved_models:
        return None
    if len(resolved_models) == 1:
        first = resolved_models[0]
        return limit_model_concurrency(first, model_concurrency) if model_concurrency else first

    fallback_model = FallbackModel(resolved_models[0], *resolved_models[1:])
    return (
        limit_model_concurrency(fallback_model, model_concurrency)
        if model_concurrency
        else fallback_model
    )


def _resolve_workflow_usage_limits(
    usage_limits: UsageLimits | TokenBudgetConfig | None,
    deps: DevOpsAgentContext | None,
) -> UsageLimits | None:
    """Resolve UsageLimits from explicit argument or dependency container."""
    if isinstance(usage_limits, TokenBudgetConfig):
        return usage_limits.to_usage_limits()
    if isinstance(usage_limits, UsageLimits):
        return usage_limits
    if deps is not None and deps.budget is not None:
        return deps.budget.to_usage_limits()
    return None


async def execute_structured_workflow(
    agent: Any,
    prompt: str | Any,
    deps: DevOpsAgentContext | None = None,
    usage_limits: UsageLimits | TokenBudgetConfig | None = None,
    model_settings: Any = None,
) -> Any:
    """Execute asynchronous structured agent workflow with dependency injection and token governance."""
    active_limits = _resolve_workflow_usage_limits(usage_limits, deps)
    if deps is not None and deps.governance is not None:
        pacing_delay = deps.governance.acquire_token_permit(estimated_tokens=50)
        if pacing_delay > 0:
            await asyncio.sleep(pacing_delay)

    result = await agent.run(
        prompt,
        deps=deps,
        usage_limits=active_limits,
        model_settings=model_settings,
    )

    if deps is not None and deps.governance is not None and hasattr(result, "usage"):
        deps.governance.record_run_usage(result.usage)

    return result


def execute_structured_workflow_sync(
    agent: Any,
    prompt: str | Any,
    deps: DevOpsAgentContext | None = None,
    usage_limits: UsageLimits | TokenBudgetConfig | None = None,
    model_settings: Any = None,
) -> Any:
    """Execute synchronous structured agent workflow with dependency injection and token governance."""
    active_limits = _resolve_workflow_usage_limits(usage_limits, deps)
    if deps is not None and deps.governance is not None:
        pacing_delay = deps.governance.acquire_token_permit(estimated_tokens=50)
        if pacing_delay > 0:
            time.sleep(pacing_delay)

    result = agent.run_sync(
        prompt,
        deps=deps,
        usage_limits=active_limits,
        model_settings=model_settings,
    )

    if deps is not None and deps.governance is not None and hasattr(result, "usage"):
        deps.governance.record_run_usage(result.usage)

    return result


__all__ = [
    "DevOpsAgentContext",
    "build_fallback_cascade_model",
    "create_cached_user_prompt",
    "create_pydantic_ai_agent",
    "execute_structured_workflow",
    "execute_structured_workflow_sync",
    "get_persona_pydantic_agent",
    "inject_prompt_cache_points",
    "is_pydantic_ai_available",
    "resolve_pydantic_ai_model",
]
