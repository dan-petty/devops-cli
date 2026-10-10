"""Structured JSON logging for devops-cli service mode."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Final

from devops_cli.security.sanitizer import mask_secrets

CONTEXT_LOG_KEYS: Final[tuple[str, ...]] = (
    "repo",
    "lane",
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
            "message": mask_secrets(record.getMessage()),
        }
        if record.exc_info:
            log_entry["exception"] = mask_secrets(self.formatException(record.exc_info))
        for key in CONTEXT_LOG_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = mask_secrets(str(val)) if isinstance(val, str) else val
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

    Handing it to uvicorn as `log_config` leaves the process's logging alone until the server
    starts. Loggers that exist by then stay enabled.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": JsonLogFormatter}},
        "handlers": {"json": {"class": JsonLogStreamHandler, "formatter": "json"}},
        "root": {"handlers": ["json"], "level": numeric_level},
        "loggers": {
            name: {"handlers": ["json"], "level": numeric_level, "propagate": False}
            for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "devops_cli")
        },
    }
