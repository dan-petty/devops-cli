"""W3C traceparent and distributed context propagation helpers for devops-cli."""

from __future__ import annotations

import secrets

from devops_cli.telemetry.tracer import get_current_span_context


def generate_trace_id() -> str:
    """Generate 16-byte cryptographically random hex trace ID (32 hex characters)."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate 8-byte cryptographically random hex span ID (16 hex characters)."""
    return secrets.token_hex(8)


def generate_traceparent(trace_id: str | None = None, span_id: str | None = None) -> str:
    """Generate a standard W3C traceparent header string (00-{trace_id}-{span_id}-01)."""
    t_id = trace_id or generate_trace_id()
    s_id = span_id or generate_span_id()
    return f"00-{t_id}-{s_id}-01"


def inject_traceparent_headers(
    headers: dict[str, str] | None = None,
    auto_generate: bool = False,
    tracestate: str | None = None,
) -> dict[str, str]:
    """Inject W3C traceparent header into an HTTP headers dictionary.

    If an active span exists, its trace context is used.
    If no active span exists and auto_generate is True, a synthetic traceparent is generated.
    """
    result = dict(headers or {})
    ctx = get_current_span_context()
    if ctx and ctx.get("trace_id") and ctx.get("span_id"):
        trace_id = ctx["trace_id"]
        span_id = ctx["span_id"]
        # W3C format: version(00)-trace_id(32)-parent_id(16)-trace_flags(01)
        result["traceparent"] = f"00-{trace_id}-{span_id}-01"
    elif auto_generate and "traceparent" not in result:
        result["traceparent"] = generate_traceparent()

    if tracestate and "tracestate" not in result:
        result["tracestate"] = tracestate

    return result


def extract_traceparent(header_value: str | None) -> dict[str, str] | None:
    """Parse a W3C traceparent header string into trace_id and span_id components."""
    if not header_value:
        return None
    parts = header_value.strip().split("-")
    if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
        return {"trace_id": parts[1], "parent_span_id": parts[2], "trace_flags": parts[3]}
    return None


def extract_traceparent_from_headers(headers: dict[str, str]) -> dict[str, str] | None:
    """Case-insensitively extract and parse traceparent header from headers mapping."""
    for key, val in headers.items():
        if key.lower() == "traceparent":
            return extract_traceparent(val)
    return None
