"""Submodule-aligned test suite for workload sandbox lifecycle engine and CLI."""

from __future__ import annotations

import datetime
import json
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
    SandboxPortAllocationError,
    SandboxValidationError,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    PortBinding,
    SandboxDeployConfig,
    SandboxExecResult,
    SandboxInstance,
    SandboxStatus,
)
from devops_cli.sandbox.ports import (
    allocate_ports,
    find_available_port,
    is_port_available,
)
from devops_cli.sandbox.registry import SandboxRegistry

# ─────────────────────────────────────────────────────────────────────────────
# 1. Models & Port Allocation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_sandbox_models_serialization() -> None:
    """Test round-trip serialization of SandboxInstance and related models."""
    port_binding = PortBinding(container_port=8080, host_port=18080, protocol="tcp")
    instance = SandboxInstance(
        instance_id="sandbox-test-123456",
        container_id="cont-abc-123",
        name="test-web",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[port_binding],
        workspace_dir="/tmp/workspace",
        created_at="2026-09-11T20:00:00Z",
        uptime_seconds=120.5,
        metadata={"managed_by": "devops-cli"},
    )

    data = instance.model_dump()
    assert data["instance_id"] == "sandbox-test-123456"
    assert data["status"] == "running"
    assert len(data["port_bindings"]) == 1
    assert data["port_bindings"][0]["host_port"] == 18080

    restored = SandboxInstance.model_validate(data)
    assert restored.instance_id == instance.instance_id
    assert restored.port_bindings[0].container_port == 8080


def test_port_availability_check() -> None:
    """Test is_port_available helper on free and bound ports."""
    # Binding to a port to simulate in-use port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    bound_port = sock.getsockname()[1]

    try:
        assert not is_port_available(bound_port)
    finally:
        sock.close()

    # Free port should now be available (or another ephemeral port)
    assert is_port_available(bound_port)


def test_find_available_port_with_reserved_ports() -> None:
    """find_available_port respects reserved ports and bounded range."""
    reserved = {10000, 10001, 10002}
    port = find_available_port(reserved_ports=reserved, start=10000, end=10005)
    assert port not in reserved
    assert 10000 <= port <= 10005


def test_find_available_port_exhaustion_raises_error() -> None:
    """find_available_port raises SandboxPortAllocationError when range exhausted."""
    reserved = {10000, 10001}
    with pytest.raises(SandboxPortAllocationError, match="exhausted"):
        find_available_port(reserved_ports=reserved, start=10000, end=10001)


def test_allocate_ports_success() -> None:
    """allocate_ports assigns non-conflicting host ports for container ports."""
    bindings = allocate_ports([80, 443], reserved_ports={10000})
    assert len(bindings) == 2
    assert bindings[0].container_port == 80
    assert bindings[1].container_port == 443
    assert bindings[0].host_port != bindings[1].host_port
    assert bindings[0].host_port != 10000


# ─────────────────────────────────────────────────────────────────────────────
# 2. Registry Persistence Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_sandbox_registry_crud(tmp_path: Path) -> None:
    """Test registry CRUD operations and persistence across instances."""
    registry_file = tmp_path / "sandbox" / "instances.json"
    reg = SandboxRegistry(registry_file=registry_file)

    assert reg.list_instances() == []
    assert reg.get_allocated_host_ports() == set()

    inst = SandboxInstance(
        instance_id="sb-test-1",
        container_id="cid-1",
        name="svc-1",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=10080)],
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )

    reg.register_instance(inst)
    assert registry_file.exists()

    loaded = reg.get_instance("sb-test-1")
    assert loaded is not None
    assert loaded.name == "svc-1"
    assert reg.get_allocated_host_ports() == {10080}

    # Query by name
    by_name = reg.get_instance("svc-1")
    assert by_name is not None
    assert by_name.instance_id == "sb-test-1"

    # Update status
    updated = reg.update_instance_status("sb-test-1", SandboxStatus.STOPPED, uptime_seconds=42.0)
    assert updated.status == SandboxStatus.STOPPED
    assert updated.uptime_seconds == 42.0
    # Stopped instances do not reserve host ports
    assert reg.get_allocated_host_ports() == set()

    # Remove
    assert reg.remove_instance("sb-test-1") is True
    assert reg.get_instance("sb-test-1") is None
    assert reg.remove_instance("sb-test-1") is False


