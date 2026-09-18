"""Data models and schemas for workload sandbox lifecycle management."""

from __future__ import annotations

import ipaddress
import socket
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_BRIDGE,
    CONST_SANDBOX_NETWORK_ISOLATED,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    CONST_SANDBOX_NETWORK_MODE_ALIASES,
    CONST_SANDBOX_NETWORK_MODES,
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SANDBOX_CPUS,
    DEFAULT_SANDBOX_IMAGE,
    DEFAULT_SANDBOX_MEMORY,
    DEFAULT_SANDBOX_NAME,
    DEFAULT_SANDBOX_NAMESPACE,
)
from devops_cli.core.validation import is_loopback_or_private_host


class SandboxStatus(StrEnum):
    """Lifecycle status states for workload sandbox containers."""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class SandboxNetworkMode(StrEnum):
    """Multi-tier network modes for workload sandbox isolation and access control."""

    ISOLATED = CONST_SANDBOX_NETWORK_ISOLATED
    SANDBOX_NAMESPACE = CONST_SANDBOX_NETWORK_NAMESPACE
    PUBLIC_WHITELIST = CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST
    LOCAL_WHITELIST = CONST_SANDBOX_NETWORK_LOCAL_WHITELIST
    BRIDGE = CONST_SANDBOX_NETWORK_BRIDGE


def _extract_host_or_ip(endpoint: str) -> str:
    """Extract hostname, domain, or IP from a URL or bare endpoint string."""
    clean = endpoint.strip()
    if "://" in clean:
        parsed = urlparse(clean)
        return parsed.hostname or ""
    if "/" in clean:
        return clean.split("/")[0].strip()
    if ":" in clean and not clean.startswith("["):
        return clean.split(":")[0].strip()
    return clean.strip("[]")


def _validate_public_whitelist_item(item: str) -> None:
    """Ensure public whitelist entry does not resolve to private IP, loopback, or metadata."""
    host = _extract_host_or_ip(item)
    if not host:
        raise ValueError(f"Invalid public whitelist entry: '{item}'")
    if is_loopback_or_private_host(host, resolve_dns=True):
        raise ValueError(
            f"Public whitelist entry '{item}' (host '{host}') cannot be private, loopback, or metadata."
        )


def _validate_local_whitelist_item(item: str) -> None:
    """Ensure local whitelist entry targets local/private endpoints and not link-local metadata."""
    host = _extract_host_or_ip(item)
    if not host:
        raise ValueError(f"Invalid local whitelist entry: '{item}'")
    if host == "169.254.169.254" or host.startswith("169.254."):
        raise ValueError(
            f"Cloud metadata '{item}' is forbidden in local whitelist to mitigate SSRF."
        )
    if not is_loopback_or_private_host(host, resolve_dns=False) and host not in (
        "localhost",
        "host.docker.internal",
    ):
        raise ValueError(
            f"Local whitelist entry '{item}' (host '{host}') must resolve to a private or loopback destination."
        )


def _build_dns_egress_rule() -> dict[str, Any]:
    """Build standard CoreDNS port 53 UDP/TCP egress rule for Kubernetes NetworkPolicy."""
    return {
        "to": [
            {
                "namespaceSelector": {},
                "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
            }
        ],
        "ports": [
            {"protocol": "UDP", "port": 53},
            {"protocol": "TCP", "port": 53},
        ],
    }


def _resolve_public_host(host: str) -> list[str]:
    """Resolve public host/domain to validated public IPv4/IPv6 address strings."""
    try:
        ip_net = ipaddress.ip_network(host, strict=False)
        if (
            ip_net.is_private
            or ip_net.is_loopback
            or ip_net.is_link_local
            or ip_net.is_reserved
            or ip_net.is_multicast
        ):
            raise ValueError(f"Public whitelist entry resolves to non-public network: {ip_net}")
        return [str(ip_net) if "/" in host else f"{host}/32"]
    except ValueError as exc:
        if "non-public network" in str(exc):
            raise
    try:
        addr_info = socket.getaddrinfo(host, None)
        resolved_ips = {str(info[4][0]) for info in addr_info if len(info) >= 5}
    except OSError as exc:
        raise ValueError(f"Public whitelist domain '{host}' DNS resolution failed: {exc}") from exc
    if not resolved_ips:
        raise ValueError(f"Public whitelist domain '{host}' yielded no address records.")
    cidrs: list[str] = []
    for ip_str in sorted(resolved_ips):
        ip_obj = ipaddress.ip_address(ip_str)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        ):
            raise ValueError(
                f"Public whitelist domain '{host}' resolves to non-public address '{ip_str}'."
            )
        cidrs.append(f"{ip_str}/32")
    return cidrs


