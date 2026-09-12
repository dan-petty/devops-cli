"""Data models and schemas for workload sandbox lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

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

    @field_validator("container_port", "host_port")
    @classmethod
    def validate_port_bounds(cls, v: int) -> int:
        """Ensure port is within valid TCP/UDP port range 1-65535."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v


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

    @field_validator("network_mode")
    @classmethod
    def validate_network_mode(cls, v: str) -> str:
        """Reject host networking to preserve container network namespace isolation."""
        clean = v.strip().lower()
        if clean == "host":
            raise ValueError(
                "Network mode 'host' violates sandbox network namespace isolation and conflicts with port mapping; only 'bridge' or 'none' allowed."
            )
        if clean not in ("bridge", "none"):
            raise ValueError(f"Unsupported network mode '{v}'; only 'bridge' or 'none' permitted.")
        return clean

    @field_validator("read_only")
    @classmethod
    def validate_read_only(cls, v: bool) -> bool:
        """Enforce mandatory read-only root filesystem for containment boundary."""
        if not v:
            raise ValueError(
                "Sandboxes strictly require a read-only root filesystem for containment integrity."
            )
        return v

    @field_validator("ports")
    @classmethod
    def validate_container_ports(cls, v: list[int]) -> list[int]:
        """Validate all requested container ports are within valid port boundaries."""
        for p in v:
            if not (1 <= p <= 65535):
                raise ValueError(f"Container port must be between 1 and 65535, got {p}")
        return v


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


class ProbeProtocol(StrEnum):
    """Supported network protocols for endpoint readiness and health probing."""

    TCP = "tcp"
    HTTP = "http"
    OPENAPI = "openapi"
    GRPC = "grpc"


class ProbeStatus(StrEnum):
    """Outcome status for individual probes and aggregated report."""

    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class EndpointProbeResult(BaseModel):
    """Individual probe outcome for a specific target endpoint and protocol."""

    protocol: ProbeProtocol
    target: str
    status: ProbeStatus
    latency_ms: float = 0.0
    status_code: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SandboxProbeReport(BaseModel):
    """Aggregated health and readiness report for a sandbox or target."""

    instance_id: str | None = None
    target: str
    overall_status: ProbeStatus
    total_probes: int = 0
    passed_probes: int = 0
    failed_probes: int = 0
    duration_seconds: float = 0.0
    results: list[EndpointProbeResult] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


__all__ = [
    "EndpointProbeResult",
    "PortBinding",
    "ProbeProtocol",
    "ProbeStatus",
    "SandboxDeployConfig",
    "SandboxExecResult",
    "SandboxInstance",
    "SandboxProbeReport",
    "SandboxStatus",
]
