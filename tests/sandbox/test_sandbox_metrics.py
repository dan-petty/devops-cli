"""The sandbox metrics snapshot: the model, the collector and the engine."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.metrics import (
    collect_sandbox_metrics,
)
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    PortBinding,
    PrometheusMetric,
    SandboxInstance,
    SandboxMetricsSnapshot,
    SandboxStatus,
)
from tests.support.fakes.dial import http_response, record_connects
from tests.support.fakes.docker_engine import DockerEngineFake
from tests.support.sandbox import (
    port_of,
)


def test_sandbox_metrics_snapshot_model() -> None:
    """Test SandboxMetricsSnapshot serialization and properties."""
    snapshot = SandboxMetricsSnapshot(
        instance_id="sandbox-test-108",
        target="api-service",
        cgroup=CgroupV2Metrics(cpu_percent=12.5, memory_current_bytes=52428800),
        prometheus_metrics=[PrometheusMetric(name="up", metric_type="gauge", labels={}, value=1.0)],
        warnings=[],
        timestamp="2026-09-12T13:00:00Z",
    )
    dump = snapshot.model_dump()
    assert dump["instance_id"] == "sandbox-test-108"
    assert len(dump["prometheus_metrics"]) == 1
    assert snapshot.is_healthy is True


def test_collect_sandbox_metrics_with_instance(prom_server: str, tmp_path: Path) -> None:
    """Test collect_sandbox_metrics against a SandboxInstance object."""
    instance = SandboxInstance(
        instance_id="sandbox-test-metrics-1",
        container_id="cont-metrics-1",
        name="web-service",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[
            PortBinding(container_port=8080, host_port=port_of(prom_server), protocol="tcp")
        ],
        workspace_dir=str(tmp_path / "workspace"),
        created_at="2026-09-12T13:00:00Z",
    )
    cgroup_dir = tmp_path / "cgroup" / "system.slice" / "docker-cont-metrics-1.scope"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "memory.current").write_text("104857600\n")
    (cgroup_dir / "memory.max").write_text("209715200\n")
    (cgroup_dir / "pids.current").write_text("10\n")

    snapshot = collect_sandbox_metrics(
        instance, prom_endpoint="/metrics", timeout=2.0, cgroup_root=tmp_path / "cgroup"
    )

    assert snapshot.instance_id == "sandbox-test-metrics-1"
    assert snapshot.target == "web-service"
    assert snapshot.cgroup is not None
    assert (snapshot.cgroup.memory_usage_percent, snapshot.cgroup.pids_current) == (50.0, 10)
    assert len(snapshot.prometheus_metrics) >= 6
    assert snapshot.is_healthy is True


def test_collect_sandbox_metrics_with_raw_url(prom_server: str) -> None:
    """Test collect_sandbox_metrics against a raw URL."""
    snapshot = collect_sandbox_metrics(prom_server, prom_endpoint="/metrics", timeout=2.0)
    assert snapshot.cgroup is None
    assert len(snapshot.prometheus_metrics) >= 6


def test_engine_metrics_reports_the_resource_use_and_scrape_of_a_registered_sandbox(
    register_sandbox: Callable[..., SandboxInstance], prom_server: str
) -> None:
    """The engine reads the container's resource use and scrapes its published port."""
    register_sandbox("sandbox-engine-1", name="engine-svc", host_ports=[port_of(prom_server)])

    snapshot = WorkloadSandboxEngine().metrics("sandbox-engine-1")

    assert (
        snapshot.instance_id,
        snapshot.target,
        snapshot.cgroup.cpu_percent if snapshot.cgroup else None,
        len(snapshot.prometheus_metrics) >= 6,
    ) == ("sandbox-engine-1", "engine-svc", 2.0, True)


def test_engine_metrics_raises_not_found() -> None:
    """Test WorkloadSandboxEngine.metrics raises SandboxNotFoundError if not found."""
    with pytest.raises(SandboxNotFoundError) as raised:
        WorkloadSandboxEngine().metrics("nonexistent-id")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


def test_a_sandbox_with_no_published_port_is_scraped_on_8080(
    monkeypatch: pytest.MonkeyPatch, docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """Test port resolution defaults to 8080 when no bindings present."""
    recorder = record_connects(monkeypatch, [http_response(200, "up 1\n")])
    inst = SandboxInstance(
        instance_id="inst-no-ports",
        container_id="c-no-ports",
        name="no-ports",
        image="alpine",
        status=SandboxStatus.RUNNING,
        port_bindings=[],
        workspace_dir=str(tmp_path),
        created_at="2026-09-12T13:00:00Z",
    )

    collect_sandbox_metrics(inst, cgroup_root=tmp_path)

    assert ("127.0.0.1", 8080) in recorder.dialled


def test_a_failed_scrape_leaves_the_snapshot_unhealthy_with_its_error(prom_server: str) -> None:
    """Test that failed metrics scrapes preserve error details and mark snapshot unhealthy."""
    snapshot = collect_sandbox_metrics(prom_server, prom_endpoint="/error")

    assert snapshot.scrape_error == f"HTTP 500 response from {prom_server}/error"
    assert len(snapshot.warnings) == 0
    assert snapshot.is_healthy is False
