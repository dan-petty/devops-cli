"""A sandbox as `devops sandbox deploy` leaves it: in the registry, with its container in the Docker fake."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from devops_cli.sandbox.models import PortBinding, SandboxInstance, SandboxStatus
from devops_cli.sandbox.registry import SandboxRegistry
from tests.support.fakes.docker_engine import DockerEngineFake

CREATED_AT = "2026-09-12T12:00:00Z"


@pytest.fixture
def register_sandbox(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> Callable[..., SandboxInstance]:
    """Register a sandbox in the test's own registry, with a container for it in the Docker fake.

    The container is named after the instance. The sandbox runs unless `running` is false.
    `host_ports` become the published ports, each mapped to port 80 of the container.
    `log_frames` are the `(stream, bytes)` frames the container's log holds.
    """

    def register(
        instance_id: str = "sandbox-test-1",
        *,
        name: str = "api-svc",
        host_ports: Sequence[int] = (),
        running: bool = True,
        metadata: dict[str, str] | None = None,
        log_frames: Sequence[tuple[str, bytes]] | None = None,
        created_at: str = CREATED_AT,
    ) -> SandboxInstance:
        container_id = docker_daemon.add_container(instance_id, "alpine:3", running=running)
        if log_frames is not None:
            docker_daemon.script_run(instance_id, frames=log_frames)
        instance = SandboxInstance(
            instance_id=instance_id,
            container_id=container_id,
            name=name,
            image="alpine:3",
            status=SandboxStatus.RUNNING if running else SandboxStatus.STOPPED,
            port_bindings=[
                PortBinding(container_port=80, host_port=port, protocol="tcp")
                for port in host_ports
            ],
            workspace_dir=str(tmp_path / "workspace"),
            created_at=created_at,
            metadata=dict(metadata or {}),
        )
        SandboxRegistry().register_instance(instance)
        return instance

    return register
