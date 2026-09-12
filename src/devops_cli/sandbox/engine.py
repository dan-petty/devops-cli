"""Workload sandbox execution and lifecycle orchestration engine."""

from __future__ import annotations

import datetime
import logging
import os
import time
from pathlib import Path
from typing import Any, Final

from devops_cli.config.defaults import DEFAULT_DOCKER_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
    SandboxValidationError,
)
from devops_cli.sandbox.models import (
    PortBinding,
    SandboxDeployConfig,
    SandboxExecResult,
    SandboxInstance,
    SandboxStatus,
)
from devops_cli.sandbox.ports import allocate_ports
from devops_cli.sandbox.registry import SandboxRegistry
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

_FORBIDDEN_ROOTS: Final[set[str]] = {
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/sys",
    "/proc",
    "/dev",
    "/var",
}
_SENSITIVE_SUBPATHS: Final[set[str]] = {".ssh", ".aws", ".kube", ".git"}


def _get_docker_client() -> Any:
    """Connect to local or remote Docker daemon via Docker SDK."""
    import docker  # type: ignore[import-untyped]

    return docker.from_env(timeout=int(DEFAULT_DOCKER_TIMEOUT_SECONDS))


def _resolve_user_string(rootless: bool) -> str | None:
    """Resolve container user string for rootless container execution."""
    if rootless and hasattr(os, "getuid"):
        return f"{os.getuid()}:{os.getgid()}"
    return None


