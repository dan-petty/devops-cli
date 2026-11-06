"""Tests for the BuildKit layer cache introspection and the prune calls of `DockerEngineService`.

The service runs over `docker_daemon`, the in-memory engine of
`tests/support/fakes/docker_engine.py` (#1316).
"""

from __future__ import annotations

import pytest

from devops_cli.docker.engine import (
    build_cache_report,
    get_engine,
)
from devops_cli.exceptions.docker import DockerEngineError
from tests.support.fakes.docker_engine import DockerEngineFake

_CACHE_ENTRIES = [
    {
        "ID": "cache-a",
        "Type": "regular",
        "Description": "RUN uv sync",
        "InUse": True,
        "Shared": True,
        "Size": 300,
        "UsageCount": 4,
        "CreatedAt": "2026-09-20T10:00:00Z",
        "LastUsedAt": "2026-09-21T09:00:00Z",
    },
    {
        "ID": "cache-b",
        "Type": "source.local",
        "Description": "local source",
        "InUse": False,
        "Shared": False,
        "Size": 100,
        "UsageCount": 0,
        "CreatedAt": "2026-09-19T10:00:00Z",
    },
]


def test_build_cache_report_aggregates_reuse() -> None:
    """Cache records aggregate into totals, reclaimable bytes, and a reuse ratio."""
    report = build_cache_report(_CACHE_ENTRIES)

    assert (
        report.total_bytes,
        report.reclaimable_bytes,
        report.in_use_count,
        report.shared_count,
        report.reuse_ratio,
        report.records[1].last_used_at,
    ) == (400, 100, 1, 1, 0.75, None)


def test_build_cache_report_handles_empty_cache() -> None:
    """An empty build cache reports zeroed totals without dividing by zero."""
    report = build_cache_report([])
    assert (report.total_bytes, report.reuse_ratio, report.records) == (0, 0.0, [])


def test_build_cache_report_tolerates_unknown_record_type() -> None:
    """A cache record class outside the known BuildKit vertex set is still projected."""
    report = build_cache_report([{"ID": "x", "Type": "future.kind", "Size": 10}])
    assert report.records[0].cache_type == "future.kind"


def test_engine_build_cache_reads_disk_usage(docker_daemon: DockerEngineFake) -> None:
    """The build cache report is sourced from the Engine API disk-usage endpoint."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]
    engine = get_engine()

    report = engine.build_cache()
    engine.build_cache()

    # The second call is served from the response cache.
    assert (report.total_bytes, docker_daemon.call_names().count("df")) == (400, 1)


def test_engine_disk_usage_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A failing disk-usage query surfaces as a typed engine error."""
    docker_daemon.fail("df", RuntimeError("endpoint unavailable"))

    with pytest.raises(DockerEngineError, match="Engine disk usage query failed"):
        get_engine().disk_usage()


def test_prune_build_cache_invalidates_cached_usage(docker_daemon: DockerEngineFake) -> None:
    """Pruning removes the unused records, reports their bytes, and invalidates the memoised
    disk-usage response."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]
    engine = get_engine()

    engine.build_cache()
    reclaimed = engine.prune_build_cache()
    after = engine.build_cache()

    assert (
        reclaimed,
        [record.cache_id for record in after.records],
        docker_daemon.call_names().count("df"),
    ) == (100, ["cache-a"], 2)


def test_prune_build_cache_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A refused prune surfaces as a typed engine error."""
    docker_daemon.fail("api.prune_builds", RuntimeError("prune unsupported"))

    with pytest.raises(DockerEngineError, match="Build cache prune failed"):
        get_engine().prune_build_cache()


def test_engine_prune_calls_collections_in_order(docker_daemon: DockerEngineFake) -> None:
    """DockerEngineService.prune calls containers, networks, and images in order."""
    get_engine().prune()

    assert [name for name in docker_daemon.call_names() if name.endswith(".prune")] == [
        "containers.prune",
        "networks.prune",
        "images.prune",
    ]


def test_engine_prune_with_volumes(docker_daemon: DockerEngineFake) -> None:
    """DockerEngineService.prune with volumes=True calls volumes.prune."""
    get_engine().prune(volumes=True)

    assert [name for name in docker_daemon.call_names() if name.endswith(".prune")] == [
        "containers.prune",
        "networks.prune",
        "images.prune",
        "volumes.prune",
    ]


def test_engine_prune_reclaimed_bytes_sum(docker_daemon: DockerEngineFake) -> None:
    """DockerEngineService.prune sums SpaceReclaimed across the prunes, and a volume prune adds
    the anonymous volumes."""
    docker_daemon.add_container("old", running=False, size=500)
    docker_daemon.add_image(size=300)
    docker_daemon.add_volume("anonymous", anonymous=True, size=200)
    engine = get_engine()

    assert (engine.prune(), engine.prune(volumes=True)) == (800, 200)


def test_engine_prune_invalidates_disk_usage_cache(docker_daemon: DockerEngineFake) -> None:
    """Pruning invalidates the memoised disk-usage response."""
    engine = get_engine()
    engine.build_cache()
    engine.prune()
    engine.build_cache()

    assert docker_daemon.call_names().count("df") == 2


def test_engine_prune_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A collection prune failure surfaces as a typed DockerEngineError."""
    from docker.errors import APIError

    docker_daemon.fail("containers.prune", APIError("daemon error"))

    with pytest.raises(DockerEngineError, match="daemon error"):
        get_engine().prune()
