"""Tool execution, step loop, thinking extraction, and output validation helpers."""

from __future__ import annotations

import concurrent.futures
import inspect
import json
import re
from collections.abc import Callable, Sequence
from typing import Any, cast

from pydantic import BaseModel

from devops_cli.ai.agents.capabilities import (
    BaseCapability,
    DeferredToolRequests,
    DeferredToolResults,
    HandleDeferredToolCalls,
    ToolApproved,
    ToolCallPart,
    ToolDenied,
)
from devops_cli.ai.agents.context import (
    AgentHooks,
    AgentStepNode,
    AgentUsage,
    RunContext,
)
from devops_cli.ai.agents.models import AgentResponse
from devops_cli.ai.agents.tools import AgentTool, ToolCall
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.exceptions import ModelRetry
from devops_cli.models.ai import ChatMessage

_TOOL_PROTOCOL_TEMPLATE = load_task_prompt("tool_execution_protocol.md")
_TOOL_FEEDBACK_TEMPLATE = load_task_prompt("agent_tool_feedback.md")
_TOOL_ALREADY_CALLED_PROMPT = load_task_prompt("agent_tool_already_called.md")
_INVOKE_TOOL_REQUEST_TEMPLATE = load_task_prompt("agent_invoke_tool_request.md")
_DIRECT_RESPONSE_FROM_TOOLS_PROMPT = load_task_prompt("agent_direct_response_from_tools.md")
_DIRECT_RESPONSE_FROM_REASONING_PROMPT = load_task_prompt("agent_direct_response_from_reasoning.md")


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
        from devops_cli.exceptions.ai import (
            ApprovalRequired,
            CallDeferred,
            SkipToolExecution,
            ToolFailed,
        )

        if isinstance(exc, SkipToolExecution):
            return "ok", clean_args, exc.result
        if isinstance(exc, ToolFailed):
            if hooks and ctx is not None:
                for h_err in hooks.on_tool_error:
                    try:
                        h_err(ctx, tool_name, exc)
                    except Exception:
                        pass
            return "tool_failed", clean_args, exc.message
        if isinstance(exc, ApprovalRequired):
            return "approval_required", clean_args, exc
        if isinstance(exc, CallDeferred):
            return "call_deferred", clean_args, exc

        if hooks and ctx is not None:
            for h_err in hooks.on_tool_error:
                try:
                    h_err(ctx, tool_name, exc)
                except Exception:
                    pass
        return "error", clean_args, f"Tool execution failed for {tool_name}: {exc}"
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


def _is_scratchpad_deliberation(final_output: str) -> bool:
    """Check if agent output is raw tool JSON rather than a final response."""
    if not final_output:
        return True
    return (
        final_output.startswith('{"tool"')
        or final_output.startswith('```json\n{"tool"')
        or ('"tool":' in final_output and '"arguments":' in final_output)
    )


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
    """Resolve final response string, falling back to tool outputs if empty."""
    if final_output and not _is_scratchpad_deliberation(final_output):
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


def _find_deferred_tool_handler(
    capabilities: Sequence[BaseCapability],
    req: DeferredToolRequests,
) -> DeferredToolResults | None:
    """Find and execute a capability handler for deferred tool requests."""
    for cap in capabilities:
        if isinstance(cap, HandleDeferredToolCalls):
            return cap.handle_deferred(req)
        handler_hook = getattr(cap, "handle_deferred_tool_calls", None) or getattr(
            cap, "handle_deferred", None
        )
        if callable(handler_hook):
            res = handler_hook(req)
            if isinstance(res, DeferredToolResults):
                return res
            if res is not None:
                return cast(DeferredToolResults, res)
    return None


def _create_deferred_tool_request(
    status: str,
    tool_name: str,
    clean_args: dict[str, Any],
    result: Any,
) -> DeferredToolRequests:
    """Construct a DeferredToolRequests object from a tool result."""
    part = ToolCallPart(tool_name=tool_name, args=clean_args, tool_call_id=tool_name)
    req = DeferredToolRequests()
    if status == "approval_required":
        req.approvals.append(part)
    else:
        req.calls.append(part)
    req_meta = getattr(result, "metadata", {})
    if req_meta:
        req.metadata[tool_name] = req_meta
    return req


