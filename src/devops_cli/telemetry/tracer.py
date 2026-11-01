"""Lightweight OpenTelemetry OTLP tracing and metrics emitter for devops-cli."""

from __future__ import annotations

import atexit
import contextlib
import contextvars
import functools
import hashlib
import logging
import os
import platform
import secrets
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Generator
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_OTEL_METRIC_UNIT_ONE,
    CONST_OTEL_SCOPE_NAME,
    CONST_OTEL_SERVICE_NAME,
    CONST_OTEL_SPAN_KIND_INTERNAL,
)
from devops_cli.config.defaults import (
    DEFAULT_OTEL_COUNTER_AMOUNT,
    DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS,
    DEFAULT_OTEL_ENDPOINT,
    DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS,
    DEFAULT_OTEL_TEST_TIMEOUT,
    DEFAULT_OTEL_WARNING_INTERVAL_SECONDS,
    DEFAULT_SPAN_BUFFER_MAX_SPANS,
)
from devops_cli.exceptions.telemetry import OtlpProtocolError
from devops_cli.telemetry.exporter import (
    JSON_CONTENT_TYPE,
    OtlpExporter,
    OtlpSignal,
    RefusedExporter,
    json_body,
    otlp_exporter,
)
from devops_cli.telemetry.propagation import (
    TraceContext,
    extract_env,
    extract_headers,
    inject_env,
    inject_headers,
    new_trace_context,
)

if TYPE_CHECKING:
    from devops_cli.config.settings import TelemetryConfig

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ContextPropagatingThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor that automatically propagates ContextVar snapshots to worker threads."""

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:  # type: ignore[override]
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, fn, *args, **kwargs)


class ContextPropagatingThread(threading.Thread):
    """Thread that runs its target under a snapshot of the spawning thread's context.

    Unless the interpreter is started with `thread_inherit_context`, a thread begins with
    empty context variables, so work moved onto one loses the active trace and any span it
    opens becomes a new root. The snapshot is taken in the constructor, which still runs on
    the spawning thread, and handed to the native `context` parameter rather than assigned
    over the attribute the standard library uses for it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("context", contextvars.copy_context())
        super().__init__(*args, **kwargs)


def bind_context(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Callable[[], Any]:
    """Bind a callable to a snapshot of the *caller's* context.

    The snapshot has to be taken here, on the thread that still holds the context. A helper
    that copied the context inside the worker would capture the worker's own empty context
    and silently propagate nothing, which is the failure it exists to prevent.

    Intended for handing work to a pool this module does not own::

        pool.submit(bind_context(do_work, arg))
    """
    ctx = contextvars.copy_context()
    return functools.partial(ctx.run, fn, *args, **kwargs)


def _generate_trace_id() -> str:
    return secrets.token_hex(16)


def _generate_span_id() -> str:
    return secrets.token_hex(8)


def _otlp_attributes(attributes: dict[str, Any] | None) -> list[dict[str, Any]]:
    """OTLP key-value attributes."""
    return [{"key": k, "value": _to_otlp_any_value(v)} for k, v in (attributes or {}).items()]


def _sdk_metric_attributes(
    attributes: dict[str, Any] | None,
) -> dict[str, str | bool | int | float]:
    """Normalize metric attributes to scalar values accepted by the OTel SDK."""
    if not attributes:
        return {}
    return {
        str(k): v if isinstance(v, (str, bool, int, float)) else str(v)
        for k, v in attributes.items()
        if v is not None
    }


def _encode_sum_metric(metric: Any, data: Any) -> dict[str, Any]:
    points = [
        {
            "startTimeUnixNano": str(dp.start_time_unix_nano),
            "timeUnixNano": str(dp.time_unix_nano),
            "asDouble": float(dp.value),
            "attributes": _otlp_attributes(dict(dp.attributes)),
        }
        for dp in data.data_points
    ]
    return {
        "name": metric.name,
        "unit": metric.unit,
        "sum": {
            "dataPoints": points,
            "aggregationTemporality": int(data.aggregation_temporality),
            "isMonotonic": bool(data.is_monotonic),
        },
    }


def _encode_gauge_metric(metric: Any, data: Any) -> dict[str, Any]:
    points = [
        {
            "timeUnixNano": str(dp.time_unix_nano),
            "asDouble": float(dp.value),
            "attributes": _otlp_attributes(dict(dp.attributes)),
        }
        for dp in data.data_points
    ]
    return {"name": metric.name, "unit": metric.unit, "gauge": {"dataPoints": points}}


def _encode_exponential_histogram_metric(metric: Any, data: Any) -> dict[str, Any]:
    points = [
        {
            "startTimeUnixNano": str(dp.start_time_unix_nano),
            "timeUnixNano": str(dp.time_unix_nano),
            "count": dp.count,
            "sum": float(dp.sum),
            "scale": dp.scale,
            "zeroCount": dp.zero_count,
            "positive": {
                "offset": dp.positive.offset,
                "bucketCounts": list(dp.positive.bucket_counts),
            },
            "negative": {
                "offset": dp.negative.offset,
                "bucketCounts": list(dp.negative.bucket_counts),
            },
            "min": float(dp.min),
            "max": float(dp.max),
            "attributes": _otlp_attributes(dict(dp.attributes)),
        }
        for dp in data.data_points
    ]
    return {
        "name": metric.name,
        "unit": metric.unit,
        "exponentialHistogram": {
            "dataPoints": points,
            "aggregationTemporality": int(data.aggregation_temporality),
        },
    }


def _encode_sdk_metric_entry(metric: Any) -> dict[str, Any]:
    """Encode an OTel SDK Metric into an OTLP JSON metric entry."""
    from opentelemetry.sdk.metrics.export import ExponentialHistogram, Gauge, Sum

    data = metric.data
    if isinstance(data, Sum):
        return _encode_sum_metric(metric, data)
    if isinstance(data, Gauge):
        return _encode_gauge_metric(metric, data)
    if isinstance(data, ExponentialHistogram):
        return _encode_exponential_histogram_metric(metric, data)
    return {"name": metric.name, "unit": metric.unit}


def _encode_sdk_metrics_data(metrics_data: Any) -> dict[str, Any]:
    """Encode an OTel SDK MetricsData batch into an OTLP JSON resourceMetrics payload."""
    resource_metrics: list[dict[str, Any]] = []
    for rm in metrics_data.resource_metrics:
        scope_metrics = [
            {
                "scope": {"name": sm.scope.name},
                "metrics": [_encode_sdk_metric_entry(m) for m in sm.metrics if m.data.data_points],
            }
            for sm in rm.scope_metrics
        ]
        scope_metrics = [sm for sm in scope_metrics if sm["metrics"]]
        if scope_metrics:
            resource_metrics.append(
                {
                    "resource": {"attributes": _otlp_attributes(dict(rm.resource.attributes))},
                    "scopeMetrics": scope_metrics,
                }
            )
    return {"resourceMetrics": resource_metrics}


def _to_otlp_any_value(val: Any) -> dict[str, Any]:
    """Convert a Python scalar or sequence into a strongly-typed OpenTelemetry AnyValue dict."""
    if isinstance(val, bool):
        return {"boolValue": val}
    if isinstance(val, int):
        return {"intValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": float(val)}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, (list, tuple)):
        return {"arrayValue": {"values": [_to_otlp_any_value(item) for item in val]}}
    if isinstance(val, dict):
        return {
            "kvlistValue": {
                "values": [{"key": k, "value": _to_otlp_any_value(v)} for k, v in val.items()]
            }
        }
    return {"stringValue": str(val)}


