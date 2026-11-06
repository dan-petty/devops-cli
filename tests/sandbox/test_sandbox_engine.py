"""The workload sandbox engine: deploy, status, stop and exec over the Docker engine."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.exceptions.docker import DockerEngineError
from devops_cli.exceptions.sandbox import SandboxError, SandboxNotFoundError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxInstance,
    SandboxNetworkMode,
    SandboxStatus,
)
from devops_cli.sandbox.registry import SandboxRegistry
from tests.support.fakes.docker_engine import DockerEngineFake
from tests.web_fakes import http_response, record_connects

_IMAGE = "python:3.14-slim"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def _a_minute_ago() -> str:
    """The time 60 seconds ago, as a sandbox that was created then records it."""
    return (datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=60)).isoformat()


def _call(docker_daemon: DockerEngineFake, name: str) -> list:
    """The calls the Docker fake answered with this name, oldest first."""
    return [call for call in docker_daemon.calls if call.name == name]


def test_engine_deploy_dry_run(tmp_path: Path) -> None:
    """Engine deploy in dry-run mode constructs instance without spawning container."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=reg)

    cfg = SandboxDeployConfig(
        image=_IMAGE,
        name="test-dry-run",
        ports=[8000],
        workspace_dir=_workspace(tmp_path),
        env={"TEST_VAR": "true"},
    )

    instance = engine.deploy(cfg, dry_run=True)
    assert instance.instance_id.startswith("sandbox-")
    assert instance.status == SandboxStatus.PENDING
    assert len(instance.port_bindings) == 1
    assert instance.port_bindings[0].container_port == 8000
    # Dry run should not record in persistent registry
    assert reg.list_instances() == []


def test_engine_deploy_docker_sdk(tmp_path: Path, docker_daemon: DockerEngineFake) -> None:
    """Engine deploy provisions container with security opts and records to registry."""
    docker_daemon.add_image("nginx:alpine")
    reg = SandboxRegistry(tmp_path / "reg.json")
    cfg = SandboxDeployConfig(
        image="nginx:alpine",
        name="web-svc",
        ports=[80],
        workspace_dir=_workspace(tmp_path),
        memory_limit="1g",
        cpu_limit=1.5,
    )

    instance = WorkloadSandboxEngine(registry=reg).deploy(cfg)

    (created,) = _call(docker_daemon, "containers.create")
    assert (instance.status, instance.name) == (SandboxStatus.RUNNING, "web-svc")
    assert docker_daemon.container_state[instance.container_id]["State"]["Running"] is True
    # Check container creation kwargs for security settings
    assert created.kwargs["cap_drop"] == ["ALL"]
    assert created.kwargs["security_opt"] == ["no-new-privileges:true"]
    assert created.kwargs["pids_limit"] == 256
    assert created.kwargs["read_only"] is True
    assert "/tmp" in created.kwargs["tmpfs"]  # nosec B108  # the in-container mount, under test
    # Explicit loopback binding
    assert created.kwargs["ports"]["80/tcp"][0] == "127.0.0.1"
    # Check registry persistence
    stored = reg.get_instance(instance.instance_id)
    assert stored is not None
    assert stored.status == SandboxStatus.RUNNING


