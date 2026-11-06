"""Tests for the internal network provisioning of `DockerEngineService`.

The service runs over `docker_daemon`, the in-memory engine of
`tests/support/fakes/docker_engine.py` (#1316).
"""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
)
from devops_cli.docker.engine import (
    get_engine,
)
from tests.support.fakes.docker_engine import DockerEngineFake


def test_ensure_internal_network_accepts_conforming_network(
    docker_daemon: DockerEngineFake,
) -> None:
    """An existing internal bridge network is accepted without being recreated."""
    docker_daemon.add_network(CONST_SANDBOX_DOCKER_INTERNAL_NET, internal=True)

    assert (
        get_engine().ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET),
        "networks.create" in docker_daemon.call_names(),
    ) == (True, False)


def test_ensure_internal_network_recreates_drifted_network(docker_daemon: DockerEngineFake) -> None:
    """A network that lost its internal (egress-denied) flag is removed and recreated."""
    docker_daemon.add_network(CONST_SANDBOX_DOCKER_INTERNAL_NET, internal=False)

    ensured = get_engine().ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET)

    assert (
        ensured,
        [call.name for call in docker_daemon.calls if call.name.startswith("network")],
        docker_daemon.calls[-1].kwargs,
        docker_daemon.find_network(CONST_SANDBOX_DOCKER_INTERNAL_NET)["Internal"],
    ) == (
        True,
        ["networks.get", "network.remove", "networks.create"],
        {"driver": "bridge", "internal": True},
        True,
    )


def test_ensure_internal_network_reports_creation_failure(docker_daemon: DockerEngineFake) -> None:
    """A refused network creation reports failure rather than raising."""
    docker_daemon.fail("networks.create", RuntimeError("permission denied"))

    assert get_engine().ensure_internal_network("net") is False


def test_ensure_internal_network_handles_unavailable_daemon(
    docker_daemon: DockerEngineFake,
) -> None:
    """An unreachable daemon reports network provisioning failure without raising."""
    docker_daemon.unreachable = True

    assert get_engine().ensure_internal_network("net") is False
