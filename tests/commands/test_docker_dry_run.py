"""Tests for dry-run request plans and classifications across 9 docker commands.

Issue #2251: The dry-run rule (#412) states that a dry run makes zero external requests and
returns the requests that the real run would make.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.docker import (
    build as docker_build,
)
from devops_cli.commands.docker import (
    build_cache as docker_cache,
)
from devops_cli.commands.docker import (
    docker_sandbox,
    docker_sign,
    docker_verify,
)
from devops_cli.commands.docker import (
    list_images as docker_images,
)
from devops_cli.commands.docker import (
    prune as docker_prune,
)
from devops_cli.commands.docker import (
    push as docker_push,
)
from devops_cli.commands.docker import (
    stats as docker_stats,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

DOCKER_REQUEST_PLAN_COMMANDS = [
    ("docker images", docker_images, ["docker", "images", "--dry-run"]),
    ("docker build", docker_build, ["docker", "build", ".", "--dry-run"]),
    ("docker push", docker_push, ["docker", "push", "example.com/org/repo:1.0", "--dry-run"]),
    ("docker prune", docker_prune, ["docker", "prune", "--force", "--dry-run"]),
    ("docker stats", docker_stats, ["docker", "stats", "--dry-run"]),
    ("docker cache", docker_cache, ["docker", "cache", "--dry-run"]),
    ("docker sandbox", docker_sandbox, ["docker", "sandbox", "echo", "hello", "--dry-run"]),
    ("docker sign", docker_sign, ["docker", "sign", "example.com/org/repo:1.0", "--dry-run"]),
    ("docker verify", docker_verify, ["docker", "verify", "example.com/org/repo:1.0", "--dry-run"]),
]


@pytest.fixture
def block_docker_and_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no Docker client or subprocess call is made during dry run."""

    def _fail_engine(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Docker engine accessed during dry-run: {args} {kwargs}")

    def _fail_subprocess(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Subprocess call attempted during dry-run: {args} {kwargs}")

    monkeypatch.setattr("devops_cli.commands.docker._engine", _fail_engine)
    monkeypatch.setattr("subprocess.run", _fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", _fail_subprocess)


@pytest.mark.parametrize("name,callback,_argv", DOCKER_REQUEST_PLAN_COMMANDS)
def test_docker_commands_classified_request_plan(
    name: str,
    callback: Any,
    _argv: list[str],
) -> None:
    """Criterion 1: Every docker command carries the request-plan classification."""
    assert get_dry_run_class(callback) == "request-plan", (
        f"Command '{name}' must have dry_run_class 'request-plan'"
    )


@pytest.mark.usefixtures("block_docker_and_subprocesses")
@pytest.mark.parametrize("name,_callback,argv", DOCKER_REQUEST_PLAN_COMMANDS)
def test_docker_dry_run_makes_no_external_requests(
    name: str,
    _callback: Any,
    argv: list[str],
    tmp_path: Path,
) -> None:
    """Criterion 3: Dry run makes zero external requests and returns exit code 0."""
    effective_argv = (
        ["docker", "sandbox", "--workspace", str(tmp_path), "echo", "hello", "--dry-run"]
        if name == "docker sandbox"
        else argv
    )
    result = runner.invoke(app, effective_argv)
    assert result.exit_code == 0, f"Command '{name}' dry-run failed:\n{result.output}"
    assert "Planned requests for" in result.output, (
        f"Command '{name}' output must contain 'Planned requests for':\n{result.output}"
    )


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_images_plan_content() -> None:
    """Verify docker images dry run shows the planned engine request."""
    result = runner.invoke(app, ["docker", "images", "--name", "alpine", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER GET /images/json" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_build_plan_content() -> None:
    """Verify docker build dry run shows planned build request."""
    result = runner.invoke(
        app, ["docker", "build", ".", "--tag", "my-app:1.0", "--no-cache", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "DOCKER POST /build" in result.output
    assert "my-app:1.0" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_push_plan_content() -> None:
    """Verify docker push dry run shows planned image push request."""
    result = runner.invoke(app, ["docker", "push", "example.com/test:latest", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER POST /images/example.com/test:latest/push" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_prune_plan_content() -> None:
    """Verify docker prune dry run shows planned prune requests for containers, images, networks, and volumes."""
    result = runner.invoke(app, ["docker", "prune", "--volumes", "--force", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER POST /containers/prune" in result.output
    assert "DOCKER POST /images/prune" in result.output
    assert "DOCKER POST /networks/prune" in result.output
    assert "DOCKER POST /volumes/prune" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_stats_plan_content() -> None:
    """Verify docker stats dry run shows planned stats request."""
    result = runner.invoke(app, ["docker", "stats", "--name", "web", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER GET /containers/json" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_cache_plan_content() -> None:
    """Verify docker cache dry run shows planned system df and prune requests."""
    result = runner.invoke(app, ["docker", "cache", "--prune", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER GET /system/df" in result.output
    assert "DOCKER POST /build/prune" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_sandbox_plan_content(tmp_path: Path) -> None:
    """Verify docker sandbox dry run shows planned container lifecycle requests."""
    result = runner.invoke(
        app, ["docker", "sandbox", "--workspace", str(tmp_path), "echo", "hello", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "DOCKER POST /containers/create" in result.output
    assert "DOCKER POST /containers/<container-id>/start" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_sign_plan_content() -> None:
    """Verify docker sign dry run shows planned cosign sign request."""
    result = runner.invoke(
        app, ["docker", "sign", "example.com/test:latest", "--key", "cosign.key", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "cosign sign" in result.output


@pytest.mark.usefixtures("block_docker_and_subprocesses")
def test_docker_verify_plan_content() -> None:
    """Verify docker verify dry run shows planned cosign verify request."""
    result = runner.invoke(
        app, ["docker", "verify", "example.com/test:latest", "--key", "cosign.pub", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "cosign verify" in result.output
