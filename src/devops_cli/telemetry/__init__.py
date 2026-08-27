"""Telemetry, OpenTelemetry tracing, and metrics module for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.context import (
    extract_traceparent,
    inject_traceparent_headers,
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
    "GLOBAL_METRICS",
    "ContextPropagatingThreadPoolExecutor",
    "InMemoryMetricsRegistry",
    "OTelTelemetryClient",
    "SpanWaterfallNode",
    "TraceCorrelationFilter",
    "attach_trace_correlation_filter",
    "build_span_waterfall_tree",
    "clear_span_buffer",
    "extract_traceparent",
    "get_current_span_context",
    "get_current_trace_correlation",
    "get_recent_spans",
    "get_trace_spans",
    "get_tracer",
    "inject_trace_context",
    "inject_traceparent_headers",
    "record_completed_span",
    "record_metric",
    "reset_tracer",
    "trace_span",
    "traced",
]
