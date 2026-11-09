"""Tool abstractions, function decorators, toolsets, and specifications."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.ai.function_signature import FunctionSignature

from pydantic import BaseModel, Field

from devops_cli.ai.agents.context import RunContext, _check_path_traversal
from devops_cli.ai.tools import Tool as Tool
from devops_cli.ai.toolsets import (
    AbstractToolset as AbstractToolset,
)
from devops_cli.ai.toolsets import (
    FunctionToolset as FunctionToolset,
)


class AgentTool(BaseModel):
    """Encapsulates an executable tool available to an agent."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = Field(default_factory=dict)
    takes_ctx: bool = False
    timeout: float | None = None
    max_retries: int | None = None
    requires_approval: bool = False
    include_return_schema: bool | None = None
    args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate and filter tool arguments against the declared parameter schema."""
        clean_args: dict[str, Any] = {}
        valid_params = set(self.parameters.keys()) if self.parameters else None
        for k, v in args.items():
            if valid_params is None or k in valid_params:
                _check_path_traversal(k, v)
                clean_args[k] = v

        if self.args_validator_func is not None:
            validated = self.args_validator_func(clean_args)
            if validated is not None:
                clean_args = validated

        return clean_args

    def execute(self, ctx: RunContext[Any] | None = None, **kwargs: Any) -> Any:
        """Invoke the tool callback with kwargs and optional RunContext."""
        if self.requires_approval and not (ctx and ctx.tool_call_approved):
            from devops_cli.exceptions.ai import ApprovalRequired

            raise ApprovalRequired(f"Tool '{self.name}' requires human approval")
        if self.takes_ctx and ctx is not None:
            return self.func(ctx, **kwargs)
        return self.func(**kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow invoking the underlying tool function directly."""
        return self.func(*args, **kwargs)

    def to_function_signature(self) -> FunctionSignature:
        """Convert this tool into a native Pydantic AI FunctionSignature."""
        from devops_cli.ai.function_signature import signature_from_callable, signature_from_schema

        try:
            return signature_from_callable(
                self.func,
                name=self.name,
                description=self.description,
                takes_ctx=self.takes_ctx,
            )
        except Exception:
            params = self.parameters or {}
            if isinstance(params, dict) and "properties" in params and "type" in params:
                schema_dict = params
            else:
                schema_dict = {
                    "type": "object",
                    "properties": {p: {"type": "string"} for p in params},
                    "required": list(params.keys()),
                }
            return signature_from_schema(
                name=self.name,
                parameters_schema=schema_dict,
                description=self.description,
            )


class ToolReturn(BaseModel):
    """Rich tool return object separating return value, LLM message content, and metadata."""

    return_value: Any = None
    content: list[Any] | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)


class ToolCall(BaseModel):
    """Record of a tool call executed during an agent run."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSpec(BaseModel):
    """Declarative specification for constructing an agent."""

    model: str = ""
    name: str | None = None
    description: str | None = None
    instructions: str | list[str] | None = None
    model_settings: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[Any] = Field(default_factory=list)
    deps_schema: dict[str, Any] | None = None
    retries: int | None = None
    end_strategy: str = "early"
    tool_timeout: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> AgentSpec:
        """Parse AgentSpec from YAML string."""
        import yaml

        data = yaml.safe_load(yaml_str) or {}
        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: str | Path) -> AgentSpec:
        """Load AgentSpec from YAML or JSON file."""
        p = Path(path)
        content = p.read_text(encoding="utf-8")
        if p.suffix in (".yaml", ".yml"):
            return cls.from_yaml(content)
        return cls.model_validate(json.loads(content))


__all__ = [
    "AbstractToolset",
    "AgentSpec",
    "AgentTool",
    "FunctionToolset",
    "Tool",
    "ToolCall",
    "ToolReturn",
]
