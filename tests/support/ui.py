"""Shared helpers, sample data and fixtures for dashboard UI tests."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    DockerSummary,
    TelemetrySummary,
    ValkeySummary,
)
from devops_cli.ui.widgets import LogPane
from tests.support.waits import POLL_INTERVAL_SECONDS, THREAD_HANDOFF_BOUND_SECONDS


def _containers(count: int) -> DockerSummary:
    """Construct a DockerSummary holding count containers."""
    return DockerSummary(
        connected=True,
        containers=[
            {"id": f"c{index:05d}", "name": f"app-{index}", "image": "app:1", "status": "running"}
            for index in range(count)
        ],
    )


def _wide_containers(count: int) -> DockerSummary:
    """Containers whose names run past the table width."""
    long_name = "nested-" * 12
    return DockerSummary(
        connected=True,
        containers=[
            {
                "id": f"c{index:05d}",
                "name": f"{long_name}app-{index}",
                "image": f"{long_name}image:1",
                "status": "running",
            }
            for index in range(count)
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
    "docker": sample_docker,
    "telemetry": sample_telemetry,
    "valkey": sample_valkey,
}

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
