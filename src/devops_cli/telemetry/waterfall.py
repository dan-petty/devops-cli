"""Waterfall visualization helpers and Tempo trace querying for devops-cli."""

from __future__ import annotations

import base64
import binascii
import logging
import re
from typing import Any

import httpx2

from devops_cli.config.defaults import (
    DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS,
    DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS,
)
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.telemetry.tracer import SpanWaterfallNode

logger = logging.getLogger(__name__)

_TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{16,32}$")
_HEX_ID_RE = re.compile(r"^[0-9a-fA-F]+$")


def render_waterfall_bar(
    offset_pct: float, dur_pct: float, total_slots: int = 24, is_error: bool = False
) -> str:
    """Render a text-based Gantt-style execution bar for trace spans."""
    start_slot = min(total_slots - 1, int(offset_pct / 100.0 * total_slots))
    span_len = max(1, min(total_slots - start_slot, int(dur_pct / 100.0 * total_slots)))

    lead = " " * start_slot
    bar = "█" * span_len
    trail = " " * (total_slots - start_slot - span_len)

    color = (
        "red"
        if is_error
        else ("green" if dur_pct < 25 else ("yellow" if dur_pct < 65 else "magenta"))
    )
    return f"[{color}]{lead}{bar}{trail}[/{color}]"


def flatten_waterfall_tree(
    nodes: list[SpanWaterfallNode],
) -> list[tuple[SpanWaterfallNode, str]]:
    """Flatten hierarchical waterfall tree into list of (node, visual_prefix) tuples."""
    rows: list[tuple[SpanWaterfallNode, str]] = []

    def _walk(node: SpanWaterfallNode, prefix: str = "", is_last: bool = True) -> None:
        marker = "└─ " if is_last else "├─ "
        display_prefix = prefix + marker if node.depth > 0 else ""
        rows.append((node, display_prefix))
        child_prefix = prefix + ("   " if is_last else "│  ") if node.depth > 0 else ""
        for i, child in enumerate(node.children):
            _walk(child, child_prefix, i == len(node.children) - 1)

    for i, root in enumerate(nodes):
        _walk(root, "", i == len(nodes) - 1)
    return rows


def _decode_otlp_id(raw_id: Any) -> str:
    """Decode an OTLP traceId or spanId from hex or protojson base64 into lowercase hex."""
    if not isinstance(raw_id, str) or not raw_id:
        return ""
    if _HEX_ID_RE.fullmatch(raw_id):
        return raw_id.lower()
    try:
        return base64.b64decode(raw_id, validate=True).hex()
    except ValueError, binascii.Error:
        return raw_id


def _normalize_otlp_status(raw_status: Any) -> dict[str, Any]:
    """Normalize OTLP span status dictionary into standard code and message fields."""
    if not isinstance(raw_status, dict):
        return {"code": "STATUS_CODE_OK"}
    raw_code = raw_status.get("code", "STATUS_CODE_OK")
    code = (
        "STATUS_CODE_ERROR"
        if raw_code in ("STATUS_CODE_ERROR", "ERROR", 2, "2")
        else "STATUS_CODE_OK"
    )
    message = str(raw_status.get("message", ""))
    return {"code": code, "message": message} if message else {"code": code}


def _convert_tempo_span(span: dict[str, Any]) -> dict[str, Any]:
    """Convert a single Tempo OTLP span object into the normalized span dictionary."""
    parent_hex = _decode_otlp_id(span.get("parentSpanId"))
    parent_id = parent_hex if parent_hex and any(ch != "0" for ch in parent_hex) else None
    start_ns = str(span.get("startTimeUnixNano", "0"))
    end_ns = str(span.get("endTimeUnixNano", start_ns))
    raw_attrs = span.get("attributes")
    return {
        "traceId": _decode_otlp_id(span.get("traceId")),
        "spanId": _decode_otlp_id(span.get("spanId")),
        "parentSpanId": parent_id,
        "name": str(span.get("name", "unknown")),
        "startTimeUnixNano": start_ns,
        "endTimeUnixNano": end_ns,
        "status": _normalize_otlp_status(span.get("status")),
        "attributes": raw_attrs if isinstance(raw_attrs, list) else [],
    }


