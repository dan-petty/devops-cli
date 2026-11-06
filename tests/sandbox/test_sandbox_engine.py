"""The workload sandbox engine: deploy, status, stop and exec over the Docker engine."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.docker import DockerEngineError
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxInstance,
    SandboxStatus,
)
from devops_cli.sandbox.registry import SandboxRegistry


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


def test_engine_deploy_docker_sdk(tmp_path: Path, docker_engine: Any) -> None:
    """Engine deploy provisions container with security opts and records to registry."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    mock_container = MagicMock()
    mock_container.id = "cont-sdk-1234567890"
    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with docker_engine(mock_client):
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
        assert "/tmp" in create_kwargs["tmpfs"]  # nosec B108  # the in-container mount, under test
        # Explicit loopback binding
        assert create_kwargs["ports"]["80/tcp"][0] == "127.0.0.1"

        # Check registry persistence
        stored = reg.get_instance(instance.instance_id)
        assert stored is not None
        assert stored.status == SandboxStatus.RUNNING


def test_engine_status_reconciliation(tmp_path: Path, docker_engine: Any) -> None:
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
    mock_container.attrs = {"Id": "cid-live-1", "State": {"Status": "running", "Running": True}}
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client):
        statuses = engine.status("sb-live-1")
        assert (len(statuses), statuses[0].status) == (1, SandboxStatus.RUNNING)

    # When the container has exited
    mock_container.attrs = {"Id": "cid-live-1", "State": {"Status": "exited", "Running": False}}
    with docker_engine(mock_client):
        statuses = engine.status("sb-live-1")
        assert statuses[0].status == SandboxStatus.STOPPED


def test_engine_stop(tmp_path: Path, docker_engine: Any) -> None:
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

    with docker_engine(mock_client):
        stopped = engine.stop("sb-stop-1", timeout=5)
        assert stopped.status == SandboxStatus.STOPPED
        mock_client.api.stop.assert_called_once_with("cid-stop-1", timeout=5)
        mock_client.api.remove_container.assert_called_once_with("cid-stop-1", force=True)

    # Stop non-existent instance raises SandboxNotFoundError
    with pytest.raises(SandboxNotFoundError) as raised:
        engine.stop("non-existent-instance")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


def test_engine_exec(tmp_path: Path, docker_engine: Any) -> None:
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

    with docker_engine(mock_client):
        res = engine.exec("sb-exec-1", ["echo", "hello"])
        assert res.exit_code == 0
        assert "hello from sandbox" in res.stdout


def test_engine_deploy_surfaces_engine_failure(tmp_path: Path, docker_engine: Any) -> None:
    """Engine deploy surfaces daemon creation failures instead of degrading to the CLI."""
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

    mock_client = MagicMock()
    mock_client.containers.create.side_effect = RuntimeError("daemon offline")

    with docker_engine(mock_client):
        with pytest.raises(SandboxError, match="Failed deploying sandbox container"):
            engine.deploy(cfg)

    assert reg.list_instances() == []


def test_engine_status_not_found_and_client_error(tmp_path: Path, docker_engine: Any) -> None:
    """Engine status raises SandboxNotFoundError for a missing instance and tolerates an unreachable daemon."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    with pytest.raises(SandboxNotFoundError) as raised:
        engine.status("non-existent-instance")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"

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

    mock_client = MagicMock()
    mock_client.ping.side_effect = RuntimeError("Docker dead")

    with docker_engine(mock_client):
        statuses = engine.status()
        assert (len(statuses), statuses[0].status) == (1, SandboxStatus.RUNNING)


def test_engine_stop_forces_removal_when_graceful_stop_fails(
    tmp_path: Path, docker_engine: Any
) -> None:
    """A rejected graceful stop escalates to a forced Engine API container removal."""
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

    mock_client = MagicMock()
    mock_client.api.stop.side_effect = RuntimeError("container unresponsive")

    with docker_engine(mock_client):
        stopped = engine.stop("sb-stop-subp", timeout=5)

    assert stopped.status == SandboxStatus.STOPPED
    mock_client.api.remove_container.assert_called_once_with("cid-stop-subp", force=True)


def test_engine_exec_non_running_and_engine_failure(tmp_path: Path, docker_engine: Any) -> None:
    """Engine exec rejects non-running sandboxes and propagates Engine API failures."""
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

    # Calling exec on a non-running sandbox raises SandboxError.
    with pytest.raises(SandboxError, match="status is"):
        engine.exec("sb-exec-subp", ["ls"])

    inst.status = SandboxStatus.RUNNING
    reg.register_instance(inst)

    mock_container = MagicMock()
    mock_container.exec_run.side_effect = RuntimeError("exec rejected")
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client):
        with pytest.raises(DockerEngineError, match="Container exec failed"):
            engine.exec("sb-exec-subp", ["echo", "test"], workdir="/workspace")


def test_generate_instance_id_uniqueness() -> None:
    """Instance IDs include a random nonce preventing same-second collisions."""
    engine = WorkloadSandboxEngine()
    id1 = engine._generate_instance_id("test")
    id2 = engine._generate_instance_id("test")
    assert id1 != id2
    assert id1.startswith("sandbox-test-")
    assert id2.startswith("sandbox-test-")


def test_engine_spawn_cleans_created_container_on_start_failure(
    tmp_path: Path, docker_engine: Any
) -> None:
    """A failed container start removes the created container and raises SandboxError."""
    ws = tmp_path / "ws"
    ws.mkdir()
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))

    mock_container = MagicMock()
    mock_container.id = "cid-start-failed"
    mock_container.start.side_effect = RuntimeError("Failed starting container")
    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with docker_engine(mock_client):
        cfg = SandboxDeployConfig(image="alpine", workspace_dir=ws)
        with pytest.raises(SandboxError, match="Failed starting sandbox container"):
            engine._spawn_container(cfg, ws, [])

    mock_client.api.remove_container.assert_called_once_with("cid-start-failed", force=True)


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


def test_engine_uptime_calculation_and_stop_persistence(tmp_path: Path, docker_engine: Any) -> None:
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
    mock_container.attrs = {
        "Id": "cid-uptime-test",
        "State": {"Status": "running", "Running": True},
    }
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client):
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


def test_workload_sandbox_engine_prior_samples_instance_isolation(tmp_path: Path) -> None:
    """Verify that _prior_samples is isolated per WorkloadSandboxEngine instance (#420)."""
    reg1 = SandboxRegistry(tmp_path / "reg1.json")
    reg2 = SandboxRegistry(tmp_path / "reg2.json")
    engine1 = WorkloadSandboxEngine(registry=reg1)
    engine2 = WorkloadSandboxEngine(registry=reg2)

    engine1._prior_samples["test-key"] = (100.0, None)  # type: ignore[assignment]
    assert "test-key" not in engine2._prior_samples