_SPAN_KINDS = {
    "internal": "SPAN_KIND_INTERNAL",
    "server": "SPAN_KIND_SERVER",
    "client": "SPAN_KIND_CLIENT",
    "producer": "SPAN_KIND_PRODUCER",
    "consumer": "SPAN_KIND_CONSUMER",
}


class SpanWaterfallNode(BaseModel):
    """Hierarchical node representing a completed OpenTelemetry span for visual profiling."""

    span_id: str
    trace_id: str
    name: str
    parent_id: str | None = None
    start_time_ns: int
    end_time_ns: int
    duration_ms: float
    status_code: str
    status_message: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    depth: int = 0
    relative_offset_pct: float = 0.0
    relative_duration_pct: float = 0.0
    children: list[SpanWaterfallNode] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize waterfall node into dictionary structure."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "duration_ms": round(self.duration_ms, 2),
            "status_code": self.status_code,
            "status_message": self.status_message,
            "depth": self.depth,
            "relative_offset_pct": round(self.relative_offset_pct, 2),
            "relative_duration_pct": round(self.relative_duration_pct, 2),
            "attributes": self.attributes,
            "children": [c.to_dict() for c in self.children],
        }


_SPANS_BUFFER_LOCK = threading.Lock()
_MAX_SPANS_BUFFER_SIZE = DEFAULT_SPAN_BUFFER_MAX_SPANS
# A deque evicts in constant time. The list this replaced used pop(0), which shifts every
# retained span on each append once the buffer is full, so the cost of recording a span
# grew with the retention limit exactly when spans were arriving fastest.
_COMPLETED_SPANS_BUFFER: deque[dict[str, Any]] = deque(maxlen=_MAX_SPANS_BUFFER_SIZE)


def record_completed_span(span_data: dict[str, Any]) -> None:
    """Store a completed span in the bounded, thread-safe in-memory ring buffer."""
    with _SPANS_BUFFER_LOCK:
        _COMPLETED_SPANS_BUFFER.append(dict(span_data))


def get_recent_spans() -> list[dict[str, Any]]:
    """Retrieve copy of all buffered completed spans."""
    with _SPANS_BUFFER_LOCK:
        return [dict(s) for s in _COMPLETED_SPANS_BUFFER]


def clear_span_buffer() -> None:
    """Clear in-memory span buffer (used in tests and profiling)."""
    with _SPANS_BUFFER_LOCK:
        _COMPLETED_SPANS_BUFFER.clear()


