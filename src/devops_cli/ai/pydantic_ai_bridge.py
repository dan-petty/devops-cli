"""PydanticAI Standardized Agent Framework adapter and bridge."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from pydantic_ai.concurrency import AnyConcurrencyLimit
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.concurrency import limit_model_concurrency
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.settings import ModelSettings

from devops_cli.config.constants import (
    CONST_AI_CASCADE_PROVIDERS,
    CONST_AI_CLAUDE_GROUP_MAX_OUTPUT_TOKENS,
    CONST_AI_GATEWAY_DEFAULT_ROUTE,
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_URL_SETTINGS,
    CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
    CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    CONST_AI_JEV_MODEL,
    CONST_AI_JEV_MODEL_TARGETS,
    CONST_AI_JEV_SYSTEM_ONE_PREFIXES,
    CONST_AI_PYDANTIC_MODEL_PREFIXES,
    CONST_URL_GITHUB_COPILOT_API_BASE,
    CONST_URL_TYPESAFE_API_BASE,
)
from devops_cli.config.settings import (
    AIConfig,
    Settings,
    get_ai_api_key,
    is_decision_model_name,
    load_settings,
)
from devops_cli.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_CLAUDE_GROUP_NAME_PREFIX = "openai-chat:claude-"


def _gateway_prefix(model_str: str) -> str | None:
    """The gateway (`litellm` or `portkey`) a model name's prefix names, or None."""
    prefix, sep, _ = model_str.partition(":")
    return prefix if sep and prefix in CONST_AI_GATEWAY_URL_SETTINGS else None


def _model_prefix_and_target(model_str: str, ai_cfg: AIConfig) -> tuple[str, str]:
    """The pydantic-ai prefix a remote model is inferred with, and the name it is sent under.

    A gateway prefix (`litellm:`, `portkey:`) is kept. Under provider `gateway` every other
    name is a route of `ai.gateway_provider`'s gateway, sent whole as `LLMClient` sends it,
    even one whose text before its first colon names a provider (`mistral:7b` is an Ollama
    tag). Otherwise a name prefixed with a provider's name keeps that prefix, and any other
    name, as `devops-review` or `qwen3.8:27b`, takes the prefix `ai.provider` maps to.
    """
    from devops_cli.ai.providers import is_pydantic_ai_provider

    prefix, sep, target = model_str.partition(":")
    if sep and prefix in CONST_AI_GATEWAY_URL_SETTINGS:
        return prefix, target
    if ai_cfg.provider == CONST_AI_GATEWAY_PROVIDER:
        return ai_cfg.gateway_provider, model_str
    if sep and is_pydantic_ai_provider(prefix):
        return prefix, target
    if model_str.startswith(CONST_AI_JEV_MODEL_TARGETS) and ai_cfg.provider == "ollama":
        return ai_cfg.gateway_provider, model_str
    return CONST_AI_PYDANTIC_MODEL_PREFIXES.get(ai_cfg.provider, ""), model_str


def _resolve_remote_provider_endpoint(
    model_str: str, active_settings: Settings
) -> tuple[str, str | None]:
    """The name pydantic-ai infers a remote model from, and its base URL.

    A gateway's model is inferred as an OpenAI chat model sent to that gateway's URL; any
    other is sent to `ai.api_base_url`, or to Copilot's API for provider `copilot` when that
    is unset.
    """
    ai_cfg = active_settings.ai
    prefix, target = _model_prefix_and_target(model_str, ai_cfg)
    if setting := CONST_AI_GATEWAY_URL_SETTINGS.get(prefix):
        gateway_url = getattr(ai_cfg, setting)
        if not gateway_url:
            raise ConfigurationError(
                f"No AI gateway URL configured. Run: devops config set ai.{setting} <url>",
                key=f"ai.{setting}",
            )
        return f"openai-chat:{target}", gateway_url
    copilot_base = CONST_URL_GITHUB_COPILOT_API_BASE if ai_cfg.provider == "copilot" else None
    typesafe_base = (
        CONST_URL_TYPESAFE_API_BASE if prefix in CONST_AI_JEV_SYSTEM_ONE_PREFIXES else None
    )
    name = f"{prefix}:{target}" if prefix else target
    return name, ai_cfg.api_base_url or copilot_base or typesafe_base


