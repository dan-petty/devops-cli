"""The Service's JSON log lines carry the ids of the open span, and Grafana links them to Tempo.

The Service writes each log record as one JSON line to stdout through the `json` handler of
`service_log_config`. A line written while a span is open names that span's `trace_id` and
`span_id`, so a Loki line leads to its trace (#4510).
"""

from __future__ import annotations

import json
import logging
import logging.config
from collections.abc import Iterator
from typing import Any

import pytest

from devops_cli.server.json_logs import service_log_config
from devops_cli.telemetry.tracer import trace_span
from tests.support.fakes.otlp import FakeCollector

SERVICE_LOGGER = "devops_cli.tests.service_log_trace_ids"


@pytest.fixture
def service_logger() -> Iterator[logging.Logger]:
    """A logger that writes through the Service's own `json` handler, formatter and filters.

    The handler is built by `dictConfig` from `service_log_config`, as uvicorn builds it, but only
    this logger gets it, so the process's root and named loggers stay as they are.
    """
    config = service_log_config("INFO")
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": config["formatters"],
            "filters": config.get("filters", {}),
            "handlers": config["handlers"],
            "loggers": {
                SERVICE_LOGGER: {"handlers": ["json"], "level": logging.INFO, "propagate": False}
            },
        }
    )
    logger = logging.getLogger(SERVICE_LOGGER)
    yield logger
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]


def test_a_line_written_in_a_span_names_that_spans_trace_and_span_ids(
    otlp: FakeCollector, service_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Service line written while a span of the own tracer is open carries its two ids."""
    with trace_span("service.round"):
        service_logger.info("Round done.", extra={"repo": "example-org/repo1"})
    span = otlp.spans[0]

    assert [
        (line["message"], line["repo"], line.get("trace_id"), line.get("span_id"))
        for line in _lines(capsys)
    ] == [("Round done.", "example-org/repo1", span.trace_id, span.span_id)]


def test_a_line_written_in_an_opentelemetry_span_names_that_spans_ids(
    service_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """A line written in a span of an OpenTelemetry SDK tracer, as a library opens it, carries
    that span's ids when no span of the own tracer is open."""
    from opentelemetry.sdk.trace import TracerProvider

    tracer = TracerProvider().get_tracer("example.library")
    with tracer.start_as_current_span("chat") as span:
        service_logger.info("Model reply.")
    context = span.get_span_context()

    assert [(line.get("trace_id"), line.get("span_id")) for line in _lines(capsys)] == [
        (format(context.trace_id, "032x"), format(context.span_id, "016x"))
    ]


def test_a_line_written_outside_a_span_has_no_trace_keys(
    service_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """A line written with no open span has neither key, not an empty value."""
    service_logger.info("Service started.")

    assert [sorted(line) for line in _lines(capsys)] == [["level", "logger", "message", "time"]]
