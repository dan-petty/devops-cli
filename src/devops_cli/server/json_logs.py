"""Structured JSON logging for devops-cli service mode."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Final

from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.logging_bridge import TraceCorrelationFilter

CONTEXT_LOG_KEYS: Final[tuple[str, ...]] = (
    "repo",
    "lane",
    "source",
    "provider",
    "event",
    "action",
    "delivery",
    "outcome",
    "duration_s",
    "result",
)

# The ids of the span open when the record was logged; `TraceCorrelationFilter` sets them.
TRACE_LOG_KEYS: Final[tuple[str, ...]] = ("trace_id", "span_id")


class JsonLogFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        record_time = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        log_entry: dict[str, Any] = {
            "time": record_time,
            "level": record.levelname,
            "logger": record.name,
            "message": mask_secrets(record.getMessage()),
        }
        if record.exc_info:
            log_entry["exception"] = mask_secrets(self.formatException(record.exc_info))
        for key in CONTEXT_LOG_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = mask_secrets(str(val)) if isinstance(val, str) else val
        for key in TRACE_LOG_KEYS:
            if trace_value := getattr(record, key, ""):
                log_entry[key] = trace_value
        return json.dumps(log_entry, separators=(",", ":"), ensure_ascii=False)


class JsonLogStreamHandler(logging.StreamHandler[Any]):
    """StreamHandler dynamically referencing sys.stdout and safely handling closed streams."""

    @property
    def stream(self) -> Any:
        return sys.stdout

    @stream.setter
    def stream(self, val: Any) -> None:
        pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except ValueError, OSError:
            pass


def service_log_config(log_level: str = "INFO") -> dict[str, Any]:
    """The service's logging, single-line JSON to stdout from the root, uvicorn and devops_cli
    loggers, as the `logging.config.dictConfig` schema uvicorn applies when it starts.

    The `json` handler's `TraceCorrelationFilter` puts the ids of the open span on each record
    the handler gets, also on one that propagates to the root, and the formatter writes them.

    Handing it to uvicorn as `log_config` leaves the process's logging alone until the server
    starts. Loggers that exist by then stay enabled.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    loggers: dict[str, Any] = {
        name: {"handlers": ["json"], "level": numeric_level, "propagate": False}
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "devops_cli")
    }
    for name in ("httpx", "httpx2", "httpcore"):
        loggers[name] = {"handlers": ["json"], "level": logging.WARNING, "propagate": False}
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": JsonLogFormatter}},
        "filters": {"trace": {"()": TraceCorrelationFilter}},
        "handlers": {
            "json": {"class": JsonLogStreamHandler, "formatter": "json", "filters": ["trace"]}
        },
        "root": {"handlers": ["json"], "level": numeric_level},
        "loggers": loggers,
    }
