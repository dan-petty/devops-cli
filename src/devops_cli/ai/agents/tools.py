"""Tool abstractions, function decorators, toolsets, and specifications."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.context import RunContext, _check_path_traversal


class AgentTool(BaseModel):
    """Encapsulates an executable tool available to a PydanticAgent."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = Field(default_factory=dict)
    takes_ctx: bool = False
    timeout: float | None = None
    max_retries: int | None = None
    requires_approval: bool = False
    include_return_schema: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate and filter tool arguments against the declared parameter schema."""
        if not self.parameters:
            return args
        valid_params = set(self.parameters.keys())
        clean_args: dict[str, Any] = {}
        for k, v in args.items():
            if k in valid_params:
                _check_path_traversal(k, v)
                clean_args[k] = v
        return clean_args

    def execute(self, ctx: RunContext[Any] | None = None, **kwargs: Any) -> Any:
        """Invoke the tool callback with kwargs and optional RunContext."""
        if self.requires_approval and not (ctx and ctx.tool_call_approved):
            from devops_cli.exceptions.ai import ApprovalRequired

            raise ApprovalRequired(f"Tool '{self.name}' requires human approval")
        if self.takes_ctx and ctx is not None:
            return self.func(ctx, **kwargs)
        return self.func(**kwargs)


class ToolReturn(BaseModel):
    """Rich tool return object separating return value, LLM message content, and metadata."""

    return_value: Any = None
    content: list[Any] | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)


class Tool(AgentTool):
    """Pydantic AI Tool model for registering function tools with rich configuration."""

    strict: bool | None = None

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        takes_ctx: bool | None = None,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
        include_return_schema: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Tool:
        """Construct a Tool instance from a callable."""
        tool_name = name or func.__name__
        tool_doc = description or (inspect.getdoc(func) or tool_name)
        sig = inspect.signature(func)
        params: dict[str, Any] = {}
        inferred_takes_ctx = takes_ctx
        for idx, (p_name, p) in enumerate(sig.parameters.items()):
            if idx == 0 and (p_name == "ctx" or "RunContext" in str(p.annotation)):
                if inferred_takes_ctx is None:
                    inferred_takes_ctx = True
                continue
            ann = p.annotation if p.annotation != inspect.Parameter.empty else str
            params[p_name] = str(ann)
        return cls(
            name=tool_name,
            description=tool_doc,
            func=func,
            parameters=params,
            takes_ctx=bool(inferred_takes_ctx),
            strict=strict,
            requires_approval=requires_approval,
            timeout=timeout,
            max_retries=max_retries,
            include_return_schema=include_return_schema,
            metadata=metadata or {},
        )

    @classmethod
    def from_schema(
        cls,
        function: Callable[..., Any],
        *,
        name: str,
        description: str = "",
        json_schema: dict[str, Any] | None = None,
        takes_ctx: bool = False,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Tool:
        """Construct a Tool instance from an arbitrary callable and explicit JSON schema."""
        properties = json_schema.get("properties", {}) if json_schema else {}
        params = {
            k: v.get("type", "str") if isinstance(v, dict) else "str" for k, v in properties.items()
        }
        return cls(
            name=name,
            description=description,
            func=function,
            parameters=params,
            takes_ctx=takes_ctx,
            strict=strict,
            requires_approval=requires_approval,
            timeout=timeout,
            max_retries=max_retries,
        )


class ToolCall(BaseModel):
    """Record of a tool call executed during an agent run."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FunctionToolset[DepsT = Any](BaseModel):
    """Bundles local functions and domain instructions into a reusable toolset."""

    instructions: str = ""
    tools: list[AgentTool | Callable[..., Any]] = Field(default_factory=list)
    timeout: float | None = None
    max_retries: int | None = None

    def tool(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Any:
        """Decorator to register a tool on this toolset."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools.append(
                Tool.from_function(
                    fn,
                    name=name,
                    description=description,
                    strict=strict,
                    requires_approval=requires_approval,
                    timeout=timeout if timeout is not None else self.timeout,
                    max_retries=max_retries if max_retries is not None else self.max_retries,
                )
            )
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    def tool_plain(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Any:
        """Decorator to register a plain tool on this toolset."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools.append(
                Tool.from_function(
                    fn,
                    name=name,
                    description=description,
                    takes_ctx=False,
                    strict=strict,
                    requires_approval=requires_approval,
                    timeout=timeout if timeout is not None else self.timeout,
                    max_retries=max_retries if max_retries is not None else self.max_retries,
                )
            )
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    def add_tool(self, tool: AgentTool | Callable[..., Any]) -> None:
        """Add a tool or callable to this toolset."""
        self.tools.append(tool)

    def add_function(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        takes_ctx: bool = False,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Add a function as a Tool instance with custom metadata."""
        self.tools.append(
            Tool.from_function(
                func,
                name=name,
                description=description,
                takes_ctx=takes_ctx,
                strict=strict,
                requires_approval=requires_approval,
                timeout=timeout if timeout is not None else self.timeout,
                max_retries=max_retries if max_retries is not None else self.max_retries,
            )
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        """Return all tools registered on this toolset."""
        return list(self.tools)

    def get_instructions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        """Return static instructions for this toolset."""
        if self.instructions and self.instructions.strip():
            return [self.instructions.strip()]
        return []


class TemplateStr(str):
    """Template string that renders {{variable}} against deps attributes or keys at runtime."""

    def render(self, deps: Any) -> str:
        """Render Handlebars-style template variables using fields from deps."""
        if not deps:
            return str(self)
        rendered = str(self)
        pattern = r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}"

        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if isinstance(deps, dict):
                val = deps.get(key)
                return str(val) if val is not None else match.group(0)
            if hasattr(deps, key):
                val = getattr(deps, key)
                return str(val) if val is not None else match.group(0)
            return match.group(0)

        return re.sub(pattern, replacer, rendered)


class AgentSpec(BaseModel):
    """Declarative specification for constructing a PydanticAgent."""

    model: str = ""
    name: str | None = None
    description: str | None = None
    instructions: str | list[str] | None = None
    model_settings: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[Any] = Field(default_factory=list)
    deps_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
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
