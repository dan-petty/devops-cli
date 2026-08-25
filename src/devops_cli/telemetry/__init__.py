"""Telemetry and OpenTelemetry tracing module for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.tracer import (
    ContextPropagatingThreadPoolExecutor,
    OTelTelemetryClient,
    get_tracer,
    inject_trace_context,
    record_metric,
    reset_tracer,
    trace_span,
    traced,
)

__all__ = [
    "ContextPropagatingThreadPoolExecutor",
    "OTelTelemetryClient",
    "get_tracer",
    "inject_trace_context",
    "record_metric",
    "reset_tracer",
    "trace_span",
    "traced",
]
