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


def create_pydantic_ai_agent[T: BaseModel](
    model_name: str | None = None,
    system_prompt: str = "",
    result_type: type[T] | None = None,
    deps_type: type[Any] = DevOpsAgentContext,
    capabilities: Sequence[BaseCapability] | None = None,
    tools: Sequence[Any] | None = None,
    client: LLMClient | None = None,
) -> Any:
    """Instantiate a standardized PydanticAI Agent with typed dependencies, capabilities, and outputs."""
    settings: Settings = load_settings()
    target_model = model_name or getattr(getattr(settings, "ai", None), "model", None)
    res_model = result_type or ReviewResult
    active_caps = list(capabilities or [])
    active_tools = list(tools or [])

    try:
        from pydantic_ai import Agent

        kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "deps_type": deps_type,
        }
        sig = inspect.signature(Agent.__init__)
        if "output_type" in sig.parameters:
            kwargs["output_type"] = res_model
        elif "result_type" in sig.parameters:
            kwargs["result_type"] = res_model

        if "capabilities" in sig.parameters and active_caps:
            kwargs["capabilities"] = active_caps
        if "tools" in sig.parameters and active_tools:
            kwargs["tools"] = active_tools

        if target_model:
            try:
                return Agent(model=target_model, **kwargs)
            except Exception as exc:
                logger.debug("Failed initializing model %s on Agent: %s", target_model, exc)

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
            output_schema=res_model,
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
        result_type=ReviewResult,
        deps_type=DevOpsAgentContext,
        capabilities=capabilities,
        tools=tools,
    )
