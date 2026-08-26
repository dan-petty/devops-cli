"""Unit tests for OpenTelemetry log correlation filter and bridge."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from devops_cli.telemetry.logging_bridge import (
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
