"""The OTLP endpoint check refuses a Service that the cluster does not hold (#4528)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.gate.k8s_checks import otel_endpoints

OLD_SERVICE = "http://otel-collector.otel.svc.cluster.local:4318"
COLLECTOR = "http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318"


def _write(root: Path, value: str) -> None:
    """A manifest under `root/k8s` with one OTLP endpoint variable."""
    (root / "k8s").mkdir()
    (root / "k8s" / "template.yaml").write_text(
        f"env:\n  - name: OTEL_EXPORTER_OTLP_ENDPOINT\n    value: {value}\n", encoding="utf-8"
    )


def test_the_check_refuses_a_service_the_cluster_does_not_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, OLD_SERVICE)
    monkeypatch.setattr(otel_endpoints, "REPO_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="names no Collector Service"):
        otel_endpoints.check_every_otlp_endpoint_names_the_collector_service()


def test_the_check_accepts_the_collector_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, COLLECTOR)
    monkeypatch.setattr(otel_endpoints, "REPO_ROOT", tmp_path)

    assert otel_endpoints.check_every_otlp_endpoint_names_the_collector_service() is None
