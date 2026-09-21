"""Isolated Dockerized workload sandbox execution engine."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_SENSITIVE_SUBPATHS,
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SANDBOX_CPUS,
    DEFAULT_SANDBOX_EXCLUDE_HOME,
    DEFAULT_SANDBOX_IMAGE,
    DEFAULT_SANDBOX_MEMORY,
    DEFAULT_SANDBOX_NETWORK,
    DEFAULT_SANDBOX_PIDS_LIMIT,
)
from devops_cli.docker.engine import decode_stream as _decode_logs
from devops_cli.docker.engine import get_engine
from devops_cli.exceptions.docker import DockerSandboxError
from devops_cli.sandbox.engine import is_home_or_subpath
from devops_cli.sandbox.models import SandboxNetworkConfig, SandboxNetworkMode
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _ensure_internal_network() -> None:
    """Ensure the egress-denied internal bridge network backing namespaced sandboxes exists."""
    if not get_engine().ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET):
        raise DockerSandboxError(
            f"Cannot provision internal sandbox network '{CONST_SANDBOX_DOCKER_INTERNAL_NET}'; "
            "the Docker daemon is unreachable or refused the request."
        )


class WorkloadSandboxConfig(BaseModel):
    """Configuration options for isolated Docker workload sandbox."""

    workspace_dir: Path = Field(default_factory=lambda: Path(DEFAULT_CURRENT_PATH).resolve())
    command: list[str]
    image: str = DEFAULT_SANDBOX_IMAGE
    read_only: bool = True
    memory_limit: str = DEFAULT_SANDBOX_MEMORY
    cpu_limit: float = DEFAULT_SANDBOX_CPUS
    network_config: SandboxNetworkConfig = Field(
        default_factory=lambda: SandboxNetworkConfig(mode=SandboxNetworkMode.ISOLATED)
    )
    network_mode: str = DEFAULT_SANDBOX_NETWORK
    public_whitelist: list[str] = Field(default_factory=list)
    local_whitelist: list[str] = Field(default_factory=list)
    rootless: bool = True
    timeout: float = 300.0
    env: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_network_fields(cls, data: Any) -> Any:
        """Synchronize network_mode and SandboxNetworkConfig model."""
        if not isinstance(data, dict):
            return data
        net_cfg = data.get("network_config")
        net_mode = data.get("network_mode")
        pub_wl = data.get("public_whitelist")
        loc_wl = data.get("local_whitelist")

        if net_cfg is not None:
            if isinstance(net_cfg, dict):
                net_cfg = SandboxNetworkConfig(**net_cfg)
            data["network_config"] = net_cfg
            data["network_mode"] = (
                "none" if net_cfg.mode == SandboxNetworkMode.ISOLATED else net_cfg.mode.value
            )
        elif net_mode is not None:
            kwargs: dict[str, Any] = {"mode": net_mode}
            if pub_wl:
                kwargs["public_whitelist"] = pub_wl
            if loc_wl:
                kwargs["local_whitelist"] = loc_wl
            cfg = SandboxNetworkConfig(**kwargs)
            data["network_config"] = cfg
            data["network_mode"] = (
                "none" if cfg.mode == SandboxNetworkMode.ISOLATED else cfg.mode.value
            )
        else:
            cfg = SandboxNetworkConfig(mode=SandboxNetworkMode.ISOLATED)
            data["network_config"] = cfg
            data["network_mode"] = "none"
        return data


class WorkloadSandboxResult(BaseModel):
    """Execution results from a sandboxed Docker workload."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    container_id: str | None = None
    duration_seconds: float = 0.0

    @field_validator("stdout", "stderr", mode="before")
    @classmethod
    def sanitize_output(cls, v: Any) -> str:
        """Mask secrets in workload sandbox stdout/stderr."""
        if not v:
            return ""
        from devops_cli.security.sanitizer import mask_secrets

        return mask_secrets(str(v))


def _check_home_boundary(resolved: Path, exclude_home_dir: bool) -> None:
    """Validate home directory boundaries based on user preference."""
    if exclude_home_dir and is_home_or_subpath(resolved):
        raise DockerSandboxError(f"Sandbox access to user home directory is excluded: {resolved}")
    if not exclude_home_dir:
        try:
            if resolved == Path.home().resolve():
                raise DockerSandboxError(
                    f"Mounting user home directory into sandbox is forbidden: {resolved}"
                )
        except RuntimeError:
            pass


