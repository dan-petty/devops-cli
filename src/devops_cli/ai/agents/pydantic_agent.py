"""Fully-functional Pydantic Agent with tools, reasoning/thinking, and streaming.

Example:
    >>> from devops_cli.ai.agents.pydantic_agent import PydanticAgent
    >>> from devops_cli.ai.client import LLMClient
    >>>
    >>> client = LLMClient()
    >>> agent = PydanticAgent(
    ...     client=client,
    ...     name="Architect",
    ...     system_prompt="Review system architecture and modular boundaries.",
    ... )
    >>> response = agent.run("Evaluate component dependencies in src/devops_cli/core/")
"""

from __future__ import annotations

import inspect
import json
import re
from collections import defaultdict
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from devops_cli.ai.agents.memory import AgentMemory
from devops_cli.ai.client import LLMClient
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import DEFAULT_AGENT_MAX_TURNS
from devops_cli.exceptions import ModelRetry, SecurityError, UnexpectedModelBehavior
from devops_cli.models.ai import ChatMessage

_TOOL_PROTOCOL_TEMPLATE = load_task_prompt("tool_execution_protocol.md")
_TOOL_FEEDBACK_TEMPLATE = load_task_prompt("agent_tool_feedback.md")
_TOOL_ALREADY_CALLED_PROMPT = load_task_prompt("agent_tool_already_called.md")
_INVOKE_TOOL_REQUEST_TEMPLATE = load_task_prompt("agent_invoke_tool_request.md")
_DIRECT_RESPONSE_FROM_TOOLS_PROMPT = load_task_prompt("agent_direct_response_from_tools.md")
_DIRECT_RESPONSE_FROM_REASONING_PROMPT = load_task_prompt("agent_direct_response_from_reasoning.md")

T = TypeVar("T", bound=BaseModel)
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


class AgentTool(BaseModel):
    """Encapsulates an executable tool available to a PydanticAgent."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = Field(default_factory=dict)
    takes_ctx: bool = False
    timeout: float | None = None
    max_retries: int | None = None

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
        timeout: float | None = None,
        max_retries: int | None = None,
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
            timeout=timeout,
            max_retries=max_retries,
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
            timeout=timeout,
            max_retries=max_retries,
        )


class ToolCall(BaseModel):
    """Record of a tool call executed during an agent run."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse[T](BaseModel):
    """Structured response returned by a PydanticAgent run."""

    content: str
    data: T | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    thoughts: list[str] = Field(default_factory=list)
    turns: int = 1
    backend_info: str | None = None
    usage: AgentUsage = Field(default_factory=AgentUsage)
    messages: list[ChatMessage] = Field(default_factory=list)
    new_messages_list: list[ChatMessage] = Field(default_factory=list)

    def all_messages(self) -> list[ChatMessage]:
        """Return the complete message history including prior turns and tool exchanges."""
        return list(self.messages)

    def new_messages(self) -> list[ChatMessage]:
        """Return messages generated in this specific agent run."""
        return list(self.new_messages_list)


def _execute_single_tool(
    tool_obj: AgentTool,
    tool_name: str,
    args: dict[str, Any],
    tool_calls: list[ToolCall],
    ctx: RunContext[Any] | None = None,
    hooks: AgentHooks | None = None,
    default_timeout: float | None = None,
) -> tuple[str, dict[str, Any], Any]:
    """Execute a single validated tool invocation with deduplication, timeouts, and hooks."""
    import concurrent.futures

    try:
        clean_args = tool_obj.validate_args(args)
    except Exception as exc:
        return "validation_error", args, f"Tool argument validation error for {tool_name}: {exc}"

    prior = next(
        (c for c in tool_calls if c.tool_name == tool_name and c.arguments == clean_args), None
    )
    if prior is not None:
        return "already_called", clean_args, None

    if hooks and ctx is not None:
        for h_bt in hooks.before_tool_execute:
            try:
                h_bt(ctx, tool_name, clean_args)
            except Exception:
                pass

    try:
        t_limit = tool_obj.timeout if tool_obj.timeout is not None else default_timeout
        if t_limit and t_limit > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool_obj.execute, ctx=ctx, **clean_args)
                tool_result = future.result(timeout=t_limit)
        else:
            tool_result = tool_obj.execute(ctx=ctx, **clean_args)
        if hooks and ctx is not None:
            for h_at in hooks.after_tool_execute:
                try:
                    h_at(ctx, tool_name, clean_args, tool_result)
                except Exception:
                    pass
    except (TimeoutError, concurrent.futures.TimeoutError) as timeout_exc:
        t_sec = tool_obj.timeout if tool_obj.timeout is not None else default_timeout
        timeout_msg = f"Timed out after {t_sec} seconds."
        if hooks and ctx is not None:
            for h_err in hooks.on_tool_error:
                try:
                    h_err(ctx, tool_name, timeout_exc)
                except Exception:
                    pass
        return "retry_requested", clean_args, timeout_msg
    except ModelRetry as retry_exc:
        if hooks and ctx is not None:
            for h_err in hooks.on_tool_error:
                try:
                    h_err(ctx, tool_name, retry_exc)
                except Exception:
                    pass
        return "retry_requested", clean_args, str(retry_exc)
    except Exception as exc:
        if hooks and ctx is not None:
            for h_err in hooks.on_tool_error:
                try:
                    h_err(ctx, tool_name, exc)
                except Exception:
                    pass
        tool_result = f"Tool execution error for {tool_name}: {exc}"
    return "ok", clean_args, tool_result


