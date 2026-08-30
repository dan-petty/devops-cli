"""Agent capability interfaces, progressive disclosure, and provider-native tool bindings."""

from __future__ import annotations

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


class NativeTool(BaseCapability):
    """Capability that configures and exposes provider-native server tools."""

    id: str = "native_tool"
    tool: WebSearchTool | WebFetchTool | CodeExecutionTool | MCPServerTool | BaseModel

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        """Return model runtime settings configuring the provider-native tool."""
        if isinstance(self.tool, WebSearchTool):
            return {
                "native_web_search": True,
                "web_search_config": self.tool.model_dump(exclude_none=True),
            }
        elif isinstance(self.tool, WebFetchTool):
            return {
                "native_web_fetch": True,
                "web_fetch_config": self.tool.model_dump(exclude_none=True),
            }
        elif isinstance(self.tool, CodeExecutionTool):
            return {
                "native_code_execution": True,
                "code_execution_config": self.tool.model_dump(exclude_none=True),
            }
        elif isinstance(self.tool, MCPServerTool):
            return {
                "native_mcp_server": True,
                "mcp_server_config": self.tool.model_dump(exclude_none=True),
            }
        return {"native_tool": self.tool.model_dump(exclude_none=True)}

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if isinstance(self.tool, WebSearchTool):
            return ["Provider-native web search capability is enabled."]
        elif isinstance(self.tool, WebFetchTool):
            return ["Provider-native web fetch capability is enabled."]
        elif isinstance(self.tool, CodeExecutionTool):
            return ["Provider-native sandboxed code execution capability is enabled."]
        elif isinstance(self.tool, MCPServerTool):
            return [f"Provider-native MCP server capability is enabled (id: {self.tool.id})."]
        return []


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
        if hasattr(self.local, "get_tools") and callable(self.local.get_tools):
            tools_val = self.local.get_tools()
            if isinstance(tools_val, list):
                return [t for t in tools_val if isinstance(t, Tool) or callable(t)]
        if isinstance(self.local, list):
            return [t for t in self.local if isinstance(t, Tool) or callable(t)]
        return []

    def get_model_settings(self, ctx: RunContext[Any] | None = None) -> dict[str, Any]:
        if self.native:
            if isinstance(self.native, MCPServerTool):
                return {
                    "native_mcp_server": True,
                    "mcp_server_config": self.native.model_dump(exclude_none=True),
                }
            elif self.url:
                return {
                    "native_mcp_server": True,
                    "mcp_server_config": {"url": self.url, "id": "mcp_server"},
                }
        return {}

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        target = self.url or (
            self.native.url if isinstance(self.native, MCPServerTool) else "local client"
        )
        return [f"Model Context Protocol (MCP) capability active (target: {target})."]


class WebSearch(BaseCapability):
    """Provider-adaptive Web Search capability supporting native provider search and local fallbacks."""

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
        elif hasattr(self.local, "get_tools") and callable(self.local.get_tools):
            tools_val = self.local.get_tools()
            if isinstance(tools_val, list):
                return [t for t in tools_val if isinstance(t, Tool) or callable(t)]
        elif isinstance(self.local, (Tool, BaseCapability)) or callable(self.local):
            if isinstance(self.local, BaseCapability):
                return self.local.get_tools()
            elif isinstance(self.local, Tool):
                return [self.local]
            elif callable(self.local):
                return [Tool.from_function(self.local)]
        elif isinstance(self.local, list):
            return [t for t in self.local if isinstance(t, Tool) or callable(t)]
        return []

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
        elif hasattr(self.local, "get_tools") and callable(self.local.get_tools):
            tools_val = self.local.get_tools()
            if isinstance(tools_val, list):
                return [t for t in tools_val if isinstance(t, Tool) or callable(t)]
        elif isinstance(self.local, (Tool, BaseCapability)) or callable(self.local):
            if isinstance(self.local, BaseCapability):
                return self.local.get_tools()
            elif isinstance(self.local, Tool):
                return [self.local]
            elif callable(self.local):
                return [Tool.from_function(self.local)]
        elif isinstance(self.local, list):
            return [t for t in self.local if isinstance(t, Tool) or callable(t)]
        return []

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