class WorkloadSandboxRunner:
    """Orchestrator for managing the lifecycle of disposable sandbox containers."""

    def __init__(
        self,
        config: WorkloadSandboxConfig,
        *,
        exclude_home_dir: bool | None = None,
    ) -> None:
        self.config = config
        if exclude_home_dir is not None:
            self.exclude_home_dir = exclude_home_dir
        else:
            try:
                from devops_cli.config import load_settings

                self.exclude_home_dir = load_settings().sandbox.exclude_home_dir
            except Exception:
                self.exclude_home_dir = DEFAULT_SANDBOX_EXCLUDE_HOME

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
            "network_config": self.config.network_config.model_dump(),
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

    def _validate_workspace_dir(self) -> Path:
        ws = self.config.workspace_dir
        if ws.is_symlink():
            raise DockerSandboxError(f"Workspace directory cannot be a symbolic link: {ws}")
        resolved = ws.resolve()
        if str(resolved) in self._FORBIDDEN_ROOTS or resolved == Path(resolved.anchor):
            raise DockerSandboxError(
                f"Mounting sensitive root system directory into sandbox is forbidden: {resolved}"
            )
        _check_home_boundary(resolved, self.exclude_home_dir)

        if resolved.name in CONST_SANDBOX_SENSITIVE_SUBPATHS or any(
            p in CONST_SANDBOX_SENSITIVE_SUBPATHS for p in resolved.parts
        ):
            raise DockerSandboxError(
                f"Mounting sensitive credential or repository metadata directory into sandbox is forbidden: {resolved}"
            )

        if "docker.sock" in str(resolved):
            raise DockerSandboxError(
                f"Mounting Docker socket into sandbox is forbidden: {resolved}"
            )
        return resolved

    _INTERNAL_NETWORK_MODES: frozenset[SandboxNetworkMode] = frozenset(
        {
            SandboxNetworkMode.SANDBOX_NAMESPACE,
            SandboxNetworkMode.PUBLIC_WHITELIST,
            SandboxNetworkMode.LOCAL_WHITELIST,
        }
    )
    _PROXY_ENFORCED_MODES: frozenset[SandboxNetworkMode] = frozenset(
        {SandboxNetworkMode.PUBLIC_WHITELIST, SandboxNetworkMode.LOCAL_WHITELIST}
    )

    def _network_create_kwargs(self) -> dict[str, Any]:
        """Resolve Engine API network and proxy settings for the configured isolation tier."""
        mode = self.config.network_config.mode
        if mode in self._PROXY_ENFORCED_MODES and not self.config.network_config.egress_proxy:
            raise DockerSandboxError(
                f"Docker runner cannot enforce egress whitelist filtering for '{mode.value}' without an egress proxy. Use isolated or sandbox_namespace mode, or deploy to Kubernetes where NetworkPolicy enforces egress boundaries."
            )
        if mode in self._INTERNAL_NETWORK_MODES:
            _ensure_internal_network()

        if mode == SandboxNetworkMode.ISOLATED:
            return {"network_mode": "none", "environment": dict(self.config.env)}
        if mode == SandboxNetworkMode.SANDBOX_NAMESPACE:
            return {
                "network_mode": CONST_SANDBOX_DOCKER_INTERNAL_NET,
                "environment": dict(self.config.env),
            }
        if mode in self._PROXY_ENFORCED_MODES:
            proxy_url = self.config.network_config.egress_proxy or ""
            return {
                "network_mode": CONST_SANDBOX_DOCKER_INTERNAL_NET,
                "environment": {
                    "HTTP_PROXY": proxy_url,
                    "HTTPS_PROXY": proxy_url,
                    "ALL_PROXY": proxy_url,
                    **self.config.env,
                },
            }
        return {"network_mode": "bridge", "environment": dict(self.config.env)}

    def _build_create_kwargs(self, ws_resolved: Path) -> dict[str, Any]:
        """Assemble the hardened Engine API container creation payload."""
        mount_mode = "ro" if self.config.read_only else "rw"
        user_str = (
            f"{os.getuid()}:{os.getgid()}"
            if self.config.rootless and hasattr(os, "getuid")
            else None
        )
        return {
            "image": self.config.image,
            "command": self.config.command,
            "working_dir": "/workspace",
            "volumes": {str(ws_resolved): {"bind": "/workspace", "mode": mount_mode}},
            "user": user_str,
            "mem_limit": self.config.memory_limit,
            "nano_cpus": int(self.config.cpu_limit * 1e9) if self.config.cpu_limit else None,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "pids_limit": DEFAULT_SANDBOX_PIDS_LIMIT,
            "detach": True,
            **self._network_create_kwargs(),
        }

    def _collect_output(self, container: Any) -> tuple[int, str, str]:
        """Run the container to completion and drain its stdout and stderr streams."""
        container.start()
        result = container.wait(timeout=int(self.config.timeout))
        exit_code = result.get("StatusCode", 0) if isinstance(result, dict) else int(result)
        return (
            exit_code,
            _decode_logs(container.logs(stdout=True, stderr=False)),
            _decode_logs(container.logs(stdout=False, stderr=True)),
        )

    def run(self) -> WorkloadSandboxResult:
        """Spawn, execute, capture output, and tear down an ephemeral sandbox container."""
        start_time = time.monotonic()
        ws_resolved = self._validate_workspace_dir()

        with trace_span(
            "docker.workload_sandbox.run",
            attributes={"image": self.config.image, "network_mode": self.config.network_mode},
        ):
            engine = get_engine()
            container = engine.create_container(**self._build_create_kwargs(ws_resolved))
            container_id = str(container.id)

            try:
                exit_code, stdout, stderr = self._collect_output(container)
            except Exception as exc:
                logger.debug("Sandbox container %s execution failed: %s", container_id, exc)
                exit_code = CONST_SANDBOX_TIMEOUT_EXIT_CODE
                stdout, stderr = (
                    "",
                    (f"Container execution timed out after {self.config.timeout}s: {exc}"),
                )
            finally:
                engine.remove_container(container_id, force=True)

            return WorkloadSandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                container_id=container_id,
                duration_seconds=round(time.monotonic() - start_time, 2),
            )
