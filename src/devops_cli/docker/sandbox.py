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
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SANDBOX_CPUS,
    DEFAULT_SANDBOX_IMAGE,
    DEFAULT_SANDBOX_MEMORY,
    DEFAULT_SANDBOX_NETWORK,
)
from devops_cli.docker.engine import decode_stream as _decode_logs
from devops_cli.docker.engine import get_engine
from devops_cli.exceptions.docker import DockerError, DockerSandboxError
from devops_cli.exceptions.sandbox import SandboxValidationError
from devops_cli.sandbox.engine import validate_sandbox_workspace
from devops_cli.sandbox.models import (
    DEFAULT_SANDBOX_POLICY,
    SandboxNetworkConfig,
    SandboxNetworkMode,
    SandboxPolicy,
)
from devops_cli.telemetry import get_tracer, trace_span

logger = logging.getLogger(__name__)


def _ensure_internal_network() -> None:
    """Ensure the egress-denied internal bridge network backing namespaced sandboxes exists."""
    if not get_engine().ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET):
        raise DockerSandboxError(
            f"Cannot provision internal sandbox network '{CONST_SANDBOX_DOCKER_INTERNAL_NET}'; "
            "the Docker daemon is unreachable or refused the request."
        )


def resolve_sandbox_user(rootless: bool) -> str | None:
    """Resolve container user string based on rootless configuration and engine mode."""
    if not rootless:
        return None
    try:
        if get_engine().is_rootless():
            return "0:0"
    except (DockerError, OSError) as exc:
        logger.debug("Failed querying engine rootless status for sandbox user: %s", exc)
    if hasattr(os, "getuid"):
        return f"{os.getuid()}:{os.getgid()}"
    return None


class WorkloadSandboxConfig(BaseModel):
    """Configuration options for isolated Docker workload sandbox."""

    workspace_dir: Path = Field(default_factory=lambda: Path(DEFAULT_CURRENT_PATH).resolve())
    command: list[str]
    image: str = DEFAULT_SANDBOX_IMAGE
    read_only: bool = True
    memory_limit: str = DEFAULT_SANDBOX_MEMORY
    cpu_limit: float = DEFAULT_SANDBOX_CPUS
    policy: SandboxPolicy = Field(default_factory=lambda: DEFAULT_SANDBOX_POLICY)
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
                from devops_cli.config.settings import load_settings, setting_default

                self.exclude_home_dir = load_settings().sandbox.exclude_home_dir
            except Exception:
                self.exclude_home_dir = setting_default("sandbox.exclude_home_dir")

    def _validate_workspace_dir(self) -> Path:
        """Resolve the workspace through the shared sandbox workspace check."""
        try:
            return validate_sandbox_workspace(
                self.config.workspace_dir, exclude_home_dir=self.exclude_home_dir
            )
        except SandboxValidationError as exc:
            raise DockerSandboxError(exc.message, details=exc.details) from exc

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

    def declared_controls(self, *, inline_seccomp: bool = True) -> dict[str, Any]:
        """The hardening this runner declares to the engine, before any engine call.

        These are the policy's security options, the Docker network of the network mode and the
        mode the workspace is mounted in. The method is pure: it asks the engine nothing,
        provisions no network and injects no trace, so the dry run reads the controls the
        container is created with. A seccomp profile is in its inline form unless
        `inline_seccomp` is False.
        """
        return {
            **self.config.policy.to_docker_security_kwargs(
                read_only=self.config.read_only, inline_seccomp=inline_seccomp
            ),
            "network_mode": self.config.network_config.to_docker_network_mode(),
            "workspace_mount_mode": "ro" if self.config.read_only else "rw",
        }

    def _provision_network_environment(self) -> dict[str, str]:
        """Provision the configured isolation tier and return the container environment for it.

        A whitelist needs the egress proxy that enforces it, which the environment points at.
        """
        mode = self.config.network_config.mode
        if mode in self._PROXY_ENFORCED_MODES and not self.config.network_config.egress_proxy:
            raise DockerSandboxError(
                f"Docker runner cannot enforce egress whitelist filtering for '{mode.value}' without an egress proxy. Use isolated or sandbox_namespace mode, or deploy to Kubernetes where NetworkPolicy enforces egress boundaries."
            )
        if mode in self._INTERNAL_NETWORK_MODES:
            _ensure_internal_network()
        if mode not in self._PROXY_ENFORCED_MODES:
            return dict(self.config.env)
        proxy_url = self.config.network_config.egress_proxy or ""
        return {
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
            "ALL_PROXY": proxy_url,
            **self.config.env,
        }

    def _build_create_kwargs(self, ws_resolved: Path) -> dict[str, Any]:
        """Assemble the hardened Engine API container creation payload.

        The declared controls come first, and the workspace is mounted in the mode they declare.
        The container's environment carries the active trace context, so a workload that traces
        is parented to the span that runs it.
        """
        policy = self.config.policy
        inline_seccomp = (
            policy.seccomp_profile is None or get_engine().accepts_inline_seccomp_profile()
        )
        declared = self.declared_controls(inline_seccomp=inline_seccomp)
        mount_mode = declared.pop("workspace_mount_mode")
        user_str = resolve_sandbox_user(self.config.rootless)
        environment = self._provision_network_environment()
        get_tracer().inject_trace_env(environment)
        kwargs: dict[str, Any] = {
            "image": self.config.image,
            "command": self.config.command,
            "working_dir": "/workspace",
            "volumes": {str(ws_resolved): {"bind": "/workspace", "mode": mount_mode}},
            "mem_limit": self.config.memory_limit,
            "nano_cpus": int(self.config.cpu_limit * 1e9) if self.config.cpu_limit else None,
            "detach": True,
            "environment": environment,
            **declared,
        }
        if user_str is not None:
            kwargs["user"] = user_str
        return kwargs

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
