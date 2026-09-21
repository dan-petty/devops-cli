"""W3C Trace Context propagation across HTTP calls, processes, and threads.

Parsing and formatting of `traceparent` previously existed twice, in
`telemetry/context.py` and on the tracer client, and the two disagreed about what a valid
header is: one checked field lengths and ignored the version, the other checked the version
and ignored the lengths. Neither rejected non-hexadecimal characters, so a malformed value
inherited from the environment propagated into trace ids and out to the exporter.

This module is the single implementation. It validates against the specification, and it
distinguishes the two carriers that must not share a spelling: HTTP headers are lowercase
`traceparent`, process environments are uppercase `TRACEPARENT`.

Reference: https://www.w3.org/TR/trace-context/
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Final

from devops_cli.config.constants import (
    CONST_SPAN_ID_HEX_LENGTH,
    CONST_TRACE_FLAG_NOT_SAMPLED,
    CONST_TRACE_FLAG_SAMPLED,
    CONST_TRACE_FLAGS_HEX_LENGTH,
    CONST_TRACE_ID_HEX_LENGTH,
    CONST_TRACEPARENT_ENV_VAR,
    CONST_TRACEPARENT_HEADER,
    CONST_TRACEPARENT_INVALID_VERSION,
    CONST_TRACEPARENT_VERSION,
    CONST_TRACESTATE_ENV_VAR,
    CONST_TRACESTATE_HEADER,
    CONST_TRACESTATE_MAX_MEMBERS,
)

_HEX_DIGITS: Final[frozenset[str]] = frozenset("0123456789abcdef")


def _is_lower_hex(value: str, length: int) -> bool:
    """Report whether a value is exactly `length` lowercase hexadecimal digits.

    The specification requires lowercase; accepting uppercase would let the same context be
    represented two ways and compare unequal downstream.
    """
    return len(value) == length and all(char in _HEX_DIGITS for char in value)


def _is_all_zero(value: str) -> bool:
    """Report whether an id is the all-zero value the specification forbids."""
    return value == "0" * len(value)


def generate_trace_id() -> str:
    """Generate a 16-byte random trace id as 32 lowercase hex characters."""
    return secrets.token_hex(CONST_TRACE_ID_HEX_LENGTH // 2)


def generate_span_id() -> str:
    """Generate an 8-byte random span id as 16 lowercase hex characters."""
    return secrets.token_hex(CONST_SPAN_ID_HEX_LENGTH // 2)


@dataclass(frozen=True)
class TraceContext:
    """A validated W3C trace context."""

    trace_id: str
    span_id: str
    trace_flags: str = CONST_TRACE_FLAG_SAMPLED
    trace_state: str | None = None

    @property
    def sampled(self) -> bool:
        """Report whether the sampled bit is set."""
        try:
            return bool(int(self.trace_flags, 16) & 0x01)
        except ValueError:
            return False

    def to_traceparent(self) -> str:
        """Render this context as a `traceparent` value."""
        return f"{CONST_TRACEPARENT_VERSION}-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    def child(self, span_id: str | None = None) -> TraceContext:
        """Derive a context for a child span within the same trace."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=span_id or generate_span_id(),
            trace_flags=self.trace_flags,
            trace_state=self.trace_state,
        )


def new_trace_context(sampled: bool = True) -> TraceContext:
    """Start a fresh root trace context."""
    return TraceContext(
        trace_id=generate_trace_id(),
        span_id=generate_span_id(),
        trace_flags=CONST_TRACE_FLAG_SAMPLED if sampled else CONST_TRACE_FLAG_NOT_SAMPLED,
    )


