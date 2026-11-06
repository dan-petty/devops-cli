"""The warnings that resource use and scraped metrics raise against their thresholds."""

from __future__ import annotations

from devops_cli.sandbox.metrics import (
    evaluate_threshold_warnings,
)
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    PrometheusMetric,
)


def test_evaluate_threshold_warnings_healthy() -> None:
    """Test evaluation when metrics are within healthy operating parameters."""
    cgroup = CgroupV2Metrics(
        cpu_percent=25.0,
        memory_current_bytes=104857600,
        memory_limit_bytes=524288000,
        memory_usage_percent=20.0,
    )
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"code": "200"}, value=100.0),
        PrometheusMetric(name="http_requests_total", labels={"code": "500"}, value=1.0),
    ]
    warnings = evaluate_threshold_warnings(
        cgroup, prom_metrics, memory_threshold_pct=80.0, cpu_threshold_pct=85.0
    )
    assert len(warnings) == 0


def test_evaluate_threshold_warnings_high_memory() -> None:
    """Test warning triggered when memory exceeds threshold."""
    cgroup = CgroupV2Metrics(
        cpu_percent=10.0,
        memory_current_bytes=471859200,
        memory_limit_bytes=524288000,
        memory_usage_percent=90.0,
    )
    warnings = evaluate_threshold_warnings(cgroup, [], memory_threshold_pct=80.0)
    assert len(warnings) >= 1
    assert any("memory" in w.lower() for w in warnings)


def test_evaluate_threshold_warnings_high_cpu() -> None:
    """Test warning triggered when CPU utilization exceeds threshold."""
    cgroup = CgroupV2Metrics(
        cpu_percent=92.5,
        memory_current_bytes=52428800,
        memory_limit_bytes=524288000,
        memory_usage_percent=10.0,
    )
    warnings = evaluate_threshold_warnings(cgroup, [], cpu_threshold_pct=85.0)
    assert len(warnings) >= 1
    assert any("cpu" in w.lower() for w in warnings)


def test_evaluate_threshold_warnings_high_error_rate() -> None:
    """Test warning triggered when Prometheus metrics indicate high 5xx error rate."""
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"code": "200"}, value=80.0),
        PrometheusMetric(name="http_requests_total", labels={"code": "500"}, value=20.0),
    ]
    warnings = evaluate_threshold_warnings(None, prom_metrics)
    assert len(warnings) >= 1
    assert any("error" in w.lower() for w in warnings)


def test_evaluate_threshold_warnings_memory_leak_trajectory() -> None:
    """Test evaluate_threshold_warnings detects memory leak trajectory when growth exceeds 20% and 5MB."""
    prior = CgroupV2Metrics(
        cpu_percent=10.0,
        memory_current_bytes=10 * 1024 * 1024,  # 10MB
    )
    current = CgroupV2Metrics(
        cpu_percent=10.0,
        memory_current_bytes=20 * 1024 * 1024,  # 20MB (100% growth, +10MB)
    )
    warnings = evaluate_threshold_warnings(
        cgroup=current,
        prom_metrics=[],
        previous_cgroup=prior,
    )
    assert len(warnings) == 1
    assert "memory leak trajectory" in warnings[0].lower()
    assert "100.0%" in warnings[0]


def test_evaluate_threshold_warnings_histogram_latency_degradation() -> None:
    """Test evaluate_threshold_warnings computes average latency from histogram sum and count."""
    prom_metrics = [
        PrometheusMetric(
            name="http_request_duration_seconds_sum",
            metric_type="histogram",
            labels={"handler": "orders"},
            value=60.0,  # 60 seconds total
        ),
        PrometheusMetric(
            name="http_request_duration_seconds_count",
            metric_type="histogram",
            labels={"handler": "orders"},
            value=50.0,  # across 50 requests -> 1.2s avg = 1200ms
        ),
    ]
    warnings = evaluate_threshold_warnings(
        cgroup=None,
        prom_metrics=prom_metrics,
        latency_threshold_ms=500.0,
    )
    assert len(warnings) == 1
    assert "High average request latency" in warnings[0]
    assert "1200.0ms >= 500.0ms" in warnings[0]


def test_evaluate_threshold_warnings_status_label_5xx() -> None:
    """Test evaluate_threshold_warnings detects 5xx spikes when metric uses status instead of code."""
    prom_metrics = [
        PrometheusMetric(name="http_requests_total", labels={"status": "200"}, value=80.0),
        PrometheusMetric(name="http_requests_total", labels={"status": "500"}, value=20.0),
    ]
    warnings = evaluate_threshold_warnings(None, prom_metrics)
    assert len(warnings) >= 1
    assert any("5xx" in w for w in warnings)


def test_evaluate_threshold_warnings_optional_latency_sla() -> None:
    """Test latency SLA is only evaluated when explicitly configured."""
    prom_metrics = [
        PrometheusMetric(
            name="http_request_duration_seconds_sum",
            metric_type="histogram",
            value=100.0,
        ),
        PrometheusMetric(
            name="http_request_duration_seconds_count",
            metric_type="histogram",
            value=10.0,
        ),
    ]
    # No latency SLA configured (None) -> no warnings generated
    warnings_none = evaluate_threshold_warnings(
        cgroup=None,
        prom_metrics=prom_metrics,
        latency_threshold_ms=None,
    )
    assert len(warnings_none) == 0

    # Configured SLA (5000ms < 10000ms average) -> warning generated
    warnings_configured = evaluate_threshold_warnings(
        cgroup=None,
        prom_metrics=prom_metrics,
        latency_threshold_ms=5000.0,
    )
    assert len(warnings_configured) == 1
    assert "High average request latency" in warnings_configured[0]