def _extract_resource_spans(tempo_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the resourceSpans or batches list from a Tempo /api/v2/traces response."""
    if not isinstance(tempo_data, dict):
        return []
    trace_obj = tempo_data.get("trace")
    candidates = (
        trace_obj.get("resourceSpans") if isinstance(trace_obj, dict) else None,
        tempo_data.get("resourceSpans"),
        tempo_data.get("batches"),
    )
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _iter_scope_spans(resource_span: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all span dicts nested inside a resourceSpan's scopeSpans."""
    scopes = resource_span.get("scopeSpans") or resource_span.get("instrumentationLibrarySpans")
    if not isinstance(scopes, list):
        return []
    return [
        span
        for scope in scopes
        if isinstance(scope, dict)
        for span in (scope.get("spans") or [])
        if isinstance(span, dict)
    ]


def normalize_tempo_spans(tempo_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Tempo HTTP API (/api/v2/traces/{id}) OTLP trace payload into standard span dicts."""
    return [
        _convert_tempo_span(span)
        for resource_span in _extract_resource_spans(tempo_data)
        for span in _iter_scope_spans(resource_span)
    ]


def query_tempo_trace(
    trace_id: str,
    tempo_url: str | None = None,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Fetch trace spans from Tempo HTTP API (/api/v2/traces/{trace_id}).

    Tempo is reached at its configured hostname through a loopback-level client, so the connect
    admits a public or loopback address and refuses private, link-local and metadata ones, whatever
    `ai.allow_private_network` says. TLS and the Host header carry the hostname. `timeout` bounds
    every phase of the request, the connect included.
    """
    clean_id = trace_id.strip() if trace_id else ""
    if not clean_id or not _TRACE_ID_RE.fullmatch(clean_id) or not tempo_url:
        return []
    api_url = f"{tempo_url.rstrip('/')}/api/v2/traces/{clean_id}"
    try:
        with new_http_client(level=EgressLevel.LOOPBACK, timeout=httpx2.Timeout(timeout)) as client:
            resp = client.get(api_url)
            if resp.status_code != 200:
                return []
            return normalize_tempo_spans(resp.json())
    except (httpx2.RequestError, httpx2.InvalidURL, SSRFBlockedError, ValueError) as exc:
        logger.warning("Failed to query Tempo trace %s: %s", clean_id, exc)
        return []


def resolve_trace_spans(
    trace_id: str | None = None,
    tempo_url: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve trace spans from local buffer first, falling back to Tempo query."""
    from devops_cli.telemetry.tracer import get_trace_spans

    spans = get_trace_spans(trace_id)
    if spans:
        resolved_id = str(spans[0].get("traceId", trace_id or "unknown"))
        return resolved_id, spans

    if trace_id:
        tempo_spans = query_tempo_trace(trace_id, tempo_url=tempo_url)
        if tempo_spans:
            return trace_id, tempo_spans

    return trace_id or "unknown", []


def poll_trace_spans(
    trace_id: str,
    tempo_url: str,
    *,
    timeout: float = DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS,
    interval: float = DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS,
    query_fn: Any = None,
) -> list[dict[str, Any]]:
    """Poll Tempo until the trace stops growing, within a fixed bound."""
    import time

    deadline = time.monotonic() + timeout
    spans: list[dict[str, Any]] = []
    fn = query_fn or query_tempo_trace
    while True:
        fetched = fn(trace_id, tempo_url=tempo_url)
        if fetched and len(fetched) == len(spans):
            return fetched
        spans = fetched or spans
        if time.monotonic() >= deadline:
            return spans
        time.sleep(interval)


def run_profiled_command(
    command: str,
    argv: list[str],
    tracer: Any,
) -> str:
    """Run a devops-cli command inside a profile span and return the trace it ran under."""
    import shlex
    import time

    from devops_cli.core.command_resolver import resolve_command_path
    from devops_cli.core.process import run_subprocess
    from devops_cli.output import print_info
    from devops_cli.telemetry.tracer import trace_span

    command_path, args_count = resolve_command_path(shlex.split(command)[1:])
    attributes = {"cli.command_path": command_path, "cli.args_count": args_count}
    with trace_span("telemetry.profile", attributes=attributes) as span_h:
        trace_id = tracer.current_trace_id or ""
        print_info(f"Profiling command: [bold]{command}[/bold] (Trace: {trace_id})", prefix=False)
        start_time = time.perf_counter()
        proc = run_subprocess(argv, capture_output=False, quiet=True, isolate_env=False)
        span_h.set_attribute("cli.exit_code", proc.returncode)
        span_h.set_attribute("cli.elapsed_ms", (time.perf_counter() - start_time) * 1000)
    tracer.flush()
    return trace_id


read_trace_from_tempo = poll_trace_spans


__all__ = [
    "flatten_waterfall_tree",
    "normalize_tempo_spans",
    "poll_trace_spans",
    "query_tempo_trace",
    "read_trace_from_tempo",
    "render_waterfall_bar",
    "resolve_trace_spans",
    "run_profiled_command",
]