def parse_traceparent(value: str | None, trace_state: str | None = None) -> TraceContext | None:
    """Parse a `traceparent` value, returning ``None`` if it is not valid.

    Invalid input yields ``None`` rather than raising, because the value arrives from a
    caller's headers or from the ambient environment. The correct response to a malformed
    upstream context is to start a new trace, not to fail the operation that carried it.
    """
    if not value:
        return None
    fields = value.strip().split("-")
    if len(fields) < 4:
        return None

    version, trace_id, span_id, flags = fields[0], fields[1], fields[2], fields[3]
    if not _is_lower_hex(version, 2) or version == CONST_TRACEPARENT_INVALID_VERSION:
        return None
    # Version 00 defines exactly four fields; later versions may append more, which this
    # implementation ignores rather than rejects, as the specification requires.
    if version == CONST_TRACEPARENT_VERSION and len(fields) != 4:
        return None
    if not _is_lower_hex(trace_id, CONST_TRACE_ID_HEX_LENGTH) or _is_all_zero(trace_id):
        return None
    if not _is_lower_hex(span_id, CONST_SPAN_ID_HEX_LENGTH) or _is_all_zero(span_id):
        return None
    if not _is_lower_hex(flags, CONST_TRACE_FLAGS_HEX_LENGTH):
        return None

    return TraceContext(
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=flags,
        trace_state=sanitize_tracestate(trace_state),
    )


def sanitize_tracestate(value: str | None) -> str | None:
    """Trim a `tracestate` value to the list members the specification permits.

    An oversized or empty header is dropped rather than forwarded: vendors are required to
    truncate, and passing one through unchanged breaks the next hop instead of this one.
    """
    if not value:
        return None
    members = [member.strip() for member in value.split(",") if member.strip()]
    if not members:
        return None
    return ",".join(members[:CONST_TRACESTATE_MAX_MEMBERS])


# =============================================================================
# HTTP header carrier
# =============================================================================


def inject_headers(context: TraceContext, headers: dict[str, str] | None = None) -> dict[str, str]:
    """Return a copy of `headers` carrying this context, using lowercase header names."""
    result = dict(headers or {})
    result[CONST_TRACEPARENT_HEADER] = context.to_traceparent()
    if context.trace_state:
        result[CONST_TRACESTATE_HEADER] = context.trace_state
    return result


def extract_headers(headers: dict[str, str]) -> TraceContext | None:
    """Extract a trace context from HTTP headers, matching names case-insensitively."""
    folded = {key.lower(): value for key, value in headers.items()}
    return parse_traceparent(
        folded.get(CONST_TRACEPARENT_HEADER), folded.get(CONST_TRACESTATE_HEADER)
    )


# =============================================================================
# Process environment carrier
# =============================================================================


def inject_env(context: TraceContext, env: dict[str, str]) -> dict[str, str]:
    """Write this context into a child process environment, in place.

    The environment is mutated rather than copied because the caller has already built the
    environment it is about to pass to the child; returning a copy is how the context came
    to be silently dropped before.

    The value is written under the uppercase name and any inherited lowercase spelling is
    removed, so a stale context inherited from a grandparent process cannot shadow the one
    being injected here.
    """
    env[CONST_TRACEPARENT_ENV_VAR] = context.to_traceparent()
    env.pop(CONST_TRACEPARENT_HEADER, None)
    if context.trace_state:
        env[CONST_TRACESTATE_ENV_VAR] = context.trace_state
    else:
        env.pop(CONST_TRACESTATE_ENV_VAR, None)
    env.pop(CONST_TRACESTATE_HEADER, None)
    return env


def extract_env(env: dict[str, str] | None = None) -> TraceContext | None:
    """Extract the trace context a parent process passed to this one."""
    source = os.environ if env is None else env
    raw = source.get(CONST_TRACEPARENT_ENV_VAR) or source.get(CONST_TRACEPARENT_HEADER)
    state = source.get(CONST_TRACESTATE_ENV_VAR) or source.get(CONST_TRACESTATE_HEADER)
    return parse_traceparent(raw, state)


__all__ = [
    "TraceContext",
    "extract_env",
    "extract_headers",
    "generate_span_id",
    "generate_trace_id",
    "inject_env",
    "inject_headers",
    "new_trace_context",
    "parse_traceparent",
    "sanitize_tracestate",
]
