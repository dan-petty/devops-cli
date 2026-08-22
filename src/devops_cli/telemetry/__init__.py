"""Telemetry and OpenTelemetry tracing module for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    inject_trace_context,
    record_metric,
    reset_tracer,
    trace_span,
    traced,
)

__all__ = [
    "OTelTelemetryClient",
    "get_tracer",
    "inject_trace_context",
    "record_metric",
    "reset_tracer",
    "trace_span",
    "traced",
]
