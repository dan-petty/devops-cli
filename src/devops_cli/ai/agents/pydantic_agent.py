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
from collections.abc import Callable, Generator
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from devops_cli.ai.agents.memory import AgentMemory
from devops_cli.ai.client import LLMClient
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import DEFAULT_AGENT_MAX_TURNS
from devops_cli.exceptions import SecurityError
from devops_cli.models.ai import ChatMessage

_TOOL_PROTOCOL_TEMPLATE = load_task_prompt("tool_execution_protocol.md")
_TOOL_FEEDBACK_TEMPLATE = load_task_prompt("agent_tool_feedback.md")
_TOOL_ALREADY_CALLED_PROMPT = load_task_prompt("agent_tool_already_called.md")
_INVOKE_TOOL_REQUEST_TEMPLATE = load_task_prompt("agent_invoke_tool_request.md")
_DIRECT_RESPONSE_FROM_TOOLS_PROMPT = load_task_prompt("agent_direct_response_from_tools.md")
_DIRECT_RESPONSE_FROM_REASONING_PROMPT = load_task_prompt("agent_direct_response_from_reasoning.md")

T = TypeVar("T", bound=BaseModel)


def _check_path_traversal(key: str, value: Any) -> None:
    """Validate that path parameters do not contain traversal sequences."""
    if isinstance(value, str) and any(sub in key.lower() for sub in ("path", "file", "dest")):
        if ".." in value and not value.startswith("."):
            raise SecurityError(f"Path traversal sequence detected in parameter '{key}': {value}")


class AgentTool(BaseModel):
    """Encapsulates an executable tool available to a PydanticAgent."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = Field(default_factory=dict)

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

    def execute(self, **kwargs: Any) -> Any:
        """Invoke the tool callback with kwargs."""
        return self.func(**kwargs)


class ToolCall(BaseModel):
    """Record of a tool call executed during an agent run."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None


class AgentResponse[T](BaseModel):
    """Structured response returned by a PydanticAgent run."""

    content: str
    data: T | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    thoughts: list[str] = Field(default_factory=list)
    turns: int = 1
    backend_info: str | None = None


def _execute_single_tool(
    tool_obj: AgentTool,
    tool_name: str,
    args: dict[str, Any],
    tool_calls: list[ToolCall],
) -> tuple[str, dict[str, Any], Any]:
    """Execute a single agent tool call, validating arguments and preventing loop repetition.

    Returns:
        (status, clean_args, result) where status is "ok", "validation_error", or "already_called".
    """
    try:
        clean_args = tool_obj.validate_args(args)
    except Exception as exc:
        return "validation_error", args, f"Tool argument validation error for {tool_name}: {exc}"

    # Prevent infinite tool repetition loops with identical arguments
    prior = next(
        (
            prev
            for prev in tool_calls
            if prev.tool_name == tool_name and prev.arguments == clean_args
        ),
        None,
    )
    if prior is not None:
        return "already_called", clean_args, None

    try:
        tool_result = tool_obj.execute(**clean_args)
    except Exception as exc:
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


class PydanticAgent[T]:
    """Agent built on Pydantic models supporting tools, memory, reasoning, and streaming."""

    def __init__(
        self,
        client: LLMClient,
        system_prompt: str = "You are a helpful DevOps assistant.",
        *,
        name: str = "Assistant",
        output_schema: type[T] | None = None,
        tools: list[AgentTool | Callable[..., Any]] | None = None,
        memory: AgentMemory | None = None,
    ) -> None:
        self.client = client
        self.system_prompt = system_prompt
        self.name = name
        self.output_schema = output_schema
        self.memory: AgentMemory = memory or AgentMemory(session_id=name)
        self._tools: dict[str, AgentTool] = {}
        if tools:
            for tool in tools:
                self.add_tool(tool)

    def add_tool(self, tool: AgentTool | Callable[..., Any]) -> None:
        """Register a tool callback or AgentTool instance."""
        if isinstance(tool, AgentTool):
            self._tools[tool.name] = tool
        else:
            name = tool.__name__
            doc = inspect.getdoc(tool) or name
            sig = inspect.signature(tool)
            params: dict[str, Any] = {}
            for param_name, param in sig.parameters.items():
                annotation = (
                    param.annotation if param.annotation != inspect.Parameter.empty else str
                )
                params[param_name] = str(annotation)
            agent_tool = AgentTool(
                name=name,
                description=doc,
                func=tool,
                parameters=params,
            )
            self._tools[name] = agent_tool

    def _build_system_prompt_with_tools(self) -> str:
        prompt_parts: list[str] = [self.system_prompt.strip()]

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
            status, clean_args, result = _execute_single_tool(tool_obj, tool_name, args, tool_calls)
            if status == "already_called":
                already_called = True
                continue

            tc = ToolCall(tool_name=tool_name, arguments=clean_args, result=result)
            tool_calls.append(tc)
            executed_any = True
            if status == "ok" and on_tool_call:
                on_tool_call(tool_name, clean_args, result)

            messages.append(ChatMessage(role="assistant", content=response_text))
            feedback_content = _TOOL_FEEDBACK_TEMPLATE.format(
                tool_name=tool_name,
                tool_result=json.dumps(result, default=str),
            )
            messages.append(ChatMessage(role="user", content=feedback_content))
        return executed_any, already_called

    def run(
        self,
        user_prompt: str,
        *,
        max_turns: int = DEFAULT_AGENT_MAX_TURNS,
        enable_thinking: bool = True,
        on_tool_call: Callable[[str, dict[str, Any], Any], None] | None = None,
        on_thought: Callable[[str], None] | None = None,
    ) -> AgentResponse[T]:
        """Execute the agent tool loop until completion or max_turns is reached."""
        self.memory.add_interaction("user", user_prompt)
        self.memory.auto_summarize_if_needed(llm_client=self.client)

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

        messages: list[ChatMessage] = self.memory.to_chat_messages()
        if not messages or messages[-1].content != user_prompt:
            messages.append(ChatMessage(role="user", content=user_prompt))

        tool_calls: list[ToolCall] = []
        response_text = ""
        all_thoughts: list[str] = []

        for turn in range(1, max_turns + 1):
            res_obj = self.client.chat_messages(system, messages, enable_thinking=enable_thinking)
            response_text = str(res_obj)
            b_info = getattr(res_obj, "backend_info", None)

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
                    fixed.tool_calls, tool_calls, messages, response_text, on_tool_call
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

            self.memory.add_interaction("assistant", final_output)
            self.memory.auto_summarize_if_needed(llm_client=self.client)

            return AgentResponse[T](
                content=final_output,
                data=fixed.parsed_model,
                tool_calls=tool_calls,
                thoughts=all_thoughts,
                turns=turn,
                backend_info=b_info,
            )

        self.memory.add_interaction("assistant", response_text)
        self.memory.auto_summarize_if_needed(llm_client=self.client)

        return AgentResponse[T](
            content=response_text,
            tool_calls=tool_calls,
            thoughts=all_thoughts,
            turns=max_turns,
            backend_info=b_info if "b_info" in locals() else None,
        )

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
