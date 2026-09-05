"""PydanticAgent class providing tool loop orchestration, memory, and streaming."""

from __future__ import annotations

import inspect
import json
from collections import defaultdict
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar, cast

from devops_cli.ai.agents.capabilities import (
    BaseCapability,
    DeferredToolRequests,
    DeferredToolResults,
)
from devops_cli.ai.agents.context import (
    AgentHooks,
    AgentRetries,
    AgentStepNode,
    AgentUsage,
    RunContext,
)
from devops_cli.ai.agents.memory import AgentMemory
from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.agents.runner import (
    _DIRECT_RESPONSE_FROM_REASONING_PROMPT,
    _DIRECT_RESPONSE_FROM_TOOLS_PROMPT,
    _TOOL_ALREADY_CALLED_PROMPT,
    _TOOL_FEEDBACK_TEMPLATE,
    _TOOL_PROTOCOL_TEMPLATE,
    _append_deferred_request,
    _build_deferred_agent_response,
    _create_deferred_tool_request,
    _create_tool_retry_message,
    _detect_tool_intent,
    _execute_single_tool,
    _execute_stream_tool_step,
    _find_deferred_tool_handler,
    _handle_deferred_resolution,
    _is_scratchpad_deliberation,
    _record_and_broadcast_thoughts,
    _resolve_fallback_output,
    _resolve_thinking_preference,
    _validate_agent_output,
)
from devops_cli.ai.agents.tools import (
    AbstractToolset,
    AgentSpec,
    AgentTool,
    TemplateStr,
    Tool,
    ToolCall,
    ToolReturn,
)
from devops_cli.ai.client import LLMClient
from devops_cli.config.defaults import DEFAULT_AGENT_MAX_TURNS
from devops_cli.exceptions import UnexpectedModelBehavior
from devops_cli.models.ai import ChatMessage

T = TypeVar("T")
DepsT = TypeVar("DepsT")

ALLOW_MODEL_REQUESTS: bool = True


