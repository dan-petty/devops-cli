"""Unit tests for in-memory Prometheus metrics collector."""

from __future__ import annotations

import pytest

from devops_cli.telemetry import (
    InMemoryMetricsRegistry,
    extract_traceparent,
    inject_traceparent_headers,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


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
    from prometheus_client.parser import text_string_to_metric_families

    registry = InMemoryMetricsRegistry()
    registry.record_histogram("devops_cli_llm_turn_duration_ms", 120.0, {"model": "qwen2.5"})
    registry.record_histogram("devops_cli_llm_turn_duration_ms", 180.0, {"model": "qwen2.5"})

    families = {
        f.name: f for f in text_string_to_metric_families(registry.export_prometheus_text())
    }
    hist = families["devops_cli_llm_turn_duration_ms"]
    samples = {(s.name, s.labels.get("le")): s.value for s in hist.samples}
    assert "get_histogram_samples" not in dir(registry)
    assert (
        hist.type,
        samples[("devops_cli_llm_turn_duration_ms_count", None)],
        samples[("devops_cli_llm_turn_duration_ms_sum", None)],
        samples[("devops_cli_llm_turn_duration_ms_bucket", "+Inf")],
    ) == ("histogram", 2.0, 300.0, 2.0)


def test_metrics_export_prometheus_text() -> None:
    registry = InMemoryMetricsRegistry()
    registry.increment_counter("test_counter", 5.0, {"env": "prod"})
    registry.set_gauge("test_gauge", 42.0)
    registry.record_histogram("test_hist", 0.25, {"tag": "a"})

    output = registry.export_prometheus_text()
    assert (
        "# TYPE test_counter_total counter" in output,
        'test_counter_total{env="prod"} 5.0' in output,
        "# TYPE test_gauge gauge" in output,
        "test_gauge 42.0" in output,
        'test_hist_bucket{le="+Inf",tag="a"} 1.0' in output,
        'test_hist_count{tag="a"} 1.0' in output,
        'test_hist_sum{tag="a"} 0.25' in output,
    ) == (True,) * 7


def test_metrics_registry_rejects_conflicting_collector_types() -> None:
    """Registering the same metric family name with two different collector types raises ValueError."""
    import pytest

    registry = InMemoryMetricsRegistry()
    registry.increment_counter("devops_cli_shared_metric", 1.0)
    with pytest.raises(ValueError, match="Duplicated timeseries"):
        registry.set_gauge("devops_cli_shared_metric", 2.0)
    with pytest.raises(ValueError, match="Duplicated timeseries"):
        registry.record_histogram("devops_cli_shared_metric", 0.5)


def test_both_metrics_routes_parse_via_prometheus_client(
    tmp_path: object, monkeypatch: object
) -> None:
    """Both `/metrics` routes return `CONTENT_TYPE_LATEST` and parse cleanly with `prometheus_client.parser`."""
    from pathlib import Path

    import pytest
    from fastapi.testclient import TestClient
    from prometheus_client import CONTENT_TYPE_LATEST
    from prometheus_client.parser import text_string_to_metric_families

    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.server.app import create_app
    from devops_cli.server.service import create_service_app
    from devops_cli.telemetry.metrics import GLOBAL_METRICS

    mp = monkeypatch  # type: ignore[assignment]
    assert isinstance(mp, pytest.MonkeyPatch)
    assert isinstance(tmp_path, Path)
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    mp.setattr("devops_cli.ai.spend.ledger.get_spend_ledger", lambda: ledger)
    GLOBAL_METRICS.record_histogram(
        "devops_cli_service_request_seconds", 0.05, {"route": "/healthz"}
    )

    for app in (create_app(), create_service_app()):
        resp = TestClient(app).get("/metrics")
        families = list(text_string_to_metric_families(resp.text))
        histograms = [f for f in families if f.type == "histogram"]
        assert (resp.status_code, resp.headers["content-type"], len(families) > 0) == (
            200,
            CONTENT_TYPE_LATEST,
            True,
        )
        for hist in histograms:
            names = {s.name for s in hist.samples}
            inf_buckets = [
                s
                for s in hist.samples
                if s.name == f"{hist.name}_bucket" and s.labels.get("le") == "+Inf"
            ]
            assert (
                {f"{hist.name}_bucket", f"{hist.name}_sum", f"{hist.name}_count"} <= names,
                len(inf_buckets) > 0,
            ) == (True, True)


def test_w3c_traceparent_helpers(tracer: object) -> None:
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

    from devops_cli.telemetry.tracer import trace_span

    with trace_span("test_span_inject"):
        injected_active = inject_traceparent_headers({"Custom": "1"})
        assert "traceparent" in injected_active
        assert injected_active["traceparent"].startswith("00-")
