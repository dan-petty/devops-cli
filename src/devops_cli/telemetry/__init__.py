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
    get_current_span_context,
    get_tracer,
    inject_trace_context,
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
    "TraceCorrelationFilter",
    "attach_trace_correlation_filter",
    "extract_traceparent",
    "get_current_span_context",
    "get_current_trace_correlation",
    "get_tracer",
    "inject_trace_context",
    "inject_traceparent_headers",
    "record_metric",
    "reset_tracer",
    "trace_span",
    "traced",
]
