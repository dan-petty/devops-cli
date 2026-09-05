"""PydanticAI Standardized Agent Framework adapter and bridge."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import BaseCapability, PydanticAgent
from devops_cli.ai.client import LLMClient
from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.config.settings import Settings, get_ai_api_key, load_settings

logger = logging.getLogger(__name__)


class DevOpsAgentContext(BaseModel):
    """Execution context and dependency container passed to PydanticAI agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    settings: Settings | None = None
    target_repo: str = "."
    active_persona: str = "devsecops"
    context_tokens_budget: int = 16384
    capabilities: list[BaseCapability] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)
    client: LLMClient | None = None


def is_pydantic_ai_available() -> bool:
    """Check if pydantic_ai library is installed and importable."""
    try:
        import pydantic_ai  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_pydantic_ai_model(
    model: str | Any | None = None,
    settings: Settings | None = None,
) -> Any:
    """Resolve and configure native PydanticAI Model instance.

    Supports OllamaProvider with dynamic cluster URLs, TestModel for offline testing,
    and automatic model inference across providers.
    """
    if model is None:
        return None

    import devops_cli.ai.agents.agent as agent_module
    import devops_cli.ai.agents.testing as testing_module

    if not getattr(testing_module, "ALLOW_MODEL_REQUESTS", True) or not getattr(
        agent_module, "ALLOW_MODEL_REQUESTS", True
    ):
        from pydantic_ai.models.test import TestModel

        return TestModel()

    from pydantic_ai.models import Model

    if isinstance(model, Model):
        return model

    if model == "test":
        from pydantic_ai.models.test import TestModel

        return TestModel()

    if not isinstance(model, str):
        return model

    active_settings = settings or load_settings()
    model_str = model.strip()
    provider = getattr(active_settings.ai, "provider", "ollama")

    if model_str.startswith("ollama:") or provider == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider

        clean_name = model_str.removeprefix("ollama:").strip()
        urls = active_settings.ai.get_ollama_urls if hasattr(active_settings, "ai") else []
        base_url = urls[0] if urls else "http://localhost:11434"
        ollama_provider = OllamaProvider(base_url=f"{base_url.rstrip('/')}/v1")
        return OllamaModel(clean_name, provider=ollama_provider)

    try:
        from pydantic_ai.models import infer_model

        return infer_model(model_str)
    except Exception:
        return model_str


def create_pydantic_ai_agent[T: BaseModel](
    model_name: str | Any | None = None,
    system_prompt: str = "",
    output_type: type[T] | None = None,
    result_type: type[T] | None = None,
    deps_type: type[Any] = DevOpsAgentContext,
    capabilities: Sequence[BaseCapability] | None = None,
    tools: Sequence[Any] | None = None,
    client: LLMClient | None = None,
    end_strategy: str = "graceful",
    retries: int | None = None,
) -> Any:
    """Instantiate a standardized PydanticAI Agent with typed dependencies, capabilities, and outputs."""
    settings: Settings = load_settings()
    target_model = model_name or getattr(getattr(settings, "ai", None), "model", None)
    res_model = output_type or result_type or ReviewResult
    active_caps = list(capabilities or [])
    active_tools = list(tools or [])

    try:
        from pydantic_ai import Agent

        resolved_model = resolve_pydantic_ai_model(target_model, settings=settings)

        kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "deps_type": deps_type,
            "end_strategy": end_strategy,
        }
        if retries is not None:
            kwargs["retries"] = retries
        sig = inspect.signature(Agent.__init__)
        if "output_type" in sig.parameters:
            kwargs["output_type"] = res_model
        elif "result_type" in sig.parameters:
            kwargs["result_type"] = res_model

        if "capabilities" in sig.parameters and active_caps:
            kwargs["capabilities"] = active_caps
        if "tools" in sig.parameters and active_tools:
            kwargs["tools"] = active_tools

        if resolved_model is not None:
            return Agent(model=resolved_model, **kwargs)

        return Agent(**kwargs)
    except Exception as exc:
        logger.debug("Native PydanticAI agent unavailable, creating PydanticAgent: %s", exc)
        active_client = client or LLMClient(settings.ai, api_key=get_ai_api_key(settings))
        return PydanticAgent(
            client=active_client,
            name=f"agent-{target_model or 'default'}",
            system_prompt=system_prompt,
            tools=active_tools,
            capabilities=active_caps,
            output_type=res_model,
        )


def get_persona_pydantic_agent(
    persona: Persona | str = Persona.DEVSECOPS,
    settings: Settings | None = None,
    capabilities: Sequence[BaseCapability] | None = None,
    tools: Sequence[Any] | None = None,
) -> Any:
    """Build a persona-specialized PydanticAI agent instance."""
    p_enum = Persona(persona) if isinstance(persona, str) else persona
    p_def = PERSONAS[p_enum]
    active_settings = settings or load_settings()

    return create_pydantic_ai_agent(
        model_name=active_settings.ai.model,
        system_prompt=p_def.system_prompt,
        output_type=ReviewResult,
        deps_type=DevOpsAgentContext,
        capabilities=capabilities,
        tools=tools,
    )
