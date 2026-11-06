"""The `devops sandbox` lifecycle commands: deploy, status, stop and exec, and their MCP tools."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import devops_cli.main  # noqa: F401  # loaded here, not in a test: MCP dispatches through it
from devops_cli.sandbox.models import SandboxInstance, SandboxStatus
from devops_cli.sandbox.registry import SandboxRegistry
from tests.support.fakes.docker_engine import DockerEngineFake

_IMAGE = "python:3.14-slim"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_cli_sandbox_deploy_dry_run(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """CLI sandbox deploy with --dry-run prints plan without starting container."""
    res = cli(
        "sandbox",
        "deploy",
        "--image",
        _IMAGE,
        "--name",
        "my-dry-run-app",
        "--port",
        "8080",
        "--workspace",
        _workspace(tmp_path),
        "--dry-run",
    )

    assert res.exit_code == 0
    assert "dry-run" in res.output.lower()
    assert "my-dry-run-app" in res.output


def test_cli_sandbox_status_empty(cli: Callable[..., Any], docker_daemon: DockerEngineFake) -> None:
    """CLI sandbox status displays empty state cleanly."""
    res = cli("sandbox", "status")

    assert res.exit_code == 0
    assert "no sandbox instances found" in res.output.lower() or "empty" in res.output.lower()


def test_cli_sandbox_status_json(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """CLI sandbox status --json outputs valid JSON."""
    register_sandbox("sb-json-1", name="json-svc")

    res = cli("sandbox", "status", "--json")

    assert res.exit_code == 0
    data = json.loads(res.output)
    assert [(item["instance_id"], item["name"], item["status"]) for item in data] == [
        ("sb-json-1", "json-svc", "running")
    ]


def test_cli_sandbox_deploy_success(
    tmp_path: Path, cli: Callable[..., Any], docker_daemon: DockerEngineFake
) -> None:
    """CLI sandbox deploy successfully provisions and renders instance table."""
    docker_daemon.add_image(_IMAGE)

    res = cli(
        "sandbox",
        "deploy",
        "--image",
        _IMAGE,
        "--name",
        "test-cli-deploy",
        "--port",
        "80",
        "--workspace",
        _workspace(tmp_path),
        "-e",
        "FOO=BAR",
    )

    deployed = SandboxRegistry().list_instances()
    assert res.exit_code == 0
    assert "deployed successfully" in res.output.lower()
    assert [(item.name, item.status) for item in deployed] == [
        ("test-cli-deploy", SandboxStatus.RUNNING)
    ]
    assert deployed[0].instance_id in res.output
    created = next(call for call in docker_daemon.calls if call.name == "containers.create")
    assert created.kwargs["environment"]["FOO"] == "BAR"


def test_cli_sandbox_deploy_validation_error(cli: Callable[..., Any]) -> None:
    """CLI sandbox deploy exits with error code 1 when path is invalid."""
    res = cli("sandbox", "deploy", "--workspace", "/etc")

    assert res.exit_code == 1
    assert "failed deploying sandbox" in res.output.lower()


def test_cli_sandbox_stop_single(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    docker_daemon: DockerEngineFake,
) -> None:
    """CLI sandbox stop terminates requested sandbox instance."""
    register_sandbox("sb-stop-target", name="stop-target")

    res = cli("sandbox", "stop", "sb-stop-target")

    assert res.exit_code == 0
    assert "stopped and removed" in res.output.lower()
    stored = SandboxRegistry().get_instance("sb-stop-target")
    assert stored is not None
    assert stored.status == SandboxStatus.STOPPED
    assert "api.stop" in docker_daemon.call_names()


def test_cli_sandbox_stop_without_an_instance_exits_1(cli: Callable[..., Any]) -> None:
    """CLI sandbox stop with no instance and no --all flag exits 1."""
    assert cli("sandbox", "stop").exit_code == 1


def test_cli_sandbox_stop_dry_run(cli: Callable[..., Any]) -> None:
    """CLI sandbox stop supports --dry-run."""
    dry_res = cli("sandbox", "stop", "sb-dry", "--dry-run")

    assert dry_res.exit_code == 0
    assert "dry" in dry_res.output.lower()


def test_cli_sandbox_exec(
    cli: Callable[..., Any],
    register_sandbox: Callable[..., SandboxInstance],
    docker_daemon: DockerEngineFake,
) -> None:
    """CLI sandbox exec streams output and preserves exit code."""
    register_sandbox("sb-exec-target", name="exec-target")
    docker_daemon.script_exec("sb-exec-target", ["echo", "hi"], exit_code=0, output=b"hi\n")
    docker_daemon.script_exec("sb-exec-target", ["false"], exit_code=42, output=b"error occurred\n")

    res = cli("sandbox", "exec", "sb-exec-target", "echo", "hi")
    res_fail = cli("sandbox", "exec", "sb-exec-target", "false")

    assert (res.exit_code, "hi" in res.output) == (0, True)
    assert res_fail.exit_code == 42


def test_fastmcp_sandbox_tools(
    tmp_path: Path, monkeypatch: Any, docker_daemon: DockerEngineFake
) -> None:
    """The FastMCP sandbox tools and resource run the lifecycle commands in process."""
    from devops_cli.ai.mcp.server import (
        get_sandbox_instances_resource,
        sandbox_deploy,
        sandbox_status,
        sandbox_stop,
    )

    monkeypatch.chdir(tmp_path)
    docker_daemon.add_image(_IMAGE)

    deployed = sandbox_deploy(
        image=_IMAGE, name="mcp-sb", ports=[8080], workspace=str(_workspace(tmp_path))
    )
    status = sandbox_status("mcp-sb")
    listed = json.loads(get_sandbox_instances_resource())
    stopped = sandbox_stop("mcp-sb")

    assert "deployed successfully" in deployed.lower()
    assert "mcp-sb" in status
    assert [item["name"] for item in listed] == ["mcp-sb"]
    assert "stopped and removed" in stopped.lower()
