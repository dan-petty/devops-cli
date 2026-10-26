"""OpenTelemetry log correlation bridge for standard library logging and SIEM audit logs."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any

from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.tracer import (
    _normalize_code_filepath,
    _to_otlp_any_value,
    get_current_span_context,
)

_LOG_RECURSION_GUARD = threading.local()

# Attributes omitted to avoid leaking prompt and reply text into logs (#606).
_PROMPT_REPLY_ATTR_KEYS: frozenset[str] = frozenset(
    {
        "prompt",
        "completion",
        "reply",
        "response",
        "llm_output",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
    }
)

_RECORD_BUILTIN_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "trace_id",
        "span_id",
        "message",
    }
)


def _log_level_to_severity(levelno: int) -> tuple[int, str]:
    """Convert standard logging level to OTel (severityNumber, severityText)."""
    if levelno >= logging.CRITICAL:
        return 21, "FATAL"
    if levelno >= logging.ERROR:
        return 17, "ERROR"
    if levelno >= logging.WARNING:
        return 13, "WARN"
    if levelno >= logging.INFO:
        return 9, "INFO"
    return 5, "DEBUG"


class TraceCorrelationFilter(logging.Filter):
    """Logging filter that injects active OpenTelemetry trace_id and span_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Enrich LogRecord with active trace_id and span_id attributes."""
        ctx = get_current_span_context() or {}
        setattr(record, "trace_id", ctx.get("trace_id") or "")
        setattr(record, "span_id", ctx.get("span_id") or "")
        return True


def get_current_trace_correlation() -> dict[str, str]:
    """Retrieve current trace correlation identifiers."""
    ctx = get_current_span_context() or {}
    return {
        "trace_id": ctx.get("trace_id") or "",
        "span_id": ctx.get("span_id") or "",
    }


def attach_trace_correlation_filter(logger: logging.Logger | None = None) -> None:
    """Attach TraceCorrelationFilter to the target logger if not already present."""
    target = logger or logging.getLogger()
    for flt in target.filters:
        if isinstance(flt, TraceCorrelationFilter):
            return
    target.addFilter(TraceCorrelationFilter())


def _extract_record_attributes(record: logging.LogRecord) -> dict[str, Any]:
    """Collect standard and extra attributes from a LogRecord."""
    attrs: dict[str, Any] = {"log.logger": record.name}
    if record.pathname:
        attrs["code.filepath"] = _normalize_code_filepath(record.pathname)
    if record.funcName:
        attrs["code.function"] = record.funcName
    if record.lineno:
        attrs["code.lineno"] = int(record.lineno)

    if record.exc_info and record.exc_info[0]:
        attrs["exception.type"] = getattr(record.exc_info[0], "__name__", str(record.exc_info[0]))
        if record.exc_info[1]:
            attrs["exception.message"] = mask_secrets(str(record.exc_info[1]))
        formatted_tb = "".join(traceback.format_exception(*record.exc_info))
        attrs["exception.stacktrace"] = mask_secrets(formatted_tb)

    for key, val in record.__dict__.items():
        if key.startswith("_") or key in attrs or key in _RECORD_BUILTIN_ATTRS:
            continue
        key_lower = key.lower()
        if (
            key in _PROMPT_REPLY_ATTR_KEYS
            or "prompt" in key_lower
            or "reply" in key_lower
            or "completion" in key_lower
        ):
            continue
        if isinstance(val, (str, int, float, bool)):
            attrs[key] = mask_secrets(val) if isinstance(val, str) else val
    return attrs


def _build_log_entry(record: logging.LogRecord) -> dict[str, Any]:
    """Construct an OTLP log record payload from a standard logging LogRecord."""
    now_nano = str(int(time.time() * 1e9))
    created_nano = str(int(record.created * 1e9))
    sev_num, sev_txt = _log_level_to_severity(record.levelno)
    body_text = mask_secrets(record.getMessage())
    attrs = _extract_record_attributes(record)

    ctx = get_current_span_context() or {}
    trace_id = getattr(record, "trace_id", None) or ctx.get("trace_id") or ""
    span_id = getattr(record, "span_id", None) or ctx.get("span_id") or ""

    entry: dict[str, Any] = {
        "timeUnixNano": created_nano,
        "observedTimeUnixNano": now_nano,
        "severityNumber": sev_num,
        "severityText": sev_txt,
        "body": {"stringValue": body_text},
        "attributes": [{"key": k, "value": _to_otlp_any_value(v)} for k, v in attrs.items()],
    }
    if trace_id:
        entry["traceId"] = str(trace_id)
    if span_id:
        entry["spanId"] = str(span_id)
    return entry


def _resolve_exporter(
    configured: Callable[[dict[str, Any]], None] | None,
) -> Callable[[dict[str, Any]], None] | None:
    """Resolve active log exporter callable."""
    if configured is not None:
        return configured
    import devops_cli.telemetry.tracer as tr

    if tr._GLOBAL_TRACER is None or not tr._GLOBAL_TRACER.enabled:
        return None
    return tr._GLOBAL_TRACER.export_log_record


class OTelLoggingHandler(logging.Handler):
    """Logging handler that formats LogRecords into OTLP log records and exports them."""

    def __init__(
        self,
        level: int = logging.WARNING,
        exporter: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(level)
        self._exporter = exporter

    def emit(self, record: logging.LogRecord) -> None:
        """Translate a LogRecord to an OTLP log record and queue it for export."""
        if record.levelno < self.level:
            return
        if getattr(_LOG_RECURSION_GUARD, "active", False):
            return
        if record.name.startswith("devops_cli.telemetry"):
            return

        exporter = _resolve_exporter(self._exporter)
        if exporter is None:
            return

        _LOG_RECURSION_GUARD.active = True
        try:
            entry = _build_log_entry(record)
            exporter(entry)
        finally:
            _LOG_RECURSION_GUARD.active = False


def attach_otel_logging_handler(
    logger: logging.Logger | None = None,
    handler: OTelLoggingHandler | None = None,
) -> OTelLoggingHandler:
    """Attach OTelLoggingHandler and TraceCorrelationFilter to the specified logger."""
    target = logger or logging.getLogger()
    attach_trace_correlation_filter(target)
    for h in target.handlers:
        if isinstance(h, OTelLoggingHandler):
            return h
    inst = handler if handler is not None else OTelLoggingHandler()
    target.addHandler(inst)
    return inst


def detach_otel_logging_handler(logger: logging.Logger | None = None) -> None:
    """Detach OTelLoggingHandler from the specified logger."""
    target = logger or logging.getLogger()
    for h in list(target.handlers):
        if isinstance(h, OTelLoggingHandler):
            target.removeHandler(h)