class SystemPrompt(str):
    """String holding the base system prompt while functioning as a decorator callback."""

    _agent: Any

    def __new__(cls, content: str = "", agent: Any = None) -> SystemPrompt:
        instance = super().__new__(cls, content)
        instance._agent = agent
        return instance

    def __call__(self, func: Callable[..., str]) -> Callable[..., str]:
        if getattr(self, "_agent", None) is not None:
            return self._agent.system_prompt_fn(func)  # type: ignore[no-any-return]
        return func


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
        model: str | Any | None = None,
        system_prompt: str | None = None,
        *,
        client: LLMClient | Any = None,
        instructions: str | list[str] | None = None,
        name: str = "Assistant",
        output_type: type[T] | None = None,
        output_schema: type[T] | None = None,
        tools: list[AgentTool | Callable[..., Any]] | None = None,
        memory: AgentMemory | None = None,
        deps_type: type[DepsT] | None = None,
        hooks: AgentHooks | None = None,
        capabilities: list[BaseCapability] | None = None,
        toolsets: list[AbstractToolset] | None = None,
        retries: int | AgentRetries | dict[str, int] | None = None,
        tool_timeout: float | None = None,
    ) -> None:
        if client is not None:
            self.client = client
        elif isinstance(model, str):
            from devops_cli.config.settings import AIConfig

            self.client = LLMClient(config=AIConfig(model=model))
        elif model is not None:
            self.client = model
        else:
            self.client = LLMClient()

        if instructions is not None:
            if isinstance(instructions, list):
                raw_system_prompt = "\n\n".join(instructions)
            else:
                raw_system_prompt = instructions
        elif system_prompt is not None:
            raw_system_prompt = system_prompt
        else:
            raw_system_prompt = "You are a helpful DevOps assistant."

        self.system_prompt: SystemPrompt = SystemPrompt(raw_system_prompt, agent=self)

        self.name = name
        self.output_schema = output_type or output_schema
        self.memory: AgentMemory = memory or AgentMemory(session_id=name)
        self.deps_type = deps_type
        self.hooks = hooks or AgentHooks()
        self.capabilities: list[BaseCapability] = list(capabilities or [])
        self.toolsets: list[AbstractToolset] = list(toolsets or [])
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

    @property
    def tools(self) -> list[AgentTool]:
        """Return the list of registered tools for this agent."""
        return list(self._tools.values())

    @property
    def model(self) -> str | None:
        """Return the model identifier configured on this agent's LLM client."""
        if hasattr(self.client, "config") and hasattr(self.client.config, "model"):
            return str(self.client.config.model)
        if hasattr(self.client, "model"):
            return str(self.client.model)
        return None

    @property
    def output_type(self) -> type[T] | None:
        """Return the structured response model type."""
        return self.output_schema

    @property
    def output_json_schema(self) -> dict[str, Any] | None:
        """Return the JSON schema dictionary for output validation if available."""
        if self.output_schema is None:
            return None
        schema_getter = getattr(self.output_schema, "model_json_schema", None)
        if callable(schema_getter):
            res = schema_getter()
            return cast(dict[str, Any], res) if isinstance(res, dict) else None
        return None

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
        """Decorator to register a tool function on this agent with optional timeout/metadata."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add_tool(
                Tool.from_function(
                    fn,
                    name=name,
                    description=description,
                    strict=strict,
                    requires_approval=requires_approval,
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
        requires_approval: bool = False,
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
                    requires_approval=requires_approval,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            )
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    def instructions(self, func: Callable[..., str]) -> Callable[..., str]:
        """Decorator to register dynamic agent instructions (PydanticAI parity alias)."""
        return self.system_prompt_fn(func)

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

    def set_mcp_sampling_model(self, model: str | Any | None = None) -> None:
        """Set the sampling model on all MCPToolsets registered with this agent."""
        target_model = model or self.model
        for ts in self.toolsets:
            if hasattr(ts, "sampling_model"):
                setattr(ts, "sampling_model", target_model)

    @contextmanager
    def override(
        self,
        *,
        model: str | Any | None = None,
        client: LLMClient | Any = None,
        deps: DepsT | None = None,
        toolsets: list[AbstractToolset] | None = None,
        capabilities: list[BaseCapability] | None = None,
        native_tools: list[Any] | None = None,
    ) -> Iterator[None]:
        """Context manager to temporarily override agent model, client, tools, or dependencies for testing."""
        orig_client = self.client
        orig_toolsets = list(self.toolsets)
        orig_capabilities = list(self.capabilities)
        orig_tools = dict(self._tools)

        try:
            if model is not None:
                if isinstance(model, str):
                    from devops_cli.config.settings import AIConfig

                    self.client = LLMClient(config=AIConfig(model=model))
                else:
                    self.client = model
            elif client is not None:
                self.client = client

            if toolsets is not None:
                self.toolsets = list(toolsets)
                for ts in self.toolsets:
                    for ts_tool in ts.get_tools():
                        self.add_tool(ts_tool)

            if capabilities is not None:
                self.capabilities = list(capabilities)

            yield
        finally:
            self.client = orig_client
            self.toolsets = orig_toolsets
            self.capabilities = orig_capabilities
            self._tools = orig_tools

    async def __aenter__(self) -> PydanticAgent[T, DepsT]:
        """Enter asynchronous context, opening any connected MCP toolsets or capabilities."""
        for ts in self.toolsets:
            if hasattr(ts, "__aenter__") and callable(ts.__aenter__):
                await ts.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit asynchronous context, closing any opened MCP toolsets or capabilities."""
        for ts in self.toolsets:
            if hasattr(ts, "__aexit__") and callable(ts.__aexit__):
                await ts.__aexit__(exc_type, exc_val, exc_tb)

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
        base_prompt: str = str(self.system_prompt)
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
                prompt_parts.extend(
                    addition.strip()
                    for addition in cap.get_system_prompt_additions(ctx=ctx)
                    if addition and addition.strip()
                )

        # Toolset instruction additions
        for ts in self.toolsets:
            prompt_parts.extend(
                ts_inst.strip()
                for ts_inst in ts.get_instructions(ctx=ctx)
                if ts_inst and ts_inst.strip()
            )

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
        deferred_tool_results: DeferredToolResults | None = None,
    ) -> tuple[bool, bool, DeferredToolRequests | None]:
        """Dispatch extracted tool calls and append feedback messages."""
        executed_any = False
        already_called = False
        deferred_requests: DeferredToolRequests | None = None

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

            # Handle ApprovalRequired or CallDeferred
            if status in ("approval_required", "call_deferred"):
                req = _create_deferred_tool_request(status, tool_name, clean_args, result)
                resolved = (
                    deferred_tool_results
                    if deferred_tool_results is not None
                    else _find_deferred_tool_handler(self.capabilities, req)
                )

                if resolved is None:
                    deferred_requests = _append_deferred_request(deferred_requests, req)
                    continue

                handled_ext, status, clean_args, result = _handle_deferred_resolution(
                    resolved,
                    tool_name,
                    clean_args,
                    tool_obj,
                    tool_calls,
                    messages,
                    response_text,
                    ctx,
                    self.hooks,
                    effective_timeout,
                )
                if handled_ext:
                    executed_any = True
                    continue

            if status == "retry_requested":
                if tool_retries is not None and tool_retries[tool_name] + 1 > tool_budget:
                    raise UnexpectedModelBehavior(f"Tool '{tool_name}' exceeded retry budget")
                if tool_retries is not None:
                    tool_retries[tool_name] += 1
                tc = ToolCall(tool_name=tool_name, arguments=clean_args, result=result)
                tool_calls.append(tc)
                executed_any = True
                messages.append(ChatMessage(role="assistant", content=response_text))
                retry_feedback = f"ModelRetry requested by tool: {result}. Please adjust arguments and try again."
                messages.append(
                    ChatMessage(
                        role="user",
                        content=_TOOL_FEEDBACK_TEMPLATE.format(
                            tool_name=tool_name, tool_result=retry_feedback
                        ),
                    )
                )
                continue

            if tool_retries is not None and status == "ok":
                tool_retries[tool_name] = 0

            return_val = result
            call_meta: dict[str, Any] = {}
            if isinstance(result, ToolReturn):
                return_val = result.return_value
                call_meta = result.metadata
                if ctx and result.tools:
                    ctx.loaded_capability_ids.update(result.tools)

            tc = ToolCall(
                tool_name=tool_name, arguments=clean_args, result=return_val, metadata=call_meta
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
        return executed_any, already_called, deferred_requests

    def run(
        self,
        user_prompt: str,
        *,
        deps: DepsT | None = None,
        max_turns: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
        skip_rag: bool = False,
        message_history: list[ChatMessage] | None = None,
        deferred_tool_results: DeferredToolResults | None = None,
        retries: int | AgentRetries | dict[str, int] | None = None,
        on_tool_call: Callable[[str, dict[str, Any], Any], None] | None = None,
        on_thought: Callable[[str], None] | None = None,
    ) -> AgentResponse[Any]:
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

            turn_thinking = _resolve_thinking_preference(
                self.capabilities, ctx.loaded_capability_ids, ctx, enable_thinking
            )

            import devops_cli.ai.agents.agent as agent_module
            import devops_cli.ai.agents.testing as testing_module

            if not getattr(testing_module, "ALLOW_MODEL_REQUESTS", True) or not getattr(
                agent_module, "ALLOW_MODEL_REQUESTS", True
            ):
                from devops_cli.ai.agents.testing import (
                    FunctionModel,
                    ModelNotAllowedError,
                    TestModel,
                )

                if not isinstance(self.client, (TestModel, FunctionModel)):
                    raise ModelNotAllowedError(
                        "Model requests are disabled via ALLOW_MODEL_REQUESTS=False"
                    )

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
                executed, already, deferred_reqs = self._dispatch_tool_calls(
                    fixed.tool_calls,
                    tool_calls,
                    messages,
                    response_text,
                    on_tool_call,
                    ctx=ctx,
                    tool_retries=tool_retries,
                    tool_budget=active_retries.tools,
                    tool_timeout=self.tool_timeout,
                    deferred_tool_results=deferred_tool_results,
                )
                if deferred_reqs is not None:
                    return _build_deferred_agent_response(
                        response_text,
                        deferred_reqs,
                        tool_calls,
                        all_thoughts,
                        turn,
                        b_info,
                        total_input_tokens,
                        total_output_tokens,
                        messages,
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
                target_val = fixed.parsed_model if fixed.parsed_model is not None else final_output
                val_err, fixed.parsed_model = _validate_agent_output(
                    self._output_validators, target_val, ctx, fixed.parsed_model
                )
                if val_err and turn < max_turns and output_retries + 1 > active_retries.output:
                    err_text = f"Output validation exceeded retry budget of {active_retries.output}: {val_err}"
                    raise UnexpectedModelBehavior(err_text)
                if val_err and turn < max_turns:
                    output_retries += 1
                    messages.append(ChatMessage(role="assistant", content=response_text))
                    retry_prompt = f"Output validation failed: {val_err}. Please adjust your response and try again."
                    messages.append(ChatMessage(role="user", content=retry_prompt))
                    continue

            self.memory.add_interaction("assistant", final_output)
            self.memory.auto_summarize_if_needed(llm_client=self.client)
            messages.append(ChatMessage(role="assistant", content=final_output))

            from devops_cli.ai.agents.testing import _RUN_MESSAGES_CAPTURE

            if (capture_buf := _RUN_MESSAGES_CAPTURE.get()) is not None:
                capture_buf.extend(messages)

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

        from devops_cli.ai.agents.testing import _RUN_MESSAGES_CAPTURE

        if (capture_buf := _RUN_MESSAGES_CAPTURE.get()) is not None:
            capture_buf.extend(messages)

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

    def _stream_turn_tools(
        self,
        tool_calls: list[Any],
        ctx: RunContext[Any] | None,
        response_text: str,
        messages: list[ChatMessage],
    ) -> Generator[AgentStepNode]:
        """Yield step nodes for tools executed during a stream turn."""
        for tc in tool_calls:
            if tc.tool_name in self._tools:
                yield from _execute_stream_tool_step(
                    tc, self._tools[tc.tool_name], ctx, self.hooks, response_text, messages
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
                yield from self._stream_turn_tools(fixed.tool_calls, ctx, response_text, messages)
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

    def run_sync(
        self,
        user_prompt: str,
        *,
        deps: DepsT | None = None,
        max_turns: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
        skip_rag: bool = False,
        message_history: list[ChatMessage] | None = None,
        deferred_tool_results: DeferredToolResults | None = None,
        retries: int | AgentRetries | dict[str, int] | None = None,
        on_tool_call: Callable[[str, dict[str, Any], Any], None] | None = None,
        on_thought: Callable[[str], None] | None = None,
    ) -> AgentResponse[T]:
        """Synchronously execute the agent tool loop (PydanticAI parity alias for run)."""
        return self.run(
            user_prompt,
            deps=deps,
            max_turns=max_turns,
            enable_thinking=enable_thinking,
            skip_rag=skip_rag,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
            retries=retries,
            on_tool_call=on_tool_call,
            on_thought=on_thought,
        )

    def run_stream_sync(
        self,
        user_prompt: str,
        *,
        enable_thinking: bool = True,
    ) -> Generator[str]:
        """Synchronously stream response tokens in real-time (PydanticAI parity alias)."""
        yield from self.run_stream(user_prompt, enable_thinking=enable_thinking)

    def to_cli(
        self,
        user_prompt: str | None = None,
        *,
        deps: DepsT | None = None,
    ) -> str:
        """Run the agent and print output to the CLI, returning the final response."""
        return self.to_cli_sync(user_prompt, deps=deps)

    def to_cli_sync(
        self,
        user_prompt: str | None = None,
        *,
        deps: DepsT | None = None,
    ) -> str:
        """Synchronously execute prompt and return content string."""
        prompt = user_prompt or "Hello"
        res = self.run(prompt, deps=deps)
        return str(res.output)
