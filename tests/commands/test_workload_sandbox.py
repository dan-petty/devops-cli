"""Tests for `devops test sandbox` and `devops docker sandbox`.

The commands run through `cli`, over `docker_daemon`, the in-memory Docker engine of
`tests/support/fakes/docker_engine.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.docker_engine import DockerEngineFake


@pytest.fixture(autouse=True)
def _every_name_is_public(dns: DnsFake) -> None:
    """Resolve every external name to one public address, as the whitelist checks need."""
    dns.answer_every_name()


def _created(engine: DockerEngineFake) -> dict[str, Any]:
    """The arguments of the one container creation that reached the engine."""
    (create,) = [call for call in engine.calls if call.name == "containers.create"]
    return {"image": create.args[0], **create.kwargs}


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


@pytest.mark.parametrize("flag_first", [True, False])
def test_cli_test_sandbox_dry_run_lists_the_docker_requests(
    tmp_path: Path, cli: Callable[..., Any], docker_daemon: DockerEngineFake, flag_first: bool
) -> None:
    """A dry run builds no Docker client and lists the five engine requests (#2260)."""
    argv = ["test", "sandbox", "--workspace", str(tmp_path), "--image", "alpine:latest"]
    argv = ["--dry-run", *argv] if flag_first else [*argv, "--dry-run"]

    res = cli([*argv, "--", "echo", "test"])

    assert res.exit_code == 0, res.output
    assert (docker_daemon.factory_params, docker_daemon.calls) == ([], [])
    assert _plan_lines(res.output) == [
        "DOCKER POST /containers/create",
        "DOCKER POST /containers/<container-id>/start",
        "DOCKER POST /containers/<container-id>/wait",
        "DOCKER GET /containers/<container-id>/logs",
        "DOCKER DELETE /containers/<container-id>",
    ]
    body = json.loads(res.output.split("POST /containers/create\n", 1)[1].splitlines()[0])
    sandbox = WorkloadSandboxRunner(
        WorkloadSandboxConfig(workspace_dir=tmp_path, command=["echo", "test"], read_only=False)
    )
    assert body["image"] == "alpine:latest"
    assert body["command"] == ["echo", "test"]
    assert body["network_mode"] == "none"
    assert body["declared_controls"] == sandbox.declared_controls()


def test_cli_test_sandbox_runs_the_create_of_its_plan(
    tmp_path: Path, cli: Callable[..., Any], docker_daemon: DockerEngineFake
) -> None:
    """The real run creates the container with the image, command and network of the plan."""
    argv = ["test", "sandbox", "--workspace", str(tmp_path), "--image", "alpine:latest"]
    planned = cli([*argv, "--dry-run", "--", "echo", "test"]).output
    body = json.loads(planned.split("POST /containers/create\n", 1)[1].splitlines()[0])
    docker_daemon.script_every_run(stdout=b"test\n")

    result = cli([*argv, "--", "echo", "test"])

    assert result.exit_code == 0, result.output
    kwargs = _created(docker_daemon)
    assert (kwargs["image"], kwargs["command"], kwargs.get("network_mode")) == (
        body["image"],
        body["command"],
        body["network_mode"],
    )


def test_cli_test_sandbox_whitelist_url_with_path(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Test devops test sandbox accepts valid whitelist URLs with paths."""
    res = cli(
        "test",
        "sandbox",
        "--dry-run",
        "--workspace",
        str(tmp_path),
        "--network-mode",
        "public_whitelist",
        "--public-whitelist",
        "https://example.com/path",
        "echo",
        "test",
    )
    assert (res.exit_code, "echo" in res.output) == (0, True)


def test_cli_docker_sandbox_dry_run(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Test devops docker sandbox CLI subcommand with dry-run."""
    res = cli(
        "docker", "sandbox", "--dry-run", "--workspace", str(tmp_path), "pytest", "tests/unit"
    )
    assert (res.exit_code, "pytest" in res.output) == (0, True)
