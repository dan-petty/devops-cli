"""Structured JSON logging for devops-cli service mode."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Final

CONTEXT_LOG_KEYS: Final[tuple[str, ...]] = (
    "repo",
    "source",
    "event",
    "action",
    "delivery",
    "outcome",
    "duration_s",
    "result",
)


class JsonLogFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        record_time = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        log_entry: dict[str, Any] = {
            "time": record_time,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        for key in CONTEXT_LOG_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
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


def setup_service_logging(log_level: str = "INFO") -> None:
    """Configure root and uvicorn loggers to emit single-line JSON to stdout."""
    handler = JsonLogStreamHandler()
    handler.setFormatter(JsonLogFormatter())
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "devops_cli"):
        u_log = logging.getLogger(name)
        u_log.handlers.clear()
        u_log.addHandler(handler)
        u_log.setLevel(numeric_level)
        u_log.propagate = False
