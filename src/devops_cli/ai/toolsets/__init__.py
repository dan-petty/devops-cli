"""Native Pydantic AI Toolsets subsystem.

Provides full native adoption of pydantic_ai.toolsets primitives, combinators,
protocols, schemas, and high-level domain helpers for workstation automation.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import (
    Any,
    Generic,
    TypeVar,
    cast,
)

from pydantic import BaseModel, ConfigDict
from pydantic_ai.tools import Tool as NativeTool
from pydantic_ai.toolsets import (
    AbstractToolset as NativeAbstractToolset,
)
from pydantic_ai.toolsets import (
    AgentToolset,
    ApprovalRequiredToolset,
    CombinedToolset,
    DeferredLoadingToolset,
    DynamicToolset,
    ExternalToolset,
    FilteredToolset,
    IncludeReturnSchemasToolset,
    PrefixedToolset,
    PreparedToolset,
    RenamedToolset,
    SetMetadataToolset,
    ToolsetFunc,
    ToolsetTool,
    WrapperToolset,
)
from pydantic_ai.toolsets import (
    FunctionToolset as NativeFunctionToolset,
)
from pydantic_ai.toolsets.abstract import AgentDepsT  # type: ignore[attr-defined]

from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.tools import Tool

DepsT = TypeVar("DepsT", default=Any)


class AbstractToolset(BaseModel, NativeAbstractToolset[DepsT], Generic[DepsT]):
    """Abstract base class for modular agent toolsets.

    Bridges native Pydantic AI asynchronous toolset execution with workstation
    synchronous tool inspection and execution pipelines.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    _id: str | None = None

    @property
    def id(self) -> str | None:
        """An ID for the toolset unique among registered agent toolsets."""
        return self._id or self.__class__.__name__

    def get_tools(self, ctx: Any = None) -> Any:
        """Return tools provided by this toolset.

        When called without arguments (or ctx=None), returns a synchronous list of
        Tool instances for backward compatibility. When called with a RunContext,
        returns a coroutine resolving to dict[str, ToolsetTool] for native Pydantic AI.
        """
        if ctx is None:
            return []
        return self._async_get_tools(ctx)

    async def _async_get_tools(self, ctx: RunContext[DepsT]) -> dict[str, ToolsetTool[DepsT]]:
        """Async fallback for native Pydantic AI agent runs."""
        sync_tools = self.get_tools()
        if not sync_tools:
            return {}
        fts: FunctionToolset[DepsT] = FunctionToolset()
        for t in sync_tools:
            if isinstance(t, Tool):
                fts.add_tool(t)
            elif callable(t):
                fts.add_function(t)
        return cast(dict[str, ToolsetTool[DepsT]], await fts.get_tools(ctx))

    async def call_tool(  # type: ignore[override]
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[DepsT],
        tool: ToolsetTool[DepsT],
    ) -> Any:
        """Call a tool with the given arguments."""
        sync_tools = self.get_tools()
        for t in sync_tools:
            if getattr(t, "name", "") == name:
                if hasattr(t, "execute"):
                    return t.execute(ctx, **tool_args)
                if callable(t):
                    res = t(ctx, **tool_args) if getattr(t, "takes_ctx", False) else t(**tool_args)
                    if inspect.iscoroutine(res):
                        return await res
                    return res
        raise KeyError(f"Tool '{name}' not found on toolset {self.label}")

    def get_instructions(self, ctx: Any = None) -> Any:
        """Return system prompt instructions for this toolset.

        Supports synchronous string list extraction or asynchronous native instruction parts.
        """
        if ctx is None:
            return []
        return self._async_get_instructions(ctx)

    async def _async_get_instructions(self, ctx: RunContext[DepsT]) -> list[str]:
        sync_inst = self.get_instructions()
        return list(sync_inst) if isinstance(sync_inst, (list, tuple)) else []


