"""Agent capability interfaces, progressive disclosure, and provider-native tool bindings."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.context import AgentHooks, RunContext
from devops_cli.ai.agents.tools import AgentTool, Tool


class BaseCapability(BaseModel):
    """Abstract base class for modular agent capabilities."""

    id: str = ""
    description: str = ""
    defer_loading: bool = False

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        """Return tools provided by this capability."""
        return []

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        """Return prompt additions provided by this capability."""
        return []

    def get_hooks(self) -> AgentHooks | None:
        """Return lifecycle hooks provided by this capability."""
        return None

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        """Return model runtime settings provided by this capability."""
        return {}

    def prefix_tools(self, prefix: str) -> Any:
        """Return a PrefixTools capability wrapper for this capability."""
        return PrefixTools(self, prefix=prefix)

    def with_metadata(self, metadata: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        """Return a SetToolMetadata capability wrapper attaching metadata to this capability's tools."""
        combined = {**(metadata or {}), **kwargs}
        return SetToolMetadata(capability=self, metadata=combined)


class ToolApproved(BaseModel):
    """Signals approval of a deferred tool call with optional argument overrides."""

    override_args: dict[str, Any] | None = None

    def __init__(self, override_args: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(override_args=override_args, **kwargs)


class ToolDenied(BaseModel):
    """Signals denial of a deferred tool call with feedback message for the model."""

    message: str = "Tool call was denied"

    def __init__(self, message: str = "Tool call was denied", **kwargs: Any) -> None:
        super().__init__(message=message, **kwargs)


class ToolCallPart(BaseModel):
    """A tool call specification requiring approval or external execution."""

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str = ""


class ThinkingPart(BaseModel):
    """A structured model thinking/reasoning part."""

    content: str = ""
    encrypted_content: str | None = None
    signature: str | None = None
    part_kind: str = "thinking"


class DeferredToolResults(BaseModel):
    """Resolution of deferred tool calls providing approval decisions and external results."""

    approvals: dict[str, bool | ToolApproved | ToolDenied] = Field(default_factory=dict)
    calls: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)


class DeferredToolRequests(BaseModel):
    """Collection of tool calls pending human approval or external execution."""

    calls: list[ToolCallPart] = Field(default_factory=list)
    approvals: list[ToolCallPart] = Field(default_factory=list)
    metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def build_results(
        self,
        approvals: dict[str, bool | ToolApproved | ToolDenied] | None = None,
        calls: dict[str, Any] | None = None,
        metadata: dict[str, dict[str, Any]] | None = None,
        *,
        approve_all: bool = False,
        deny_all: bool = False,
    ) -> DeferredToolResults:
        """Construct a DeferredToolResults object matching this request."""
        appr_map = dict(approvals or {})
        if approve_all:
            for p in self.approvals:
                key = p.tool_call_id or p.tool_name
                if key and key not in appr_map:
                    appr_map[key] = ToolApproved()
        elif deny_all:
            for p in self.approvals:
                key = p.tool_call_id or p.tool_name
                if key and key not in appr_map:
                    appr_map[key] = ToolDenied()
        return DeferredToolResults(
            approvals=appr_map,
            calls=calls or {},
            metadata=metadata or {},
        )


class WebSearchUserLocation(BaseModel):
    """Geographic location configuration for native web search requests."""

    city: str | None = None
    country: str | None = None
    region: str | None = None
    timezone: str | None = None


class WebSearchTool(BaseModel):
    """Configuration for provider-native Web Search tool capability."""

    search_context_size: str = "medium"
    user_location: WebSearchUserLocation | None = None
    blocked_domains: list[str] = Field(default_factory=list)
    allowed_domains: list[str] | None = None
    max_uses: int | None = None


class WebFetchTool(BaseModel):
    """Configuration for provider-native Web Fetch tool capability."""

    allowed_domains: list[str] | None = None
    blocked_domains: list[str] = Field(default_factory=list)
    max_uses: int | None = None
    enable_citations: bool | None = None
    max_content_tokens: int | None = None


