"""Isolated Dockerized workload sandbox execution engine."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_CURRENT_PATH, DEFAULT_DOCKER_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.docker import DockerSandboxError
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _get_docker_client() -> Any:
    """Connect to the local or remote Docker daemon via Docker SDK."""
    import docker  # type: ignore[import-untyped]

    return docker.from_env(timeout=int(DEFAULT_DOCKER_TIMEOUT_SECONDS))


class WorkloadSandboxConfig(BaseModel):
    """Configuration options for isolated Docker workload sandbox."""

    workspace_dir: Path = Field(default_factory=lambda: Path(DEFAULT_CURRENT_PATH).resolve())
    command: list[str]
    image: str = "python:3.14-slim"
    read_only: bool = True
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    network_mode: str = "bridge"  # bridge | none | host
    rootless: bool = True
    timeout: float = 300.0
    env: dict[str, str] = Field(default_factory=dict)


class WorkloadSandboxResult(BaseModel):
    """Execution results from a sandboxed Docker workload."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    container_id: str | None = None
    duration_seconds: float = 0.0


class WorkloadSandboxRunner:
    """Orchestrator for managing the lifecycle of disposable sandbox containers."""

    def __init__(self, config: WorkloadSandboxConfig) -> None:
        self.config = config

    def build_dry_run_details(self) -> dict[str, Any]:
        """Construct structured summary for dry-run inspection."""
        user_str = (
            f"{os.getuid()}:{os.getgid()}"
            if self.config.rootless and hasattr(os, "getuid")
            else "root"
        )
        return {
            "image": self.config.image,
            "command": self.config.command,
            "workspace_dir": str(self.config.workspace_dir.resolve()),
            "read_only": self.config.read_only,
            "memory_limit": self.config.memory_limit,
            "cpu_limit": self.config.cpu_limit,
            "network_mode": self.config.network_mode,
            "user": user_str,
        }

    _FORBIDDEN_ROOTS: set[str] = {
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
    _SENSITIVE_SUBPATHS: set[str] = {".ssh", ".aws", ".kube", ".git"}

    def _validate_workspace_dir(self) -> Path:
        ws = self.config.workspace_dir
        if ws.is_symlink():
            raise DockerSandboxError(f"Workspace directory cannot be a symbolic link: {ws}")
        resolved = ws.resolve()
        if str(resolved) in self._FORBIDDEN_ROOTS or resolved == Path(resolved.anchor):
            raise DockerSandboxError(
                f"Mounting sensitive root system directory into sandbox is forbidden: {resolved}"
            )
        try:
            if resolved == Path.home().resolve():
                raise DockerSandboxError(
                    f"Mounting user home directory into sandbox is forbidden: {resolved}"
                )
        except RuntimeError:
            pass

        if resolved.name in self._SENSITIVE_SUBPATHS or any(
            p in self._SENSITIVE_SUBPATHS for p in resolved.parts
        ):
            raise DockerSandboxError(
                f"Mounting sensitive credential or repository metadata directory into sandbox is forbidden: {resolved}"
            )

        if "docker.sock" in str(resolved):
            raise DockerSandboxError(
                f"Mounting Docker socket into sandbox is forbidden: {resolved}"
            )
        return resolved

    def run(self) -> WorkloadSandboxResult:
        """Spawn, execute, capture output, and tear down ephemeral sandbox container."""
        start_time = time.monotonic()
        ws_resolved = self._validate_workspace_dir()
        ws_abs = str(ws_resolved)
        mount_mode = "ro" if self.config.read_only else "rw"
        volumes = {ws_abs: {"bind": "/workspace", "mode": mount_mode}}

        user_str = None
        if self.config.rootless and hasattr(os, "getuid"):
            user_str = f"{os.getuid()}:{os.getgid()}"

        with trace_span(
            "docker.workload_sandbox.run",
            attributes={"image": self.config.image, "network_mode": self.config.network_mode},
        ):
            try:
                client = _get_docker_client()
                nano_cpus = int(self.config.cpu_limit * 1e9) if self.config.cpu_limit else None

                container = client.containers.create(
                    image=self.config.image,
                    command=self.config.command,
                    working_dir="/workspace",
                    volumes=volumes,
                    user=user_str,
                    mem_limit=self.config.memory_limit,
                    nano_cpus=nano_cpus,
                    network_mode=self.config.network_mode,
                    environment=self.config.env,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"],
                    pids_limit=256,
                    detach=True,
                )
            except Exception as exc:
                logger.debug("Falling back to docker run subprocess: %s", exc)
                return self._run_via_subprocess()

            container_id = container.id
            stdout = ""
            stderr = ""
            exit_code = 0

            try:
                container.start()
                res = container.wait(timeout=int(self.config.timeout))
                exit_code = res.get("StatusCode", 0) if isinstance(res, dict) else int(res)
                raw_out = container.logs(stdout=True, stderr=False)
                raw_err = container.logs(stdout=False, stderr=True)
                stdout = (
                    raw_out.decode("utf-8", errors="replace")
                    if isinstance(raw_out, bytes)
                    else str(raw_out)
                )
                stderr = (
                    raw_err.decode("utf-8", errors="replace")
                    if isinstance(raw_err, bytes)
                    else str(raw_err)
                )
            except Exception as wait_exc:
                logger.debug("Container wait failed or timed out: %s", wait_exc)
                exit_code = 124
                stderr = f"Container execution timed out after {self.config.timeout}s: {wait_exc}"
            finally:
                try:
                    container.remove(force=True)
                except Exception as rem_exc:
                    logger.debug("Failed removing container %s: %s", container_id, rem_exc)

            duration = round(time.monotonic() - start_time, 2)
            return WorkloadSandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                container_id=container_id,
                duration_seconds=duration,
            )

    def _run_via_subprocess(self) -> WorkloadSandboxResult:
        """Fallback to executing docker CLI via subprocess."""
        start_time = time.monotonic()
        ws_abs = str(self.config.workspace_dir.resolve())
        mount_mode = "ro" if self.config.read_only else "rw"
        cmd = [
            "docker",
            "run",
            "--rm",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=256",
            "-v",
            f"{ws_abs}:/workspace:{mount_mode}",
            "-w",
            "/workspace",
            "-m",
            self.config.memory_limit,
            f"--cpus={self.config.cpu_limit}",
            f"--network={self.config.network_mode}",
        ]
        for env_key, env_val in self.config.env.items():
            cmd.extend(["-e", f"{env_key}={env_val}"])
        if self.config.rootless and hasattr(os, "getuid"):
            cmd.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
        cmd.append(self.config.image)
        cmd.extend(self.config.command)

        proc = run_subprocess(cmd, check=False, timeout=int(self.config.timeout))
        duration = round(time.monotonic() - start_time, 2)
        return WorkloadSandboxResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
        )
