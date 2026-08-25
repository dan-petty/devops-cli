"""PydanticAI Standardized Agent Framework adapter and bridge."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from pydantic import BaseModel

from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.config.settings import Settings, load_settings

logger = logging.getLogger(__name__)


class DevOpsAgentContext(BaseModel):
    """Execution context and dependency container passed to PydanticAI agents."""

    settings: Any = None
    target_repo: str = "."
    active_persona: str = "devsecops"
    context_tokens_budget: int = 16384


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
) -> Any:
    """Instantiate a standardized PydanticAI Agent with typed dependencies and outputs."""
    try:
        from pydantic_ai import Agent

        settings: Settings = load_settings()
        target_model = model_name or getattr(getattr(settings, "ai", None), "model", None)

        kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "deps_type": deps_type,
        }
        sig = inspect.signature(Agent.__init__)
        res_model = result_type or ReviewResult
        if "output_type" in sig.parameters:
            kwargs["output_type"] = res_model
        elif "result_type" in sig.parameters:
            kwargs["result_type"] = res_model

        if target_model:
            try:
                return Agent(model=target_model, **kwargs)
            except Exception as exc:
                logger.debug("Failed initializing model %s on Agent: %s", target_model, exc)

        return Agent(**kwargs)
    except Exception as exc:
        logger.debug("Failed creating native PydanticAI agent: %s", exc)
        return None


def get_persona_pydantic_agent(
    persona: Persona | str = Persona.DEVSECOPS,
    settings: Settings | None = None,
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
    )