def _claude_group_model(name: str, provider_factory: Any) -> Any:
    """The chat model of a Claude group on a gateway, with the profile that forbids a forced tool
    choice. A Claude model answers 400 to `tool_choice` `required`, which an agent with a tool
    output sends, and a gateway fallback then hides the 400 (#4205). With the profile, the agent
    sends `auto` and offers the same tools.

    The request sets `max_tokens`: a request that sets none gets the Anthropic default of 4096
    tokens, which cuts the reply of a stage plan before it holds a part (#4220).

    The request sets `parallel_tool_calls` false. The gateway maps it to the Anthropic setting
    `disable_parallel_tool_use`, so the model makes one tool call in a reply and the gateway
    joins no arguments of several calls into one JSON text that does not parse (#4228)."""
    from pydantic_ai.models.openai import OpenAIChatModel

    provider_name, _, target = name.partition(":")
    return OpenAIChatModel(
        target,
        provider=provider_factory(provider_name),
        profile={"supports_forced_tool_choice": False},
        settings=ModelSettings(
            max_tokens=CONST_AI_CLAUDE_GROUP_MAX_OUTPUT_TOKENS, parallel_tool_calls=False
        ),
    )


def _is_jev_decision_name(name: str) -> bool:
    """Whether the prefixed `name` names a TypeSafe Jev or System One decision model."""
    return ":" in name and is_decision_model_name(name)


def _jev_decision_model(name: str, provider_factory: Any) -> Any:
    """The System One decision model for TypeSafe Jev (`typesafe/jev-1.14`), with its profile."""
    from pydantic_ai.models.system_one import SystemOneModel
    from pydantic_ai.profiles.typesafe import typesafe_model_profile

    _, _, target = name.partition(":")
    return SystemOneModel(
        target,
        provider=provider_factory("system-one"),
        profile=typesafe_model_profile(target),
    )


def _resolve_remote_inferred_model(model_str: str, active_settings: Settings) -> Any:
    """Infer a remote model that is sent to the endpoint its settings name.

    The provider's client dials at the configured level, and the connect checks each address:
    a request to an address that the level refuses raises SSRFBlockedError. Raises
    ConfigurationError naming the endpoint's setting when it has no URL, and naming
    `ai.provider` and `ai.model` when pydantic-ai cannot infer the model, rather than leaving
    pydantic-ai to send the prompts to the vendor's own endpoint.
    """
    from pydantic_ai.models import infer_model

    from devops_cli.ai.providers import create_pydantic_ai_provider

    name, base_url = _resolve_remote_provider_endpoint(model_str, active_settings)
    api_key = get_ai_api_key(active_settings)
    allow_private = active_settings.ai.allow_private_network
    to_gateway = bool(
        active_settings.ai.provider == CONST_AI_GATEWAY_PROVIDER or _gateway_prefix(model_str)
    )

    def _provider_factory(prov_name: str) -> Any:
        return create_pydantic_ai_provider(
            prov_name,
            base_url=base_url,
            api_key=api_key,
            allow_private_network=allow_private,
            gateway_caller=to_gateway,
        )

    try:
        if _is_jev_decision_name(name):
            model_obj = _jev_decision_model(name, _provider_factory)
        elif to_gateway and name.startswith(_CLAUDE_GROUP_NAME_PREFIX):
            model_obj = _claude_group_model(name, _provider_factory)
        else:
            model_obj = infer_model(name, provider_factory=_provider_factory)
        if to_gateway:
            setattr(model_obj, "served_by", base_url)
        return model_obj
    except (UserError, ValueError, ImportError) as exc:
        # UserError: pydantic-ai knows no such model or has no key for it. ValueError: a name
        # left unprefixed, under a provider that maps to none, reads its tag's base as one.
        # ImportError: the prefix names a provider whose optional package is not installed.
        prefix = name.partition(":")[0] if ":" in name else "<none>"
        logger.debug("pydantic-ai cannot infer a model prefixed %r: %s", prefix, type(exc).__name__)
        raise ConfigurationError(
            f"ai.model {model_str!r} cannot be resolved for ai.provider "
            f"{active_settings.ai.provider!r}: {str(exc)[:256]}",
            key="ai.model",
        ) from exc


def _resolve_ollama_model(model_str: str, active_settings: Settings) -> Any:
    """Resolve an Ollama model on the configured cluster URLs, parameters and timeout.

    Its client dials at the configured level of these settings.
    """
    from devops_cli.ai.models.ollama import create_ollama_model

    ai_cfg = active_settings.ai
    return create_ollama_model(
        model_str,
        urls=ai_cfg.get_ollama_urls,
        temperature=ai_cfg.temperature,
        max_tokens=ai_cfg.max_tokens,
        reasoning_effort=ai_cfg.reasoning_effort,
        timeout=ai_cfg.timeout,
        ai_config=ai_cfg,
    )


def _resolve_string_model(model_str: str, active_settings: Settings) -> Any:
    """Resolve a model name: a gateway-prefixed one at its gateway under any provider, an
    `ollama:` one or any other under provider `ollama` on Ollama, the rest remotely."""
    if (
        not _gateway_prefix(model_str)
        and not is_decision_model_name(model_str)
        and (model_str.startswith("ollama:") or active_settings.ai.provider == "ollama")
    ):
        return _resolve_ollama_model(model_str, active_settings)
    return _resolve_remote_inferred_model(model_str, active_settings)