def test_sandbox_registry_corrupted_file_handling(tmp_path: Path) -> None:
    """Registry safely handles corrupted JSON files by returning empty list."""
    registry_file = tmp_path / "corrupted.json"
    registry_file.write_text("invalid json content! { [", encoding="utf-8")
    reg = SandboxRegistry(registry_file=registry_file)
    assert reg.list_instances() == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. Security Boundary Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_sandbox_workspace_validation_forbidden_roots(tmp_path: Path) -> None:
    """Engine rejects forbidden root paths, user home, and sensitive dirs."""
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))

    # Sensitive paths
    for forbidden in ["/", "/etc", "/usr", "/bin"]:
        cfg = SandboxDeployConfig(workspace_dir=Path(forbidden))
        with pytest.raises(SandboxValidationError, match=r"forbidden|symbolic link"):
            engine.validate_workspace_dir(cfg.workspace_dir)

    # Symlink workspace
    target = tmp_path / "real_dir"
    target.mkdir()
    symlink_dir = tmp_path / "symlink_dir"
    symlink_dir.symlink_to(target)

    cfg_symlink = SandboxDeployConfig(workspace_dir=symlink_dir)
    with pytest.raises(SandboxValidationError, match="symbolic link"):
        engine.validate_workspace_dir(cfg_symlink.workspace_dir)

    # docker.sock in path
    sock_path = tmp_path / "var" / "run" / "docker.sock"
    cfg_sock = SandboxDeployConfig(workspace_dir=sock_path)
    with pytest.raises(SandboxValidationError, match="Docker socket"):
        engine.validate_workspace_dir(cfg_sock.workspace_dir)

    # Sensitive subpath (.git, .ssh, .kube, .aws)
    git_path = tmp_path / ".git"
    git_path.mkdir()
    cfg_git = SandboxDeployConfig(workspace_dir=git_path)
    with pytest.raises(SandboxValidationError, match="credential or repository"):
        engine.validate_workspace_dir(cfg_git.workspace_dir)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Engine Deploy, Status, Stop, Exec Tests (Mocked Docker SDK & Fallback)
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_deploy_dry_run(tmp_path: Path) -> None:
    """Engine deploy in dry-run mode constructs instance without spawning container."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    cfg = SandboxDeployConfig(
        image="python:3.14-slim",
        name="test-dry-run",
        ports=[8000],
        workspace_dir=ws,
        env={"TEST_VAR": "true"},
    )

    instance = engine.deploy(cfg, dry_run=True)
    assert instance.instance_id.startswith("sandbox-")
    assert instance.status == SandboxStatus.PENDING
    assert len(instance.port_bindings) == 1
    assert instance.port_bindings[0].container_port == 8000
    # Dry run should not record in persistent registry
    assert reg.list_instances() == []


def test_engine_deploy_docker_sdk(tmp_path: Path) -> None:
    """Engine deploy provisions container with security opts and records to registry."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    mock_container = MagicMock()
    mock_container.id = "cont-sdk-1234567890"
    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client):
        cfg = SandboxDeployConfig(
            image="nginx:alpine",
            name="web-svc",
            ports=[80],
            workspace_dir=ws,
            memory_limit="1g",
            cpu_limit=1.5,
        )
        instance = engine.deploy(cfg)

        assert instance.container_id == "cont-sdk-1234567890"
        assert instance.status == SandboxStatus.RUNNING
        assert instance.name == "web-svc"
        mock_container.start.assert_called_once()

        # Check container creation kwargs for security settings
        create_kwargs = mock_client.containers.create.call_args[1]
        assert create_kwargs["cap_drop"] == ["ALL"]
        assert create_kwargs["security_opt"] == ["no-new-privileges:true"]
        assert create_kwargs["pids_limit"] == 256
        assert create_kwargs["read_only"] is True
        assert "/tmp" in create_kwargs["tmpfs"]
        # Explicit loopback binding
        assert create_kwargs["ports"]["80/tcp"][0] == "127.0.0.1"

        # Check registry persistence
        stored = reg.get_instance(instance.instance_id)
        assert stored is not None
        assert stored.status == SandboxStatus.RUNNING