class CodeExecutionTool(BaseModel):
    """Configuration for provider-native Code Execution sandbox tool capability."""

    language: str = "python"
    timeout: float | None = None


class MCPServerTool(BaseModel):
    """Configuration for provider-native or remote Model Context Protocol (MCP) server tool."""

    id: str = "mcp_server"
    url: str = ""
    authorization_token: str | None = None
    description: str | None = None


_NATIVE_TOOL_SETTINGS_BUILDERS: dict[type, Callable[[Any], dict[str, Any]]] = {
    WebSearchTool: lambda t: {
        "native_web_search": True,
        "web_search_config": t.model_dump(exclude_none=True),
    },
    WebFetchTool: lambda t: {
        "native_web_fetch": True,
        "web_fetch_config": t.model_dump(exclude_none=True),
    },
    CodeExecutionTool: lambda t: {
        "native_code_execution": True,
        "code_execution_config": t.model_dump(exclude_none=True),
    },
    MCPServerTool: lambda t: {
        "native_mcp_server": True,
        "mcp_server_config": t.model_dump(exclude_none=True),
    },
}

_NATIVE_TOOL_PROMPT_BUILDERS: dict[type, Callable[[Any], list[str]]] = {
    WebSearchTool: lambda _: ["Provider-native web search capability is enabled."],
    WebFetchTool: lambda _: ["Provider-native web fetch capability is enabled."],
    CodeExecutionTool: lambda _: [
        "Provider-native sandboxed code execution capability is enabled."
    ],
    MCPServerTool: lambda t: [f"Provider-native MCP server capability is enabled (id: {t.id})."],
}


def _extract_local_tools(local_obj: Any) -> list[AgentTool | Callable[..., Any]]:
    """Extract callable or Tool instances from polymorphic local capability/tool objects."""
    if not local_obj:
        return []
    if isinstance(local_obj, BaseCapability):
        return local_obj.get_tools()
    if isinstance(local_obj, Tool):
        return [local_obj]
    if callable(local_obj):
        return [Tool.from_function(local_obj)]
    if hasattr(local_obj, "get_tools") and callable(local_obj.get_tools):
        tools_val = local_obj.get_tools()
        if isinstance(tools_val, list):
            return [t for t in tools_val if isinstance(t, (AgentTool, Tool)) or callable(t)]
    if isinstance(local_obj, list):
        return [t for t in local_obj if isinstance(t, (AgentTool, Tool)) or callable(t)]
    return []


class NativeTool(BaseCapability):
    """Capability that configures and exposes provider-native server tools."""

    id: str = "native_tool"
    tool: WebSearchTool | WebFetchTool | CodeExecutionTool | MCPServerTool | BaseModel

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        """Return model runtime settings configuring the provider-native tool."""
        builder = _NATIVE_TOOL_SETTINGS_BUILDERS.get(type(self.tool))
        if builder is not None:
            return builder(self.tool)
        return {"native_tool": self.tool.model_dump(exclude_none=True)}

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        builder = _NATIVE_TOOL_PROMPT_BUILDERS.get(type(self.tool))
        return builder(self.tool) if builder is not None else []


class MCP(BaseCapability):
    """Provider-adaptive Model Context Protocol (MCP) capability supporting local and native servers."""

    id: str = "mcp"
    url: str | None = None
    native: bool | MCPServerTool = False
    local: Any = True

    def __init__(
        self,
        url: str | None = None,
        *,
        native: bool | MCPServerTool = False,
        local: Any = True,
    ) -> None:
        super().__init__(url=url, native=native, local=local)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        if self.local is False:
            return []
        return _extract_local_tools(self.local)

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        if self.native:
            if isinstance(self.native, MCPServerTool):
                return {
                    "native_mcp_server": True,
                    "mcp_server_config": self.native.model_dump(exclude_none=True),
                }
            return {
                "native_mcp_server": True,
                "mcp_server_config": {"url": self.url} if self.url else {},
            }
        return {}

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        target = self.url or (
            self.native.url if isinstance(self.native, MCPServerTool) else "local client"
        )
        return [f"Model Context Protocol (MCP) capability active (target: {target})."]