class FunctionToolset(NativeFunctionToolset[DepsT], Generic[DepsT]):
    """Bundles local functions, tools, and domain instructions into a reusable toolset.

    Subclasses native pydantic_ai.toolsets.FunctionToolset while maintaining dual
    synchronous list inspection and asynchronous native Pydantic AI execution.
    """

    def __init__(
        self,
        tools: Sequence[Tool | Callable[..., Any]] = (),
        *,
        instructions: str | Sequence[str] | Any = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retries: int | None = None,
        requires_approval: bool = False,
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_retries = retries if retries is not None else max_retries
        super().__init__(
            max_retries=resolved_retries,
            timeout=timeout,
            requires_approval=requires_approval,
            id=id,
            instructions=instructions,
            **kwargs,
        )
        for t in tools:
            self.add_tool(t)

    def add_tool(self, tool: Any) -> None:
        """Add a Tool, AgentTool, or callable to this toolset."""
        from devops_cli.ai.agents.tools import AgentTool as AgentToolClass

        if isinstance(tool, AgentToolClass):
            tool_inst = Tool.from_function(
                tool.func,
                name=tool.name,
                description=tool.description,
                takes_ctx=tool.takes_ctx,
                timeout=tool.timeout or self.timeout,
                max_retries=tool.max_retries or self.max_retries,
                requires_approval=tool.requires_approval or self.requires_approval,
                include_return_schema=tool.include_return_schema,
                args_validator_func=tool.args_validator_func,
                metadata=tool.metadata,
            )
            super().add_tool(tool_inst)
        elif isinstance(tool, Tool):
            super().add_tool(tool)
        elif isinstance(tool, NativeTool):
            wrapped = Tool(
                tool.function,
                takes_ctx=tool.takes_ctx,
                max_retries=tool.max_retries,
                name=tool.name,
                description=tool.description,
                prepare=tool.prepare,
                args_validator=tool.args_validator,
                docstring_format=tool.docstring_format,
                require_parameter_descriptions=tool.require_parameter_descriptions,
                strict=tool.strict,
                sequential=tool.sequential,
                requires_approval=tool.requires_approval,
                metadata=tool.metadata,
                timeout=tool.timeout,
                defer_loading=tool.defer_loading,
                include_return_schema=tool.include_return_schema,
            )
            super().add_tool(wrapped)
        elif callable(tool):
            self.add_function(tool)
        else:
            raise TypeError(f"Expected Tool, AgentTool, or callable, got {type(tool)}")

    def add_function(  # type: ignore[override]
        self,
        func: Callable[..., Any],
        *,
        takes_ctx: bool | None = None,
        name: str | None = None,
        description: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retries: int | None = None,
        requires_approval: bool | None = None,
        include_return_schema: bool | None = None,
        args_validator: Any = None,
        args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Tool:
        """Add a function to this toolset with custom metadata and validation."""
        resolved_retries = retries if retries is not None else max_retries
        validator = args_validator or args_validator_func
        tool_inst: Tool = Tool(
            func,
            takes_ctx=takes_ctx,
            name=name,
            description=description,
            timeout=timeout if timeout is not None else self.timeout,
            max_retries=resolved_retries if resolved_retries is not None else self.max_retries,
            requires_approval=(
                requires_approval if requires_approval is not None else self.requires_approval
            ),
            include_return_schema=include_return_schema,
            args_validator=cast(Any, validator),
            args_validator_func=args_validator_func,
            metadata=metadata,
            **kwargs,
        )
        self.add_tool(tool_inst)
        return tool_inst

    def tool(
        self,
        func: Callable[..., Any] | None = None,
        *,
        takes_ctx: bool | None = None,
        name: str | None = None,
        description: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retries: int | None = None,
        requires_approval: bool | None = None,
        include_return_schema: bool | None = None,
        args_validator: Any = None,
        args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Decorator to register a tool on this toolset."""
        resolved_retries = retries if retries is not None else max_retries
        validator = args_validator or args_validator_func

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add_function(
                func=fn,
                takes_ctx=takes_ctx,
                name=name,
                description=description,
                timeout=timeout if timeout is not None else self.timeout,
                retries=resolved_retries if resolved_retries is not None else self.max_retries,
                requires_approval=(
                    requires_approval if requires_approval is not None else self.requires_approval
                ),
                include_return_schema=include_return_schema,
                args_validator=validator,
                args_validator_func=args_validator_func,
                metadata=metadata,
                **kwargs,
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
        timeout: float | None = None,
        max_retries: int | None = None,
        retries: int | None = None,
        requires_approval: bool | None = None,
        include_return_schema: bool | None = None,
        args_validator: Any = None,
        args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Decorator to register a plain (context-free) tool on this toolset."""
        return self.tool(
            func=func,
            takes_ctx=False,
            name=name,
            description=description,
            timeout=timeout,
            max_retries=max_retries,
            retries=retries,
            requires_approval=requires_approval,
            include_return_schema=include_return_schema,
            args_validator=args_validator,
            args_validator_func=args_validator_func,
            metadata=metadata,
            **kwargs,
        )

    def get_tools(self, ctx: Any = None) -> Any:
        """Return tools registered on this toolset.

        If ctx is None, returns a synchronous list of Tool instances.
        If ctx is provided, returns native coroutine resolving to dict[str, ToolsetTool].
        """
        if ctx is None:
            tools_list: list[Tool] = []
            for t in self.tools.values():
                if isinstance(t, Tool):
                    tools_list.append(t)
                elif isinstance(t, NativeTool):
                    tools_list.append(
                        Tool(
                            t.function,
                            takes_ctx=t.takes_ctx,
                            max_retries=t.max_retries,
                            name=t.name,
                            description=t.description,
                            prepare=t.prepare,
                            args_validator=t.args_validator,
                            docstring_format=t.docstring_format,
                            require_parameter_descriptions=t.require_parameter_descriptions,
                            strict=t.strict,
                            sequential=t.sequential,
                            requires_approval=t.requires_approval,
                            metadata=t.metadata,
                            timeout=t.timeout,
                            defer_loading=t.defer_loading,
                            include_return_schema=t.include_return_schema,
                        )
                    )
            return tools_list
        return super().get_tools(ctx)

    def get_instructions(self, ctx: Any = None) -> Any:
        """Return instructions configured for this toolset.

        If ctx is None, returns a synchronous list of string instructions.
        If ctx is provided, returns native coroutine resolving to instructions.
        """
        if ctx is None:
            instructions = self._instructions
            if isinstance(instructions, str):
                return [instructions.strip()] if instructions.strip() else []
            if isinstance(instructions, (list, tuple)):
                res: list[str] = []
                for inst in instructions:
                    if isinstance(inst, str) and inst.strip():
                        res.append(inst.strip())
                    elif hasattr(inst, "content") and getattr(inst, "content"):
                        res.append(str(getattr(inst, "content")).strip())
                return res
            return []
        return super().get_instructions(ctx)


def create_function_toolset(
    tools: Sequence[Tool | Callable[..., Any]] = (),
    *,
    instructions: str | Sequence[str] | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    requires_approval: bool = False,
    id: str | None = None,
    **kwargs: Any,
) -> FunctionToolset[Any]:
    """Construct a modernized FunctionToolset from a sequence of tools or callables."""
    return FunctionToolset(
        tools=tools,
        instructions=instructions,
        timeout=timeout,
        max_retries=max_retries,
        requires_approval=requires_approval,
        id=id,
        **kwargs,
    )


def combine_toolsets(
    *toolsets: AbstractToolset[Any] | NativeAbstractToolset[Any],
) -> CombinedToolset[Any]:
    """Combine multiple toolsets into a single CombinedToolset."""
    return CombinedToolset(list(toolsets))


def prefix_toolset(
    toolset: AbstractToolset[Any] | NativeAbstractToolset[Any],
    prefix: str,
) -> PrefixedToolset[Any]:
    """Prefix all tool names within a toolset using native PrefixedToolset."""
    clean_prefix = prefix[:-1] if prefix.endswith("_") else prefix
    return toolset.prefixed(clean_prefix)


def filter_toolset(
    toolset: AbstractToolset[Any] | NativeAbstractToolset[Any],
    filter_func: Callable[..., bool | Awaitable[bool]],
) -> FilteredToolset[Any]:
    """Filter tools within a toolset using a filter predicate."""
    return toolset.filtered(filter_func)


def rename_toolset(
    toolset: AbstractToolset[Any] | NativeAbstractToolset[Any],
    name_map: dict[str, str],
) -> RenamedToolset[Any]:
    """Rename tools within a toolset using a name mapping dictionary."""
    return toolset.renamed(name_map)


def require_approval_toolset(
    toolset: AbstractToolset[Any] | NativeAbstractToolset[Any],
    approval_func: Callable[..., bool] | None = None,
) -> ApprovalRequiredToolset[Any]:
    """Wrap a toolset to require approval before calling its tools."""
    if approval_func is not None:
        return toolset.approval_required(approval_func)
    return toolset.approval_required()


def defer_loading_toolset(
    toolset: AbstractToolset[Any] | NativeAbstractToolset[Any],
) -> DeferredLoadingToolset[Any]:
    """Wrap a toolset to defer loading of its tools until revealed."""
    return toolset.defer_loading()


def is_toolset(val: Any) -> bool:
    """Check whether a value is an instance of native or modernized AbstractToolset."""
    return isinstance(val, (NativeAbstractToolset, AbstractToolset))


def extract_tools_from_toolset(
    toolset: Any,
    ctx: Any = None,
) -> list[Tool]:
    """Extract list of Tool instances from a toolset synchronously or via inspection."""
    if hasattr(toolset, "get_tools"):
        res = None
        try:
            if ctx is None:
                try:
                    res = toolset.get_tools()
                except TypeError:
                    res = toolset.get_tools(None)
            else:
                try:
                    res = toolset.get_tools(ctx)
                except TypeError:
                    res = toolset.get_tools()
        except Exception:
            res = None

        if isinstance(res, list):
            out: list[Tool] = []
            for t in res:
                if isinstance(t, Tool):
                    out.append(t)
                elif isinstance(t, NativeTool):
                    out.append(
                        Tool.from_function(
                            t.function,
                            name=t.name,
                            description=t.description,
                            takes_ctx=t.takes_ctx,
                            timeout=t.timeout,
                            max_retries=t.max_retries,
                            requires_approval=t.requires_approval,
                        )
                    )
                elif hasattr(t, "func"):
                    out.append(
                        Tool.from_function(
                            t.func,
                            name=getattr(t, "name", None),
                            description=getattr(t, "description", None),
                            takes_ctx=getattr(t, "takes_ctx", False),
                        )
                    )
                elif callable(t):
                    out.append(Tool.from_function(t))
            return out
        if isinstance(res, dict):
            return [
                Tool.from_function(getattr(item, "call_func", lambda: None), name=k)
                for k, item in res.items()
            ]
    if hasattr(toolset, "tools") and isinstance(toolset.tools, dict):
        dict_out: list[Tool] = []
        for t in toolset.tools.values():
            if isinstance(t, Tool):
                dict_out.append(t)
            elif isinstance(t, NativeTool):
                dict_out.append(
                    Tool.from_function(
                        t.function,
                        name=t.name,
                        description=t.description,
                        takes_ctx=t.takes_ctx,
                        timeout=t.timeout,
                        max_retries=t.max_retries,
                        requires_approval=t.requires_approval,
                    )
                )
        return dict_out
    return []


__all__ = [
    "AbstractToolset",
    "AgentDepsT",
    "AgentToolset",
    "ApprovalRequiredToolset",
    "CombinedToolset",
    "DeferredLoadingToolset",
    "DynamicToolset",
    "ExternalToolset",
    "FilteredToolset",
    "FunctionToolset",
    "IncludeReturnSchemasToolset",
    "NativeAbstractToolset",
    "NativeFunctionToolset",
    "PrefixedToolset",
    "PreparedToolset",
    "RenamedToolset",
    "SetMetadataToolset",
    "ToolsetFunc",
    "ToolsetTool",
    "WrapperToolset",
    "combine_toolsets",
    "create_function_toolset",
    "defer_loading_toolset",
    "extract_tools_from_toolset",
    "filter_toolset",
    "is_toolset",
    "prefix_toolset",
    "rename_toolset",
    "require_approval_toolset",
]
