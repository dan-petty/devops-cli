"""Telemetry, OpenTelemetry tracing, and metrics module for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.context import (
    extract_traceparent,
    inject_traceparent_headers,
)
from devops_cli.telemetry.logfire import (
    AgentTurnHandle,
    LogfireBridge,
    LogfireOTelBridgeProcessor,
    LogfireStatus,
    get_logfire_bridge,
    logfire_agent_turn,
    render_agent_turn_panel,
    render_agent_turn_table,
    reset_logfire_bridge,
)
from devops_cli.telemetry.logging_bridge import (
    TraceCorrelationFilter,
    attach_trace_correlation_filter,
    get_current_trace_correlation,
)
from devops_cli.telemetry.metrics import (
    GLOBAL_METRICS,
    InMemoryMetricsRegistry,
)
from devops_cli.telemetry.tracer import (
    ContextPropagatingThreadPoolExecutor,
    OTelTelemetryClient,
    SpanWaterfallNode,
    build_span_waterfall_tree,
    clear_span_buffer,
    get_current_span_context,
    get_recent_spans,
    get_trace_spans,
    get_tracer,
    inject_trace_context,
    record_completed_span,
    record_metric,
    reset_tracer,
    trace_span,
    traced,
)

__all__ = [
    "AgentTurnHandle",
    "GLOBAL_METRICS",
    "ContextPropagatingThreadPoolExecutor",
    "InMemoryMetricsRegistry",
    "LogfireBridge",
    "LogfireOTelBridgeProcessor",
    "LogfireStatus",
    "OTelTelemetryClient",
    "SpanWaterfallNode",
    "TraceCorrelationFilter",
    "attach_trace_correlation_filter",
    "build_span_waterfall_tree",
    "clear_span_buffer",
    "extract_traceparent",
    "get_current_span_context",
    "get_current_trace_correlation",
    "get_logfire_bridge",
    "get_recent_spans",
    "get_trace_spans",
    "get_tracer",
    "inject_trace_context",
    "inject_traceparent_headers",
    "logfire_agent_turn",
    "record_completed_span",
    "record_metric",
    "render_agent_turn_panel",
    "render_agent_turn_table",
    "reset_logfire_bridge",
    "reset_tracer",
    "trace_span",
    "traced",
]
