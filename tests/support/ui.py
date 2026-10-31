"""Shared helpers, sample data and fixtures for dashboard UI tests."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from typing import Any

from textual.widgets import DataTable, Static

from devops_cli.models.k8s import ContainerInfo, PodInfo
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    TelemetrySummary,
    ValkeySummary,
)
from devops_cli.ui.widgets import LogPane
from tests.support.fakes.kubernetes import pod
from tests.support.waits import POLL_INTERVAL_SECONDS, THREAD_HANDOFF_BOUND_SECONDS


def _pod(
    name: str,
    namespace: str = "default",
    *,
    status: str = "Running",
    containers: tuple[str, ...] = ("app",),
) -> PodInfo:
    """Construct a PodInfo object for testing."""
    healthy = status == "Running"
    return PodInfo(
        namespace=namespace,
        name=name,
        status=status,
        ready_containers=f"{len(containers) if healthy else 0}/{len(containers)}",
        containers=[ContainerInfo(name=container, ready=healthy) for container in containers],
        default_container=containers[0],
        unhealthy=not healthy,
    )


def _pods(count: int) -> K8sSummary:
    """Construct a K8sSummary holding count pods."""
    return K8sSummary(connected=True, pods=[_pod(f"pod-{index:02d}") for index in range(count)])


def _wide_pods(count: int) -> K8sSummary:
    """Pods whose names run past the pod table's width, as real generated names do."""
    folder = "nested-" * 12
    return K8sSummary(
        connected=True, pods=[_pod(f"{folder}pod-{index:02d}") for index in range(count)]
    )


def _containers(count: int) -> DockerSummary:
    """Construct a DockerSummary holding count containers."""
    return DockerSummary(
        connected=True,
        containers=[
            {"id": f"c{index:05d}", "name": f"app-{index}", "image": "app:1", "status": "running"}
            for index in range(count)
        ],
    )


def _cluster(*, extra: tuple[PodInfo, ...] = (), without: str = "") -> K8sSummary:
    """63 pods, as on a small workstation cluster: one crashlooping, nine log collectors."""
    pods = [
        _pod("coredns-0", "kube-system"),
        _pod("exporter-0", "monitoring", status="CrashLoopBackOff"),
        _pod("grafana-0", "monitoring", containers=("grafana", "sidecar")),
        _pod("prometheus-server-0", "monitoring", containers=("server", "reloader")),
        *(_pod(f"alloy-logs-{index}", "monitoring") for index in range(9)),
        *(_pod(f"web-{index:02d}", "shop") for index in range(50)),
        *extra,
    ]
    return K8sSummary(
        connected=True,
        context="lab",
        pods=[p for p in pods if without not in (p.namespace, p.name)],
    )


def _shown(app: DashboardApp) -> list[str]:
    """Name the pods the Kubernetes table lists, in row order."""
    table = app.query_one("#k8s-table", DataTable)
    return [json.loads(str(row_key.value))[1] for row_key in table.rows]


def _k8s_banner_text(app: DashboardApp) -> str:
    """Retrieve rendered text from the k8s-banner widget."""
    return str(app.query_one("#k8s-banner", Static).render())


def _numbered_lines(count: int) -> Callable[..., Callable[[], Any]]:
    """A pod log source factory whose every stream is the same finite set of lines."""
    return lambda *args, **kwargs: lambda: iter([f"line-{index}" for index in range(count)])


def _sidecar_pod(annotated: bool) -> K8sSummary:
    """A pod with containers [sidecar, app], optionally annotated to default to app."""
    annotations = {"kubectl.kubernetes.io/default-container": "app"} if annotated else None
    api_pod = pod("web-0", containers=("sidecar", "app"), annotations=annotations)
    return K8sSummary(connected=True, pods=[PodInfo.from_pod(api_pod)])


def _recording_source(requested: list[str | None]) -> Callable[..., Callable[[], Any]]:
    """A pod log source factory recording the container each stream was opened for."""

    def source(pod: str, namespace: str, container: str | None = None, **_: Any) -> Any:
        requested.append(container)
        return lambda: iter([f"{container} line"])

    return source


