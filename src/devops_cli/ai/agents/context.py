"""Execution context, usage tracking, and security checks for agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

import pydantic_ai._function_schema as _pydantic_fs
from pydantic import BaseModel, Field
from pydantic_ai.tools import RunContext as NativeRunContext

from devops_cli.exceptions import SecurityError

DepsT = TypeVar("DepsT")


def _check_path_traversal(key: str, value: Any) -> None:
    """Validate that path parameters do not contain traversal sequences."""
    if isinstance(value, str) and any(
        sub in key.lower() for sub in ("path", "file", "dest", "target")
    ):
        clean_val = value.strip()
        if ".." in clean_val:
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


class RunContext[DepsT](NativeRunContext[DepsT]):
    """Runtime context passed to agent tools and system prompt providers."""

    session_id: str
    retry: int
    loaded_capability_ids: set[str]
    tool_call_approved: bool
    tool_call_metadata: dict[str, Any]

    def __init__(
        self,
        deps: DepsT | None = None,
        model: Any = None,
        usage: Any = None,
        session_id: str = "",
        retry: int = 0,
        loaded_capability_ids: set[str] | None = None,
        tool_call_approved: bool = False,
        tool_call_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            super().__init__(
                deps=deps,  # type: ignore[arg-type]
                model=model,
                usage=usage if usage is not None else cast(Any, AgentUsage()),
                **kwargs,
            )
        except TypeError:
            super().__init__(deps=deps, **kwargs)  # type: ignore[arg-type]

        self.session_id = session_id
        self.retry = retry
        self.loaded_capability_ids = (
            loaded_capability_ids if loaded_capability_ids is not None else set()
        )
        self.tool_call_approved = tool_call_approved
        self.tool_call_metadata = tool_call_metadata or {}

    def model_copy(
        self,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> RunContext[DepsT]:
        """Provide pydantic BaseModel model_copy compatibility on RunContext."""
        import copy

        copied = copy.deepcopy(self) if deep else copy.copy(self)
        if update:
            for k, v in update.items():
                setattr(copied, k, v)
        return copied


# Allow pydantic_ai._function_schema to recognize subclasses of NativeRunContext
_orig_fs_is_call_ctx = _pydantic_fs._is_call_ctx


def _subclass_aware_is_call_ctx(annotation: Any) -> bool:
    if _orig_fs_is_call_ctx(annotation):
        return True
    origin = getattr(annotation, "__origin__", None) or annotation
    return isinstance(origin, type) and issubclass(origin, NativeRunContext)


_pydantic_fs._is_call_ctx = _subclass_aware_is_call_ctx


class AgentStepNode(BaseModel):
    """Represents a discrete step or node in the agent execution graph."""

    kind: str  # "user_prompt", "model_request", "tool_call", "tool_result", "end"
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentHooks(BaseModel):
    """Lifecycle hooks for intercepting agent model requests, tool calls, and errors."""

    before_run: list[Callable[..., None]] = Field(default_factory=list)
    after_run: list[Callable[..., None]] = Field(default_factory=list)
    before_model_request: list[Callable[..., None]] = Field(default_factory=list)
    after_model_request: list[Callable[..., None]] = Field(default_factory=list)
    before_tool_execute: list[Callable[..., None]] = Field(default_factory=list)
    after_tool_execute: list[Callable[..., None]] = Field(default_factory=list)
    on_tool_error: list[Callable[..., None]] = Field(default_factory=list)
