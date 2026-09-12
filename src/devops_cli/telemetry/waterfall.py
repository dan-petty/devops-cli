"""Waterfall visualization helpers and Jaeger trace querying for devops-cli."""

from __future__ import annotations

from typing import Any

import httpx2

from devops_cli.telemetry.tracer import SpanWaterfallNode


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


def _extract_jaeger_parent_id(references: list[dict[str, Any]]) -> str | None:
    """Extract parent span ID from Jaeger span references."""
    for ref in references:
        if ref.get("refType") == "CHILD_OF":
            return ref.get("spanID")
    return None


def _extract_jaeger_tags(tags: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Extract attributes and status code from Jaeger span tags."""
    attrs: list[dict[str, Any]] = []
    status_code = "STATUS_CODE_OK"
    for tag in tags:
        k = str(tag.get("key", ""))
        v = tag.get("value")
        attrs.append({"key": k, "value": {"stringValue": str(v)}})
        if k == "error" and v is True:
            status_code = "STATUS_CODE_ERROR"
    return attrs, status_code


def _convert_jaeger_span(span: dict[str, Any]) -> dict[str, Any]:
    """Convert single Jaeger span object into OpenTelemetry span dictionary."""
    start_us = int(span.get("startTime", 0))
    dur_us = int(span.get("duration", 0))
    attrs, status_code = _extract_jaeger_tags(span.get("tags", []))
    parent_id = _extract_jaeger_parent_id(span.get("references", []))
    return {
        "traceId": span.get("traceID", ""),
        "spanId": span.get("spanID", ""),
        "parentSpanId": parent_id,
        "name": span.get("operationName", "unknown"),
        "startTimeUnixNano": str(start_us * 1000),
        "endTimeUnixNano": str((start_us + dur_us) * 1000),
        "status": {"code": status_code},
        "attributes": attrs,
    }


def normalize_jaeger_spans(jaeger_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Jaeger HTTP API trace payload into standard OpenTelemetry span dicts."""
    traces = jaeger_data.get("data", [])
    if not isinstance(traces, list):
        return []
    spans_out: list[dict[str, Any]] = []
    for trace in traces:
        for span in trace.get("spans", []):
            spans_out.append(_convert_jaeger_span(span))
    return spans_out


def query_jaeger_trace(
    trace_id: str,
    jaeger_url: str | None = None,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Fetch trace spans from Jaeger REST API (/api/traces/{trace_id})."""
    if not trace_id:
        return []
    url = (jaeger_url or "http://localhost:16686").rstrip("/")
    api_url = f"{url}/api/traces/{trace_id}"
    try:
        with httpx2.Client(timeout=timeout) as client:
            resp = client.get(api_url)
            if resp.status_code != 200:
                return []
            return normalize_jaeger_spans(resp.json())
    except httpx2.RequestError, ValueError, OSError:
        return []


def resolve_trace_spans(
    trace_id: str | None = None,
    jaeger_url: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve trace spans from local buffer first, falling back to Jaeger query."""
    from devops_cli.telemetry.tracer import get_trace_spans

    spans = get_trace_spans(trace_id)
    if spans:
        resolved_id = str(spans[0].get("traceId", trace_id or "unknown"))
        return resolved_id, spans

    if trace_id:
        jaeger_spans = query_jaeger_trace(trace_id, jaeger_url=jaeger_url)
        if jaeger_spans:
            return trace_id, jaeger_spans

    return trace_id or "unknown", []


__all__ = [
    "flatten_waterfall_tree",
    "normalize_jaeger_spans",
    "query_jaeger_trace",
    "render_waterfall_bar",
    "resolve_trace_spans",
]