def test_engine_status_reconciliation(tmp_path: Path) -> None:
    """Engine status reconciles live container state against Docker daemon."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    inst = SandboxInstance(
        instance_id="sb-live-1",
        container_id="cid-live-1",
        name="live-svc",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg.register_instance(inst)

    mock_container = MagicMock()
    mock_container.status = "running"
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client):
        statuses = engine.status("sb-live-1")
        assert len(statuses) == 1
        assert statuses[0].status == SandboxStatus.RUNNING

    # When container is exited
    mock_container.status = "exited"
    with patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client):
        statuses = engine.status("sb-live-1")
        assert statuses[0].status == SandboxStatus.STOPPED


def test_engine_stop(tmp_path: Path) -> None:
    """Engine stop gracefully terminates container and updates status."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    inst = SandboxInstance(
        instance_id="sb-stop-1",
        container_id="cid-stop-1",
        name="stop-svc",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg.register_instance(inst)

    mock_container = MagicMock()
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client):
        stopped = engine.stop("sb-stop-1", timeout=5)
        assert stopped.status == SandboxStatus.STOPPED
        mock_container.stop.assert_called_once_with(timeout=5)
        mock_container.remove.assert_called_once_with(force=True)

    # Stop non-existent instance raises SandboxNotFoundError
    with pytest.raises(SandboxNotFoundError):
        engine.stop("non-existent-instance")


def test_engine_exec(tmp_path: Path) -> None:
    """Engine exec executes commands inside running container."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    inst = SandboxInstance(
        instance_id="sb-exec-1",
        container_id="cid-exec-1",
        name="exec-svc",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg.register_instance(inst)

    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"hello from sandbox\n")
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client):
        res = engine.exec("sb-exec-1", ["echo", "hello"])
        assert res.exit_code == 0
        assert "hello from sandbox" in res.stdout


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLI Command Tests
# ─────────────────────────────────────────────────────────────────────────────


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


def test_cli_sandbox_status_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI sandbox status displays empty state cleanly."""
    from devops_cli.commands.sandbox import app as sandbox_app

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(sandbox_app, ["status"])
    assert res.exit_code == 0
    assert "no sandbox instances found" in res.output.lower() or "empty" in res.output.lower()


def test_cli_sandbox_status_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_fastmcp_sandbox_tools() -> None:
    """Test FastMCP sandbox tool definitions and resource dispatch."""
    from devops_cli.ai.mcp.server import (
        get_sandbox_instances_resource,
        sandbox_deploy,
        sandbox_exec,
        sandbox_status,
        sandbox_stop,
    )

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="mcp output") as mock_run:
        assert sandbox_deploy(image="python:3.14-slim", name="mcp-sb", ports=[8080]) == "mcp output"
        assert sandbox_status("mcp-sb") == "mcp output"
        assert sandbox_stop("mcp-sb") == "mcp output"
        assert sandbox_exec("mcp-sb", ["ls", "-la"]) == "mcp output"
        assert get_sandbox_instances_resource() == "mcp output"
        assert mock_run.call_count == 5


def test_exception_truncation() -> None:
    """Verify bounded string truncation in sandbox exceptions."""
    long_str = "x" * 500
    err = SandboxError("test error", instance_id=long_str, details={"key": long_str})
    assert len(err.details["instance_id"]) <= 256
    assert err.details["instance_id"].endswith("...")
    assert len(err.details["key"]) <= 256


def test_sandbox_workspace_validation_user_home(tmp_path: Path) -> None:
    """Workspace validation blocks mounting user home directory."""
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))
    with pytest.raises(SandboxValidationError, match="home directory"):
        engine.validate_workspace_dir(Path.home())


def test_ports_boundary_check() -> None:
    """is_port_available returns False on out-of-range ports."""
    assert is_port_available(0) is False
    assert is_port_available(70000) is False


def test_engine_deploy_subprocess_fallback(tmp_path: Path) -> None:
    """Engine deploy falls back to docker run subprocess when SDK fails."""
    import subprocess

    ws = tmp_path / "workspace"
    ws.mkdir()
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    cfg = SandboxDeployConfig(
        image="python:3.14-slim",
        name="subp-app",
        ports=[8080],
        workspace_dir=ws,
    )

    mock_proc = subprocess.CompletedProcess(
        args=["docker", "run"],
        returncode=0,
        stdout="cid-subp-123\n",
        stderr="",
    )

    with (
        patch(
            "devops_cli.sandbox.engine._get_docker_client", side_effect=RuntimeError("SDK offline")
        ),
        patch("devops_cli.sandbox.engine.run_subprocess", return_value=mock_proc) as mock_subp,
    ):
        inst = engine.deploy(cfg)
        assert inst.container_id == "cid-subp-123"
        assert inst.status == SandboxStatus.RUNNING
        cmd = mock_subp.call_args[0][0]
        assert any(arg.startswith("127.0.0.1:") for arg in cmd)


