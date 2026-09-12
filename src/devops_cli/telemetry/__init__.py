"""Telemetry, OpenTelemetry tracing, and metrics module for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.context import (
    extract_traceparent,
    extract_traceparent_from_headers,
    generate_span_id,
    generate_trace_id,
    generate_traceparent,
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
from devops_cli.telemetry.waterfall import (
    flatten_waterfall_tree,
    normalize_jaeger_spans,
    query_jaeger_trace,
    render_waterfall_bar,
    resolve_trace_spans,
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
    "extract_traceparent_from_headers",
    "flatten_waterfall_tree",
    "generate_span_id",
    "generate_trace_id",
    "generate_traceparent",
    "get_current_span_context",
    "get_current_trace_correlation",
    "get_logfire_bridge",
    "get_recent_spans",
    "get_trace_spans",
    "get_tracer",
    "inject_trace_context",
    "inject_traceparent_headers",
    "logfire_agent_turn",
    "normalize_jaeger_spans",
    "query_jaeger_trace",
    "record_completed_span",
    "record_metric",
    "render_agent_turn_panel",
    "render_agent_turn_table",
    "render_waterfall_bar",
    "reset_logfire_bridge",
    "reset_tracer",
    "resolve_trace_spans",
    "trace_span",
    "traced",
]
