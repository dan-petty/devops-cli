"""Tests for the dashboard Telemetry data provider."""

from __future__ import annotations

from devops_cli.ui.data_providers import TelemetrySummary, fetch_telemetry_status


def test_fetch_telemetry_status() -> None:
    """fetch_telemetry_status inspects in-memory metric counters and gauges."""
    from devops_cli.telemetry.metrics import GLOBAL_METRICS

    GLOBAL_METRICS.reset()
    GLOBAL_METRICS.increment_counter("cli.commands.invoked", 3.0)
    GLOBAL_METRICS.set_gauge("memory.rss.bytes", 1024.0)
    GLOBAL_METRICS.record_histogram("request.duration.seconds", 0.042)

    summary = fetch_telemetry_status()
    assert isinstance(summary, TelemetrySummary)
    assert summary.counter_count >= 1
    assert summary.gauge_count >= 1
    assert summary.histogram_count >= 1
    assert "cli.commands.invoked" in summary.counters