def _resolve_local_host(host: str) -> list[str]:
    """Resolve local host/domain to validated private/loopback IPv4/IPv6 address strings."""
    if host in ("localhost", "host.docker.internal"):
        return ["127.0.0.1/32"]
    try:
        ip_net = ipaddress.ip_network(host, strict=False)
        if ip_net.is_link_local or str(ip_net).startswith("169.254."):
            raise ValueError(f"Link-local cloud metadata '{host}' is forbidden in local whitelist.")
        if not (ip_net.is_private or ip_net.is_loopback):
            raise ValueError(f"Local whitelist entry '{host}' must be a private or loopback IP.")
        return [str(ip_net) if "/" in host else f"{host}/32"]
    except ValueError as exc:
        if "forbidden" in str(exc) or "must be a private" in str(exc):
            raise
    try:
        addr_info = socket.getaddrinfo(host, None)
        resolved_ips = {str(info[4][0]) for info in addr_info if len(info) >= 5}
    except OSError as exc:
        raise ValueError(f"Local whitelist hostname '{host}' DNS resolution failed: {exc}") from exc
    if not resolved_ips:
        raise ValueError(f"Local whitelist hostname '{host}' yielded no address records.")
    cidrs: list[str] = []
    for ip_str in sorted(resolved_ips):
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_link_local or ip_str.startswith("169.254."):
            raise ValueError(
                f"Local whitelist hostname '{host}' resolves to forbidden link-local '{ip_str}'."
            )
        if not (ip_obj.is_private or ip_obj.is_loopback):
            raise ValueError(
                f"Local whitelist hostname '{host}' resolves to non-private address '{ip_str}'."
            )
        cidrs.append(f"{ip_str}/32")
    return cidrs


def _build_public_whitelist_egress(whitelist: list[str]) -> list[dict[str, Any]]:
    """Build egress rules allowing public internet egress strictly to validated whitelisted destinations."""
    to_rules: list[dict[str, Any]] = []
    for item in whitelist:
        host = _extract_host_or_ip(item)
        if not host:
            continue
        for cidr in _resolve_public_host(host):
            to_rules.append({"ipBlock": {"cidr": cidr}})
    if not to_rules:
        raise ValueError("Public whitelist mode requires at least one valid public destination.")
    return [
        _build_dns_egress_rule(),
        {"to": to_rules},
    ]


def _build_local_whitelist_egress(whitelist: list[str]) -> list[dict[str, Any]]:
    """Build egress rules permitting specific local CIDRs, IPs, and endpoints."""
    to_rules: list[dict[str, Any]] = []
    for item in whitelist:
        host = _extract_host_or_ip(item)
        if not host:
            continue
        for cidr in _resolve_local_host(host):
            to_rules.append({"ipBlock": {"cidr": cidr}})
    if not to_rules:
        raise ValueError(
            "Local whitelist mode requires at least one valid local or private destination."
        )
    return [
        _build_dns_egress_rule(),
        {"to": to_rules},
    ]