def _endless(release: threading.Event) -> Callable[..., Callable[[], Any]]:
    """A pod log source factory whose streams never end until released."""

    def source(pod: str, namespace: str, container: str | None = None, **_: Any) -> Any:
        def lines() -> Any:
            index = 0
            while not release.is_set():
                index += 1
                yield f"{pod}/{container} {index}"
                release.wait(0.01)

        return lines

    return source


def sample_k8s() -> K8sSummary:
    """Return a representative Kubernetes summary for dashboard tests."""
    return K8sSummary(
        connected=True,
        context="lab",
        nodes_ready=1,
        nodes_total=1,
        pods=[
            PodInfo(
                namespace="devops-system",
                name="api-0",
                status="Running",
                ready_containers="1/1",
                containers=[ContainerInfo(name="api", ready=True, state="Running")],
                default_container="api",
            )
        ],
    )


def sample_docker() -> DockerSummary:
    """Return a representative Docker summary for dashboard tests."""
    return DockerSummary(
        connected=True,
        containers=[{"id": "abc123", "name": "valkey", "image": "valkey:8", "status": "running"}],
        images=[
            {
                "id": "img001",
                "tag": "valkey:8",
                "size": "41.2MB",
                "created": "2026-09-01 10:00:00",
            }
        ],
        networks=[
            {
                "id": "net001",
                "name": "bridge",
                "driver": "bridge",
                "scope": "local",
                "containers": "1",
            }
        ],
        volumes=[
            {
                "name": "data",
                "driver": "local",
                "mountpoint": "/var/lib/docker/volumes/data/_data",
                "size": "-",
                "created": "2026-09-01 10:00:00",
            }
        ],
        registries=[
            {"name": "https://index.docker.io/v1/", "kind": "default", "status": "configured"}
        ],
    )


def sample_telemetry() -> TelemetrySummary:
    """Return a representative Telemetry summary for dashboard tests."""
    return TelemetrySummary(
        counter_count=2,
        gauge_count=1,
        histogram_count=0,
        counters={"requests": 12.0, "errors": 1.0},
        gauges={"queue_depth": 3.0},
    )


def sample_valkey() -> ValkeySummary:
    """Return a representative Valkey summary for dashboard tests."""
    return ValkeySummary(
        connected=True,
        version="8.0.1",
        used_memory="12M",
        hit_ratio=94.5,
        connected_clients=3,
        key_count=120,
        total_commands=9001,
    )


SAMPLES: dict[str, Any] = {
    "k8s": sample_k8s,
    "docker": sample_docker,
    "telemetry": sample_telemetry,
    "valkey": sample_valkey,
}

_k8s = sample_k8s
_docker = sample_docker
_telemetry = sample_telemetry
_valkey = sample_valkey


async def _settle(pilot: Any, predicate: Callable[[], bool]) -> bool:
    """Pump the UI until a predicate holds, so tests do not depend on a fixed sleep."""
    deadline = time.monotonic() + THREAD_HANDOFF_BOUND_SECONDS
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        await pilot.pause(POLL_INTERVAL_SECONDS)
    return True


async def _stream_into(pilot: Any, pane: LogPane, lines: list[str]) -> None:
    """Stream a finite list of lines into a pane and wait for it to drain."""
    pane.start_stream(lambda: iter(lines))
    await _settle(pilot, lambda: pane.buffer.total_appended >= len(lines))
    await pilot.pause()


def _stream_ended(pane: LogPane) -> Callable[[], bool]:
    """A predicate that holds once the pane's current stream has ended."""
    reader = pane._producer
    consumers = [
        worker
        for worker in pane.app.workers
        if worker.node is pane and worker.group == "log-stream"
    ]
    assert reader is not None
    assert len(consumers) == 1
    return lambda: not reader.is_alive() and consumers[0].is_finished


async def _loaded(pilot: Any, app: DashboardApp) -> None:
    """Wait until every refresh worker has handed its snapshot to the UI and it is drawn."""
    await app.workers.wait_for_complete()
    await pilot.pause()
    await pilot.pause()


async def _refresh(pilot: Any, app: DashboardApp) -> None:
    """Run one full refresh, as the timer does, and wait for it to be drawn."""
    app.action_refresh_data()
    await _loaded(pilot, app)
