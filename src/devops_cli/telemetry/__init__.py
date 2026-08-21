"""Telemetry and OpenTelemetry tracing module for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    record_metric,
    trace_span,
)

__all__ = [
    "OTelTelemetryClient",
    "get_tracer",
    "record_metric",
    "trace_span",
]