class WorkloadSandboxEngine:
    """Orchestrator for managing isolated background Docker container sandboxes."""

    def __init__(self, registry: SandboxRegistry | None = None) -> None:
        self.registry = registry or SandboxRegistry()

    def validate_workspace_dir(self, workspace_dir: Path) -> Path:
        """Enforce strict security boundaries preventing host system root or secret mounts."""
        if workspace_dir.is_symlink():
            raise SandboxValidationError(
                f"Workspace directory cannot be a symbolic link: {workspace_dir}",
                path=str(workspace_dir),
            )

        resolved = workspace_dir.resolve()
        resolved_str = str(resolved)

        if resolved_str in _FORBIDDEN_ROOTS or resolved == Path(resolved.anchor):
            raise SandboxValidationError(
                f"Mounting sensitive root system directory into sandbox is forbidden: {resolved}",
                path=resolved_str,
            )

        try:
            if resolved == Path.home().resolve():
                raise SandboxValidationError(
                    f"Mounting user home directory into sandbox is forbidden: {resolved}",
                    path=resolved_str,
                )
        except RuntimeError:
            pass

        if resolved.name in _SENSITIVE_SUBPATHS or any(
            part in _SENSITIVE_SUBPATHS for part in resolved.parts
        ):
            raise SandboxValidationError(
                f"Mounting sensitive credential or repository metadata directory into sandbox is forbidden: {resolved}",
                path=resolved_str,
            )

        if "docker.sock" in resolved_str:
            raise SandboxValidationError(
                f"Mounting Docker socket into sandbox is forbidden: {resolved}",
                path=resolved_str,
            )

        return resolved

    def _generate_instance_id(self, name: str) -> str:
        """Create a deterministic unique timestamped instance identifier."""
        ts = int(time.time())
        clean_name = "".join(c if c.isalnum() or c == "-" else "-" for c in name.lower()).strip("-")
        return f"sandbox-{clean_name}-{ts}"

    def _build_create_kwargs(
        self,
        config: SandboxDeployConfig,
        ws_resolved: Path,
        port_bindings: list[PortBinding],
    ) -> dict[str, Any]:
        """Construct Docker container creation options with strict security containment."""
        mount_mode = "ro" if config.read_only else "rw"
        volumes = {str(ws_resolved): {"bind": "/workspace", "mode": mount_mode}}
        ports_map = {f"{b.container_port}/{b.protocol}": b.host_port for b in port_bindings}
        nano_cpus = int(config.cpu_limit * 1e9) if config.cpu_limit else None

        return {
            "image": config.image,
            "command": config.command,
            "working_dir": "/workspace",
            "volumes": volumes,
            "ports": ports_map,
            "user": _resolve_user_string(config.rootless),
            "mem_limit": config.memory_limit,
            "nano_cpus": nano_cpus,
            "network_mode": config.network_mode,
            "environment": config.env,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "pids_limit": 256,
            "read_only": config.read_only,
            "tmpfs": {"/tmp": "size=64m,noexec"},
            "detach": True,
        }

    def deploy(
        self,
        config: SandboxDeployConfig,
        dry_run: bool = False,
    ) -> SandboxInstance:
        """Provision, launch, and register an isolated long-running container sandbox."""
        ws_resolved = self.validate_workspace_dir(config.workspace_dir)
        reserved_ports = self.registry.get_allocated_host_ports()
        port_bindings = allocate_ports(config.ports, reserved_ports=reserved_ports)
        name = config.name or "app"
        instance_id = self._generate_instance_id(name)
        now_str = datetime.datetime.now(datetime.UTC).isoformat()

        if dry_run:
            return SandboxInstance(
                instance_id=instance_id,
                container_id="simulated-container-id",
                name=name,
                image=config.image,
                status=SandboxStatus.PENDING,
                port_bindings=port_bindings,
                workspace_dir=str(ws_resolved),
                created_at=now_str,
                metadata={"dry_run": True},
            )

        with trace_span(
            "sandbox.deploy", attributes={"image": config.image, "instance_id": instance_id}
        ):
            container_id = self._spawn_container(config, ws_resolved, port_bindings)
            instance = SandboxInstance(
                instance_id=instance_id,
                container_id=container_id,
                name=name,
                image=config.image,
                status=SandboxStatus.RUNNING,
                port_bindings=port_bindings,
                workspace_dir=str(ws_resolved),
                created_at=now_str,
            )
            self.registry.register_instance(instance)
            return instance

    def _spawn_container(
        self,
        config: SandboxDeployConfig,
        ws_resolved: Path,
        port_bindings: list[PortBinding],
    ) -> str:
        """Create and start container via Docker SDK or fallback subprocess."""
        create_kwargs = self._build_create_kwargs(config, ws_resolved, port_bindings)
        try:
            client = _get_docker_client()
            container = client.containers.create(**create_kwargs)
            container.start()
            return str(container.id)
        except Exception as exc:
            logger.debug("Docker SDK create/start failed (%s); falling back to CLI subprocess", exc)
            return self._spawn_via_subprocess(config, ws_resolved, port_bindings)

    def _spawn_via_subprocess(
        self,
        config: SandboxDeployConfig,
        ws_resolved: Path,
        port_bindings: list[PortBinding],
    ) -> str:
        """Spawn container using `docker run -d` via subprocess."""
        mount_mode = "ro" if config.read_only else "rw"
        cmd = [
            "docker",
            "run",
            "-d",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=256",
            "-v",
            f"{ws_resolved}:/workspace:{mount_mode}",
            "-w",
            "/workspace",
            "-m",
            config.memory_limit,
            f"--cpus={config.cpu_limit}",
            f"--network={config.network_mode}",
        ]
        if config.read_only:
            cmd.extend(["--read-only", "--tmpfs=/tmp:size=64m,noexec"])
        for b in port_bindings:
            cmd.extend(["-p", f"{b.host_port}:{b.container_port}/{b.protocol}"])
        for k, v in config.env.items():
            cmd.extend(["-e", f"{k}={v}"])
        user_str = _resolve_user_string(config.rootless)
        if user_str:
            cmd.extend(["--user", user_str])
        cmd.append(config.image)
        cmd.extend(config.command)

        proc = run_subprocess(cmd, check=True, timeout=int(config.timeout))
        return proc.stdout.strip()

    def status(self, identifier: str | None = None) -> list[SandboxInstance]:
        """Query sandbox status and reconcile liveness against Docker daemon."""
        instances = (
            [self.registry.get_instance(identifier)]
            if identifier
            else self.registry.list_instances()
        )
        resolved = [inst for inst in instances if inst is not None]
        if identifier and not resolved:
            raise SandboxNotFoundError(
                f"Sandbox instance '{identifier}' not found",
                identifier=identifier,
            )

        client = None
        try:
            client = _get_docker_client()
        except Exception as exc:
            logger.debug("Could not initialize Docker SDK for status check: %s", exc)

        for inst in resolved:
            self._reconcile_single_instance(inst, client)

        return resolved

    def _reconcile_single_instance(self, inst: SandboxInstance, client: Any) -> None:
        """Reconcile a single instance's state against the running Docker daemon."""
        if not client:
            return
        try:
            container = client.containers.get(inst.container_id)
            status_str = str(container.status).lower()
            new_status = SandboxStatus.RUNNING if status_str == "running" else SandboxStatus.STOPPED
            if new_status != inst.status:
                self.registry.update_instance_status(inst.instance_id, new_status)
                inst.status = new_status
        except Exception as exc:
            logger.debug("Failed polling container %s status: %s", inst.container_id, exc)

    def stop(
        self,
        identifier: str,
        timeout: int = 10,
        dry_run: bool = False,
    ) -> SandboxInstance:
        """Gracefully stop and tear down a sandbox container instance."""
        inst = self.registry.get_instance(identifier)
        if not inst:
            raise SandboxNotFoundError(
                f"Cannot stop; sandbox instance '{identifier}' not found",
                identifier=identifier,
            )

        if dry_run:
            inst.status = SandboxStatus.STOPPED
            return inst

        with trace_span("sandbox.stop", attributes={"instance_id": inst.instance_id}):
            self._terminate_container(inst.container_id, timeout=timeout)
            return self.registry.update_instance_status(inst.instance_id, SandboxStatus.STOPPED)

    def _terminate_container(self, container_id: str, timeout: int) -> None:
        """Terminate and remove container via SDK or subprocess fallback."""
        try:
            client = _get_docker_client()
            container = client.containers.get(container_id)
            container.stop(timeout=timeout)
            container.remove(force=True)
        except Exception as exc:
            logger.debug("Docker SDK container stop failed (%s); trying subprocess", exc)
            run_subprocess(["docker", "stop", "-t", str(timeout), container_id], check=False)
            run_subprocess(["docker", "rm", "-f", container_id], check=False)

    def exec(
        self,
        identifier: str,
        command: list[str],
        workdir: str | None = None,
    ) -> SandboxExecResult:
        """Execute a command inside an active sandbox container."""
        inst = self.registry.get_instance(identifier)
        if not inst:
            raise SandboxNotFoundError(
                f"Cannot exec; sandbox instance '{identifier}' not found",
                identifier=identifier,
            )
        if inst.status != SandboxStatus.RUNNING:
            raise SandboxError(
                f"Cannot exec in sandbox '{identifier}'; status is '{inst.status}'",
                instance_id=inst.instance_id,
            )

        start_time = time.monotonic()
        try:
            client = _get_docker_client()
            container = client.containers.get(inst.container_id)
            exit_code, output = container.exec_run(command, workdir=workdir)
            stdout = (
                output.decode("utf-8", errors="replace")
                if isinstance(output, bytes)
                else str(output)
            )
            duration = round(time.monotonic() - start_time, 2)
            return SandboxExecResult(
                instance_id=inst.instance_id,
                command=command,
                exit_code=exit_code,
                stdout=stdout,
                stderr="",
                duration_seconds=duration,
            )
        except Exception as exc:
            logger.debug("Docker SDK exec failed (%s); fallback to subprocess", exc)
            return self._exec_via_subprocess(inst, command, workdir, start_time)

    def _exec_via_subprocess(
        self,
        inst: SandboxInstance,
        command: list[str],
        workdir: str | None,
        start_time: float,
    ) -> SandboxExecResult:
        """Fallback to docker exec via subprocess."""
        cmd = ["docker", "exec"]
        if workdir:
            cmd.extend(["-w", workdir])
        cmd.append(inst.container_id)
        cmd.extend(command)

        proc = run_subprocess(cmd, check=False)
        duration = round(time.monotonic() - start_time, 2)
        return SandboxExecResult(
            instance_id=inst.instance_id,
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
        )


__all__ = ["WorkloadSandboxEngine"]
