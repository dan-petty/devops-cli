"""A sandbox deploy pulls its image before it creates the container (#2554)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.defaults import DEFAULT_SANDBOX_IMAGE
from devops_cli.exceptions.sandbox import SandboxError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import SandboxDeployConfig, SandboxStatus
from devops_cli.sandbox.registry import SandboxRegistry
from tests.support.fakes.docker_engine import DockerEngineFake

_IMAGE_CALLS = ("images.get", "images.pull", "containers.create")


def _engine(tmp_path: Path) -> WorkloadSandboxEngine:
    return WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))


def _config(workspace: Path) -> SandboxDeployConfig:
    return SandboxDeployConfig(image=DEFAULT_SANDBOX_IMAGE, workspace_dir=workspace)


def _image_calls(fake: DockerEngineFake) -> list[str]:
    return [name for name in fake.call_names() if name in _IMAGE_CALLS]


def test_deploy_pulls_a_missing_image_before_it_creates_the_container(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    docker_daemon: DockerEngineFake,
) -> None:
    """A registry image that the engine lacks is pulled, and the sandbox then runs."""
    docker_daemon.publish_image(DEFAULT_SANDBOX_IMAGE)
    workspace = tmp_path_factory.mktemp("ws")

    instance = _engine(tmp_path).deploy(_config(workspace))

    assert (instance.status, _image_calls(docker_daemon)) == (
        SandboxStatus.RUNNING,
        ["images.get", "images.pull", "containers.create"],
    )


def test_deploy_makes_no_pull_for_a_local_image(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    docker_daemon: DockerEngineFake,
) -> None:
    """An image the engine already holds is looked up and used with no pull request."""
    docker_daemon.add_image(DEFAULT_SANDBOX_IMAGE)
    workspace = tmp_path_factory.mktemp("ws")

    instance = _engine(tmp_path).deploy(_config(workspace))

    assert (instance.status, _image_calls(docker_daemon)) == (
        SandboxStatus.RUNNING,
        ["images.get", "containers.create"],
    )


def test_a_refused_pull_names_the_image_and_leaves_no_instance(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    docker_daemon: DockerEngineFake,
) -> None:
    """A pull that no registry serves stops the deploy with the image and the reason."""
    workspace = tmp_path_factory.mktemp("ws")
    registry = SandboxRegistry(tmp_path / "reg.json")

    with pytest.raises(
        SandboxError,
        match=r"Image pull failed for python:3\.14-slim: .*pull access denied",
    ):
        WorkloadSandboxEngine(registry=registry).deploy(_config(workspace))

    assert (
        "containers.create" in docker_daemon.call_names(),
        registry.list_instances(),
    ) == (False, [])