class WebSearch(BaseCapability):
    """Provider-adaptive Web Search capability supporting native provider search and local fallback."""

    id: str = "web_search"
    local: Any = False
    native: bool | WebSearchTool = True

    def __init__(
        self,
        *,
        local: Any = False,
        native: bool | WebSearchTool = True,
    ) -> None:
        super().__init__(local=local, native=native)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        if not self.local:
            return []
        if self.local is True or self.local == "duckduckgo":
            from devops_cli.ai.common_tools import duckduckgo_search_tool

            return [duckduckgo_search_tool()]
        return _extract_local_tools(self.local)

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        if self.native:
            if isinstance(self.native, WebSearchTool):
                return {
                    "native_web_search": True,
                    "web_search_config": self.native.model_dump(exclude_none=True),
                }
            return {"native_web_search": True, "web_search_config": {}}
        return {}

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.native:
            return ["Provider-native web search capability is enabled."]
        if self.local:
            return ["Local web search capability is enabled."]
        return []


class WebFetch(BaseCapability):
    """Provider-adaptive Web Fetch capability supporting native provider fetch and local fallback."""

    id: str = "web_fetch"
    allowed_domains: list[str] | None = None
    blocked_domains: list[str] = Field(default_factory=list)
    local: Any = False
    native: bool | WebFetchTool = True

    def __init__(
        self,
        *,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        local: Any = False,
        native: bool | WebFetchTool = True,
    ) -> None:
        super().__init__(
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains or [],
            local=local,
            native=native,
        )

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        if not self.local:
            return []
        if self.local is True:
            from devops_cli.ai.common_tools import web_fetch_tool

            return [web_fetch_tool(allowed_domains=self.allowed_domains)]
        return _extract_local_tools(self.local)

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        if self.native:
            if isinstance(self.native, WebFetchTool):
                return {
                    "native_web_fetch": True,
                    "web_fetch_config": self.native.model_dump(exclude_none=True),
                }
            config: dict[str, Any] = {}
            if self.allowed_domains:
                config["allowed_domains"] = self.allowed_domains
            if self.blocked_domains:
                config["blocked_domains"] = self.blocked_domains
            return {"native_web_fetch": True, "web_fetch_config": config}
        return {}

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.native:
            return ["Provider-native web fetch capability is enabled."]
        if self.local:
            return ["Local web fetch capability is enabled."]
        return []


class Thinking(BaseCapability):
    """Capability configuring unified thinking and reasoning effort across LLM providers."""

    id: str = "thinking"
    effort: str | bool = "medium"
    budget_tokens: int | None = None
    include_thoughts: bool = True
    include_encrypted_content: bool = False
    reasoning_format: str = "parsed"

    def __init__(
        self,
        effort: str | bool = "medium",
        *,
        budget_tokens: int | None = None,
        include_thoughts: bool = True,
        include_encrypted_content: bool = False,
        reasoning_format: str = "parsed",
    ) -> None:
        super().__init__(
            effort=effort,
            budget_tokens=budget_tokens,
            include_thoughts=include_thoughts,
            include_encrypted_content=include_encrypted_content,
            reasoning_format=reasoning_format,
        )

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        settings: dict[str, Any] = {
            "thinking": self.effort if isinstance(self.effort, (str, bool)) else True,
            "include_thoughts": self.include_thoughts,
            "reasoning_format": self.reasoning_format,
        }
        if self.budget_tokens is not None:
            settings["budget_tokens"] = self.budget_tokens
            settings["thinking_budget_tokens"] = self.budget_tokens
        if self.include_encrypted_content:
            settings["include_encrypted_content"] = True
            settings["xai_include_encrypted_content"] = True
        return settings

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return [f"Thinking capability is enabled (effort={self.effort})."]