def test_registry_reserve_and_register_pending(tmp_path: Path) -> None:
    """Registry reserve_and_register_pending atomically assigns ports and saves pending instance."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    inst1, bindings1 = reg.reserve_and_register_pending(
        instance_id="sb-1",
        name="test-1",
        image="alpine",
        workspace_dir=str(tmp_path),
        requested_ports=[8080],
        now_str="2026-09-12T06:00:00Z",
    )
    assert inst1.status == SandboxStatus.PENDING
    assert len(bindings1) == 1
    port1 = bindings1[0].host_port

    # Second allocation must atomically recognize port1 as reserved
    inst2, bindings2 = reg.reserve_and_register_pending(
        instance_id="sb-2",
        name="test-2",
        image="alpine",
        workspace_dir=str(tmp_path),
        requested_ports=[8080],
        now_str="2026-09-12T06:00:00Z",
    )
    port2 = bindings2[0].host_port
    assert port1 != port2
    assert reg.get_allocated_host_ports() == {port1, port2}


def test_engine_status_not_found_and_client_error(tmp_path: Path) -> None:
    """Engine status raises SandboxNotFoundError for missing instance, handles SDK failure."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    with pytest.raises(SandboxNotFoundError):
        engine.status("non-existent-instance")

    inst = SandboxInstance(
        instance_id="sb-stat-err",
        container_id="cid-stat-err",
        name="stat-err",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg.register_instance(inst)

    with patch(
        "devops_cli.sandbox.engine._get_docker_client", side_effect=RuntimeError("Docker dead")
    ):
        statuses = engine.status()
        assert len(statuses) == 1
        assert statuses[0].status == SandboxStatus.RUNNING


def test_engine_stop_subprocess_fallback(tmp_path: Path) -> None:
    """Engine stop falls back to docker stop/rm subprocess when SDK fails."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    inst = SandboxInstance(
        instance_id="sb-stop-subp",
        container_id="cid-stop-subp",
        name="stop-subp",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg.register_instance(inst)

    with (
        patch("devops_cli.sandbox.engine._get_docker_client", side_effect=RuntimeError("SDK fail")),
        patch("devops_cli.sandbox.engine.run_subprocess") as mock_subp,
    ):
        stopped = engine.stop("sb-stop-subp", timeout=5)
        assert stopped.status == SandboxStatus.STOPPED
        assert mock_subp.call_count == 2


def test_engine_exec_non_running_and_fallback(tmp_path: Path) -> None:
    """Engine exec checks instance state and handles subprocess fallback."""
    import subprocess

    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    inst = SandboxInstance(
        instance_id="sb-exec-subp",
        container_id="cid-exec-subp",
        name="exec-subp",
        image="alpine:latest",
        status=SandboxStatus.STOPPED,
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )
    reg.register_instance(inst)

    # Calling exec on non-running sandbox raises SandboxError
    with pytest.raises(SandboxError, match="status is"):
        engine.exec("sb-exec-subp", ["ls"])

    # Set status to RUNNING and test subprocess fallback
    inst.status = SandboxStatus.RUNNING
    reg.register_instance(inst)

    mock_proc = subprocess.CompletedProcess(
        args=["docker", "exec"],
        returncode=0,
        stdout="fallback output\n",
        stderr="",
    )

    with (
        patch("devops_cli.sandbox.engine._get_docker_client", side_effect=RuntimeError("SDK fail")),
        patch("devops_cli.sandbox.engine.run_subprocess", return_value=mock_proc),
    ):
        res = engine.exec("sb-exec-subp", ["echo", "test"], workdir="/workspace")
        assert res.exit_code == 0
        assert "fallback output" in res.stdout


def test_sandbox_models_validation_rules() -> None:
    """Test model validation constraints: network mode, read_only, and port bounds."""
    from pydantic import ValidationError

    # Network mode host rejected
    with pytest.raises(ValidationError, match="Network mode 'host' violates sandbox"):
        SandboxDeployConfig(network_mode="host")

    # Network mode bridge and none accepted
    cfg_bridge = SandboxDeployConfig(network_mode="bridge")
    assert cfg_bridge.network_mode == "bridge"
    cfg_none = SandboxDeployConfig(network_mode="none")
    assert cfg_none.network_mode == "none"

    # read_only False rejected
    with pytest.raises(ValidationError, match="read-only root filesystem"):
        SandboxDeployConfig(read_only=False)

    # Invalid port numbers rejected
    with pytest.raises(ValidationError, match="Port must be between 1 and 65535"):
        PortBinding(container_port=0, host_port=8080)
    with pytest.raises(ValidationError, match="Port must be between 1 and 65535"):
        PortBinding(container_port=80, host_port=70000)
    with pytest.raises(ValidationError, match="Container port must be between 1 and 65535"):
        SandboxDeployConfig(ports=[80, 99999])


def test_generate_instance_id_uniqueness() -> None:
    """Instance IDs include a random nonce preventing same-second collisions."""
    engine = WorkloadSandboxEngine()
    id1 = engine._generate_instance_id("test")
    id2 = engine._generate_instance_id("test")
    assert id1 != id2
    assert id1.startswith("sandbox-test-")
    assert id2.startswith("sandbox-test-")


def test_engine_spawn_cleans_created_container_on_start_failure(tmp_path: Path) -> None:
    """When SDK container.start() fails, container is removed before fallback."""
    ws = tmp_path / "ws"
    ws.mkdir()
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))

    mock_container = MagicMock()
    mock_container.start.side_effect = RuntimeError("Failed starting container")
    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "cid-fallback-subprocess\n"

    with (
        patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client),
        patch("devops_cli.sandbox.engine.run_subprocess", return_value=mock_proc),
    ):
        cfg = SandboxDeployConfig(image="alpine", workspace_dir=ws)
        cid = engine._spawn_container(cfg, ws, [])
        assert cid == "cid-fallback-subprocess"
        mock_container.remove.assert_called_once_with(force=True)


def test_engine_spawn_via_subprocess_error_translation(tmp_path: Path) -> None:
    """Subprocess failure in _spawn_via_subprocess raises normalized SandboxError."""
    ws = tmp_path / "ws"
    ws.mkdir()
    engine = WorkloadSandboxEngine()

    with patch(
        "devops_cli.sandbox.engine.run_subprocess", side_effect=RuntimeError("Subprocess failed")
    ):
        cfg = SandboxDeployConfig(image="alpine", workspace_dir=ws)
        with pytest.raises(SandboxError, match="Docker run CLI failed to spawn container"):
            engine._spawn_via_subprocess(cfg, ws, [])


def test_engine_deploy_rollback_on_failure(tmp_path: Path) -> None:
    """Failed deployment cleans up pre-registered record and terminates container."""
    ws = tmp_path / "ws"
    ws.mkdir()
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    with patch.object(engine, "_spawn_container", side_effect=RuntimeError("Docker fatal")):
        cfg = SandboxDeployConfig(image="alpine", workspace_dir=ws)
        with pytest.raises(SandboxError, match="Failed deploying sandbox container"):
            engine.deploy(cfg)

    # Registry must not contain any leaked instance records
    assert len(reg.list_instances()) == 0


def test_engine_uptime_calculation_and_stop_persistence(tmp_path: Path) -> None:
    """Reconciliation computes uptime_seconds and stop persists final uptime."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    # Instance created 60 seconds ago
    past_ts = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=60)).isoformat()
    inst = SandboxInstance(
        instance_id="sb-uptime-test",
        container_id="cid-uptime-test",
        name="uptime-test",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        workspace_dir=str(tmp_path),
        created_at=past_ts,
    )
    reg.register_instance(inst)

    mock_container = MagicMock()
    mock_container.status = "running"
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with patch("devops_cli.sandbox.engine._get_docker_client", return_value=mock_client):
        statuses = engine.status("sb-uptime-test")
        assert len(statuses) == 1
        assert statuses[0].uptime_seconds >= 59.0

        stopped = engine.stop("sb-uptime-test")
        assert stopped.status == SandboxStatus.STOPPED
        assert stopped.uptime_seconds >= 59.0

        # Persisted in registry
        stored = reg.get_instance("sb-uptime-test")
        assert stored is not None
        assert stored.status == SandboxStatus.STOPPED
        assert stored.uptime_seconds >= 59.0


def test_registry_corrupt_file_quarantine(tmp_path: Path) -> None:
    """Corrupt registry file is quarantined to .corrupt-* without clobbering."""
    reg_file = tmp_path / "instances.json"
    reg_file.write_text("{ corrupt invalid json content", encoding="utf-8")

    reg = SandboxRegistry(reg_file)
    # list_instances returns empty list and creates quarantine file
    instances = reg.list_instances()
    assert instances == []

    quarantine_files = list(tmp_path.glob("instances.json.corrupt-*"))
    assert len(quarantine_files) == 1
    assert "{ corrupt" in quarantine_files[0].read_text(encoding="utf-8")
