"""OpenTelemetry log correlation bridge for standard library logging and SIEM audit logs."""

from __future__ import annotations

import logging

from devops_cli.telemetry.tracer import get_current_span_context


class TraceCorrelationFilter(logging.Filter):
    """Logging filter that injects active OpenTelemetry trace_id and span_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Enrich LogRecord with active trace_id and span_id attributes."""
        ctx = get_current_span_context() or {}
        setattr(record, "trace_id", ctx.get("trace_id") or "")
        setattr(record, "span_id", ctx.get("span_id") or "")
        return True


def get_current_trace_correlation() -> dict[str, str]:
    """Retrieve the current active trace_id and span_id as a dictionary."""
    ctx = get_current_span_context() or {}
    return {
        "trace_id": ctx.get("trace_id") or "",
        "span_id": ctx.get("span_id") or "",
    }


def attach_trace_correlation_filter(logger: logging.Logger | None = None) -> None:
    """Attach TraceCorrelationFilter to the specified logger or root logger."""
    target = logger or logging.getLogger()
    if not any(isinstance(f, TraceCorrelationFilter) for f in target.filters):
        target.addFilter(TraceCorrelationFilter())
