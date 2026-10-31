"""Unit tests for OpenTelemetry log correlation filter and bridge."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

from devops_cli.telemetry.logging_bridge import (
    OTelLoggingHandler,
    TraceCorrelationFilter,
    attach_trace_correlation_filter,
    get_current_trace_correlation,
)


def test_trace_correlation_filter_no_context() -> None:
    filt = TraceCorrelationFilter()
    record = logging.LogRecord("test", logging.INFO, "test.py", 10, "Test message", (), None)
    assert filt.filter(record) is True
    assert getattr(record, "trace_id", None) == ""
    assert getattr(record, "span_id", None) == ""


@patch("devops_cli.telemetry.logging_bridge.get_current_span_context")
def test_trace_correlation_filter_with_context(mock_ctx: MagicMock) -> None:
    mock_ctx.return_value = {
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "span_id": "00f067aa0ba902b7",
    }
    filt = TraceCorrelationFilter()
    record = logging.LogRecord("test", logging.INFO, "test.py", 10, "Test message", (), None)
    assert filt.filter(record) is True
    assert getattr(record, "trace_id") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert getattr(record, "span_id") == "00f067aa0ba902b7"


@patch("devops_cli.telemetry.logging_bridge.get_current_span_context")
def test_get_current_trace_correlation(mock_ctx: MagicMock) -> None:
    mock_ctx.return_value = {"trace_id": "123", "span_id": "456"}
    res = get_current_trace_correlation()
    assert res == {"trace_id": "123", "span_id": "456"}


def test_attach_trace_correlation_filter() -> None:
    test_logger = logging.getLogger("test_logger_unique")
    attach_trace_correlation_filter(test_logger)
    assert any(isinstance(f, TraceCorrelationFilter) for f in test_logger.filters)
    # Double attach is idempotent
    attach_trace_correlation_filter(test_logger)
    count = sum(1 for f in test_logger.filters if isinstance(f, TraceCorrelationFilter))
    assert count == 1


def test_otel_logging_handler_formats_otlp_log_record() -> None:
    sent_records: list[dict[str, Any]] = []
    exporter = MagicMock(side_effect=lambda record: sent_records.append(record))
    handler = OTelLoggingHandler(exporter=exporter)
    handler.setLevel(logging.WARNING)

    record = logging.LogRecord(
        name="test.component",
        level=logging.WARNING,
        pathname="/workspace/src/foo.py",
        lineno=42,
        msg="Warning event: %s",
        args=("disk high",),
        exc_info=None,
        func="run_check",
    )
    record.trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    record.span_id = "00f067aa0ba902b7"

    handler.emit(record)

    assert len(sent_records) == 1
    log_rec = sent_records[0]
    assert log_rec["severityNumber"] == 13
    assert log_rec["severityText"] == "WARN"
    assert log_rec["body"] == {"stringValue": "Warning event: disk high"}
    assert log_rec["traceId"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert log_rec["spanId"] == "00f067aa0ba902b7"
    attrs = {a["key"]: a["value"] for a in log_rec["attributes"]}
    assert attrs["log.logger"] == {"stringValue": "test.component"}
    assert attrs["code.function"] == {"stringValue": "run_check"}
    assert attrs["code.lineno"] == {"intValue": "42"}


def test_otel_logging_handler_filters_below_warning() -> None:
    sent_records: list[dict[str, Any]] = []
    exporter = MagicMock(side_effect=lambda record: sent_records.append(record))
    handler = OTelLoggingHandler(exporter=exporter)

    info_record = logging.LogRecord("test", logging.INFO, "test.py", 10, "info message", (), None)
    debug_record = logging.LogRecord(
        "test", logging.DEBUG, "test.py", 10, "debug message", (), None
    )

    handler.handle(info_record)
    handler.handle(debug_record)

    assert len(sent_records) == 0


def test_otel_logging_handler_masks_secrets_and_omits_prompt_reply() -> None:
    sent_records: list[dict[str, Any]] = []
    exporter = MagicMock(side_effect=lambda record: sent_records.append(record))
    handler = OTelLoggingHandler(exporter=exporter)

    record = logging.LogRecord(
        name="test.ai",
        level=logging.ERROR,
        pathname="ai.py",
        lineno=100,
        msg="Failed with key: ghp_123456789012345678901234567890123456",
        args=(),
        exc_info=None,
    )
    setattr(record, "gen_ai.prompt", "Secret prompt text")
    setattr(record, "prompt", "User prompt")
    setattr(record, "reply", "AI completion")

    handler.emit(record)

    assert len(sent_records) == 1
    log_rec = sent_records[0]
    assert log_rec["severityNumber"] == 17
    assert log_rec["severityText"] == "ERROR"
    body_text = log_rec["body"]["stringValue"]
    assert "ghp_1234567890" not in body_text
    assert "<masked-github-token>" in body_text

    attr_keys = [a["key"] for a in log_rec["attributes"]]
    assert "gen_ai.prompt" not in attr_keys
    assert "prompt" not in attr_keys
    assert "reply" not in attr_keys


def test_otel_logging_handler_prevents_telemetry_recursion() -> None:
    sent_records: list[dict[str, Any]] = []
    exporter = MagicMock(side_effect=lambda record: sent_records.append(record))
    handler = OTelLoggingHandler(exporter=exporter)

    record = logging.LogRecord(
        name="devops_cli.telemetry.tracer",
        level=logging.WARNING,
        pathname="tracer.py",
        lineno=50,
        msg="Internal telemetry warning",
        args=(),
        exc_info=None,
    )

    handler.emit(record)
    assert len(sent_records) == 0
