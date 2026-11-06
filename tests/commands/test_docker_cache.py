"""Tests for `devops docker cache`.

The command runs through `cli`, over `docker_daemon`, the in-memory engine of
`tests/support/fakes/docker_engine.py` (#1316).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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


def test_cli_docker_cache_table(docker_daemon: DockerEngineFake, cli: Callable[..., Any]) -> None:
    """The cache command renders BuildKit records with a reuse summary."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]

    result = cli("docker", "cache")

    assert (result.exit_code, "cache-a" in result.output, "reclaimable" in result.output) == (
        0,
        True,
        True,
    )


def test_cli_docker_cache_json(docker_daemon: DockerEngineFake, cli: Callable[..., Any]) -> None:
    """The cache command emits the typed report as JSON on demand."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]

    result = cli("docker", "cache", "--json")

    assert (result.exit_code, '"reclaimable_bytes"' in result.output) == (0, True)


def test_cli_docker_cache_prune(docker_daemon: DockerEngineFake, cli: Callable[..., Any]) -> None:
    """The --prune flag reclaims unused records after reporting them."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]

    result = cli("docker", "cache", "--prune")

    assert (
        result.exit_code,
        "api.prune_builds" in docker_daemon.call_names(),
        [entry["ID"] for entry in docker_daemon.build_cache],
    ) == (0, True, ["cache-a"])


def test_cli_docker_cache_dry_run(cli: Callable[..., Any]) -> None:
    """The cache command supports dry-run inspection without contacting the daemon."""
    result = cli("docker", "cache", "--dry-run")
    assert result.exit_code == 0
    assert "DOCKER GET /system/df" in result.output


def test_cli_docker_cache_podman_engine(
    docker_daemon: DockerEngineFake, cli: Callable[..., Any]
) -> None:
    """The cache command on Podman informs user and exits 1 without prune_builds or df."""
    docker_daemon.set_podman()

    result = cli("docker", "cache")

    assert (
        result.exit_code,
        "Podman keeps no BuildKit cache; its build layers are images" in result.output,
        "df" in docker_daemon.call_names(),
        "api.prune_builds" in docker_daemon.call_names(),
    ) == (1, True, False, False)