class SandboxNetworkConfig(BaseModel):
    """Multi-tier network containment and routing configuration for sandbox workloads."""

    mode: SandboxNetworkMode = Field(default=SandboxNetworkMode.ISOLATED)
    public_whitelist: list[str] = Field(default_factory=list)
    local_whitelist: list[str] = Field(default_factory=list)
    egress_proxy: str | None = Field(
        default=None,
        description="Optional egress proxy URL for container containment in whitelist modes.",
    )
    sandbox_namespace: str = Field(default=DEFAULT_SANDBOX_NAMESPACE)

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: Any) -> SandboxNetworkMode:
        """Normalize string mode or user-friendly aliases into canonical SandboxNetworkMode enum."""
        if isinstance(v, SandboxNetworkMode):
            return v
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean == "host":
                raise ValueError(
                    "Network mode 'host' violates sandbox network namespace isolation; permitted modes: isolated, namespace, public_whitelist, local_whitelist, bridge."
                )
            if clean in CONST_SANDBOX_NETWORK_MODE_ALIASES:
                return SandboxNetworkMode(CONST_SANDBOX_NETWORK_MODE_ALIASES[clean])
            for mode_enum in SandboxNetworkMode:
                if mode_enum.value == clean:
                    return mode_enum
            raise ValueError(
                f"Unsupported sandbox network mode '{v}'. Permitted modes: {', '.join(sorted(CONST_SANDBOX_NETWORK_MODES))}"
            )
        return SandboxNetworkMode.ISOLATED

    @model_validator(mode="after")
    def validate_whitelists(self) -> SandboxNetworkConfig:
        """Validate required whitelist contents and enforce SSRF/metadata guards."""
        if self.mode == SandboxNetworkMode.PUBLIC_WHITELIST:
            if not self.public_whitelist:
                raise ValueError(
                    "Public whitelist mode requires at least one public domain or IP to be configured."
                )
            for item in self.public_whitelist:
                _validate_public_whitelist_item(item)
        elif self.mode == SandboxNetworkMode.LOCAL_WHITELIST:
            if not self.local_whitelist:
                raise ValueError(
                    "Local whitelist mode requires at least one local URL or IP to be configured."
                )
            for item in self.local_whitelist:
                _validate_local_whitelist_item(item)
        return self

    def to_docker_args(self) -> list[str]:
        """Generate Docker CLI arguments enforcing container network isolation or gateway routing."""
        if self.mode == SandboxNetworkMode.ISOLATED:
            return ["--network=none"]
        if self.mode == SandboxNetworkMode.SANDBOX_NAMESPACE:
            return [f"--network={CONST_SANDBOX_DOCKER_INTERNAL_NET}"]
        if self.mode in (SandboxNetworkMode.PUBLIC_WHITELIST, SandboxNetworkMode.LOCAL_WHITELIST):
            if self.egress_proxy:
                return [
                    f"--network={CONST_SANDBOX_DOCKER_INTERNAL_NET}",
                    "-e",
                    f"HTTP_PROXY={self.egress_proxy}",
                    "-e",
                    f"HTTPS_PROXY={self.egress_proxy}",
                    "-e",
                    f"ALL_PROXY={self.egress_proxy}",
                ]
            raise ValueError(
                f"Docker engine cannot enforce outbound egress boundaries for mode '{self.mode.value}' without an egress proxy; deploy via Kubernetes NetworkPolicy or configure egress_proxy."
            )
        return ["--network=bridge"]

    def to_k8s_network_policy(
        self, name: str = DEFAULT_SANDBOX_NAME, namespace: str | None = None
    ) -> dict[str, Any]:
        """Synthesize declarative Kubernetes NetworkPolicy manifest matching the network mode."""
        target_ns = namespace or self.sandbox_namespace
        policy: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{name}-network-policy",
                "namespace": target_ns,
            },
            "spec": {
                "podSelector": {"matchLabels": {"app.kubernetes.io/name": name}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [],
                "egress": [],
            },
        }

        if self.mode == SandboxNetworkMode.ISOLATED:
            return policy

        if self.mode == SandboxNetworkMode.SANDBOX_NAMESPACE:
            policy["spec"]["ingress"] = [{"from": [{"podSelector": {}}]}]
            policy["spec"]["egress"] = [
                {"to": [{"podSelector": {}}]},
                _build_dns_egress_rule(),
            ]
            return policy

        if self.mode == SandboxNetworkMode.PUBLIC_WHITELIST:
            policy["spec"]["egress"] = _build_public_whitelist_egress(self.public_whitelist)
            return policy

        if self.mode == SandboxNetworkMode.LOCAL_WHITELIST:
            policy["spec"]["egress"] = _build_local_whitelist_egress(self.local_whitelist)
            return policy

        policy["spec"]["ingress"] = [{"from": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]
        policy["spec"]["egress"] = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]
        return policy


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

    image: str = DEFAULT_SANDBOX_IMAGE
    name: str | None = None
    ports: list[int] = Field(default_factory=list)
    command: list[str] = Field(default_factory=lambda: ["sleep", "infinity"])
    workspace_dir: Path = Field(default_factory=lambda: Path(DEFAULT_CURRENT_PATH).resolve())
    read_only: bool = True
    memory_limit: str = DEFAULT_SANDBOX_MEMORY
    cpu_limit: float = DEFAULT_SANDBOX_CPUS
    network_config: SandboxNetworkConfig = Field(default_factory=SandboxNetworkConfig)
    network_mode: str = "none"
    public_whitelist: list[str] = Field(default_factory=list)
    local_whitelist: list[str] = Field(default_factory=list)
    rootless: bool = True
    env: dict[str, str] = Field(default_factory=dict)
    timeout: float = 300.0

    @model_validator(mode="before")
    @classmethod
    def sync_network_fields(cls, data: Any) -> Any:
        """Keep network_mode string and SandboxNetworkConfig model bidirectionally in sync."""
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

    @field_validator("network_mode")
    @classmethod
    def validate_network_mode(cls, v: str) -> str:
        """Reject host networking to preserve container network namespace isolation."""
        clean = v.strip().lower()
        if clean == "host":
            raise ValueError(
                "Network mode 'host' violates sandbox network namespace isolation; permitted modes: isolated, namespace, public_whitelist, local_whitelist, bridge."
            )
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

    @field_validator("stdout", "stderr", mode="before")
    @classmethod
    def sanitize_output(cls, v: Any) -> str:
        """Mask secrets in command execution stdout/stderr."""
        if not v:
            return ""
        from devops_cli.security.sanitizer import mask_secrets

        return mask_secrets(str(v))


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