def _handle_deferred_resolution(
    resolved_results: DeferredToolResults,
    tool_name: str,
    clean_args: dict[str, Any],
    tool_obj: AgentTool,
    tool_calls: list[ToolCall],
    messages: list[ChatMessage],
    response_text: str,
    ctx: RunContext[Any] | None,
    hooks: AgentHooks,
    effective_timeout: float | None,
) -> tuple[bool, str, dict[str, Any], Any]:
    """Process resolved approval or external call for a deferred tool request."""
    if tool_name in resolved_results.approvals:
        decision = resolved_results.approvals[tool_name]
        if isinstance(decision, ToolDenied) or decision is False:
            denial_msg = (
                decision.message if isinstance(decision, ToolDenied) else "Tool call was denied"
            )
            tool_calls.append(
                ToolCall(tool_name=tool_name, arguments=clean_args, result=denial_msg)
            )
            messages.append(ChatMessage(role="assistant", content=response_text))
            feedback = _TOOL_FEEDBACK_TEMPLATE.format(tool_name=tool_name, tool_result=denial_msg)
            messages.append(ChatMessage(role="user", content=feedback))
            return (True, "denied", clean_args, denial_msg)

        approved_args = dict(clean_args)
        if isinstance(decision, ToolApproved) and decision.override_args:
            approved_args.update(decision.override_args)
        approved_ctx = (
            ctx.model_copy(update={"tool_call_approved": True})
            if ctx is not None
            else RunContext[Any](tool_call_approved=True)
        )
        if tool_name in resolved_results.metadata:
            approved_ctx.tool_call_metadata = resolved_results.metadata[tool_name]
        status, clean_args, result = _execute_single_tool(
            tool_obj,
            tool_name,
            approved_args,
            tool_calls,
            ctx=approved_ctx,
            hooks=hooks,
            default_timeout=effective_timeout,
        )
        return (False, status, clean_args, result)

    if tool_name in resolved_results.calls:
        ext_val = resolved_results.calls[tool_name]
        tool_calls.append(ToolCall(tool_name=tool_name, arguments=clean_args, result=ext_val))
        messages.append(ChatMessage(role="assistant", content=response_text))
        feedback = _TOOL_FEEDBACK_TEMPLATE.format(
            tool_name=tool_name, tool_result=json.dumps(ext_val, default=str)
        )
        messages.append(ChatMessage(role="user", content=feedback))
        return (True, "external", clean_args, ext_val)

    return (False, "unresolved", clean_args, None)


def _build_deferred_agent_response(
    response_text: str,
    deferred_reqs: DeferredToolRequests,
    tool_calls: list[ToolCall],
    all_thoughts: list[str],
    turn: int,
    b_info: Any,
    input_tokens: int,
    output_tokens: int,
    messages: list[ChatMessage],
) -> AgentResponse[Any]:
    """Construct an AgentResponse containing deferred tool requests."""
    return AgentResponse[Any](
        content=response_text,
        data=deferred_reqs,
        tool_calls=tool_calls,
        thoughts=all_thoughts,
        turns=turn,
        backend_info=b_info,
        usage=AgentUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        messages=messages,
    )


def _append_deferred_request(
    target: DeferredToolRequests | None, req: DeferredToolRequests
) -> DeferredToolRequests:
    """Accumulate deferred tool requests."""
    if target is None:
        return req
    target.approvals.extend(req.approvals)
    target.calls.extend(req.calls)
    target.metadata.update(req.metadata)
    return target


def _resolve_thinking_preference(
    capabilities: Sequence[BaseCapability],
    loaded_ids: set[str],
    ctx: RunContext[Any] | None,
    default_thinking: bool,
) -> bool:
    """Determine whether thinking should be enabled based on capability model settings."""
    thinking = default_thinking
    for cap in capabilities:
        if not cap.defer_loading or cap.id in loaded_ids:
            cap_settings = cap.get_model_settings(ctx=ctx)
            if "enable_thinking" in cap_settings:
                thinking = bool(cap_settings["enable_thinking"])
    return thinking


def _execute_stream_tool_step(
    tc: Any,
    tool_obj: AgentTool,
    ctx: RunContext[Any] | None,
    hooks: AgentHooks,
    response_text: str,
    messages: list[ChatMessage],
) -> list[AgentStepNode]:
    """Execute a tool invocation during streaming and return emitted step nodes."""
    nodes: list[AgentStepNode] = [
        AgentStepNode(
            kind="tool_call", payload={"tool_name": tc.tool_name, "arguments": tc.arguments}
        )
    ]
    _, _, res = _execute_single_tool(tool_obj, tc.tool_name, tc.arguments, [], ctx=ctx, hooks=hooks)
    nodes.append(
        AgentStepNode(kind="tool_result", payload={"tool_name": tc.tool_name, "result": res})
    )
    messages.append(ChatMessage(role="assistant", content=response_text))
    feedback = _TOOL_FEEDBACK_TEMPLATE.format(
        tool_name=tc.tool_name, tool_result=json.dumps(res, default=str)
    )
    messages.append(ChatMessage(role="user", content=feedback))
    return nodes


def _validate_agent_output(
    output_validators: Sequence[Callable[..., Any]],
    target_val: Any,
    ctx: RunContext[Any] | None,
    fixed_model: Any | None,
) -> tuple[str | None, Any | None]:
    """Execute output validation functions and return (retry_message, updated_model)."""
    for val_fn in output_validators:
        try:
            sig = inspect.signature(val_fn)
            val_res = (
                val_fn(ctx, target_val)
                if len(sig.parameters) > 1 and ctx is not None
                else val_fn(target_val)
            )
            if fixed_model is not None and isinstance(val_res, BaseModel):
                fixed_model = val_res
        except ModelRetry as retry_exc:
            return (str(retry_exc), fixed_model)
        except Exception as exc:
            return (f"Output validation failed: {exc}", fixed_model)
    return (None, fixed_model)