def test_engine_status_reconciliation(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Engine status reconciles live container state against Docker daemon."""
    inst = register_sandbox("sb-live-1", name="live-svc")
    engine = WorkloadSandboxEngine()

    running = engine.status("sb-live-1")[0].status
    # When the container has exited
    docker_daemon.stop(inst.container_id)
    exited = engine.status("sb-live-1")[0].status

    assert (running, exited) == (SandboxStatus.RUNNING, SandboxStatus.STOPPED)


def test_engine_stop(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Engine stop gracefully terminates container and updates status."""
    inst = register_sandbox("sb-stop-1", name="stop-svc")
    engine = WorkloadSandboxEngine()

    stopped = engine.stop("sb-stop-1", timeout=5)

    assert stopped.status == SandboxStatus.STOPPED
    assert [call.kwargs["timeout"] for call in _call(docker_daemon, "api.stop")] == [5]
    assert inst.container_id not in docker_daemon.container_state

    # Stop non-existent instance raises SandboxNotFoundError
    with pytest.raises(SandboxNotFoundError) as raised:
        engine.stop("non-existent-instance")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


def test_engine_exec(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Engine exec executes commands inside running container."""
    register_sandbox("sb-exec-1", name="exec-svc")
    docker_daemon.script_exec("sb-exec-1", ["echo", "hello"], output=b"hello from sandbox\n")

    res = WorkloadSandboxEngine().exec("sb-exec-1", ["echo", "hello"])

    assert (res.exit_code, res.stdout) == (0, "hello from sandbox\n")


def test_engine_deploy_surfaces_engine_failure(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Engine deploy surfaces daemon creation failures instead of degrading to the CLI."""
    docker_daemon.add_image(_IMAGE)
    docker_daemon.fail("containers.create", RuntimeError("daemon offline"))
    reg = SandboxRegistry(tmp_path / "reg.json")
    cfg = SandboxDeployConfig(
        image=_IMAGE, name="subp-app", ports=[8080], workspace_dir=_workspace(tmp_path)
    )

    with pytest.raises(SandboxError, match="Failed deploying sandbox container"):
        WorkloadSandboxEngine(registry=reg).deploy(cfg)

    assert reg.list_instances() == []


def test_engine_status_raises_not_found_for_a_missing_instance() -> None:
    """Engine status raises SandboxNotFoundError for an instance the registry does not hold."""
    with pytest.raises(SandboxNotFoundError) as raised:
        WorkloadSandboxEngine().status("non-existent-instance")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


def test_engine_status_keeps_the_registry_view_when_the_daemon_is_unreachable(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """An unreachable daemon leaves each instance with the status the registry holds."""
    register_sandbox("sb-stat-err", name="stat-err")
    docker_daemon.unreachable = True

    statuses = WorkloadSandboxEngine().status()

    assert [(s.instance_id, s.status) for s in statuses] == [("sb-stat-err", SandboxStatus.RUNNING)]


def test_engine_stop_forces_removal_when_graceful_stop_fails(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """A rejected graceful stop escalates to a forced Engine API container removal."""
    inst = register_sandbox("sb-stop-subp", name="stop-subp")
    docker_daemon.fail("api.stop", RuntimeError("container unresponsive"))

    stopped = WorkloadSandboxEngine().stop("sb-stop-subp", timeout=5)

    assert stopped.status == SandboxStatus.STOPPED
    assert [call.kwargs["force"] for call in _call(docker_daemon, "api.remove_container")] == [True]
    assert inst.container_id not in docker_daemon.container_state


def test_engine_exec_refuses_a_sandbox_that_is_not_running(
    register_sandbox: Callable[..., SandboxInstance],
) -> None:
    """Engine exec rejects a sandbox whose status is not running."""
    register_sandbox("sb-stopped", name="exec-stopped", running=False)

    with pytest.raises(SandboxError, match="status is"):
        WorkloadSandboxEngine().exec("sb-stopped", ["ls"])


def test_engine_exec_propagates_an_engine_failure(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Engine exec raises the Engine API failure of a command that the engine rejects."""
    register_sandbox("sb-exec-subp", name="exec-subp")
    docker_daemon.fail("container.exec_run", RuntimeError("exec rejected"))

    with pytest.raises(DockerEngineError, match="Container exec failed"):
        WorkloadSandboxEngine().exec("sb-exec-subp", ["echo", "test"], workdir="/workspace")


def test_every_deploy_gets_its_own_instance_id(tmp_path: Path) -> None:
    """Instance IDs include a random nonce preventing same-second collisions."""
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))
    cfg = SandboxDeployConfig(name="test", workspace_dir=_workspace(tmp_path))

    id1 = engine.deploy(cfg, dry_run=True).instance_id
    id2 = engine.deploy(cfg, dry_run=True).instance_id

    assert id1 != id2
    assert id1.startswith("sandbox-test-")
    assert id2.startswith("sandbox-test-")


def test_engine_spawn_cleans_created_container_on_start_failure(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """A failed container start removes the created container and raises SandboxError."""
    docker_daemon.add_image("alpine")
    docker_daemon.fail("container.start", RuntimeError("Failed starting container"))
    cfg = SandboxDeployConfig(image="alpine", workspace_dir=_workspace(tmp_path))

    with pytest.raises(SandboxError, match="Failed starting sandbox container"):
        WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json")).deploy(cfg)

    assert [call.kwargs["force"] for call in _call(docker_daemon, "api.remove_container")] == [True]
    assert docker_daemon.container_state == {}


def test_engine_deploy_rollback_on_failure(tmp_path: Path, docker_daemon: DockerEngineFake) -> None:
    """Failed deployment cleans up pre-registered record and terminates container."""
    docker_daemon.fail("networks.create", RuntimeError("Docker fatal"))
    reg = SandboxRegistry(tmp_path / "reg.json")
    cfg = SandboxDeployConfig(
        image="alpine",
        network_mode=SandboxNetworkMode.SANDBOX_NAMESPACE.value,
        workspace_dir=_workspace(tmp_path),
    )

    with pytest.raises(SandboxError, match="Cannot provision internal sandbox network"):
        WorkloadSandboxEngine(registry=reg).deploy(cfg)

    # Registry must not contain any leaked instance records
    assert len(reg.list_instances()) == 0
    assert docker_daemon.container_state == {}


def test_engine_status_computes_the_uptime_of_a_running_sandbox(
    register_sandbox: Callable[..., SandboxInstance],
) -> None:
    """Reconciliation computes uptime_seconds from the creation time."""
    register_sandbox("sb-uptime-test", name="uptime-test", created_at=_a_minute_ago())

    statuses = WorkloadSandboxEngine().status("sb-uptime-test")

    assert [s.uptime_seconds >= 59.0 for s in statuses] == [True]


def test_engine_stop_persists_the_final_uptime(
    register_sandbox: Callable[..., SandboxInstance],
) -> None:
    """Stop records the stopped status and the uptime in the registry."""
    register_sandbox("sb-uptime-test", name="uptime-test", created_at=_a_minute_ago())
    engine = WorkloadSandboxEngine()

    stopped = engine.stop("sb-uptime-test")
    stored = engine.registry.get_instance("sb-uptime-test")

    assert stopped.status == SandboxStatus.STOPPED
    assert stopped.uptime_seconds >= 59.0
    assert stored is not None
    assert (stored.status, stored.uptime_seconds >= 59.0) == (SandboxStatus.STOPPED, True)


def test_each_engine_keeps_its_own_previous_cpu_sample(
    monkeypatch: pytest.MonkeyPatch,
    register_sandbox: Callable[..., SandboxInstance],
    tmp_path: Path,
) -> None:
    """The CPU percent of a reading comes from the same engine's previous reading (#420)."""
    record_connects(monkeypatch, [http_response(200, "up 1\n")] * 4)
    instance = register_sandbox("sb-isolated")
    scope = tmp_path / "cgroup" / "system.slice" / f"docker-{instance.container_id}.scope"
    scope.mkdir(parents=True)
    (scope / "cpu.stat").write_text("usage_usec 1000000\n")
    first_engine = WorkloadSandboxEngine(cgroup_root=tmp_path / "cgroup")
    second_engine = WorkloadSandboxEngine(cgroup_root=tmp_path / "cgroup")

    first_engine.metrics("sb-isolated")
    (scope / "cpu.stat").write_text("usage_usec 1500000\n")
    first_again = first_engine.metrics("sb-isolated").cgroup
    other_first = second_engine.metrics("sb-isolated").cgroup

    assert first_again is not None
    assert other_first is not None
    assert (first_again.cpu_percent is not None, other_first.cpu_percent) == (True, None)
