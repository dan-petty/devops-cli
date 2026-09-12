"""Data models and schemas for workload sandbox lifecycle management."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_CURRENT_PATH


class SandboxStatus(StrEnum):
    """Lifecycle status states for workload sandbox containers."""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class PortBinding(BaseModel):
    """Network port mapping between sandbox container and host."""

    container_port: int
    host_port: int
    protocol: str = "tcp"


class SandboxDeployConfig(BaseModel):
    """Deployment specification for long-running workload sandboxes."""

    image: str = "python:3.14-slim"
    name: str | None = None
    ports: list[int] = Field(default_factory=list)
    command: list[str] = Field(default_factory=lambda: ["sleep", "infinity"])
    workspace_dir: Path = Field(default_factory=lambda: Path(DEFAULT_CURRENT_PATH).resolve())
    read_only: bool = True
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    network_mode: str = "bridge"
    rootless: bool = True
    env: dict[str, str] = Field(default_factory=dict)
    timeout: float = 300.0


class SandboxInstance(BaseModel):
    """Persistent metadata record for a deployed sandbox container instance."""

    instance_id: str
    container_id: str
    name: str
    image: str
    status: SandboxStatus = SandboxStatus.PENDING
    port_bindings: list[PortBinding] = Field(default_factory=list)
    workspace_dir: str
    created_at: str
    uptime_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SandboxExecResult(BaseModel):
    """Result of command execution within an active sandbox container."""

    instance_id: str
    command: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0


__all__ = [
    "PortBinding",
    "SandboxDeployConfig",
    "SandboxExecResult",
    "SandboxInstance",
    "SandboxStatus",
]