def _detect_tool_intent(
    tools: dict[str, AgentTool],
    final_output: str,
    all_thoughts: list[str],
) -> str | None:
    """Detect if agent output or reasoning thoughts expressed intent to invoke a known tool."""
    if not tools:
        return None
    search_text = f"{final_output}\n{' '.join(all_thoughts)}"
    for t_name in tools:
        escaped_name = re.escape(t_name)
        pattern = rf"\b(?:call|invoke|use|run|execute)\s+(?:tool\s+)?`?{escaped_name}`?\b"
        if re.search(pattern, search_text, re.IGNORECASE):
            return t_name
    return None


_DELIBERATION_PREFIXES: tuple[str, ...] = (
    "the tool returned",
    "we need to interpret",
    "we need to decide",
    "we should double-check",
    "let's search",
    "we need to scan",
    "let's recall",
    "not sure. we need",
)


def _is_scratchpad_deliberation(final_output: str) -> bool:
    """Check if agent output is raw tool JSON or internal scratchpad deliberation."""
    if not final_output:
        return True
    is_tool_json = (
        final_output.startswith('{"tool"')
        or final_output.startswith('```json\n{"tool"')
        or ('"tool":' in final_output and '"arguments":' in final_output)
    )
    if is_tool_json:
        return True
    return final_output.lower().startswith(_DELIBERATION_PREFIXES)


def _record_and_broadcast_thoughts(
    thoughts: list[str],
    all_thoughts: list[str],
    on_thought: Callable[[str], None] | None,
) -> None:
    """Append new thoughts to history and broadcast to callback."""
    for t in thoughts:
        if t and t not in all_thoughts:
            all_thoughts.append(t)
            if on_thought:
                on_thought(t)


def _resolve_fallback_output(
    final_output: str,
    tool_calls: list[ToolCall],
    all_thoughts: list[str],
) -> str:
    """Resolve final response string, falling back to tool outputs or thoughts if empty."""
    if final_output and not _is_scratchpad_deliberation(final_output):
        return final_output
    if final_output and not (
        final_output.startswith('{"tool"') or final_output.startswith('```json\n{"tool"')
    ):
        return final_output
    if tool_calls:
        last_call = tool_calls[-1]
        if last_call.result is not None:
            return str(last_call.result)
    if all_thoughts:
        return all_thoughts[-1]
    return final_output


def _create_tool_retry_message(detected_tool: str, tool_obj: AgentTool) -> ChatMessage:
    """Construct user prompt asking model to output structured tool call invocation."""
    example_args = {k: f"<{k}>" for k in tool_obj.parameters}
    example_json = json.dumps(
        {"tool": detected_tool, "arguments": example_args}, separators=(",", ":")
    )
    content = _INVOKE_TOOL_REQUEST_TEMPLATE.format(
        detected_tool=detected_tool,
        example_json=example_json,
    )
    return ChatMessage(role="user", content=content)


