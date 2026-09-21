"""Unit tests for the isolated Dockerized workload sandbox environment."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.commands.test_cmd import app as cli_test_app
from devops_cli.config.defaults import DEFAULT_SANDBOX_PIDS_LIMIT
from devops_cli.docker.sandbox import (
    WorkloadSandboxConfig,
    WorkloadSandboxRunner,
)
from devops_cli.exceptions.docker import DockerSandboxError

runner = CliRunner()


def test_sandbox_config_defaults(tmp_path: Path) -> None:
    """Test WorkloadSandboxConfig default values and volume mapping."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["pytest", "-v"],
    )
    assert cfg.image == "python:3.14-slim"
    assert cfg.memory_limit == "2g"
    assert cfg.cpu_limit == 2.0
    assert cfg.network_mode == "none"
    assert cfg.rootless is True
    assert cfg.read_only is True


def test_sandbox_runner_dry_run(tmp_path: Path) -> None:
    """Test WorkloadSandboxRunner in dry run mode without starting Docker."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["echo", "hello"],
        memory_limit="1g",
        network_mode="none",
    )
    sandbox = WorkloadSandboxRunner(cfg)
    dry = sandbox.build_dry_run_details()

    assert dry["image"] == "python:3.14-slim"
    assert dry["command"] == ["echo", "hello"]
    assert dry["memory_limit"] == "1g"
    assert dry["network_mode"] == "none"


def test_sandbox_runner_docker_execution_success(tmp_path: Path, docker_engine: Any) -> None:
    """Test running a sandboxed command successfully using Docker SDK."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["python3", "-c", "print('sandbox-ok')"],
    )
    sandbox = WorkloadSandboxRunner(cfg)

    mock_container = MagicMock()
    mock_container.id = "c123456789"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.side_effect = [b"sandbox-ok\n", b""]

    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with docker_engine(mock_client):
        res = sandbox.run()
        assert res.exit_code == 0
        assert "sandbox-ok" in res.stdout
        assert mock_container.start.called
        mock_client.api.remove_container.assert_called_once_with("c123456789", force=True)
        create_kwargs = mock_client.containers.create.call_args.kwargs
        assert create_kwargs.get("cap_drop") == ["ALL"]
        assert create_kwargs.get("security_opt") == ["no-new-privileges:true"]
        assert create_kwargs.get("pids_limit") == 256


def test_sandbox_runner_docker_execution_failure(tmp_path: Path, docker_engine: Any) -> None:
    """Test handling container execution failure and cleanup."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["exit", "1"],
    )
    sandbox = WorkloadSandboxRunner(cfg)

    mock_container = MagicMock()
    mock_container.id = "c987654321"
    mock_container.wait.return_value = {"StatusCode": 1}
    mock_container.logs.side_effect = [b"", b"Error occurred"]

    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with docker_engine(mock_client):
        res = sandbox.run()
        assert res.exit_code == 1
        assert "Error occurred" in res.stderr
        mock_client.api.remove_container.assert_called_once_with("c987654321", force=True)


def test_cli_test_sandbox_dry_run(tmp_path: Path) -> None:
    """Test devops test sandbox CLI subcommand with dry-run."""
    res = runner.invoke(
        cli_test_app,
        ["sandbox", "--dry-run", "--image", "alpine:latest", "echo", "test"],
    )
    assert res.exit_code == 0
    assert "echo" in res.output
    assert "alpine:latest" in res.output


def test_cli_test_sandbox_whitelist_url_with_path() -> None:
    """Test devops test sandbox accepts valid whitelist URLs with paths."""
    res = runner.invoke(
        cli_test_app,
        [
            "sandbox",
            "--dry-run",
            "--network-mode",
            "public_whitelist",
            "--public-whitelist",
            "https://example.com/path",
            "echo",
            "test",
        ],
    )
    assert res.exit_code == 0
    assert "echo" in res.output


def test_cli_docker_sandbox_dry_run(tmp_path: Path) -> None:
    """Test devops docker sandbox CLI subcommand with dry-run."""
    res = runner.invoke(
        docker_app,
        ["sandbox", "--dry-run", "pytest", "tests/unit"],
    )
    assert res.exit_code == 0
    assert "pytest" in res.output


def test_sandbox_runner_env_and_hardening_propagation(tmp_path: Path, docker_engine: Any) -> None:
    """Config env and container hardening reach the Engine API creation payload."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["python3", "-c", "print('hello')"],
        env={"TEST_VAR": "custom_val", "API_KEY": "secret123"},
    )
    sandbox = WorkloadSandboxRunner(cfg)

    mock_container = MagicMock()
    mock_container.id = "c111222333"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.side_effect = [b"hello", b""]
    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with docker_engine(mock_client):
        res = sandbox.run()

    create_kwargs = mock_client.containers.create.call_args.kwargs
    assert res.exit_code == 0
    assert (
        create_kwargs["environment"],
        create_kwargs["cap_drop"],
        create_kwargs["security_opt"],
        create_kwargs["pids_limit"],
        create_kwargs["network_mode"],
    ) == (
        {"TEST_VAR": "custom_val", "API_KEY": "secret123"},
        ["ALL"],
        ["no-new-privileges:true"],
        DEFAULT_SANDBOX_PIDS_LIMIT,
        "none",
    )


def test_workload_sandbox_runner_exclude_home_dir(tmp_path: Path) -> None:
    """Verify WorkloadSandboxRunner enforces exclude_home_dir preference."""
    cfg_home = WorkloadSandboxConfig(workspace_dir=Path.home(), command=["echo", "hi"])
    runner_default = WorkloadSandboxRunner(cfg_home)
    assert runner_default.exclude_home_dir is True
    with pytest.raises(DockerSandboxError, match="home directory"):
        runner_default.run()

    cfg_subhome = WorkloadSandboxConfig(
        workspace_dir=Path.home() / "some_nested_dir",
        command=["echo", "hi"],
    )
    runner_sub = WorkloadSandboxRunner(cfg_subhome)
    with pytest.raises(DockerSandboxError, match="home directory"):
        runner_sub.run()

    # When exclude_home_dir is explicitly disabled:
    runner_allow = WorkloadSandboxRunner(cfg_home, exclude_home_dir=False)
    assert runner_allow.exclude_home_dir is False
    # Home root is still forbidden
    with pytest.raises(DockerSandboxError, match="home directory"):
        runner_allow.run()
