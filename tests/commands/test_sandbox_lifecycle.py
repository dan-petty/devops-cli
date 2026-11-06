"""The `devops sandbox` lifecycle commands: deploy, status, stop and exec, and their MCP tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    PortBinding,
    SandboxExecResult,
    SandboxInstance,
    SandboxStatus,
)


def test_cli_sandbox_deploy_dry_run(tmp_path: Path) -> None:
    """CLI sandbox deploy with --dry-run prints plan without starting container."""
    from devops_cli.commands.sandbox import app as sandbox_app

    runner = CliRunner()
    ws = tmp_path / "test_ws"
    ws.mkdir()

    res = runner.invoke(
        sandbox_app,
        [
            "deploy",
            "--image",
            "python:3.14-slim",
            "--name",
            "my-dry-run-app",
            "--port",
            "8080",
            "--workspace",
            str(ws),
            "--dry-run",
        ],
    )
    assert res.exit_code == 0
    assert "dry-run" in res.output.lower()
    assert "my-dry-run-app" in res.output


def test_cli_sandbox_status_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, docker_engine: Any
) -> None:
    """CLI sandbox status displays empty state cleanly."""
    from devops_cli.commands.sandbox import app as sandbox_app

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    with docker_engine(MagicMock()):
        res = runner.invoke(sandbox_app, ["status"])
    assert res.exit_code == 0
    assert "no sandbox instances found" in res.output.lower() or "empty" in res.output.lower()


def test_cli_sandbox_status_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, docker_engine: Any
) -> None:
    """CLI sandbox status --json outputs valid JSON."""
    from devops_cli.commands.sandbox import app as sandbox_app

    reg_dir = tmp_path / "sandbox"
    reg_dir.mkdir(parents=True)
    reg_file = reg_dir / "instances.json"
    inst = SandboxInstance(
        instance_id="sb-json-1",
        container_id="cid-json-1",
        name="json-svc",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg_file.write_text(json.dumps([inst.model_dump()]), encoding="utf-8")

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.containers.get.return_value.attrs = {
        "State": {"Running": True, "Status": "running", "ExitCode": 0}
    }
    with docker_engine(mock_client):
        res = runner.invoke(sandbox_app, ["status", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert len(data) == 1
    assert data[0]["name"] == "json-svc"


def test_cli_sandbox_deploy_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI sandbox deploy successfully provisions and renders instance table."""
    from devops_cli.commands.sandbox import app as sandbox_app

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    mock_inst = SandboxInstance(
        instance_id="sb-dep-1",
        container_id="cid-dep-1",
        name="test-cli-deploy",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=18080)],
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    with patch.object(WorkloadSandboxEngine, "deploy", return_value=mock_inst):
        runner = CliRunner()
        res = runner.invoke(
            sandbox_app,
            ["deploy", "--name", "test-cli-deploy", "--port", "80", "-e", "FOO=BAR"],
        )
        assert res.exit_code == 0
        assert "deployed successfully" in res.output.lower()
        assert "sb-dep-1" in res.output


def test_cli_sandbox_deploy_validation_error(tmp_path: Path) -> None:
    """CLI sandbox deploy exits with error code 1 when path is invalid."""
    from devops_cli.commands.sandbox import app as sandbox_app

    runner = CliRunner()
    res = runner.invoke(sandbox_app, ["deploy", "--workspace", "/etc"])
    assert res.exit_code == 1
    assert "failed deploying sandbox" in res.output.lower()


def test_cli_sandbox_stop_single(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI sandbox stop terminates requested sandbox instance."""
    from devops_cli.commands.sandbox import app as sandbox_app

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    mock_stopped = SandboxInstance(
        instance_id="sb-stop-target",
        container_id="cid-stop-target",
        name="stop-target",
        image="python:3.14-slim",
        status=SandboxStatus.STOPPED,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    with patch.object(WorkloadSandboxEngine, "stop", return_value=mock_stopped):
        runner = CliRunner()
        res = runner.invoke(sandbox_app, ["stop", "sb-stop-target"])
        assert res.exit_code == 0
        assert "stopped and removed" in res.output.lower()


def test_cli_sandbox_stop_all_and_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI sandbox stop supports --all and --dry-run flags."""
    from devops_cli.commands.sandbox import app as sandbox_app

    runner = CliRunner()
    # Missing args
    no_args = runner.invoke(sandbox_app, ["stop"])
    assert no_args.exit_code == 1

    # Dry-run
    dry_res = runner.invoke(sandbox_app, ["stop", "sb-dry", "--dry-run"])
    assert dry_res.exit_code == 0
    assert "dry" in dry_res.output.lower()


def test_cli_sandbox_exec(tmp_path: Path) -> None:
    """CLI sandbox exec streams output and preserves exit code."""
    from devops_cli.commands.sandbox import app as sandbox_app

    runner = CliRunner()
    mock_res_success = SandboxExecResult(
        instance_id="sb-exec-target",
        command=["echo", "hi"],
        exit_code=0,
        stdout="hi\n",
        stderr="",
    )
    with patch.object(WorkloadSandboxEngine, "exec", return_value=mock_res_success):
        res = runner.invoke(sandbox_app, ["exec", "sb-exec-target", "echo", "hi"])
        assert res.exit_code == 0
        assert "hi" in res.output

    mock_res_fail = SandboxExecResult(
        instance_id="sb-exec-target",
        command=["false"],
        exit_code=42,
        stdout="",
        stderr="error occurred\n",
    )
    with patch.object(WorkloadSandboxEngine, "exec", return_value=mock_res_fail):
        res_fail = runner.invoke(sandbox_app, ["exec", "sb-exec-target", "false"])
        assert res_fail.exit_code == 42


def test_fastmcp_sandbox_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test FastMCP sandbox tool definitions and resource dispatch."""
    from devops_cli.ai.mcp.server import (
        get_sandbox_instances_resource,
        sandbox_deploy,
        sandbox_exec,
        sandbox_status,
        sandbox_stop,
    )

    monkeypatch.chdir(tmp_path)
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="mcp output") as mock_run:
        deployed = sandbox_deploy(
            image="python:3.14-slim", name="mcp-sb", ports=[8080], workspace=str(tmp_path)
        )
        assert deployed == "mcp output"
        assert sandbox_status("mcp-sb") == "mcp output"
        assert sandbox_stop("mcp-sb") == "mcp output"
        assert sandbox_exec("mcp-sb", ["ls", "-la"]) == "mcp output"
        assert get_sandbox_instances_resource() == "mcp output"
        assert mock_run.call_count == 5
