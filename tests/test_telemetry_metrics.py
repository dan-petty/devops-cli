"""Unit tests for in-memory Prometheus metrics collector."""

from __future__ import annotations

from devops_cli.telemetry import (
    InMemoryMetricsRegistry,
    extract_traceparent,
    inject_traceparent_headers,
)


def test_metrics_registry_counters() -> None:
    registry = InMemoryMetricsRegistry()
    registry.increment_counter("devops_cli_commands_total", 1.0, {"subcommand": "review"})
    registry.increment_counter("devops_cli_commands_total", 2.0, {"subcommand": "review"})
    registry.increment_counter("devops_cli_commands_total", 1.0, {"subcommand": "scan"})

    assert registry.get_counter_value("devops_cli_commands_total", {"subcommand": "review"}) == 3.0
    assert registry.get_counter_value("devops_cli_commands_total", {"subcommand": "scan"}) == 1.0
    assert registry.get_counter_value("devops_cli_commands_total", {"subcommand": "k8s"}) == 0.0


def test_metrics_registry_gauges() -> None:
    registry = InMemoryMetricsRegistry()
    registry.set_gauge("devops_cli_active_workers", 4.0)
    assert registry.get_gauge_value("devops_cli_active_workers") == 4.0
    registry.set_gauge("devops_cli_active_workers", 2.0)
    assert registry.get_gauge_value("devops_cli_active_workers") == 2.0


def test_metrics_registry_histograms() -> None:
    registry = InMemoryMetricsRegistry()
    registry.record_histogram("devops_cli_llm_turn_duration_ms", 120.0, {"model": "qwen2.5"})
    registry.record_histogram("devops_cli_llm_turn_duration_ms", 180.0, {"model": "qwen2.5"})

    samples = registry.get_histogram_samples(
        "devops_cli_llm_turn_duration_ms", {"model": "qwen2.5"}
    )
    assert samples == [120.0, 180.0]


def test_metrics_export_prometheus_text() -> None:
    registry = InMemoryMetricsRegistry()
    registry.increment_counter("test_counter", 5.0, {"env": "prod"})
    registry.set_gauge("test_gauge", 42.0)
    registry.record_histogram("test_hist", 10.0, {"tag": "a"})

    output = registry.export_prometheus_text()
    assert "# TYPE test_counter counter" in output
    assert 'test_counter{env="prod"} 5.0' in output
    assert "# TYPE test_gauge gauge" in output
    assert "test_gauge 42.0" in output
    assert "test_hist_count" in output
    assert "test_hist_sum" in output


def test_w3c_traceparent_helpers() -> None:
    valid_header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    extracted = extract_traceparent(valid_header)
    assert extracted is not None
    assert extracted["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert extracted["parent_span_id"] == "00f067aa0ba902b7"

    assert extract_traceparent(None) is None
    assert extract_traceparent("invalid-header") is None

    headers: dict[str, str] = {}
    injected = inject_traceparent_headers(headers)
    assert isinstance(injected, dict)
