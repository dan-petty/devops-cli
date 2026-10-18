"""Telemetry, OpenTelemetry tracing, and metrics module for devops-cli."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.telemetry.context import (
        extract_traceparent,
        extract_traceparent_from_headers,
        generate_span_id,
        generate_trace_id,
        generate_traceparent,
        inject_traceparent_headers,
    )
    from devops_cli.telemetry.logfire import (
        AgentTurnHandle,
        LogfireBridge,
        LogfireOTelBridgeProcessor,
        LogfireStatus,
        get_logfire_bridge,
        logfire_agent_turn,
        render_agent_turn_panel,
        render_agent_turn_table,
        reset_logfire_bridge,
    )
    from devops_cli.telemetry.logging_bridge import (
        TraceCorrelationFilter,
        attach_trace_correlation_filter,
        get_current_trace_correlation,
    )
    from devops_cli.telemetry.memory_profiler import (
        MemoryAllocationItem,
        MemoryProfiler,
        MemoryProfileReport,
        MemoryProfilerError,
        count_open_sockets,
        profile_custom_callable,
        profile_fastmcp_workload,
        profile_http_pool_workload,
        run_memory_profiler,
    )
    from devops_cli.telemetry.metrics import (
        GLOBAL_METRICS,
        InMemoryMetricsRegistry,
    )
    from devops_cli.telemetry.propagation import (
        TraceContext,
        extract_env,
        extract_headers,
        inject_env,
        inject_headers,
        new_trace_context,
        parse_traceparent,
    )
    from devops_cli.telemetry.service_status import (
        emit_service_status_telemetry,
        fetch_all_service_statuses,
        fetch_cloudflare_status,
        fetch_github_status,
        record_service_status_in_registry,
    )
    from devops_cli.telemetry.tracer import (
        ContextPropagatingThread,
        ContextPropagatingThreadPoolExecutor,
        OTelTelemetryClient,
        SpanWaterfallNode,
        bind_context,
        build_span_waterfall_tree,
        clear_span_buffer,
        get_current_span_context,
        get_recent_spans,
        get_trace_spans,
        get_tracer,
        inject_trace_context,
        record_completed_span,
        record_metric,
        reset_tracer,
        trace_span,
        traced,
    )
    from devops_cli.telemetry.waterfall import (
        flatten_waterfall_tree,
        normalize_tempo_spans,
        query_tempo_trace,
        render_waterfall_bar,
        resolve_trace_spans,
    )

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "extract_traceparent": ("devops_cli.telemetry.context", "extract_traceparent"),
    "extract_traceparent_from_headers": (
        "devops_cli.telemetry.context",
        "extract_traceparent_from_headers",
    ),
    "generate_span_id": ("devops_cli.telemetry.context", "generate_span_id"),
    "generate_trace_id": ("devops_cli.telemetry.context", "generate_trace_id"),
    "generate_traceparent": ("devops_cli.telemetry.context", "generate_traceparent"),
    "inject_traceparent_headers": ("devops_cli.telemetry.context", "inject_traceparent_headers"),
    "AgentTurnHandle": ("devops_cli.telemetry.logfire", "AgentTurnHandle"),
    "LogfireBridge": ("devops_cli.telemetry.logfire", "LogfireBridge"),
    "LogfireOTelBridgeProcessor": ("devops_cli.telemetry.logfire", "LogfireOTelBridgeProcessor"),
    "LogfireStatus": ("devops_cli.telemetry.logfire", "LogfireStatus"),
    "get_logfire_bridge": ("devops_cli.telemetry.logfire", "get_logfire_bridge"),
    "logfire_agent_turn": ("devops_cli.telemetry.logfire", "logfire_agent_turn"),
    "render_agent_turn_panel": ("devops_cli.telemetry.logfire", "render_agent_turn_panel"),
    "render_agent_turn_table": ("devops_cli.telemetry.logfire", "render_agent_turn_table"),
    "reset_logfire_bridge": ("devops_cli.telemetry.logfire", "reset_logfire_bridge"),
    "TraceCorrelationFilter": ("devops_cli.telemetry.logging_bridge", "TraceCorrelationFilter"),
    "attach_trace_correlation_filter": (
        "devops_cli.telemetry.logging_bridge",
        "attach_trace_correlation_filter",
    ),
    "get_current_trace_correlation": (
        "devops_cli.telemetry.logging_bridge",
        "get_current_trace_correlation",
    ),
    "MemoryAllocationItem": ("devops_cli.telemetry.memory_profiler", "MemoryAllocationItem"),
    "MemoryProfileReport": ("devops_cli.telemetry.memory_profiler", "MemoryProfileReport"),
    "MemoryProfiler": ("devops_cli.telemetry.memory_profiler", "MemoryProfiler"),
    "MemoryProfilerError": ("devops_cli.telemetry.memory_profiler", "MemoryProfilerError"),
    "count_open_sockets": ("devops_cli.telemetry.memory_profiler", "count_open_sockets"),
    "profile_custom_callable": ("devops_cli.telemetry.memory_profiler", "profile_custom_callable"),
    "profile_fastmcp_workload": (
        "devops_cli.telemetry.memory_profiler",
        "profile_fastmcp_workload",
    ),
    "profile_http_pool_workload": (
        "devops_cli.telemetry.memory_profiler",
        "profile_http_pool_workload",
    ),
    "run_memory_profiler": ("devops_cli.telemetry.memory_profiler", "run_memory_profiler"),
    "GLOBAL_METRICS": ("devops_cli.telemetry.metrics", "GLOBAL_METRICS"),
    "InMemoryMetricsRegistry": ("devops_cli.telemetry.metrics", "InMemoryMetricsRegistry"),
    "TraceContext": ("devops_cli.telemetry.propagation", "TraceContext"),
    "extract_env": ("devops_cli.telemetry.propagation", "extract_env"),
    "extract_headers": ("devops_cli.telemetry.propagation", "extract_headers"),
    "inject_env": ("devops_cli.telemetry.propagation", "inject_env"),
    "inject_headers": ("devops_cli.telemetry.propagation", "inject_headers"),
    "new_trace_context": ("devops_cli.telemetry.propagation", "new_trace_context"),
    "parse_traceparent": ("devops_cli.telemetry.propagation", "parse_traceparent"),
    "emit_service_status_telemetry": (
        "devops_cli.telemetry.service_status",
        "emit_service_status_telemetry",
    ),
    "fetch_all_service_statuses": (
        "devops_cli.telemetry.service_status",
        "fetch_all_service_statuses",
    ),
    "fetch_cloudflare_status": ("devops_cli.telemetry.service_status", "fetch_cloudflare_status"),
    "fetch_github_status": ("devops_cli.telemetry.service_status", "fetch_github_status"),
    "record_service_status_in_registry": (
        "devops_cli.telemetry.service_status",
        "record_service_status_in_registry",
    ),
    "ContextPropagatingThread": ("devops_cli.telemetry.tracer", "ContextPropagatingThread"),
    "ContextPropagatingThreadPoolExecutor": (
        "devops_cli.telemetry.tracer",
        "ContextPropagatingThreadPoolExecutor",
    ),
    "OTelTelemetryClient": ("devops_cli.telemetry.tracer", "OTelTelemetryClient"),
    "SpanWaterfallNode": ("devops_cli.telemetry.tracer", "SpanWaterfallNode"),
    "bind_context": ("devops_cli.telemetry.tracer", "bind_context"),
    "build_span_waterfall_tree": ("devops_cli.telemetry.tracer", "build_span_waterfall_tree"),
    "clear_span_buffer": ("devops_cli.telemetry.tracer", "clear_span_buffer"),
    "get_current_span_context": ("devops_cli.telemetry.tracer", "get_current_span_context"),
    "get_recent_spans": ("devops_cli.telemetry.tracer", "get_recent_spans"),
    "get_trace_spans": ("devops_cli.telemetry.tracer", "get_trace_spans"),
    "get_tracer": ("devops_cli.telemetry.tracer", "get_tracer"),
    "inject_trace_context": ("devops_cli.telemetry.tracer", "inject_trace_context"),
    "record_completed_span": ("devops_cli.telemetry.tracer", "record_completed_span"),
    "record_metric": ("devops_cli.telemetry.tracer", "record_metric"),
    "reset_tracer": ("devops_cli.telemetry.tracer", "reset_tracer"),
    "trace_span": ("devops_cli.telemetry.tracer", "trace_span"),
    "traced": ("devops_cli.telemetry.tracer", "traced"),
    "flatten_waterfall_tree": ("devops_cli.telemetry.waterfall", "flatten_waterfall_tree"),
    "normalize_tempo_spans": ("devops_cli.telemetry.waterfall", "normalize_tempo_spans"),
    "query_tempo_trace": ("devops_cli.telemetry.waterfall", "query_tempo_trace"),
    "render_waterfall_bar": ("devops_cli.telemetry.waterfall", "render_waterfall_bar"),
    "resolve_trace_spans": ("devops_cli.telemetry.waterfall", "resolve_trace_spans"),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "GLOBAL_METRICS",
    "AgentTurnHandle",
    "ContextPropagatingThread",
    "ContextPropagatingThreadPoolExecutor",
    "InMemoryMetricsRegistry",
    "LogfireBridge",
    "LogfireOTelBridgeProcessor",
    "LogfireStatus",
    "MemoryAllocationItem",
    "MemoryProfileReport",
    "MemoryProfiler",
    "MemoryProfilerError",
    "OTelTelemetryClient",
    "SpanWaterfallNode",
    "TraceContext",
    "TraceCorrelationFilter",
    "attach_trace_correlation_filter",
    "bind_context",
    "build_span_waterfall_tree",
    "clear_span_buffer",
    "count_open_sockets",
    "emit_service_status_telemetry",
    "extract_env",
    "extract_headers",
    "extract_traceparent",
    "extract_traceparent_from_headers",
    "fetch_all_service_statuses",
    "fetch_cloudflare_status",
    "fetch_github_status",
    "flatten_waterfall_tree",
    "generate_span_id",
    "generate_trace_id",
    "generate_traceparent",
    "get_current_span_context",
    "get_current_trace_correlation",
    "get_logfire_bridge",
    "get_recent_spans",
    "get_trace_spans",
    "get_tracer",
    "inject_env",
    "inject_headers",
    "inject_trace_context",
    "inject_traceparent_headers",
    "logfire_agent_turn",
    "new_trace_context",
    "normalize_tempo_spans",
    "parse_traceparent",
    "profile_custom_callable",
    "profile_fastmcp_workload",
    "profile_http_pool_workload",
    "query_tempo_trace",
    "record_completed_span",
    "record_metric",
    "record_service_status_in_registry",
    "render_agent_turn_panel",
    "render_agent_turn_table",
    "render_waterfall_bar",
    "reset_logfire_bridge",
    "reset_tracer",
    "resolve_trace_spans",
    "run_memory_profiler",
    "trace_span",
    "traced",
]
