"""Native Pydantic AI run subsystem for devops-cli.

Provides stateful async agent runs, execution results, conversational message
queuing, OpenTelemetry traceparent propagation, and graph execution components.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic_ai._enqueue import (
    EnqueueContent,
    PendingMessage,
    PendingMessagePriority,
)
from pydantic_ai._instrumentation import current_otel_traceparent
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart
from pydantic_ai.run import (
    AgentRun,
    AgentRunResult,
    AgentRunResultEvent,
)
from pydantic_graph import (
    BaseNode,
    End,
    EndMarker,
    ErrorMarker,
    GraphRun,
    GraphRunContext,
    GraphTaskRequest,
    JoinItem,
)
from pydantic_graph.step import NodeStep


def create_pending_message(
    content: Any,
    priority: PendingMessagePriority = "when_idle",
) -> PendingMessage:
    """Construct a native PendingMessage for queuing into an active agent execution."""
    if isinstance(content, PendingMessage):
        return content
    if isinstance(content, list) and all(isinstance(c, ModelMessage) for c in content):
        return PendingMessage(messages=content, priority=priority)
    msg = PendingMessage.from_content(content, priority=priority)
    if msg is not None:
        return msg
    return PendingMessage(
        messages=[ModelRequest(parts=[UserPromptPart(content=str(content))])],
        priority=priority,
    )


def get_active_traceparent() -> str | None:
    """Resolve the active OpenTelemetry W3C traceparent string using native Pydantic AI instrumentation."""
    traceparent = current_otel_traceparent()
    if traceparent:
        return traceparent

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-{ctx.trace_flags:02x}"
    except Exception:
        pass
    return None


def format_run_summary(result: AgentRunResult[Any] | Any) -> dict[str, Any]:
    """Extract and format structured execution metadata from an AgentRunResult."""
    run_id = getattr(result, "run_id", None)
    conv_id = getattr(result, "conversation_id", None)
    ts = getattr(result, "timestamp", None)
    if isinstance(ts, datetime):
        timestamp_str = ts.isoformat()
    elif ts:
        timestamp_str = str(ts)
    else:
        timestamp_str = None

    raw_output = getattr(result, "output", None)
    if raw_output is None and hasattr(result, "get_output") and callable(result.get_output):
        try:
            raw_output = result.get_output()
        except Exception:
            raw_output = None

    run_usage = getattr(result, "usage", None)
    in_tok = int(getattr(run_usage, "input_tokens", 0) or 0) if run_usage else 0
    out_tok = int(getattr(run_usage, "output_tokens", 0) or 0) if run_usage else 0
    total_tok = (
        int(getattr(run_usage, "total_tokens", in_tok + out_tok) or (in_tok + out_tok))
        if run_usage
        else 0
    )

    traceparent = (
        getattr(result, "_traceparent_value", None)
        or getattr(result, "traceparent", None)
        or get_active_traceparent()
    )

    return {
        "run_id": run_id,
        "conversation_id": conv_id,
        "timestamp": timestamp_str,
        "output": str(raw_output) if raw_output is not None else "",
        "usage": {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": total_tok,
        },
        "traceparent": traceparent,
    }


__all__ = [
    "AgentRun",
    "AgentRunResult",
    "AgentRunResultEvent",
    "BaseNode",
    "End",
    "EndMarker",
    "EnqueueContent",
    "ErrorMarker",
    "GraphRun",
    "GraphRunContext",
    "GraphTaskRequest",
    "JoinItem",
    "NodeStep",
    "PendingMessage",
    "PendingMessagePriority",
    "create_pending_message",
    "current_otel_traceparent",
    "format_run_summary",
    "get_active_traceparent",
]
