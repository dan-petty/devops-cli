"""Tests for Telemetry Source behaviour in reactive dashboard."""

from __future__ import annotations

import pytest

import devops_cli.ui.data_providers as data_providers
from devops_cli.ui.data_providers import (
    fetch_telemetry_status,
)


def test_telemetry_falls_back_to_the_in_process_registry_without_a_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no Prometheus configured the panel reports what this process recorded."""
    monkeypatch.setattr(data_providers, "_prometheus_base_url", lambda: None)
    assert fetch_telemetry_status().source == "in-process"


def test_a_failed_backend_query_names_the_endpoint_that_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "Connection refused" against a configured endpoint is a different problem from
    having no metrics, and the banner has to distinguish them."""
    monkeypatch.setattr(data_providers, "_prometheus_base_url", lambda: "http://prom:9090")
    monkeypatch.setattr(
        data_providers,
        "_fetch_prometheus_metrics",
        lambda url: (_ for _ in ()).throw(ConnectionError("connection refused")),
    )
    summary = fetch_telemetry_status()
    assert ("http://prom:9090" in summary.error_message, summary.source) == (True, "in-process")