class PydanticAgent[T, DepsT = Any]:
    """Agent built on Pydantic models supporting tools, memory, reasoning, streaming, and context."""

    @classmethod
    def from_spec(
        cls,
        spec: AgentSpec | dict[str, Any] | str | Path,
        *,
        client: LLMClient | None = None,
        tools: list[AgentTool | Callable[..., Any]] | None = None,
        **overrides: Any,
    ) -> PydanticAgent[Any, Any]:
        """Construct a PydanticAgent from an AgentSpec, YAML string, or spec file path."""
        if isinstance(spec, (str, Path)):
            p = Path(spec)
            if p.exists() and p.is_file():
                agent_spec = AgentSpec.from_file(p)
            elif isinstance(spec, str) and ("\n" in spec or ":" in spec):
                agent_spec = AgentSpec.from_yaml(spec)
            else:
                agent_spec = AgentSpec(name=str(spec))
        elif isinstance(spec, dict):
            agent_spec = AgentSpec.model_validate(spec)
        else:
            agent_spec = spec

        name = overrides.get("name", agent_spec.name or "Assistant")
        model = overrides.get("model", agent_spec.model)
        if client is not None:
            agent_client = client
        elif model:
            from devops_cli.config.settings import AIConfig

            agent_client = LLMClient(config=AIConfig(model=model))
        else:
            agent_client = LLMClient()

        inst = agent_spec.instructions
        if isinstance(inst, list):
            system_prompt = "\n\n".join(inst)
        elif isinstance(inst, str):
            system_prompt = inst
        else:
            system_prompt = "You are a helpful DevOps assistant."

        if "system_prompt" in overrides:
            system_prompt = overrides["system_prompt"]

        return cls(
            client=agent_client,
            system_prompt=system_prompt,
            name=name,
            tools=tools,
        )

    def __init__(
        self,
        client: LLMClient,
        system_prompt: str = "You are a helpful DevOps assistant.",
        *,
        name: str = "Assistant",
        output_schema: type[T] | None = None,
        tools: list[AgentTool | Callable[..., Any]] | None = None,
        memory: AgentMemory | None = None,
        deps_type: type[DepsT] | None = None,
        hooks: AgentHooks | None = None,
        capabilities: list[BaseCapability] | None = None,
        toolsets: list[FunctionToolset[Any]] | None = None,
        retries: int | AgentRetries | dict[str, int] | None = None,
        tool_timeout: float | None = None,
    ) -> None:
        self.client = client
        self.system_prompt = system_prompt
        self.name = name
        self.output_schema = output_schema
        self.memory: AgentMemory = memory or AgentMemory(session_id=name)
        self.deps_type = deps_type
        self.hooks = hooks or AgentHooks()
        self.capabilities: list[BaseCapability] = list(capabilities or [])
        self.toolsets: list[FunctionToolset[Any]] = list(toolsets or [])
        self.tool_timeout = tool_timeout
        if isinstance(retries, int):
            self.retries = AgentRetries(tools=retries, output=retries)
        elif isinstance(retries, dict):
            self.retries = AgentRetries.model_validate(retries)
        elif isinstance(retries, AgentRetries):
            self.retries = retries
        else:
            self.retries = AgentRetries()
        self._tools: dict[str, AgentTool] = {}
        self._dynamic_system_prompts: list[Callable[..., str]] = []
        self._output_validators: list[Callable[..., Any]] = []

        if tools:
            for tool in tools:
                self.add_tool(tool)

        # Register tools from toolsets
        for ts in self.toolsets:
            for ts_tool in ts.get_tools():
                self.add_tool(ts_tool)

        # Register non-deferred capability tools and hooks
        for cap in self.capabilities:
            if not cap.defer_loading:
                for cap_tool in cap.get_tools():
                    self.add_tool(cap_tool)
                cap_hooks = cap.get_hooks()
                if cap_hooks:
                    self.hooks.before_model_request.extend(cap_hooks.before_model_request)
                    self.hooks.after_model_request.extend(cap_hooks.after_model_request)
                    self.hooks.before_tool_execute.extend(cap_hooks.before_tool_execute)
                    self.hooks.after_tool_execute.extend(cap_hooks.after_tool_execute)
                    self.hooks.on_tool_error.extend(cap_hooks.on_tool_error)

        # Register load_capability tool if any capability is deferred
        if any(cap.defer_loading for cap in self.capabilities):
            self._register_load_capability_tool()

    def _register_load_capability_tool(self) -> None:
        def load_capability(ctx: RunContext[Any], capability_id: str) -> str:
            """Load an on-demand capability by ID, unlocking its tools, instructions, and hooks."""
            matching = next(
                (c for c in self.capabilities if c.id == capability_id and c.defer_loading), None
            )
            if not matching:
                avail = [c.id for c in self.capabilities if c.defer_loading]
                return f"Capability '{capability_id}' not found. Available on-demand: {avail}"
            ctx.loaded_capability_ids.add(capability_id)
            for t in matching.get_tools():
                self.add_tool(t)
            cap_hooks = matching.get_hooks()
            if cap_hooks:
                self.hooks.before_model_request.extend(cap_hooks.before_model_request)
                self.hooks.after_model_request.extend(cap_hooks.after_model_request)
                self.hooks.before_tool_execute.extend(cap_hooks.before_tool_execute)
                self.hooks.after_tool_execute.extend(cap_hooks.after_tool_execute)
                self.hooks.on_tool_error.extend(cap_hooks.on_tool_error)
            additions = matching.get_system_prompt_additions(ctx=ctx)
            inst = (" " + " ".join(additions)) if additions else ""
            return f"Capability '{capability_id}' loaded successfully.{inst}"

        self.add_tool(load_capability)

    def tool(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        strict: bool | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Any:
        """Decorator to register a tool function on this agent with optional timeout/metadata."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add_tool(
                Tool.from_function(
                    fn,
                    name=name,
                    description=description,
                    strict=strict,
                    timeout=timeout,
                    max_retries=max_retries,
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
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Any:
        """Decorator to register a plain function tool (without context parameter)."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add_tool(
                Tool.from_function(
                    fn,
                    name=name,
                    description=description,
                    takes_ctx=False,
                    strict=strict,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            )
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    def system_prompt_fn(self, func: Callable[..., str]) -> Callable[..., str]:
        """Decorator to register a dynamic system prompt function."""
        self._dynamic_system_prompts.append(func)
        return func

    def output_validator(
        self, func: Callable[[RunContext[DepsT], T], T] | Callable[[T], T]
    ) -> Callable[..., T]:
        """Decorator to register an output validation callback that can raise ModelRetry."""
        self._output_validators.append(func)
        return func

    def before_model_request(
        self, func: Callable[[RunContext[DepsT], list[ChatMessage]], None]
    ) -> Callable[..., None]:
        """Decorator to register a hook fired before model requests."""
        self.hooks.before_model_request.append(func)
        return func

    def after_model_request(
        self, func: Callable[[RunContext[DepsT], str], None]
    ) -> Callable[..., None]:
        """Decorator to register a hook fired after model responses."""
        self.hooks.after_model_request.append(func)
        return func

    def before_tool_execute(
        self, func: Callable[[RunContext[DepsT], str, dict[str, Any]], None]
    ) -> Callable[..., None]:
        """Decorator to register a hook fired before tool execution."""
        self.hooks.before_tool_execute.append(func)
        return func

    def after_tool_execute(
        self, func: Callable[[RunContext[DepsT], str, dict[str, Any], Any], None]
    ) -> Callable[..., None]:
        """Decorator to register a hook fired after tool execution."""
        self.hooks.after_tool_execute.append(func)
        return func

    def on_tool_error(
        self, func: Callable[[RunContext[DepsT], str, Exception], None]
    ) -> Callable[..., None]:
        """Decorator to register a hook fired when a tool raises an error."""
        self.hooks.on_tool_error.append(func)
        return func

    def add_tool(self, tool: AgentTool | Callable[..., Any]) -> None:
        """Register a tool callback or AgentTool instance."""
        if isinstance(tool, AgentTool):
            self._tools[tool.name] = tool
        else:
            name = tool.__name__
            doc = inspect.getdoc(tool) or name
            sig = inspect.signature(tool)
            params: dict[str, Any] = {}
            takes_ctx = False
            for idx, (param_name, param) in enumerate(sig.parameters.items()):
                if idx == 0 and (param_name == "ctx" or "RunContext" in str(param.annotation)):
                    takes_ctx = True
                    continue
                annotation = (
                    param.annotation if param.annotation != inspect.Parameter.empty else str
                )
                params[param_name] = str(annotation)
            agent_tool = AgentTool(
                name=name,
                description=doc,
                func=tool,
                parameters=params,
                takes_ctx=takes_ctx,
            )
            self._tools[name] = agent_tool

    def _build_system_prompt_with_tools(self, ctx: RunContext[Any] | None = None) -> str:
        base_prompt = self.system_prompt
        if "{{" in base_prompt and ctx and ctx.deps is not None:
            base_prompt = TemplateStr(base_prompt).render(ctx.deps)
        prompt_parts: list[str] = [base_prompt.strip()]

        for dyn_fn in self._dynamic_system_prompts:
            try:
                sig = inspect.signature(dyn_fn)
                dyn_res = dyn_fn(ctx) if len(sig.parameters) > 0 and ctx is not None else dyn_fn()
                if dyn_res:
                    prompt_parts.append(str(dyn_res).strip())
            except Exception:
                pass

        # Capability prompt additions (always-available or loaded)
        loaded_ids = ctx.loaded_capability_ids if ctx else set()
        for cap in self.capabilities:
            if not cap.defer_loading or cap.id in loaded_ids:
                for addition in cap.get_system_prompt_additions(ctx=ctx):
                    if addition and addition.strip():
                        prompt_parts.append(addition.strip())

        # Toolset instruction additions
        for ts in self.toolsets:
            for ts_inst in ts.get_instructions(ctx=ctx):
                if ts_inst and ts_inst.strip():
                    prompt_parts.append(ts_inst.strip())

        # Advertise available deferred capabilities in prompt catalog
        unloaded_caps = [
            cap for cap in self.capabilities if cap.defer_loading and cap.id not in loaded_ids
        ]
        if unloaded_caps:
            catalog_lines = [
                "## Available On-Demand Capabilities",
                "Call `load_capability` with `capability_id` to unlock:",
            ]
            for u_cap in unloaded_caps:
                desc = u_cap.description or u_cap.id
                catalog_lines.append(f"- `{u_cap.id}`: {desc}")
            prompt_parts.append("\n".join(catalog_lines))

        if self.memory and self.memory.summary:
            raw_summary = self.memory.summary.strip()
            sanitized_summary = "".join(
                c for c in raw_summary.replace("\n", " ") if 32 <= ord(c) <= 126
            )
            if len(sanitized_summary) > 1000:
                sanitized_summary = sanitized_summary[:997] + "..."
            prompt_parts.append(f"## Prior Interaction & Memory Summary\n{sanitized_summary}")

        if self._tools:
            tools_desc: list[str] = []
            for name, tool in self._tools.items():
                params_str = json.dumps(tool.parameters, separators=(",", ":"))
                # Sanitize description: strip non-printable characters and bound length
                desc = "".join(
                    c for c in tool.description.replace("\n", " ") if 32 <= ord(c) <= 126
                )
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                tools_desc.append(f"- `{name}`: {desc} params={params_str}")

            tools_block = _TOOL_PROTOCOL_TEMPLATE.format(tools_desc="\n".join(tools_desc))
            prompt_parts.append(tools_block)

        if self.output_schema is not None:
            schema_getter = getattr(self.output_schema, "model_json_schema", None)
            if callable(schema_getter):
                schema_json = json.dumps(schema_getter(), separators=(",", ":"))
                json_block = (
                    "## Required Response Format\n"
                    "Return response as JSON matching schema:\n"
                    f"```json\n{schema_json}\n```"
                )
                prompt_parts.append(json_block)

        return "\n\n".join(prompt_parts)

    def _dispatch_tool_calls(
        self,
        tool_calls_info: list[Any],
        tool_calls: list[ToolCall],
        messages: list[ChatMessage],
        response_text: str,
        on_tool_call: Callable[[str, dict[str, Any], Any], None] | None,
        ctx: RunContext[Any] | None = None,
        tool_retries: dict[str, int] | None = None,
        tool_budget: int = 1,
        tool_timeout: float | None = None,
    ) -> tuple[bool, bool]:
        """Dispatch extracted tool calls and append feedback messages."""
        executed_any = False
        already_called = False
        for tc_info in tool_calls_info:
            tool_name = tc_info.tool_name
            args = tc_info.arguments
            if tool_name not in self._tools:
                continue
            tool_obj = self._tools[tool_name]
            effective_timeout = tool_obj.timeout if tool_obj.timeout is not None else tool_timeout
            status, clean_args, result = _execute_single_tool(
                tool_obj,
                tool_name,
                args,
                tool_calls,
                ctx=ctx,
                hooks=self.hooks,
                default_timeout=effective_timeout,
            )
            if status == "already_called":
                already_called = True
                continue

            if status == "retry_requested":
                if tool_retries is not None:
                    tool_retries[tool_name] += 1
                    if tool_retries[tool_name] > tool_budget:
                        raise UnexpectedModelBehavior(
                            f"Tool '{tool_name}' exceeded retry budget of {tool_budget}: {result}"
                        )
                tc = ToolCall(tool_name=tool_name, arguments=clean_args, result=result)
                tool_calls.append(tc)
                executed_any = True
                messages.append(ChatMessage(role="assistant", content=response_text))
                feedback_content = _TOOL_FEEDBACK_TEMPLATE.format(
                    tool_name=tool_name,
                    tool_result=f"ModelRetry requested by tool: {result}. Please adjust arguments and try again.",
                )
                messages.append(ChatMessage(role="user", content=feedback_content))
                continue

            if tool_retries is not None and status == "ok":
                tool_retries[tool_name] = 0

            return_val = result
            meta: dict[str, Any] = {}
            if isinstance(result, ToolReturn):
                return_val = result.return_value
                meta = result.metadata
                if ctx and result.tools:
                    for t in result.tools:
                        ctx.loaded_capability_ids.add(t)

            tc = ToolCall(
                tool_name=tool_name, arguments=clean_args, result=return_val, metadata=meta
            )
            tool_calls.append(tc)
            executed_any = True
            if status == "ok" and on_tool_call:
                on_tool_call(tool_name, clean_args, return_val)

            messages.append(ChatMessage(role="assistant", content=response_text))
            feedback_content = _TOOL_FEEDBACK_TEMPLATE.format(
                tool_name=tool_name,
                tool_result=json.dumps(return_val, default=str),
            )
            messages.append(ChatMessage(role="user", content=feedback_content))
            if isinstance(result, ToolReturn) and result.content:
                extra_content = (
                    "\n".join(str(c) for c in result.content)
                    if isinstance(result.content, list)
                    else str(result.content)
                )
                messages.append(ChatMessage(role="user", content=extra_content))
        return executed_any, already_called

    def run(
        self,
        user_prompt: str,
        *,
        deps: DepsT | None = None,
        max_turns: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
        skip_rag: bool = False,
        message_history: list[ChatMessage] | None = None,
        retries: int | AgentRetries | dict[str, int] | None = None,
        on_tool_call: Callable[[str, dict[str, Any], Any], None] | None = None,
        on_thought: Callable[[str], None] | None = None,
    ) -> AgentResponse[T]:
        """Execute the agent tool loop until completion or max_turns is reached."""
        from devops_cli.ai.context_budget import count_tokens

        if isinstance(retries, int):
            active_retries = AgentRetries(tools=retries, output=retries)
        elif isinstance(retries, dict):
            active_retries = AgentRetries.model_validate(retries)
        elif isinstance(retries, AgentRetries):
            active_retries = retries
        else:
            active_retries = self.retries

        tool_retries: dict[str, int] = defaultdict(int)
        output_retries: int = 0

        raw_model = getattr(self.client, "model", "")
        model_str = raw_model if isinstance(raw_model, str) else ""
        ctx = RunContext[DepsT](
            deps=deps,
            session_id=self.name,
            model=model_str,
        )
        prior_history_count = (
            len(message_history)
            if message_history is not None
            else len(self.memory.to_chat_messages())
        )
        self.memory.add_interaction("user", user_prompt)
        if max_turns > 1 and len(self.memory.entries) > self.memory.max_entries:
            self.memory.auto_summarize_if_needed(llm_client=self.client)

        system = self._build_system_prompt_with_tools(ctx=ctx)

        # RAG investigation step
        if not skip_rag:
            try:
                from devops_cli.ai.rag.investigator import (
                    format_rag_investigation_for_prompt,
                    investigate_rag_context,
                )

                rag_ctx = investigate_rag_context(user_prompt, persona=self.name)
                rag_context_str = format_rag_investigation_for_prompt(rag_ctx)
                if rag_context_str:
                    system = f"{system}\n\n{rag_context_str}"
            except Exception:
                pass

        if message_history is not None:
            messages: list[ChatMessage] = list(message_history)
        else:
            messages = self.memory.to_chat_messages()

        if not messages or messages[-1].content != user_prompt:
            messages.append(ChatMessage(role="user", content=user_prompt))

        tool_calls: list[ToolCall] = []
        response_text = ""
        all_thoughts: list[str] = []

        total_input_tokens = count_tokens(system + "\n" + user_prompt)
        total_output_tokens = 0

        for turn in range(1, max_turns + 1):
            ctx.retry = turn - 1

            for h_bm in self.hooks.before_model_request:
                try:
                    h_bm(ctx, messages)
                except Exception:
                    pass

            turn_thinking = enable_thinking
            for cap in self.capabilities:
                if not cap.defer_loading or cap.id in ctx.loaded_capability_ids:
                    cap_settings = cap.get_model_settings(ctx=ctx)
                    if "enable_thinking" in cap_settings:
                        turn_thinking = bool(cap_settings["enable_thinking"])

            res_obj = self.client.chat_messages(system, messages, enable_thinking=turn_thinking)
            response_text = str(res_obj)

            for h_am in self.hooks.after_model_request:
                try:
                    h_am(ctx, response_text)
                except Exception:
                    pass

            b_info = getattr(res_obj, "backend_info", None)
            total_output_tokens += count_tokens(response_text)

            from devops_cli.ai.response_repair import fix_llm_response

            fixed = fix_llm_response(
                response_text,
                schema=self.output_schema,
                available_tools=set(self._tools.keys()),
            )

            # Broadcast thoughts
            _record_and_broadcast_thoughts(fixed.thoughts, all_thoughts, on_thought)

            # Process extracted tool calls
            if fixed.tool_calls:
                executed, already = self._dispatch_tool_calls(
                    fixed.tool_calls,
                    tool_calls,
                    messages,
                    response_text,
                    on_tool_call,
                    ctx=ctx,
                    tool_retries=tool_retries,
                    tool_budget=active_retries.tools,
                    tool_timeout=self.tool_timeout,
                )
                if executed:
                    continue
                if already and turn < max_turns:
                    messages.append(ChatMessage(role="assistant", content=response_text))
                    messages.append(ChatMessage(role="user", content=_TOOL_ALREADY_CALLED_PROMPT))
                    continue

            final_output = fixed.content.strip()

            # Check if output or thoughts expressed intent to use a known tool
            detected_tool = _detect_tool_intent(self._tools, final_output, all_thoughts)
            if detected_tool and turn < max_turns:
                tool_obj = self._tools[detected_tool]
                messages.append(ChatMessage(role="assistant", content=response_text))
                messages.append(_create_tool_retry_message(detected_tool, tool_obj))
                continue

            if _is_scratchpad_deliberation(final_output) and turn < max_turns:
                messages.append(ChatMessage(role="assistant", content=response_text))
                prompt_msg = (
                    _DIRECT_RESPONSE_FROM_TOOLS_PROMPT
                    if tool_calls
                    else _DIRECT_RESPONSE_FROM_REASONING_PROMPT
                )
                messages.append(ChatMessage(role="user", content=prompt_msg))
                continue

            final_output = _resolve_fallback_output(final_output, tool_calls, all_thoughts)

            # Output validation stage
            if self._output_validators and (
                fixed.parsed_model is not None or self.output_schema is None
            ):
                validation_retry_msg: str | None = None
                target_val = fixed.parsed_model if fixed.parsed_model is not None else final_output
                for val_fn in self._output_validators:
                    try:
                        sig = inspect.signature(val_fn)
                        if len(sig.parameters) > 1 and ctx is not None:
                            val_res = val_fn(ctx, target_val)
                        else:
                            val_res = val_fn(target_val)
                        if fixed.parsed_model is not None and isinstance(val_res, BaseModel):
                            fixed.parsed_model = val_res  # type: ignore[assignment]
                    except ModelRetry as retry_exc:
                        validation_retry_msg = str(retry_exc)
                        break
                    except Exception as exc:
                        validation_retry_msg = f"Output validation failed: {exc}"
                        break

                if validation_retry_msg and turn < max_turns:
                    output_retries += 1
                    if output_retries > active_retries.output:
                        raise UnexpectedModelBehavior(
                            f"Output validation exceeded retry budget of {active_retries.output}: {validation_retry_msg}"
                        )
                    messages.append(ChatMessage(role="assistant", content=response_text))
                    retry_prompt = (
                        f"Output validation failed: {validation_retry_msg}. "
                        "Please adjust your response to satisfy the validation constraints and try again."
                    )
                    messages.append(ChatMessage(role="user", content=retry_prompt))
                    continue

            self.memory.add_interaction("assistant", final_output)
            self.memory.auto_summarize_if_needed(llm_client=self.client)
            messages.append(ChatMessage(role="assistant", content=final_output))

            usage = AgentUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_input_tokens + total_output_tokens,
            )
            return AgentResponse[T](
                content=final_output,
                data=fixed.parsed_model,
                tool_calls=tool_calls,
                thoughts=all_thoughts,
                turns=turn,
                backend_info=b_info,
                usage=usage,
                messages=list(messages),
                new_messages_list=list(messages[prior_history_count:]),
            )

        self.memory.add_interaction("assistant", response_text)
        self.memory.auto_summarize_if_needed(llm_client=self.client)
        messages.append(ChatMessage(role="assistant", content=response_text))

        usage = AgentUsage(
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_input_tokens + total_output_tokens,
        )
        return AgentResponse[T](
            content=response_text,
            tool_calls=tool_calls,
            thoughts=all_thoughts,
            turns=max_turns,
            backend_info=b_info if "b_info" in locals() else None,
            usage=usage,
            messages=list(messages),
            new_messages_list=list(messages[prior_history_count:]),
        )

    def iter(
        self,
        user_prompt: str,
        *,
        deps: DepsT | None = None,
        max_turns: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
    ) -> Generator[AgentStepNode]:
        """Iterate step-by-step through the agent execution nodes."""
        yield AgentStepNode(kind="user_prompt", payload={"prompt": user_prompt})

        raw_model = getattr(self.client, "model", "")
        model_str = raw_model if isinstance(raw_model, str) else ""
        ctx = RunContext[DepsT](
            deps=deps,
            session_id=self.name,
            model=model_str,
        )
        system = self._build_system_prompt_with_tools(ctx=ctx)
        messages = [ChatMessage(role="user", content=user_prompt)]

        for turn in range(1, max_turns + 1):
            yield AgentStepNode(kind="model_request", payload={"turn": turn, "system": system})
            res_obj = self.client.chat_messages(system, messages, enable_thinking=enable_thinking)
            response_text = str(res_obj)

            from devops_cli.ai.response_repair import fix_llm_response

            fixed = fix_llm_response(
                response_text,
                schema=self.output_schema,
                available_tools=set(self._tools.keys()),
            )
            if fixed.tool_calls:
                for tc in fixed.tool_calls:
                    yield AgentStepNode(
                        kind="tool_call",
                        payload={"tool_name": tc.tool_name, "arguments": tc.arguments},
                    )
                    if tc.tool_name in self._tools:
                        tool_obj = self._tools[tc.tool_name]
                        _, _, res = _execute_single_tool(
                            tool_obj, tc.tool_name, tc.arguments, [], ctx=ctx, hooks=self.hooks
                        )
                        yield AgentStepNode(
                            kind="tool_result",
                            payload={"tool_name": tc.tool_name, "result": res},
                        )
                        messages.append(ChatMessage(role="assistant", content=response_text))
                        feedback_content = _TOOL_FEEDBACK_TEMPLATE.format(
                            tool_name=tc.tool_name,
                            tool_result=json.dumps(res, default=str),
                        )
                        messages.append(ChatMessage(role="user", content=feedback_content))
                continue

            final_output = fixed.content.strip() or response_text
            yield AgentStepNode(
                kind="end",
                payload={"output": final_output, "data": fixed.parsed_model},
            )
            return

    def run_stream(
        self,
        user_prompt: str,
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        """Stream response tokens in real-time."""
        system = self._build_system_prompt_with_tools()

        # RAG investigation step
        try:
            from devops_cli.ai.rag.investigator import (
                format_rag_investigation_for_prompt,
                investigate_rag_context,
            )

            rag_ctx = investigate_rag_context(user_prompt, persona=self.name)
            rag_context_str = format_rag_investigation_for_prompt(rag_ctx)
            if rag_context_str:
                system = f"{system}\n\n{rag_context_str}"
        except Exception:
            pass

        messages = [ChatMessage(role="user", content=user_prompt)]
        yield from self.client.chat_messages_stream(
            system, messages, enable_thinking=enable_thinking
        )