def _wrap_model_concurrency(model_obj: Any, model_concurrency: AnyConcurrencyLimit) -> Any:
    """Optionally wrap model instance with concurrency limiting."""
    return limit_model_concurrency(model_obj, model_concurrency) if model_concurrency else model_obj


def resolve_pydantic_ai_model(
    model: str | Any | None = None,
    settings: Settings | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
) -> Any:
    """Resolve and configure native PydanticAI Model instance.

    Supports OllamaProvider with dynamic cluster URLs, fallback cascade models, Jev auto tool-call
    models (`auto` or `auto:<fallback_model>`), and automatic model inference across providers.
    """
    if model is None:
        return None

    if isinstance(model, (list, tuple)) or model == "cascade":
        seq = model if isinstance(model, (list, tuple)) else CONST_AI_CASCADE_PROVIDERS
        return build_fallback_cascade_model(
            seq, settings=settings, model_concurrency=model_concurrency
        )

    if not isinstance(model, str):
        return _wrap_model_concurrency(model, model_concurrency)

    active_settings = settings or load_settings()
    cleaned = model.strip()
    if cleaned == "auto" or cleaned.startswith("auto:"):
        fallback_target = (
            cleaned.split(":", 1)[1].strip()
            if cleaned.startswith("auto:")
            else active_settings.ai.model
        )
        if (
            not fallback_target
            or fallback_target == "auto"
            or is_decision_model_name(fallback_target)
        ):
            fallback_target = CONST_AI_GATEWAY_DEFAULT_ROUTE
        return build_auto_tool_model(
            fallback_target,
            settings=active_settings,
            model_concurrency=model_concurrency,
        )
    resolved = _resolve_string_model(cleaned, active_settings)
    return _wrap_model_concurrency(resolved, model_concurrency)


def _cascade_member(item: str | Any, ai_cfg: AIConfig) -> str | Any:
    """The model a cascade member names: a bare `litellm` or `portkey` is that gateway's default
    chat route, a bare `ollama` is `ai.model` on Ollama, and anything else is a model already."""
    if not isinstance(item, str):
        return item
    if item in CONST_AI_GATEWAY_URL_SETTINGS:
        return f"{item}:{CONST_AI_GATEWAY_DEFAULT_ROUTE}"
    if item == "ollama":
        return f"ollama:{ai_cfg.model.removeprefix('ollama:')}"
    return item


def build_fallback_cascade_model(
    models_or_providers: Sequence[str | Any] = CONST_AI_CASCADE_PROVIDERS,
    settings: Settings | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
) -> Any:
    """Build a FallbackModel cascading across multiple providers or models.

    Tries each resolved model in sequence upon errors, by default LiteLLM's and Portkey's
    default chat route and then `ai.model` on Ollama (`_cascade_member`).
    """
    active_settings = settings or load_settings()
    resolved_models: list[Any] = []
    for item in models_or_providers:
        m = resolve_pydantic_ai_model(
            _cascade_member(item, active_settings.ai), settings=active_settings
        )
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


def build_auto_tool_model(
    language_model: str | Any,
    *,
    jev_model: str | Any | None = None,
    route_threshold: float = CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    boolean_threshold: float = CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
    settings: Settings | None = None,
    model_concurrency: AnyConcurrencyLimit = None,
) -> Any:
    """Build an auto tool-call model that pairs TypeSafe Jev with a language model.

    Jev (`typesafe/jev-1.14`) handles closed-set tool calls and typed decisions in one System One
    request. When a route probability falls below `route_threshold` (`UnsureRoute`) or a route
    requires free-form text arguments (`UnfillableRoute`), `FallbackModel` hands the turn to
    `language_model`.
    """
    from pydantic_ai.exceptions import ModelAPIError
    from pydantic_ai.models.decision import DecisionHandOff, DecisionModelSettings

    active_settings = settings or load_settings()
    resolved_lm = resolve_pydantic_ai_model(language_model, settings=active_settings)
    decision_model = (
        resolve_pydantic_ai_model(CONST_AI_JEV_MODEL, settings=active_settings)
        if jev_model is None
        else resolve_pydantic_ai_model(jev_model, settings=active_settings)
    )
    if hasattr(decision_model, "_settings"):
        merged = dict(getattr(decision_model, "_settings", None) or {})
        merged.update(
            DecisionModelSettings(
                decision_route_threshold=route_threshold,
                decision_boolean_threshold=boolean_threshold,
            )
        )
        decision_model._settings = merged
    auto_model = FallbackModel(
        decision_model,
        resolved_lm,
        fallback_on=(DecisionHandOff, ModelAPIError, UserError),
    )
    return _wrap_model_concurrency(auto_model, model_concurrency)


__all__ = [
    "build_auto_tool_model",
    "build_fallback_cascade_model",
    "resolve_pydantic_ai_model",
]
