"""W3C traceparent and distributed context propagation helpers for devops-cli."""

from __future__ import annotations

from devops_cli.telemetry.tracer import get_current_span_context


def inject_traceparent_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject W3C traceparent header into an HTTP headers dictionary if an active span exists."""
    result = dict(headers or {})
    ctx = get_current_span_context()
    if ctx and ctx.get("trace_id") and ctx.get("span_id"):
        trace_id = ctx["trace_id"]
        span_id = ctx["span_id"]
        # W3C format: version(00)-trace_id(32)-parent_id(16)-trace_flags(01)
        result["traceparent"] = f"00-{trace_id}-{span_id}-01"
    return result


def extract_traceparent(header_value: str | None) -> dict[str, str] | None:
    """Parse a W3C traceparent header string into trace_id and span_id components."""
    if not header_value:
        return None
    parts = header_value.strip().split("-")
    if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
        return {"trace_id": parts[1], "parent_span_id": parts[2]}
    return None
