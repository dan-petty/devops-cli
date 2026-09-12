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
    trace_id: str | None = None
    results: list[EndpointProbeResult] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class CgroupV2Metrics(BaseModel):
    """Container resource telemetry extracted from cgroup v2 controllers."""

    cpu_percent: float | None = None
    cpu_usage_usec: int = 0
    memory_current_bytes: int = 0
    memory_peak_bytes: int | None = None
    memory_limit_bytes: int | None = None
    memory_usage_percent: float | None = None
    page_faults_total: int = 0
    pids_current: int = 0
    open_fds_count: int | None = None
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0

    @property
    def memory_current_mb(self) -> float:
        """Return current memory consumption in megabytes."""
        return round(self.memory_current_bytes / (1024 * 1024), 2)

    @property
    def memory_limit_mb(self) -> float | None:
        """Return configured memory limit in megabytes if bounded."""
        return (
            round(self.memory_limit_bytes / (1024 * 1024), 2)
            if self.memory_limit_bytes is not None
            else None
        )


class PrometheusMetric(BaseModel):
    """Single Prometheus metric sample with labels and value."""

    name: str
    metric_type: str = "untyped"
    labels: dict[str, str] = Field(default_factory=dict)
    value: float = 0.0
    timestamp: str | None = None


class SandboxMetricsSnapshot(BaseModel):
    """Point-in-time container resource telemetry and application metrics snapshot."""

    instance_id: str | None = None
    target: str
    cgroup: CgroupV2Metrics | None = None
    prometheus_metrics: list[PrometheusMetric] = Field(default_factory=list)
    scrape_error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_healthy(self) -> bool:
        """Check if snapshot has no threshold warnings or scrape errors."""
        if self.scrape_error is not None:
            return False
        return len(self.warnings) == 0


class PanicType(StrEnum):
    """Categorization of detected runtime crashes, panics, and stacktraces."""

    PYTHON_TRACEBACK = "python_traceback"
    GO_PANIC = "go_panic"
    JAVA_STACKTRACE = "java_stacktrace"
    RUST_PANIC = "rust_panic"
    SEGFAULT = "segfault"
    UNKNOWN = "unknown"


class PanicIncident(BaseModel):
    """Structured diagnostic incident record captured from workload container logs."""

    incident_id: str
    instance_id: str
    container_id: str
    panic_type: PanicType
    message: str
    stacktrace: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    log_stream: str = "stderr"
    archived_path: str | None = None

    @field_validator("message")
    @classmethod
    def enforce_message_length_cap(cls, v: str) -> str:
        """Cap incident message length to 256 chars to prevent log bloat and injection."""
        return v[:256] if len(v) > 256 else v


class SandboxLogLine(BaseModel):
    """Parsed single line of sandbox container log output."""

    timestamp: str | None = None
    stream: str = "stdout"
    content: str
    is_panic: bool = False
    panic_type: PanicType | None = None


class SandboxLogsReport(BaseModel):
    """Aggregated container logs, statistics, and detected panic incident collection."""

    instance_id: str
    container_id: str
    total_lines: int = 0
    panics_detected: int = 0
    incidents: list[PanicIncident] = Field(default_factory=list)
    lines: list[SandboxLogLine] = Field(default_factory=list)


__all__ = [
    "CgroupV2Metrics",
    "EndpointProbeResult",
    "PanicIncident",
    "PanicType",
    "PortBinding",
    "ProbeProtocol",
    "ProbeStatus",
    "PrometheusMetric",
    "SandboxDeployConfig",
    "SandboxExecResult",
    "SandboxInstance",
    "SandboxLogLine",
    "SandboxLogsReport",
    "SandboxMetricsSnapshot",
    "SandboxProbeReport",
    "SandboxStatus",
]