def _sanitize_nested_detail(val: Any) -> Any:
    """Recursively mask secrets and truncate strings to <= 1024 chars."""
    if isinstance(val, str):
        from devops_cli.security.sanitizer import mask_secrets

        masked = mask_secrets(val)
        return masked[:1021] + "..." if len(masked) > 1024 else masked
    if isinstance(val, dict):
        return {str(k): _sanitize_nested_detail(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_sanitize_nested_detail(item) for item in val]
    return val


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

    @field_validator("details", mode="before")
    @classmethod
    def sanitize_and_truncate_details(cls, v: Any) -> dict[str, Any]:
        """Truncate large string details and mask secrets to prevent log bloat and leakage."""
        if not isinstance(v, dict):
            return {}
        return {str(k): _sanitize_nested_detail(val) for k, val in v.items()}


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
    archive_error: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def enforce_message_length_cap(cls, v: Any) -> str:
        """Cap incident message length to 256 chars and mask secrets to prevent leakage."""
        from devops_cli.security.sanitizer import mask_secrets

        text = mask_secrets(str(v)) if v else ""
        return text[:256] if len(text) > 256 else text

    @field_validator("stacktrace", mode="before")
    @classmethod
    def sanitize_stacktrace(cls, v: Any) -> list[str]:
        """Mask secrets in stacktrace lines."""
        if not isinstance(v, list):
            return []
        from devops_cli.security.sanitizer import mask_secrets

        return [mask_secrets(str(line)) for line in v]

    @field_validator("archived_path", "archive_error", mode="before")
    @classmethod
    def sanitize_archive_fields(cls, v: Any) -> str | None:
        """Mask secrets in archived paths or archive error strings."""
        if v is None:
            return None
        from devops_cli.security.sanitizer import mask_secrets

        return mask_secrets(str(v))


class SandboxLogLine(BaseModel):
    """Parsed single line of sandbox container log output."""

    timestamp: str | None = None
    stream: str = "stdout"
    content: str
    is_panic: bool = False
    panic_type: PanicType | None = None

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: Any) -> str:
        """Mask secrets in log line content to prevent sensitive credential leakage."""
        if not v:
            return ""
        from devops_cli.security.sanitizer import mask_secrets

        return mask_secrets(str(v))


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
    "SandboxNetworkConfig",
    "SandboxNetworkMode",
    "SandboxProbeReport",
    "SandboxStatus",
]
