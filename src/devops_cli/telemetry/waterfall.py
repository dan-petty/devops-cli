"""Waterfall visualization helpers and Jaeger trace querying for devops-cli."""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
from typing import Any

import httpx2

from devops_cli.core.validation import validate_url
from devops_cli.telemetry.tracer import SpanWaterfallNode

_TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{16,32}$")


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


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check whether an IP address targets link-local, cloud metadata, or non-loopback private networks."""
    return (
        ip.is_link_local or str(ip).startswith("169.254.") or (ip.is_private and not ip.is_loopback)
    )


def _resolve_safe_jaeger_target(
    parsed: urllib.parse.ParseResult,
) -> tuple[bool, str | None]:
    """Resolve Jaeger hostname and verify destination does not target metadata services.

    Returns (is_blocked, vetted_ip).
    """
    host = parsed.hostname or ""
    clean = host.strip("[]").rstrip(".").lower()
    if clean in ("169.254.169.254", "metadata.google.internal") or clean.startswith("169.254."):
        return True, None
    try:
        ip = ipaddress.ip_address(clean)
        if _is_unsafe_ip(ip):
            return True, None
        return False, str(ip)
    except ValueError:
        pass

    default_port = 443 if parsed.scheme == "https" else 80
    port = parsed.port or default_port
    try:
        addr_info = socket.getaddrinfo(clean, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0] if isinstance(sockaddr[0], str) else ""
            if ip_str and _is_unsafe_ip(ipaddress.ip_address(ip_str)):
                return True, None
        if addr_info and isinstance(addr_info[0][4][0], str):
            return False, addr_info[0][4][0]
    except socket.gaierror, OSError, ValueError:
        pass
    return False, None


def _is_blocked_metadata_host(host: str) -> bool:
    """Return True if host targets link-local or cloud metadata services."""
    parsed = urllib.parse.urlparse(f"http://{host}")
    is_blocked, _ = _resolve_safe_jaeger_target(parsed)
    return is_blocked


def query_jaeger_trace(
    trace_id: str,
    jaeger_url: str | None = None,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Fetch trace spans from Jaeger REST API (/api/traces/{trace_id})."""
    clean_id = trace_id.strip() if trace_id else ""
    if not clean_id or not _TRACE_ID_RE.fullmatch(clean_id):
        return []
    url = (jaeger_url or "http://localhost:16686").rstrip("/")
    try:
        validated_url = validate_url(url, purpose="jaeger", allow_private=True)
        parsed = urllib.parse.urlparse(validated_url)
        if not parsed.hostname:
            return []
        is_blocked, vetted_ip = _resolve_safe_jaeger_target(parsed)
        if is_blocked or not vetted_ip:
            return []
    except Exception:
        return []

    target_host = f"[{vetted_ip}]" if ":" in vetted_ip else vetted_ip
    target_netloc = f"{target_host}:{parsed.port}" if parsed.port else target_host
    base_path = parsed.path.rstrip("/")
    api_url = f"{parsed.scheme}://{target_netloc}{base_path}/api/traces/{clean_id}"
    req_headers = {"Host": parsed.netloc}

    try:
        with httpx2.Client(timeout=timeout) as client:
            resp = client.get(api_url, headers=req_headers)
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
