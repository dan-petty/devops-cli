"""W3C traceparent helpers, layered over the single propagation implementation.

This module previously carried its own traceparent parser and formatter, which disagreed
with the tracer client's: this one validated field lengths and ignored the version, the
other validated the version and ignored the lengths, and neither rejected non-hexadecimal
characters. Both now delegate to :mod:`devops_cli.telemetry.propagation`, so a value is
valid here exactly when it is valid there.
"""

from __future__ import annotations

from dataclasses import replace

from devops_cli.config.constants import (
    CONST_TRACE_FLAG_NOT_SAMPLED,
    CONST_TRACE_FLAG_SAMPLED,
    CONST_TRACEPARENT_HEADER,
    CONST_TRACESTATE_HEADER,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.telemetry.propagation import (
    TraceContext,
    extract_headers,
    generate_span_id,
    generate_trace_id,
    inject_headers,
    new_trace_context,
    parse_traceparent,
    sanitize_tracestate,
)
from devops_cli.telemetry.tracer import get_current_span_context

__all__ = [
    "TraceValidationError",
    "extract_traceparent",
    "extract_traceparent_from_headers",
    "generate_span_id",
    "generate_trace_id",
    "generate_traceparent",
    "inject_traceparent_headers",
]


class TraceValidationError(ValidationError, ValueError):
    """Raised when trace metadata or flags fail validation."""


def generate_traceparent(
    trace_id: str | None = None,
    span_id: str | None = None,
    trace_flags: str = CONST_TRACE_FLAG_SAMPLED,
) -> str:
    """Generate a W3C traceparent header value.

    Raises on invalid input, unlike parsing: a caller constructing a context here has made
    a programming error, whereas a caller parsing one has received bad input.
    """
    if trace_flags not in {CONST_TRACE_FLAG_NOT_SAMPLED, CONST_TRACE_FLAG_SAMPLED}:
        raise TraceValidationError(
            f"Invalid trace_flags '{trace_flags}': must be "
            f"'{CONST_TRACE_FLAG_NOT_SAMPLED}' or '{CONST_TRACE_FLAG_SAMPLED}'"
        )
    context = TraceContext(
        trace_id=trace_id or generate_trace_id(),
        span_id=span_id or generate_span_id(),
        trace_flags=trace_flags,
    )
    traceparent = context.to_traceparent()
    if parse_traceparent(traceparent) is None:
        raise TraceValidationError(f"Invalid trace context components: '{traceparent}'")
    return traceparent


def inject_traceparent_headers(
    headers: dict[str, str] | None = None,
    auto_generate: bool = False,
    tracestate: str | None = None,
) -> dict[str, str]:
    """Inject a W3C traceparent into an HTTP headers mapping.

    The active span's context is used when one exists. With no active span, a synthetic
    context is generated only if `auto_generate` is set, since inventing a trace id that
    corresponds to no recorded span produces a trace no backend can resolve.
    """
    result = dict(headers or {})
    span = get_current_span_context()
    trace_id, span_id = span.get("trace_id"), span.get("span_id")
    state = sanitize_tracestate(tracestate)

    context: TraceContext | None = None
    if trace_id and span_id:
        context = TraceContext(trace_id=trace_id, span_id=span_id, trace_state=state)
    elif auto_generate and CONST_TRACEPARENT_HEADER not in {key.lower() for key in result}:
        context = replace(new_trace_context(), trace_state=state)

    if context is not None:
        return inject_headers(context, result)

    if state and CONST_TRACESTATE_HEADER not in {key.lower() for key in result}:
        result[CONST_TRACESTATE_HEADER] = state
    return result


def extract_traceparent(header_value: str | None) -> dict[str, str] | None:
    """Parse a W3C traceparent value into its components, or ``None`` if it is invalid."""
    context = parse_traceparent(header_value)
    if context is None:
        return None
    return {
        "trace_id": context.trace_id,
        "parent_span_id": context.span_id,
        "trace_flags": context.trace_flags,
    }


def extract_traceparent_from_headers(headers: dict[str, str]) -> dict[str, str] | None:
    """Case-insensitively extract and parse a traceparent from a headers mapping."""
    context = extract_headers(headers)
    if context is None:
        return None
    return {
        "trace_id": context.trace_id,
        "parent_span_id": context.span_id,
        "trace_flags": context.trace_flags,
    }
