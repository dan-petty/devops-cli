"""Unit tests for the isolated Dockerized workload sandbox environment."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.commands.test_cmd import app as cli_test_app
from devops_cli.docker.sandbox import (
    WorkloadSandboxConfig,
    WorkloadSandboxRunner,
)

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
    assert cfg.network_mode == "bridge"
    assert cfg.rootless is True
    assert cfg.read_only is False


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


def test_sandbox_runner_docker_execution_success(tmp_path: Path) -> None:
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

    with patch("devops_cli.docker.sandbox._get_docker_client", return_value=mock_client):
        res = sandbox.run()
        assert res.exit_code == 0
        assert "sandbox-ok" in res.stdout
        assert mock_container.start.called
        assert mock_container.remove.called


def test_sandbox_runner_docker_execution_failure(tmp_path: Path) -> None:
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

    with patch("devops_cli.docker.sandbox._get_docker_client", return_value=mock_client):
        res = sandbox.run()
        assert res.exit_code == 1
        assert "Error occurred" in res.stderr
        assert mock_container.remove.called


def test_cli_test_sandbox_dry_run(tmp_path: Path) -> None:
    """Test devops test sandbox CLI subcommand with dry-run."""
    res = runner.invoke(
        cli_test_app,
        ["sandbox", "--dry-run", "--image", "alpine:latest", "echo", "test"],
    )
    assert res.exit_code == 0
    assert "echo" in res.output
    assert "alpine:latest" in res.output


def test_cli_docker_sandbox_dry_run(tmp_path: Path) -> None:
    """Test devops docker sandbox CLI subcommand with dry-run."""
    res = runner.invoke(
        docker_app,
        ["sandbox", "--dry-run", "pytest", "tests/unit"],
    )
    assert res.exit_code == 0
    assert "pytest" in res.output


def test_sandbox_runner_subprocess_env_propagation(tmp_path: Path) -> None:
    """Test that WorkloadSandboxConfig.env is propagated as -e flags in subprocess fallback."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["python3", "-c", "print('hello')"],
        env={"TEST_VAR": "custom_val", "API_KEY": "secret123"},
    )
    sandbox = WorkloadSandboxRunner(cfg)

    with (
        patch("devops_cli.docker.sandbox._get_docker_client", return_value=None),
        patch("devops_cli.docker.sandbox.run_subprocess") as mock_subproc,
    ):
        mock_subproc.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
        res = sandbox.run()

        assert res.exit_code == 0
        cmd_args = mock_subproc.call_args[0][0]
        assert "-e" in cmd_args
        assert "TEST_VAR=custom_val" in cmd_args
        assert "API_KEY=secret123" in cmd_args
