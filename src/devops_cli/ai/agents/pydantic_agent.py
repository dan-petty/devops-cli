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
from devops_cli.models.ai import ChatMessage

_TOOL_PROTOCOL_TEMPLATE = load_task_prompt("tool_execution_protocol.md")
_TOOL_FEEDBACK_TEMPLATE = load_task_prompt("agent_tool_feedback.md")
_TOOL_ALREADY_CALLED_PROMPT = load_task_prompt("agent_tool_already_called.md")
_INVOKE_TOOL_REQUEST_TEMPLATE = load_task_prompt("agent_invoke_tool_request.md")
_DIRECT_RESPONSE_FROM_TOOLS_PROMPT = load_task_prompt("agent_direct_response_from_tools.md")
_DIRECT_RESPONSE_FROM_REASONING_PROMPT = load_task_prompt("agent_direct_response_from_reasoning.md")

T = TypeVar("T", bound=BaseModel)


class AgentTool(BaseModel):
    """Encapsulates an executable tool available to a PydanticAgent."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = Field(default_factory=dict)

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
            prompt_parts.append(f"## Prior Interaction & Memory Summary\n{self.memory.summary}")

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

            from devops_cli.ai.fixer import fix_llm_response

            fixed = fix_llm_response(
                response_text,
                schema=self.output_schema,
                available_tools=set(self._tools.keys()),
            )

            # Broadcast thoughts
            for t in fixed.thoughts:
                if t and t not in all_thoughts:
                    all_thoughts.append(t)
                    if on_thought:
                        on_thought(t)

            # Process extracted tool calls
            if fixed.tool_calls:
                executed_any = False
                already_called = False
                for tc_info in fixed.tool_calls:
                    tool_name = tc_info.tool_name
                    args = tc_info.arguments
                    if tool_name in self._tools:
                        tool_obj = self._tools[tool_name]
                        valid_params = set(tool_obj.parameters.keys())
                        clean_args = (
                            {k: v for k, v in args.items() if k in valid_params}
                            if valid_params
                            else args
                        )

                        # Prevent infinite tool repetition loops
                        prior = next(
                            (
                                prev
                                for prev in tool_calls
                                if prev.tool_name == tool_name and prev.arguments == clean_args
                            ),
                            None,
                        )
                        if prior is not None:
                            already_called = True
                            continue

                        try:
                            tool_result = tool_obj.execute(**clean_args)
                        except Exception as exc:
                            tool_result = f"Tool execution error for {tool_name}: {exc}"
                        tc = ToolCall(tool_name=tool_name, arguments=clean_args, result=tool_result)
                        tool_calls.append(tc)
                        executed_any = True

                        if on_tool_call:
                            on_tool_call(tool_name, clean_args, tool_result)

                        messages.append(ChatMessage(role="assistant", content=response_text))
                        messages.append(
                            ChatMessage(
                                role="user",
                                content=_TOOL_FEEDBACK_TEMPLATE.format(
                                    tool_name=tool_name,
                                    tool_result=json.dumps(tool_result, default=str),
                                ),
                            )
                        )
                if executed_any:
                    continue
                if already_called and turn < max_turns:
                    messages.append(ChatMessage(role="assistant", content=response_text))
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=_TOOL_ALREADY_CALLED_PROMPT,
                        )
                    )
                    continue

            final_output = fixed.content.strip()

            # Check if output or thoughts expressed intent to use a known tool
            detected_tool: str | None = None
            if self._tools and turn < max_turns:
                search_text = f"{final_output}\n{' '.join(all_thoughts)}"
                for t_name in self._tools:
                    escaped_name = re.escape(t_name)
                    tool_intent_pattern = (
                        rf"\b(?:call|invoke|use|run|execute)\s+(?:tool\s+)?`?{escaped_name}`?\b"
                    )
                    if re.search(tool_intent_pattern, search_text, re.IGNORECASE):
                        detected_tool = t_name
                        break

            if detected_tool and turn < max_turns:
                tool_obj = self._tools[detected_tool]
                example_args = {k: f"<{k}>" for k in tool_obj.parameters}
                example_json = json.dumps(
                    {"tool": detected_tool, "arguments": example_args}, separators=(",", ":")
                )
                messages.append(ChatMessage(role="assistant", content=response_text))
                messages.append(
                    ChatMessage(
                        role="user",
                        content=_INVOKE_TOOL_REQUEST_TEMPLATE.format(
                            detected_tool=detected_tool,
                            example_json=example_json,
                        ),
                    )
                )
                continue

            # If final_output is raw tool JSON or contains internal scratchpad deliberation
            is_tool_json = (
                final_output.startswith('{"tool"')
                or final_output.startswith('```json\n{"tool"')
                or ('"tool":' in final_output and '"arguments":' in final_output)
            )
            is_deliberation = (
                not final_output
                or is_tool_json
                or final_output.lower().startswith(
                    (
                        "the tool returned",
                        "we need to interpret",
                        "we need to decide",
                        "we should double-check",
                        "let's search",
                        "we need to scan",
                        "let's recall",
                        "not sure. we need",
                    )
                )
            )

            if is_deliberation and turn < max_turns:
                messages.append(ChatMessage(role="assistant", content=response_text))
                prompt_msg = (
                    _DIRECT_RESPONSE_FROM_TOOLS_PROMPT
                    if tool_calls
                    else _DIRECT_RESPONSE_FROM_REASONING_PROMPT
                )
                messages.append(ChatMessage(role="user", content=prompt_msg))
                continue

            # Fallback if still empty or raw tool JSON after max turns
            if not final_output or ('"tool":' in final_output and '"arguments":' in final_output):
                if tool_calls:
                    last_tc = tool_calls[-1]
                    final_output = (
                        f"**Tool Execution Completed (`{last_tc.tool_name}`):**\n\n{last_tc.result}"
                    )
                elif all_thoughts:
                    final_output = all_thoughts[-1]

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
        messages = [ChatMessage(role="user", content=user_prompt)]
        yield from self.client.chat_messages_stream(
            system, messages, enable_thinking=enable_thinking
        )