def get_trace_spans(trace_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve spans for a specific trace_id, or the latest recorded trace if None."""
    with _SPANS_BUFFER_LOCK:
        if not _COMPLETED_SPANS_BUFFER:
            return []
        if trace_id is None:
            target_trace_id = _COMPLETED_SPANS_BUFFER[-1].get("traceId")
        else:
            target_trace_id = trace_id
        return [s for s in _COMPLETED_SPANS_BUFFER if s.get("traceId") == target_trace_id]


def _from_otlp_any_value(val: dict[str, Any]) -> Any:
    """Extract Python scalar or sequence from an OpenTelemetry AnyValue dict."""
    if "stringValue" in val:
        return val["stringValue"]
    if "boolValue" in val:
        return val["boolValue"]
    if "intValue" in val:
        try:
            return int(val["intValue"])
        except ValueError:
            return val["intValue"]
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "arrayValue" in val:
        return [_from_otlp_any_value(v) for v in val["arrayValue"].get("values", [])]
    if "kvlistValue" in val:
        return {
            item["key"]: _from_otlp_any_value(item["value"])
            for item in val["kvlistValue"].get("values", [])
            if "key" in item and "value" in item
        }
    return str(val)


def _extract_span_attributes(raw_attrs: Any) -> dict[str, Any]:
    """Extract attributes dictionary from dict or OTLP key-value list."""
    if isinstance(raw_attrs, dict):
        return dict(raw_attrs)
    if not isinstance(raw_attrs, list):
        return {}
    attrs: dict[str, Any] = {}
    for attr in raw_attrs:
        if not isinstance(attr, dict):
            continue
        k = attr.get("key")
        v = attr.get("value")
        if k and v:
            attrs[k] = _from_otlp_any_value(v)
    return attrs


def _build_waterfall_node(s: dict[str, Any]) -> SpanWaterfallNode:
    """Construct a SpanWaterfallNode from a raw span dictionary."""
    span_id = str(s.get("spanId", ""))
    trace_id = str(s.get("traceId", ""))
    name = str(s.get("name", "unknown"))
    parent_id = s.get("parentSpanId")
    start_ns = int(s.get("startTimeUnixNano", 0))
    end_ns = int(s.get("endTimeUnixNano", start_ns))
    dur_ms = max(0.0, (end_ns - start_ns) / 1e6)
    status_info = s.get("status", {})
    status_code = status_info.get("code", "STATUS_CODE_OK")
    status_msg = status_info.get("message", "")
    attrs = _extract_span_attributes(s.get("attributes", []))

    return SpanWaterfallNode(
        span_id=span_id,
        trace_id=trace_id,
        name=name,
        parent_id=str(parent_id) if parent_id else None,
        start_time_ns=start_ns,
        end_time_ns=end_ns,
        duration_ms=dur_ms,
        status_code=status_code,
        status_message=status_msg,
        attributes=attrs,
    )


def _compute_relative_waterfall_offsets(nodes: dict[str, SpanWaterfallNode]) -> None:
    """Calculate relative offset and duration percentages across all nodes."""
    min_start_ns = min(n.start_time_ns for n in nodes.values())
    max_end_ns = max(n.end_time_ns for n in nodes.values())
    total_span_ns = max(1, max_end_ns - min_start_ns)

    for n in nodes.values():
        offset_ns = max(0, n.start_time_ns - min_start_ns)
        dur_ns = max(0, n.end_time_ns - n.start_time_ns)
        n.relative_offset_pct = (offset_ns / total_span_ns) * 100.0
        n.relative_duration_pct = max(1.0, (dur_ns / total_span_ns) * 100.0)


def _assign_waterfall_depth(node: SpanWaterfallNode, current_depth: int) -> None:
    """Recursively assign depth levels to waterfall nodes."""
    node.depth = current_depth
    node.children.sort(key=lambda x: x.start_time_ns)
    for child in node.children:
        _assign_waterfall_depth(child, current_depth + 1)


def _link_waterfall_hierarchy(
    nodes: dict[str, SpanWaterfallNode],
) -> list[SpanWaterfallNode]:
    """Assemble flat nodes into parent-child tree hierarchy and order by start time."""
    roots: list[SpanWaterfallNode] = []
    for n in nodes.values():
        if n.parent_id and n.parent_id in nodes and n.parent_id != n.span_id:
            nodes[n.parent_id].children.append(n)
        else:
            roots.append(n)

    roots.sort(key=lambda x: x.start_time_ns)
    for root in roots:
        _assign_waterfall_depth(root, 0)
    return roots


def build_span_waterfall_tree(spans: list[dict[str, Any]]) -> list[SpanWaterfallNode]:
    """Convert raw span dicts into a structured hierarchy with relative waterfall offsets and percentage durations."""
    if not spans:
        return []

    nodes: dict[str, SpanWaterfallNode] = {
        str(s.get("spanId", "")): _build_waterfall_node(s) for s in spans
    }
    _compute_relative_waterfall_offsets(nodes)
    return _link_waterfall_hierarchy(nodes)


class SpanHandle(str):
    """Handle yielded by trace_span allowing dynamic attribute updates, links, and event logging while
    behaving as span_id string."""

    _attributes: dict[str, Any]
    _events: list[dict[str, Any]]
    _links: list[dict[str, Any]]

    def __new__(
        cls,
        span_id: str,
        attributes: dict[str, Any] | None = None,
        events: list[dict[str, Any]] | None = None,
        links: list[dict[str, Any]] | None = None,
    ) -> SpanHandle:
        obj = str.__new__(cls, span_id)
        obj._attributes = attributes if attributes is not None else {}
        obj._events = events if events is not None else []
        obj._links = links if links is not None else []
        return obj

    def set_status(self, code: str, message: str = "") -> None:
        """Set span status code and description."""
        normalized_code = code.upper()
        self._attributes["otel.status_code"] = normalized_code
        if normalized_code == "ERROR":
            self._attributes["error"] = True
            if message:
                self._attributes["otel.status_description"] = message

    def set_attribute(self, key: str, value: Any) -> None:
        """Set or update a single attribute on the active span."""
        self._attributes[key] = value

    def set_attributes(self, mapping: dict[str, Any]) -> None:
        """Set or update multiple attributes on the active span."""
        self._attributes.update(mapping)

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        timestamp_ns: int | None = None,
    ) -> None:
        """Add a timestamped event / log annotation to the active span."""
        t_nano = timestamp_ns if timestamp_ns is not None else int(time.time() * 1e9)
        attr_list = [
            {"key": k, "value": _to_otlp_any_value(v)} for k, v in (attributes or {}).items()
        ]
        self._events.append(
            {
                "timeUnixNano": str(t_nano),
                "name": name,
                "attributes": attr_list,
            }
        )

    def add_link(
        self,
        trace_id: str,
        span_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add a causal span link to correlate with external or asynchronous trace contexts."""
        attr_list = [
            {"key": k, "value": _to_otlp_any_value(v)} for k, v in (attributes or {}).items()
        ]
        self._links.append(
            {
                "traceId": trace_id,
                "spanId": span_id,
                "attributes": attr_list,
            }
        )

    def record_exception(
        self, exc: BaseException, attributes: dict[str, Any] | None = None
    ) -> None:
        """Record structured exception details and event to the active span."""
        import traceback

        from devops_cli.security.sanitizer import mask_secrets

        exc_type = type(exc).__name__
        exc_msg = mask_secrets(str(exc))
        raw_stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        exc_stack = mask_secrets(raw_stack)
        self._attributes["error"] = True
        self._attributes["otel.status_code"] = "ERROR"
        self._attributes["exception.type"] = exc_type
        self._attributes["exception.message"] = exc_msg
        self._attributes["exception.stacktrace"] = exc_stack
        event_attrs: dict[str, Any] = {
            "exception.type": exc_type,
            "exception.message": exc_msg,
            "exception.stacktrace": exc_stack,
        }
        if attributes:
            sanitized_attrs = {
                k: mask_secrets(v) if isinstance(v, str) else v for k, v in attributes.items()
            }
            event_attrs.update(sanitized_attrs)
        self.add_event("exception", event_attrs)


def _read_packed_refs(git_dir: Path, ref: str) -> str | None:
    """Read commit SHA for a ref from packed-refs file if present."""
    packed_file = git_dir / "packed-refs"
    if not packed_file.is_file():
        return None
    try:
        content = packed_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in content.splitlines():
        line = line.strip()
        if line.endswith(ref) and len(line) >= 40:
            candidate = line.split()[0]
            if len(candidate) == 40:
                return candidate
    return None


def _read_ref_file(git_dir: Path, ref: str) -> str | None:
    """Read commit SHA from individual loose ref file if present."""
    ref_file = git_dir / ref
    if not ref_file.is_file():
        return None
    try:
        val = ref_file.read_text(encoding="utf-8", errors="replace").strip()
        return val if len(val) == 40 else None
    except OSError:
        return None


def _read_git_head_ref(git_dir: Path) -> tuple[str | None, str | None]:
    """Read branch name and commit SHA from git directory HEAD."""
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None, None
    try:
        content = head_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None, None
    if not content:
        return None, None
    if not content.startswith("ref:"):
        sha = content if len(content) == 40 else None
        return None, sha

    ref = content.removeprefix("ref:").strip()
    branch = ref.removeprefix("refs/heads/").strip() if ref.startswith("refs/heads/") else ref
    sha = _read_ref_file(git_dir, ref) or _read_packed_refs(git_dir, ref)
    return branch, sha


def _resolve_git_dir_from_file(marker: Path) -> Path | None:
    """Resolve target git directory from a .git file (e.g. worktree or submodule pointer)."""
    try:
        text = marker.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("gitdir:"):
            target_str = text.removeprefix("gitdir:").strip()
            if not target_str:
                return None
            target = (marker.parent / target_str).resolve()
            return target if target.is_dir() else None
    except OSError, RuntimeError:
        pass
    return None


def _resolve_git_dir(start_dir: Path | None = None) -> Path | None:
    """Traverse upwards from start_dir to locate active .git directory or worktree."""
    try:
        current = (start_dir or Path.cwd()).resolve()
    except OSError:
        # If the working directory no longer exists, return None
        return None
    for candidate in [current, *current.parents]:
        marker = candidate / ".git"
        if marker.is_dir():
            return marker
        if marker.is_file():
            resolved = _resolve_git_dir_from_file(marker)
            if resolved:
                return resolved
    return None


@functools.lru_cache(maxsize=1)
def _detect_vcs_metadata() -> dict[str, str]:
    """Detect current Git branch and revision ID via zero-subprocess inspection."""
    meta: dict[str, str] = {}
    git_dir = _resolve_git_dir()
    if git_dir is not None:
        branch, sha = _read_git_head_ref(git_dir)
        if branch:
            meta["vcs.ref.name"] = branch
            meta["vcs.branch"] = branch
        if sha:
            meta["vcs.revision_id"] = sha
            meta["vcs.commit"] = sha
    return meta


@functools.lru_cache(maxsize=1)
def _detect_k8s_context() -> tuple[str | None, str | None]:
    """Detect active Kubernetes context and namespace from environment or settings."""
    ctx = os.getenv("K8S_CONTEXT") or os.getenv("KUBECONFIG_CONTEXT")
    ns = os.getenv("K8S_NAMESPACE") or os.getenv("POD_NAMESPACE")
    if ctx and ns:
        return ctx, ns
    try:
        from devops_cli.config.settings import load_settings

        k8s_cfg = getattr(load_settings(), "k8s", None)
        if k8s_cfg and not ctx:
            ctx = getattr(k8s_cfg, "context", None)
    except Exception:
        pass
    return ctx, ns


def _is_telemetry_internal_frame(frame: Any) -> bool:
    """Check if stack frame belongs to telemetry internals, logging, or contextlib."""
    code = getattr(frame, "f_code", None)
    if not code:
        return True
    filename = getattr(code, "co_filename", "")
    return (
        "telemetry/tracer.py" in filename
        or "contextlib.py" in filename
        or "logging/__init__.py" in filename
    )


def _normalize_code_filepath(filepath: str) -> str:
    """Convert absolute workspace paths to relative paths for clean telemetry tags."""
    try:
        p = Path(filepath).resolve()
        cwd = Path.cwd().resolve()
        if p.is_relative_to(cwd):
            return str(p.relative_to(cwd))
        return str(p)
    except Exception:
        return filepath


def _detect_caller_code_attributes(depth_offset: int = 1) -> dict[str, Any]:
    """Inspect stack frame to extract caller source file, function name, and line number."""
    attrs: dict[str, Any] = {}
    try:
        frame: Any = sys._getframe(depth_offset)
        while frame is not None and _is_telemetry_internal_frame(frame):
            frame = frame.f_back
        if frame is not None:
            code = getattr(frame, "f_code", None)
            if code is not None:
                filepath = getattr(code, "co_filename", "")
                func_name = getattr(code, "co_name", "")
                lineno = getattr(frame, "f_lineno", 0)
                if filepath:
                    attrs["code.filepath"] = _normalize_code_filepath(filepath)
                if func_name:
                    attrs["code.function"] = func_name
                if lineno:
                    attrs["code.lineno"] = lineno
    except Exception:
        pass
    return attrs


def _enrich_span_attributes(
    attrs: dict[str, Any], *, name: str | None = None, depth_offset: int = 2
) -> None:
    """Enrich span attributes with caller location, thread, process, vcs, and k8s context."""
    caller_attrs = _detect_caller_code_attributes(depth_offset=depth_offset)
    for k, v in caller_attrs.items():
        attrs.setdefault(k, v)

    cur_thread = threading.current_thread()
    attrs.setdefault("thread.name", cur_thread.name)
    if cur_thread.ident:
        attrs.setdefault("thread.id", cur_thread.ident)
    attrs.setdefault("process.pid", os.getpid())

    vcs = _detect_vcs_metadata()
    if "vcs.ref.name" in vcs:
        attrs.setdefault("vcs.ref.name", vcs["vcs.ref.name"])
        attrs.setdefault("vcs.branch", vcs["vcs.ref.name"])
    if "vcs.revision_id" in vcs:
        attrs.setdefault("vcs.revision_id", vcs["vcs.revision_id"])
        attrs.setdefault("vcs.commit", vcs["vcs.revision_id"])

    k8s_ctx, k8s_ns = _detect_k8s_context()
    if k8s_ctx:
        attrs.setdefault("k8s.context", k8s_ctx)
        attrs.setdefault("k8s.cluster.name", k8s_ctx)
    if k8s_ns:
        attrs.setdefault("k8s.namespace", k8s_ns)
        attrs.setdefault("k8s.namespace.name", k8s_ns)


# `cli.command` has no alias. The semantic conventions give `process.command_line` to the full
# command line, and a command span holds only the name of the command (#2059).
_ATTRIBUTE_NORMALIZATION: dict[str, str] = {
    "cli.function": "code.function",
    "cli.error": "error.message",
    "file_path": "code.filepath",
    "file.path": "code.filepath",
    "subprocess.bin": "process.executable.name",
    "subprocess.cwd": "process.working_directory",
    "subprocess.exit_code": "process.exit.code",
    "http.method": "http.request.method",
    "http.status_code": "http.response.status_code",
    "http.url": "url.full",
    "http.route": "url.path",
    "git.branch": "vcs.branch",
    "git.commit": "vcs.commit",
    "git.operation": "vcs.operation",
    "k8s.namespace": "k8s.namespace.name",
    "k8s.pod": "k8s.pod.name",
    "k8s.deployment": "k8s.deployment.name",
    "argo.app": "argo.application.name",
}


_ALIAS_FALLBACKS: tuple[tuple[str, str], ...] = (
    ("vcs.branch", "vcs.ref.name"),
    ("vcs.commit", "vcs.revision_id"),
    ("k8s.namespace", "k8s.namespace.name"),
    ("k8s.context", "k8s.cluster.name"),
)


def _sync_attribute_aliases(attrs: dict[str, Any]) -> None:
    """Populate canonical alias targets if source key is present and target is missing."""
    for src, dst in _ALIAS_FALLBACKS:
        if src in attrs and dst not in attrs:
            attrs[dst] = attrs[src]


def _normalize_and_deduplicate_attributes(attrs: dict[str, Any]) -> None:
    """Normalize legacy attribute names to OTel semantic conventions and eliminate duplicate tags."""
    for legacy_k, otel_k in _ATTRIBUTE_NORMALIZATION.items():
        if legacy_k in attrs:
            attrs.setdefault(otel_k, attrs[legacy_k])
            if legacy_k in ("cli.function", "cli.error"):
                attrs.pop(legacy_k, None)

    if "code.function" in attrs:
        attrs.pop("cli.function", None)
    if "error.message" in attrs:
        attrs.pop("cli.error", None)

    _sync_attribute_aliases(attrs)


_current_trace_id_ctx: ContextVar[str | None] = ContextVar("otel_current_trace_id", default=None)
_current_span_id_ctx: ContextVar[str | None] = ContextVar("otel_current_span_id", default=None)


class OTelTelemetryClient:
    """Builds OpenTelemetry traces, metrics and logs, and hands them to an OTLP exporter."""

    def __init__(
        self,
        endpoint: str = DEFAULT_OTEL_ENDPOINT,
        *,
        protocol: str | None = None,
        service_name: str = CONST_OTEL_SERVICE_NAME,
        service_version: str | None = None,
        enabled: bool = True,
        capture_command_args: bool = False,
        capture_llm_content: bool = False,
        exporter: OtlpExporter | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        # The exporter sends what this client builds. `otlp_exporter` refuses a gRPC protocol
        # or endpoint with an `OtlpProtocolError` that names the setting.
        self._exporter: OtlpExporter = (
            exporter if exporter is not None else otlp_exporter(self.endpoint, protocol)
        )
        self.service_name = service_name
        self.service_version = service_version or self._detect_version()
        self.host_name = platform.node() or "localhost"
        self.os_type = platform.system().lower() or "linux"
        self.enabled = enabled
        # Whether a subprocess span records the arguments of its program (`process.command_args`,
        # Opt-In in the semantic conventions): `telemetry.capture_command_args` (#2025).
        self.capture_command_args = capture_command_args
        # Whether an AI inference span records prompt and response preview text:
        # `telemetry.capture_llm_content` (#606).
        self.capture_llm_content = capture_llm_content
        self._executor: ContextPropagatingThreadPoolExecutor | None = None
        self._client_lock = threading.Lock()
        # One flush at a time: the collector drops a delta that is not later than the last one
        # it added to the series, so a flush collects only once the export before it is done.
        self._flush_lock = threading.Lock()
        # Exports still in flight, drained at shutdown; and how exports have fared, so a
        # collector that never answers is reported rather than silently dropping everything.
        self._pending: set[Future[None]] = set()
        self.export_failures = 0
        self.export_successes = 0
        self.last_export_error = ""

        # Cache pre-computed resource attributes for zero-allocation reuse across all spans and metrics
        vcs_meta = _detect_vcs_metadata()
        vcs_res_attrs = [
            {"key": k, "value": {"stringValue": v}}
            for k, v in vcs_meta.items()
            if k in ("vcs.revision_id", "vcs.ref.name")
        ]
        self._cached_resource_attributes: list[dict[str, Any]] = [
            {"key": "service.name", "value": {"stringValue": self.service_name}},
            {"key": "service.version", "value": {"stringValue": self.service_version}},
            {"key": "host.name", "value": {"stringValue": self.host_name}},
            {"key": "host.arch", "value": {"stringValue": platform.machine()}},
            {"key": "os.type", "value": {"stringValue": self.os_type}},
            # platform.platform() runs `uname -p` for the processor name; system and release
            # come from os.uname() and start no process.
            {
                "key": "os.description",
                "value": {"stringValue": f"{platform.system()} {platform.release()}"},
            },
            {"key": "process.pid", "value": {"stringValue": str(os.getpid())}},
            {
                "key": "process.executable.name",
                "value": {"stringValue": Path(sys.executable).name},
            },
            {"key": "process.runtime.name", "value": {"stringValue": "cpython"}},
            {
                "key": "process.runtime.version",
                "value": {"stringValue": platform.python_version()},
            },
            {"key": "telemetry.sdk.name", "value": {"stringValue": "devops-cli-otel"}},
            {"key": "telemetry.sdk.language", "value": {"stringValue": "python"}},
            *vcs_res_attrs,
        ]
        k8s_ctx, _ = _detect_k8s_context()
        if k8s_ctx:
            self._cached_resource_attributes.append(
                {"key": "k8s.cluster.name", "value": {"stringValue": k8s_ctx}}
            )
        # The resource holds no `process.command_line` and no `process.command_args`. They are
        # Opt-In in the OpenTelemetry semantic conventions, which say not to collect them by
        # default unless sanitization excludes sensitive data. A secret pattern does not: it
        # misses a credential given to `devops config set` (#1996).
        self._meter_provider: Any = None
        self._metric_reader: Any = None
        self._meter: Any = None
        self._sdk_instruments: dict[tuple[str, str, str], Any] = {}

    @property
    def exporter(self) -> OtlpExporter:
        """The exporter that sends what this client builds to the collector."""
        return self._exporter

    @staticmethod
    def _detect_version() -> str:
        try:
            from devops_cli import __version__

            return __version__
        except Exception:
            return "0.0.0"

    def _get_resource_attributes(self) -> list[dict[str, Any]]:
        """Return standardized OpenTelemetry resource attributes."""
        return self._cached_resource_attributes

    @property
    def current_trace_id(self) -> str | None:
        return _current_trace_id_ctx.get()

    @property
    def current_span_id(self) -> str | None:
        return _current_span_id_ctx.get()

    def current_trace_context(self) -> TraceContext:
        """Return the active trace context, starting a new one if no span is open."""
        trace_id = _current_trace_id_ctx.get()
        span_id = _current_span_id_ctx.get()
        if trace_id and span_id:
            return TraceContext(trace_id=trace_id, span_id=span_id)
        return new_trace_context()

    def inject_trace_context(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Return a copy of `headers` carrying the active context as a `traceparent`.

        This is the HTTP carrier and does not mutate its argument. Use
        :meth:`inject_trace_env` for a child process environment.
        """
        out = dict(headers or {})
        if not self.enabled:
            return out
        return inject_headers(self.current_trace_context(), out)

    def inject_trace_env(self, env: dict[str, str]) -> dict[str, str]:
        """Write the active context into a child process environment, in place.

        Mutating is the point: the caller already holds the environment it is about to hand
        to the child, and the previous header-shaped injector returned a copy whose result
        was discarded at both call sites, so no child process ever received a parent span.
        """
        if not self.enabled:
            return env
        return inject_env(self.current_trace_context(), env)

    def extract_trace_context(self, headers: dict[str, str]) -> tuple[str | None, str | None]:
        """Extract trace id and parent span id from an incoming `traceparent`."""
        context = extract_headers(headers)
        if context is None:
            return None, None
        return context.trace_id, context.span_id

    def _ensure_meter(self) -> Any:
        """Lazily initialize the OTel SDK MeterProvider with DELTA temporality and exponential histograms."""
        with self._client_lock:
            if self._meter is None:
                from opentelemetry.sdk.metrics import Counter, Histogram, MeterProvider, _Gauge
                from opentelemetry.sdk.metrics.export import (
                    AggregationTemporality,
                    InMemoryMetricReader,
                )
                from opentelemetry.sdk.metrics.view import (
                    ExponentialBucketHistogramAggregation,
                    View,
                )
                from opentelemetry.sdk.resources import OTELResourceDetector, Resource

                self._metric_reader = InMemoryMetricReader(
                    preferred_temporality={
                        Counter: AggregationTemporality.DELTA,
                        Histogram: AggregationTemporality.DELTA,
                        _Gauge: AggregationTemporality.DELTA,
                    }
                )
                # Metrics identify their source by host, not process: every command is a
                # short-lived process, and the collector adds up each series' deltas across them.
                # The SDK's detector of the standard OTEL_RESOURCE_ATTRIBUTES and
                # OTEL_SERVICE_NAME merges last, as in the SDK's Resource.create, so a workload
                # whose host changes at each start, such as a pod, sets one service.instance.id
                # there and keeps its series (#1629).
                resource = Resource(
                    {
                        "service.name": self.service_name,
                        "service.instance.id": self.host_name,
                        "host.name": self.host_name,
                        "os.type": self.os_type,
                        "telemetry.sdk.name": "devops-cli-otel",
                        "telemetry.sdk.language": "python",
                    }
                ).merge(OTELResourceDetector().detect())
                self._meter_provider = MeterProvider(
                    resource=resource,
                    metric_readers=[self._metric_reader],
                    views=[
                        View(
                            instrument_type=Histogram,
                            aggregation=ExponentialBucketHistogramAggregation(),
                        )
                    ],
                    shutdown_on_exit=False,
                )
                self._meter = self._meter_provider.get_meter("devops-cli.telemetry")
            return self._meter

    def _get_sdk_instrument(self, kind: str, name: str, unit: str) -> Any:
        """Return or create a cached OTel SDK metric instrument."""
        meter = self._ensure_meter()
        key = (kind, name, unit)
        with self._client_lock:
            inst = self._sdk_instruments.get(key)
            if inst is None:
                creator = {
                    "counter": meter.create_counter,
                    "histogram": meter.create_histogram,
                    "gauge": meter.create_gauge,
                }[kind]
                inst = creator(name, unit=unit)
                self._sdk_instruments[key] = inst
            return inst

    def _build_traces_payload(
        self,
        spans: list[dict[str, Any]],
        resource_attributes: list[dict[str, Any]] | None = None,
        scope_name: str = CONST_OTEL_SCOPE_NAME,
    ) -> dict[str, Any]:
        """Build structured OTLP resourceSpans payload."""
        res_attrs = resource_attributes or self._get_resource_attributes()
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": res_attrs},
                    "scopeSpans": [{"scope": {"name": scope_name}, "spans": spans}],
                }
            ]
        }

    def _build_logs_payload(
        self,
        log_records: list[dict[str, Any]],
        resource_attributes: list[dict[str, Any]] | None = None,
        scope_name: str = CONST_OTEL_SCOPE_NAME,
    ) -> dict[str, Any]:
        """Build structured OTLP resourceLogs payload."""
        res_attrs = resource_attributes or self._get_resource_attributes()
        return {
            "resourceLogs": [
                {
                    "resource": {"attributes": res_attrs},
                    "scopeLogs": [{"scope": {"name": scope_name}, "logRecords": log_records}],
                }
            ]
        }

    def export_log_record(self, log_record: dict[str, Any]) -> None:
        """Queue one OTLP log record for asynchronous export to /v1/logs.

        A dry run sends nothing: it makes no external request, the collector included (#412).
        """
        from devops_cli.dry_run.state import in_dry_run_invocation

        if not self.enabled or in_dry_run_invocation():
            return
        payload = self._build_logs_payload([log_record])
        self._send_payload("/v1/logs", payload)

    def record_gauge(
        self,
        name: str,
        value: float,
        *,
        unit: str = CONST_OTEL_METRIC_UNIT_ONE,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Record a gauge data point in the in-process OTel SDK meter.

        `telemetry.instruments.emit()` is the one caller of the metric methods.
        """
        from devops_cli.dry_run.state import in_dry_run_invocation

        if not self.enabled or in_dry_run_invocation():
            return
        gauge = self._get_sdk_instrument("gauge", name, unit)
        gauge.set(float(value), _sdk_metric_attributes(attributes))

    def increment_counter(
        self,
        name: str,
        amount: float = DEFAULT_OTEL_COUNTER_AMOUNT,
        *,
        unit: str = CONST_OTEL_METRIC_UNIT_ONE,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add to a monotonic counter in the in-process OTel SDK meter."""
        from devops_cli.dry_run.state import in_dry_run_invocation

        if not self.enabled or in_dry_run_invocation():
            return
        counter = self._get_sdk_instrument("counter", name, unit)
        counter.add(float(amount), _sdk_metric_attributes(attributes))

    def record_histogram(
        self,
        name: str,
        value: float,
        *,
        unit: str = CONST_OTEL_METRIC_UNIT_ONE,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Observe one value of an exponential histogram in the in-process OTel SDK meter."""
        from devops_cli.dry_run.state import in_dry_run_invocation

        if not self.enabled or in_dry_run_invocation():
            return
        histogram = self._get_sdk_instrument("histogram", name, unit)
        histogram.record(float(value), _sdk_metric_attributes(attributes))

    def _populate_exception_span_attributes(
        self,
        exc: BaseException,
        attrs: dict[str, Any],
        exit_code: int | None,
    ) -> str:
        """Populate span attributes for an exception and return a descriptive error message.

        A usage error of Typer records its class and its exit code and no message: the message
        quotes what the person typed, such as "Got unexpected extra argument (<value>)", and an
        argument can be a credential (#2024).
        """
        import typer

        from devops_cli.security.sanitizer import mask_secrets

        if isinstance(exc, KeyboardInterrupt):
            attrs["error.type"] = "KeyboardInterrupt"
            attrs["cli.interrupted"] = True
            return "Command cancelled by user (SIGINT / KeyboardInterrupt)"

        attrs["error.type"] = exc.__class__.__name__
        if exit_code is not None:
            attrs["cli.exit_code"] = exit_code
            attrs["process.exit.code"] = exit_code
        if isinstance(exc, typer.TyperException):
            return f"{exc.__class__.__name__}(exit_code={exit_code})"
        clean_msg = mask_secrets(str(exc))
        attrs["error.message"] = clean_msg
        if exit_code is not None and (str(exc) == str(exit_code) or not str(exc)):
            return f"{exc.__class__.__name__}(exit_code={exit_code})"
        return clean_msg or exc.__class__.__name__

    def _resolve_parent(
        self,
        parent_context: dict[str, str] | None,
        parent_trace_id: str | None,
        parent_span_id: str | None,
    ) -> tuple[str | None, str | None]:
        """Resolve the parent trace and span for a new span, in precedence order.

        An explicit argument wins, then a context supplied by the caller, then the span
        open on this thread, and only then the context inherited from a parent process. The
        inherited value is validated before adoption: it is ambient input, and a malformed
        one would otherwise be carried into trace ids and exported as though it were real.
        """
        if parent_context:
            supplied = extract_headers(parent_context)
            if supplied:
                return supplied.trace_id, supplied.span_id

        parent_trace = parent_trace_id or _current_trace_id_ctx.get()
        parent_id = parent_span_id or _current_span_id_ctx.get()
        if parent_trace:
            return parent_trace, parent_id

        inherited = extract_env()
        if inherited:
            return inherited.trace_id, inherited.span_id
        return parent_trace, parent_id

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        kind: str = CONST_OTEL_SPAN_KIND_INTERNAL,
        links: list[dict[str, Any]] | None = None,
        parent_context: dict[str, str] | None = None,
        parent_trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Generator[SpanHandle]:
        """Context manager to measure and emit a trace span with thread-safe context propagation."""
        if not self.enabled:
            yield SpanHandle("", {})
            return

        parent_trace, parent_id = self._resolve_parent(
            parent_context, parent_trace_id, parent_span_id
        )

        trace_id = parent_trace or _generate_trace_id()
        span_id = _generate_span_id()
        start_nano = int(time.time() * 1e9)

        token_trace = _current_trace_id_ctx.set(trace_id)
        token_span = _current_span_id_ctx.set(span_id)

        attrs = dict(attributes or {})
        _enrich_span_attributes(attrs, name=name, depth_offset=2)
        _normalize_and_deduplicate_attributes(attrs)

        handle = SpanHandle(span_id, attrs)
        status_code = "STATUS_CODE_OK"
        error_msg = ""
        span_kind = _SPAN_KINDS.get(kind.lower(), "SPAN_KIND_INTERNAL")

        try:
            yield handle
        except BaseException as exc:
            exit_code = getattr(exc, "exit_code", getattr(exc, "code", None))
            if exit_code == 0:
                # Clean exit (e.g. typer.Exit(0), click.exceptions.Exit(0), SystemExit(0))
                status_code = "STATUS_CODE_OK"
                attrs.setdefault("cli.exit_code", 0)
                attrs.setdefault("process.exit.code", 0)
                raise

            status_code = "STATUS_CODE_ERROR"
            error_msg = self._populate_exception_span_attributes(exc, attrs, exit_code)
            if exit_code is None and not isinstance(exc, (SystemExit, KeyboardInterrupt)):
                handle.record_exception(exc)
            else:
                handle.set_status("ERROR", error_msg)
            raise
        finally:
            end_nano = int(time.time() * 1e9)
            _current_trace_id_ctx.reset(token_trace)
            _current_span_id_ctx.reset(token_span)

            _normalize_and_deduplicate_attributes(attrs)

            span_data: dict[str, Any] = {
                "traceId": trace_id,
                "spanId": span_id,
                "name": name,
                "kind": span_kind,
                "startTimeUnixNano": str(start_nano),
                "endTimeUnixNano": str(end_nano),
                "attributes": [
                    {"key": k, "value": _to_otlp_any_value(v)} for k, v in attrs.items()
                ],
                "status": {"code": status_code, "message": error_msg},
            }
            if handle._events:
                span_data["events"] = handle._events
            if handle._links:
                span_data["links"] = handle._links
            elif links:
                span_data["links"] = links
            if parent_id and parent_id != span_id:
                span_data["parentSpanId"] = parent_id

            record_completed_span(span_data)

            payload = self._build_traces_payload([span_data])
            self._send_payload("/v1/traces", payload)

    def test_connection(
        self, timeout: float = DEFAULT_OTEL_TEST_TIMEOUT
    ) -> tuple[bool, str, float]:
        """Probe the collector through the exporter: whether it answers, how, and in how many
        milliseconds."""
        start = time.perf_counter()
        result = self._exporter.probe(timeout)
        return result.reachable, result.detail, (time.perf_counter() - start) * 1000

    def _get_executor(self) -> ContextPropagatingThreadPoolExecutor:
        """Get or initialize thread-safe background thread executor for non-blocking payload emission."""
        with self._client_lock:
            if self._executor is None:
                self._executor = ContextPropagatingThreadPoolExecutor(
                    max_workers=2,
                    thread_name_prefix="devops-otel",
                )
            return self._executor

    def _send_payload_sync(self, path: str, payload: dict[str, Any]) -> None:
        """Hand one export request to the exporter, and count how it fared."""
        if not self.enabled:
            return
        try:
            self._exporter.export(OtlpSignal(path), json_body(payload), JSON_CONTENT_TYPE)
            self.export_successes += 1
        except Exception as exc:
            self.export_failures += 1
            self.last_export_error = str(exc) or type(exc).__name__
            logger.debug("OTel payload send failed to %s%s: %s", self.endpoint, path, exc)

    def _send_payload(self, path: str, payload: dict[str, Any]) -> None:
        """Send payload asynchronously via background thread executor to prevent blocking CLI execution.

        A dry run sends nothing: it makes no external request, the collector included (#412).
        """
        from devops_cli.dry_run.state import in_dry_run_invocation

        if not self.enabled or in_dry_run_invocation():
            return
        try:
            executor = self._get_executor()
            future = executor.submit(self._send_payload_sync, path, payload)
            self._pending.add(future)
            future.add_done_callback(self._pending.discard)
        except Exception as exc:
            logger.debug("Failed submitting OTel payload to executor: %s", exc)

    def _flush_sdk_metrics(self) -> None:
        """Collect buffered SDK metrics and queue one OTLP /v1/metrics export."""
        if self._metric_reader is None or not self.enabled:
            return
        metrics_data = self._metric_reader.get_metrics_data()
        if metrics_data is not None and metrics_data.resource_metrics:
            payload = _encode_sdk_metrics_data(metrics_data)
            if payload["resourceMetrics"]:
                self._send_payload("/v1/metrics", payload)

    def _shutdown_meter_provider(self) -> None:
        """Close the OTel SDK MeterProvider and reset cached instruments."""
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
            self._meter_provider = None
            self._metric_reader = None
            self._meter = None
            self._sdk_instruments.clear()

    def flush(self, timeout: float = DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS) -> None:
        """Export buffered SDK metrics and wait, up to ``timeout`` seconds, for queued exports to finish."""
        with self._flush_lock:
            self._flush_sdk_metrics()
            pending = [f for f in list(self._pending) if not f.done()]
            if pending:
                wait_futures(pending, timeout=timeout)

    def shutdown(self, timeout_millis: int = DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS) -> None:
        """Cleanly close the background executor and the exporter, with a bounded drain timeout.

        Exports still in flight get up to DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS to finish: a short
        command queues its spans at the very end, and cancelling them lost its root span. The
        wait happens before taking the client lock, which the exports need.
        """
        self.flush()
        if self._executor is not None:
            try:
                self._executor.shutdown(wait=True, cancel_futures=True)
            except Exception as exc:
                logger.debug("Failed closing OTel executor: %s", exc)
            self._executor = None
        with self._client_lock:
            self._shutdown_meter_provider()
        self._exporter.close()


_GLOBAL_TRACER: OTelTelemetryClient | None = None
_GLOBAL_TRACER_LOCK = threading.Lock()
# The exporter that `install_exporter` put in place of the configured one, if any.
_INSTALLED_EXPORTER: OtlpExporter | None = None


def _resolve_telemetry_settings() -> TelemetryConfig:
    """The telemetry section of the settings, `DEVOPS_CLI_TELEMETRY_*` already applied.

    Settings that cannot load do not fail the command: the registered variables alone then
    decide, and export stays off unless one turns it on (`telemetry_from_environment`, #956).
    """
    from devops_cli.config.settings import load_settings, telemetry_from_environment

    try:
        return load_settings().telemetry
    except Exception:
        return telemetry_from_environment()


def _process_exporter(telemetry: TelemetryConfig) -> tuple[OtlpExporter, bool]:
    """The exporter of the process's tracer, and whether export is on: the installed exporter
    with export on, else the configured collector's."""
    if _INSTALLED_EXPORTER is not None:
        return _INSTALLED_EXPORTER, True
    from devops_cli.config.env import ENV_OTEL_EXPORTER_OTLP_ENDPOINT

    endpoint = (
        telemetry.endpoint or os.getenv(ENV_OTEL_EXPORTER_OTLP_ENDPOINT) or DEFAULT_OTEL_ENDPOINT
    )
    try:
        return otlp_exporter(endpoint), telemetry.enabled
    except OtlpProtocolError as exc:
        # The command still runs: export stays off, the warning names the setting, and the
        # collector probe of `devops telemetry status` reports it.
        logger.warning("Telemetry export is off: %s", exc)
        return RefusedExporter(endpoint, str(exc)), False


def otel_service_name() -> str:
    """The process's OTel `service.name`: `OTEL_SERVICE_NAME`, which a workload sets, else
    devops-cli's own. The LLM gateway reads it as the caller of each call (#1668)."""
    return os.getenv("OTEL_SERVICE_NAME", CONST_OTEL_SERVICE_NAME)


def get_tracer() -> OTelTelemetryClient:
    """Retrieve or lazily initialize the singleton OTelTelemetryClient instance."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is not None:
        return _GLOBAL_TRACER

    with _GLOBAL_TRACER_LOCK:
        if _GLOBAL_TRACER is None:
            telemetry = _resolve_telemetry_settings()
            exporter, enabled = _process_exporter(telemetry)
            _GLOBAL_TRACER = OTelTelemetryClient(
                endpoint=exporter.endpoint,
                service_name=otel_service_name(),
                enabled=enabled,
                capture_command_args=telemetry.capture_command_args,
                capture_llm_content=telemetry.capture_llm_content,
                exporter=exporter,
            )
            if _GLOBAL_TRACER.enabled:
                from devops_cli.telemetry.logging_bridge import attach_otel_logging_handler

                attach_otel_logging_handler()
        return _GLOBAL_TRACER


def install_exporter(exporter: OtlpExporter) -> None:
    """Send the process's telemetry to `exporter`, with export on, until `remove_exporter`.

    The tracer in use is dropped, and each tracer that `get_tracer` builds from then on, also
    after a `reset_tracer`, exports to `exporter`. A test installs the OTLP fake this way.
    """
    global _INSTALLED_EXPORTER
    _INSTALLED_EXPORTER = exporter
    reset_tracer()


def remove_exporter() -> None:
    """Remove the exporter that `install_exporter` installed: the next tracer that `get_tracer`
    builds exports as the settings say."""
    global _INSTALLED_EXPORTER
    if _INSTALLED_EXPORTER is None:
        return
    _INSTALLED_EXPORTER = None
    reset_tracer()


def reset_tracer() -> None:
    """Reset the global tracer instance (used for testing).

    The dropped tracer is shut down first, which waits for its exports in flight: one left
    running carried a test's exports into the next test.
    """
    from devops_cli.telemetry.logging_bridge import detach_otel_logging_handler

    detach_otel_logging_handler()
    global _GLOBAL_TRACER
    dropped, _GLOBAL_TRACER = _GLOBAL_TRACER, None
    if dropped is not None:
        dropped.shutdown()
    if hasattr(_detect_vcs_metadata, "cache_clear"):
        _detect_vcs_metadata.cache_clear()
    if hasattr(_detect_k8s_context, "cache_clear"):
        _detect_k8s_context.cache_clear()


@contextlib.contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    kind: str = CONST_OTEL_SPAN_KIND_INTERNAL,
    links: list[dict[str, Any]] | None = None,
    parent_context: dict[str, str] | None = None,
    parent_trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> Generator[SpanHandle]:
    """Convenience context manager for tracing a block of execution with span kind and optional links."""
    tracer = get_tracer()
    with tracer.span(
        name,
        attributes=attributes,
        kind=kind,
        links=links,
        parent_context=parent_context,
        parent_trace_id=parent_trace_id,
        parent_span_id=parent_span_id,
    ) as handle:
        yield handle


def inject_trace_context(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Convenience function to inject W3C traceparent into outgoing HTTP headers."""
    return get_tracer().inject_trace_context(headers)


def traced(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
    *,
    kind: str = CONST_OTEL_SPAN_KIND_INTERNAL,
) -> Callable[[F], F]:
    """Decorator to trace a function execution as an OpenTelemetry span."""

    def decorator(fn: F) -> F:
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, attributes=attributes, kind=kind):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def get_current_span_context() -> dict[str, str | None]:
    """Retrieve the current active span and trace IDs as a dictionary."""
    tid = _current_trace_id_ctx.get()
    sid = _current_span_id_ctx.get()
    if tid and sid:
        return {"trace_id": tid, "span_id": sid}

    try:
        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            ctx = current_span.get_span_context()
            if ctx.is_valid and ctx.trace_id and ctx.span_id:
                return {
                    "trace_id": format(ctx.trace_id, "032x"),
                    "span_id": format(ctx.span_id, "016x"),
                }
    except Exception:
        pass

    return {
        "trace_id": tid,
        "span_id": sid,
    }


def shutdown_tracer(timeout_millis: int = DEFAULT_OTEL_SHUTDOWN_TIMEOUT_MS) -> None:
    """Flush and shut down global tracer instance with bounded timeout."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is not None:
        _GLOBAL_TRACER.shutdown(timeout_millis=timeout_millis)
        _warn_if_exports_failed(_GLOBAL_TRACER)


def _warn_if_exports_failed(client: OTelTelemetryClient) -> None:
    """Tell an interactive user, at most once a day per endpoint, that telemetry went nowhere.

    Export failures are otherwise silent, which is how a workstation's traces and metrics were
    dropped for good with nothing to show for it. Non-interactive runs (CI, tests) stay quiet.
    """
    if not client.enabled or not client.export_failures or client.export_successes:
        return
    if not sys.stderr.isatty():
        return
    marker = _export_warning_marker(client.endpoint)
    try:
        if (
            marker.exists()
            and time.time() - marker.stat().st_mtime < DEFAULT_OTEL_WARNING_INTERVAL_SECONDS
        ):
            return
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        return
    sys.stderr.write(
        f"Telemetry could not reach {client.endpoint}: {client.export_failures} export(s) failed "
        f"({client.last_export_error}). Run `devops telemetry connect` to find the cluster's "
        "collector, or set telemetry.enabled to false.\n"
    )


def _export_warning_marker(endpoint: str) -> Path:
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    digest = hashlib.sha256(endpoint.encode()).hexdigest()[:12]
    return resolve_data_path(load_settings().data.dir) / "telemetry" / f"export-warning-{digest}"


atexit.register(shutdown_tracer)