class HandleDeferredToolCalls(BaseCapability):
    """Capability providing inline handling of deferred tool calls and approvals."""

    id: str = "handle_deferred_tool_calls"
    handler: Any = None

    def __init__(
        self,
        handler: Callable[..., DeferredToolResults | None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(handler=handler or kwargs.get("handler"), **kwargs)

    def handle_deferred(
        self, requests: DeferredToolRequests, ctx: RunContext[Any] | None = None
    ) -> DeferredToolResults | None:
        """Execute the deferred tool call handler callback."""
        if not callable(self.handler):
            return None
        import inspect

        sig = inspect.signature(self.handler)
        res: Any = (
            self.handler(ctx, requests)
            if (len(sig.parameters) >= 2 and ctx is not None)
            else self.handler(requests)
        )
        if isinstance(res, DeferredToolResults):
            return res
        return None


class Capability(BaseCapability):
    """Concrete capability bundling instructions, tools, settings, and progressive disclosure."""

    instructions: str = ""
    tools: list[AgentTool | Callable[..., Any]] = Field(default_factory=list)
    model_settings: dict[str, Any] = Field(default_factory=dict)

    def tool(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to register a tool on this capability."""
        self.tools.append(func)
        return func

    def tool_plain(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to register a plain tool on this capability."""
        self.tools.append(func)
        return func

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        return list(self.tools)

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.instructions:
            return [self.instructions]
        return []

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        return dict(self.model_settings)


class SystemReminders(BaseCapability):
    """Capability that combats instruction fade by re-injecting targeted behavioral guidance on a cadence."""

    id: str = "system_reminders"
    reminders: list[str] = Field(default_factory=list)
    cadence: int = 3
    condition: Any = None
    _turn_counter: int = 0

    def __init__(
        self,
        reminders: list[str] | None = None,
        *,
        cadence: int = 3,
        condition: Callable[[RunContext[Any], int], bool] | None = None,
        id: str = "system_reminders",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            id=id,
            reminders=reminders or [],
            cadence=cadence,
            condition=condition,
            **kwargs,
        )

    def should_remind(self, ctx: RunContext[Any], turn: int) -> bool:
        """Determine whether reminders should be injected on the current turn."""
        if callable(self.condition):
            return bool(self.condition(ctx, turn))
        return self.cadence > 0 and (turn % self.cadence == 0)

    def get_reminders(self, ctx: RunContext[Any], turn: int) -> list[str]:
        """Return reminders to inject if the cadence or condition is satisfied."""
        if self.should_remind(ctx, turn):
            return list(self.reminders)
        return []

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if ctx is not None:
            self._turn_counter += 1
            return self.get_reminders(ctx, self._turn_counter)
        return list(self.reminders)


class Instrumentation(BaseCapability):
    """Capability providing OpenTelemetry distributed span tracing and metric instrumentation for agents."""

    id: str = "instrumentation"
    tracer_name: str = "devops_cli.agent"
    record_spans: bool = True
    record_metrics: bool = True

    def get_hooks(self) -> AgentHooks | None:
        """Bind OpenTelemetry tracing hooks into agent execution."""

        def before_tool(ctx: RunContext[Any], tool_name: str, args: dict[str, Any]) -> None:
            pass

        def after_tool(ctx: RunContext[Any], tool_name: str, result: Any) -> None:
            pass

        return AgentHooks(before_tool_execute=[before_tool], after_tool_execute=[after_tool])

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return []


class UseThreadExecutor(BaseCapability):
    """Capability that executes synchronous tool calls in a dedicated, bounded ThreadPoolExecutor."""

    id: str = "use_thread_executor"
    executor: Any = None
    max_workers: int = 16
    thread_name_prefix: str = "agent-worker"

    def __init__(
        self,
        executor: Any = None,
        *,
        max_workers: int = 16,
        thread_name_prefix: str = "agent-worker",
        id: str = "use_thread_executor",
        **kwargs: Any,
    ) -> None:
        if executor is None:
            from concurrent.futures import ThreadPoolExecutor

            executor = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix=thread_name_prefix
            )
        super().__init__(
            id=id,
            executor=executor,
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
            **kwargs,
        )

    def run_sync(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run synchronous function in the executor and return its result."""
        from functools import partial

        future = self.executor.submit(partial(func, *args, **kwargs))
        return future.result()


ThreadExecutor = UseThreadExecutor


class ModelSelectionContext[DepsT](BaseModel):
    """Runtime context provided to dynamic model selector callables."""

    deps: DepsT | None = None
    session_id: str = ""
    turn: int = 1
    step_number: int = 1
    current_model: str = ""


class SelectModel(BaseCapability):
    """Capability that dynamically selects the LLM model at runtime for each step."""

    id: str = "select_model"
    selector: Any = None

    def __init__(
        self,
        selector: Callable[..., str] | None = None,
        *,
        id: str = "select_model",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, selector=selector or kwargs.get("selector"), **kwargs)

    def select_model(
        self, ctx: ModelSelectionContext[Any] | RunContext[Any] | None = None
    ) -> str | None:
        """Execute selector to resolve dynamic model ID."""
        if not callable(self.selector):
            return None
        if ctx is None:
            return str(self.selector(ModelSelectionContext[Any]()))
        if isinstance(ctx, RunContext):
            sel_ctx: ModelSelectionContext[Any] = ModelSelectionContext(
                deps=ctx.deps,
                session_id=ctx.session_id,
                current_model=ctx.model,
            )
            return str(self.selector(sel_ctx))
        return str(self.selector(ctx))


class ModelResolutionContext[DepsT](BaseModel):
    """Runtime context provided to dynamic model ID resolvers."""

    deps: DepsT | None = None
    session_id: str = ""
    tenant_id: str | None = None
    model_id: str = ""


class ResolveModelId(BaseCapability):
    """Capability that intercepts and resolves custom or tenant-specific model identifiers."""

    id: str = "resolve_model_id"
    resolver: Any = None

    def __init__(
        self,
        resolver: Callable[..., Any] | None = None,
        *,
        id: str = "resolve_model_id",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, resolver=resolver or kwargs.get("resolver"), **kwargs)

    def resolve(
        self,
        model_id: str,
        ctx: ModelResolutionContext[Any] | RunContext[Any] | None = None,
    ) -> Any | None:
        """Resolve a model identifier to a concrete model ID or instance."""
        if not callable(self.resolver):
            return None
        res_ctx: ModelResolutionContext[Any]
        if ctx is None:
            res_ctx = ModelResolutionContext[Any](model_id=model_id)
        elif isinstance(ctx, RunContext):
            res_ctx = ModelResolutionContext[Any](
                deps=ctx.deps,
                session_id=ctx.session_id,
                model_id=model_id,
            )
        else:
            res_ctx = ctx
        return self.resolver(res_ctx, model_id)


class PrepareTools(BaseCapability):
    """Capability that dynamically prepares, filters, or modifies available tool definitions."""

    id: str = "prepare_tools"
    prepare_fn: Any = None

    def __init__(
        self,
        prepare_fn: Callable[..., Any] | None = None,
        *,
        id: str = "prepare_tools",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, prepare_fn=prepare_fn or kwargs.get("prepare_fn"), **kwargs)

    def prepare_tools(
        self,
        ctx: RunContext[Any],
        tools: list[Any],
    ) -> list[Any]:
        """Execute prepare_fn to filter or modify tool definitions."""
        if not callable(self.prepare_fn):
            return tools
        result = self.prepare_fn(ctx, tools)
        return result if result is not None else tools


class PrefixTools(BaseCapability):
    """Capability that prefixes all tools from a capability with a namespace prefix to prevent collisions."""

    id: str = "prefix_tools"
    capability: Any = None
    prefix: str = ""

    def __init__(
        self,
        capability: BaseCapability | None = None,
        prefix: str = "",
        *,
        id: str = "prefix_tools",
        **kwargs: Any,
    ) -> None:
        cap = capability or kwargs.get("capability")
        pfx = prefix or kwargs.get("prefix", "")
        super().__init__(id=id, capability=cap, prefix=pfx, **kwargs)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        """Return prefixed tools from the wrapped capability."""
        if self.capability is None:
            return []
        raw_tools = self.capability.get_tools()
        prefixed_tools: list[AgentTool | Callable[..., Any]] = []
        for t in raw_tools:
            if isinstance(t, Tool):
                new_name = (
                    f"{self.prefix}_{t.name}"
                    if not t.name.startswith(f"{self.prefix}_")
                    else t.name
                )
                prefixed_tools.append(
                    Tool(
                        func=t.func,
                        name=new_name,
                        description=t.description,
                        parameters=t.parameters,
                        takes_ctx=t.takes_ctx,
                        timeout=t.timeout,
                        max_retries=t.max_retries,
                        requires_approval=t.requires_approval,
                        include_return_schema=t.include_return_schema,
                    )
                )
            elif callable(t):
                base_name = getattr(t, "__name__", "tool")
                new_name = f"{self.prefix}_{base_name}"
                prefixed_tools.append(Tool.from_function(t, name=new_name))
            else:
                prefixed_tools.append(t)
        return prefixed_tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return self.capability.get_system_prompt_additions(ctx) if self.capability else []

    def get_hooks(self) -> AgentHooks | None:
        return self.capability.get_hooks() if self.capability else None

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        return self.capability.get_model_settings(ctx) if self.capability else {}


class IncludeToolReturnSchemas(BaseCapability):
    """Capability that includes return value JSON schemas in tool definitions sent to the model."""

    id: str = "include_tool_return_schemas"
    include_return_schema: bool = True

    def __init__(
        self,
        include_return_schema: bool = True,
        *,
        id: str = "include_tool_return_schemas",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, include_return_schema=include_return_schema, **kwargs)

    def prepare_tools(
        self,
        ctx: RunContext[Any],
        tools: list[Any],
    ) -> list[Any]:
        """Apply include_return_schema to all tool definitions."""
        for t in tools:
            if hasattr(t, "include_return_schema"):
                setattr(t, "include_return_schema", self.include_return_schema)
        return tools


class SetToolMetadata(BaseCapability):
    """Capability that merges custom key-value metadata pairs onto tool definitions."""

    id: str = "set_tool_metadata"
    capability: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(
        self,
        metadata: dict[str, Any] | None = None,
        capability: BaseCapability | None = None,
        *,
        id: str = "set_tool_metadata",
        **kwargs: Any,
    ) -> None:
        cap = capability or kwargs.get("capability")
        meta = metadata if metadata is not None else kwargs.get("metadata", {})
        super().__init__(id=id, capability=cap, metadata=meta, **kwargs)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        """Return tools from the wrapped capability with merged metadata."""
        if self.capability is None:
            return []
        raw_tools = self.capability.get_tools()
        tools_with_meta: list[AgentTool | Callable[..., Any]] = []
        for t in raw_tools:
            if isinstance(t, Tool):
                merged_meta = {**getattr(t, "metadata", {}), **self.metadata}
                tools_with_meta.append(
                    Tool(
                        func=t.func,
                        name=t.name,
                        description=t.description,
                        parameters=t.parameters,
                        takes_ctx=t.takes_ctx,
                        timeout=t.timeout,
                        max_retries=t.max_retries,
                        requires_approval=t.requires_approval,
                        include_return_schema=t.include_return_schema,
                        metadata=merged_meta,
                    )
                )
            elif callable(t):
                tools_with_meta.append(Tool.from_function(t, metadata=dict(self.metadata)))
            else:
                tools_with_meta.append(t)
        return tools_with_meta

    def prepare_tools(
        self,
        ctx: RunContext[Any],
        tools: list[Any],
    ) -> list[Any]:
        """Merge metadata into any tools passed at runtime."""
        for t in tools:
            if hasattr(t, "metadata") and isinstance(t.metadata, dict):
                t.metadata.update(self.metadata)
        return tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return self.capability.get_system_prompt_additions(ctx) if self.capability else []

    def get_hooks(self) -> AgentHooks | None:
        return self.capability.get_hooks() if self.capability else None

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        return self.capability.get_model_settings(ctx) if self.capability else {}


class RaiseContentFilterError(BaseCapability):
    """Capability that enforces raising a ContentFilterError whenever a model response is filtered."""

    id: str = "raise_content_filter_error"

    def __init__(
        self,
        *,
        id: str = "raise_content_filter_error",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)

    def check_response(self, response: Any) -> None:
        """Inspect model response and raise ContentFilterError if finish_reason is content_filter."""
        finish_reason = getattr(response, "finish_reason", None)
        if finish_reason is None and isinstance(response, dict):
            finish_reason = response.get("finish_reason") or response.get("stop_reason")
        if str(finish_reason).lower() in ("content_filter", "safety", "recitation", "block"):
            from devops_cli.exceptions.ai import ContentFilterError

            msg = "Model response was blocked or filtered by upstream content safety filter"
            raise ContentFilterError(message=msg, body=response)


class ReinjectSystemPrompt(BaseCapability):
    """Capability that ensures an agent's configured system prompt is present in message history."""

    id: str = "reinject_system_prompt"
    replace_existing: bool = False

    def __init__(
        self,
        replace_existing: bool = False,
        *,
        id: str = "reinject_system_prompt",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, replace_existing=replace_existing, **kwargs)

    def reinject(
        self,
        messages: list[Any],
        system_prompt: str,
    ) -> list[Any]:
        """Reinject system_prompt into the message history if missing or if replace_existing is True."""
        if not system_prompt or not system_prompt.strip():
            return messages

        has_system = False
        filtered_messages: list[Any] = []

        for m in messages:
            is_sys = False
            if isinstance(m, dict) and m.get("role") == "system":
                is_sys = True
            elif hasattr(m, "role") and getattr(m, "role") == "system":
                is_sys = True
            elif hasattr(m, "part_kind") and getattr(m, "part_kind") == "system-prompt":
                is_sys = True

            if is_sys:
                has_system = True
                if not self.replace_existing:
                    filtered_messages.append(m)
            else:
                filtered_messages.append(m)

        if self.replace_existing or not has_system:
            sys_msg: dict[str, str] = {"role": "system", "content": system_prompt.strip()}
            return [sys_msg, *filtered_messages]

        return messages


class ProcessHistory(BaseCapability):
    """Capability that intercepts and transforms message history before model execution."""

    id: str = "process_history"
    processor: Any = None

    def __init__(
        self,
        processor: Callable[..., Any] | None = None,
        *,
        id: str = "process_history",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, processor=processor or kwargs.get("processor"), **kwargs)

    def process_history(
        self,
        messages: list[Any],
        ctx: RunContext[Any] | None = None,
    ) -> list[Any]:
        """Apply the configured processor to transform or trim message history."""
        if not callable(self.processor):
            return messages

        sig = inspect.signature(self.processor)
        if len(sig.parameters) >= 2 and ctx is not None:
            res = self.processor(ctx, messages)
        elif len(sig.parameters) >= 2 and ctx is None:
            res = self.processor(RunContext(), messages)
        else:
            res = self.processor(messages)
        return res if res is not None else messages


class AgentStreamEvent(BaseModel):
    """An event emitted during streaming model execution or tool invocation."""

    event_kind: str = "token"
    content: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessEventStream(BaseCapability):
    """Capability that intercepts, observes, or transforms the event stream during agent execution."""

    id: str = "process_event_stream"
    handler: Any = None

    def __init__(
        self,
        handler: Callable[..., Any] | None = None,
        *,
        id: str = "process_event_stream",
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, handler=handler or kwargs.get("handler"), **kwargs)

    async def handle_stream(
        self,
        events: Any,
        ctx: RunContext[Any] | None = None,
    ) -> Any:
        """Forward events to handler or iterate through generator."""
        if not callable(self.handler):
            return events

        sig = inspect.signature(self.handler)
        if len(sig.parameters) >= 2 and ctx is not None:
            res = self.handler(ctx, events)
        elif len(sig.parameters) >= 2 and ctx is None:
            res = self.handler(RunContext(), events)
        else:
            res = self.handler(events)

        if inspect.iscoroutine(res):
            return await res
        return res
