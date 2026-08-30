"""Execution context, usage tracking, and security checks for agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from devops_cli.exceptions import SecurityError

DepsT = TypeVar("DepsT")


def _check_path_traversal(key: str, value: Any) -> None:
    """Validate that path parameters do not contain traversal sequences."""
    if isinstance(value, str) and any(sub in key.lower() for sub in ("path", "file", "dest")):
        if ".." in value and not value.startswith("."):
            raise SecurityError(f"Path traversal sequence detected in parameter '{key}': {value}")


class AgentUsage(BaseModel):
    """Token and execution usage metrics for an agent run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AgentRetries(BaseModel):
    """Configures retry limits for function tools and structured output validation."""

    tools: int = 1
    output: int = 1


class RunContext[DepsT](BaseModel):
    """Runtime context passed to agent tools and system prompt providers."""

    deps: DepsT | None = None
    session_id: str = ""
    retry: int = 0
    model: str = ""
    loaded_capability_ids: set[str] = Field(default_factory=set)
    tool_call_approved: bool = False
    tool_call_metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStepNode(BaseModel):
    """Represents a discrete step or node in the agent execution graph."""

    kind: str  # "user_prompt", "model_request", "tool_call", "tool_result", "end"
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentHooks(BaseModel):
    """Lifecycle hooks for intercepting agent model requests, tool calls, and errors."""

    before_model_request: list[Callable[..., None]] = Field(default_factory=list)
    after_model_request: list[Callable[..., None]] = Field(default_factory=list)
    before_tool_execute: list[Callable[..., None]] = Field(default_factory=list)
    after_tool_execute: list[Callable[..., None]] = Field(default_factory=list)
    on_tool_error: list[Callable[..., None]] = Field(default_factory=list)
