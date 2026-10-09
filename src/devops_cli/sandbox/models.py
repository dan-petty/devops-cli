"""Data models and schemas for workload sandbox lifecycle management."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from devops_cli.config.constants import (
    CONST_HOST_SANDBOX_DEFAULT_ENV,
    CONST_HOST_SANDBOX_SYSTEM_DIRS,
    CONST_HOST_SANDBOX_SYSTEM_SYMLINKS,
    CONST_OTEL_COLLECTOR_NAMESPACE,
    CONST_OTEL_COLLECTOR_POD_LABELS,
    CONST_OTEL_OTLP_GRPC_PORT,
    CONST_OTEL_OTLP_HTTP_PORT,
    CONST_SANDBOX_COLLECTOR_LANE_MODES,
    CONST_SANDBOX_NETWORK_BRIDGE,
    CONST_SANDBOX_NETWORK_ISOLATED,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    CONST_SANDBOX_NETWORK_MODE_ALIASES,
    CONST_SANDBOX_NETWORK_MODES,
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    CONST_SANDBOX_WHITELIST_DEFAULT_PORTS,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SANDBOX_CPUS,
    DEFAULT_SANDBOX_IMAGE,
    DEFAULT_SANDBOX_MEMORY,
    DEFAULT_SANDBOX_NAME,
    DEFAULT_SANDBOX_NAMESPACE,
    DEFAULT_SANDBOX_PIDS_LIMIT,
)
from devops_cli.core.validation import (
    is_cloud_metadata_host,
    is_loopback_or_private_host,
    is_non_public_ip,
)


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


def _ip_entry_host(entry: str) -> str | None:
    """The address or CIDR a whitelist entry is, or None when it is neither."""
    try:
        ip = ipaddress.ip_address(entry)
        return str(ip)
    except ValueError:
        pass
    try:
        net = ipaddress.ip_network(entry, strict=False)
        return str(net)
    except ValueError:
        return None


def _parse_whitelist_entry(entry: str) -> tuple[str, int]:
    """The host a whitelist entry names and the one TCP port it opens there.

    An IP address or CIDR, IPv6 included (which takes no port suffix), opens 443. Otherwise the
    entry is `scheme://host:port[/path]`, `host:port` or `[v6]:port`; without a port, `https` and
    no scheme open 443 and `http` 80, and any other scheme is refused. A port must be 1-65535,
    and an entry without a scheme cannot carry a path, which is how `140.82.112.0/20:8443` would
    otherwise be read as one address on 443.
    """
    clean = entry.strip()
    ip_host = _ip_entry_host(clean)
    if ip_host is not None:
        return ip_host, CONST_SANDBOX_WHITELIST_DEFAULT_PORTS[""]

    from devops_cli.http.urls import read_url_or_authority

    parts = read_url_or_authority(clean)
    if parts is None or not parts.hostname:
        raise ValueError(f"Whitelist entry '{entry}' names no host.")

    host = parts.hostname
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"Whitelist entry '{entry}' is not a host, URL or CIDR: {exc}") from exc

    if not parts.scheme and (parts.path or parts.query or parts.fragment):
        raise ValueError(
            f"Whitelist entry '{entry}' has a path but no scheme; write host:port, or a URL."
        )
    if port == 0:
        raise ValueError(f"Whitelist entry '{entry}' names port 0; a port must be 1-65535.")
    if port is None and parts.scheme not in CONST_SANDBOX_WHITELIST_DEFAULT_PORTS:
        raise ValueError(
            f"Whitelist entry '{entry}' uses scheme '{parts.scheme}', which has no default port; "
            "name the port."
        )
    return host, port or CONST_SANDBOX_WHITELIST_DEFAULT_PORTS[parts.scheme]


def _is_forbidden_local_ip(
    ip_obj: (
        ipaddress.IPv4Address
        | ipaddress.IPv6Address
        | ipaddress.IPv4Network
        | ipaddress.IPv6Network
    ),
) -> bool:
    """Return whether an IP address or network is link-local metadata forbidden in local whitelist."""
    return is_cloud_metadata_host(ip_obj, resolve_dns=False)


def _is_private_or_loopback(
    ip_obj: (
        ipaddress.IPv4Address
        | ipaddress.IPv6Address
        | ipaddress.IPv4Network
        | ipaddress.IPv6Network
    ),
) -> bool:
    """Return whether an IP address or network is private or loopback."""
    return ip_obj.is_private or ip_obj.is_loopback


def _validate_public_whitelist_item(item: str) -> None:
    """Ensure public whitelist entry does not resolve to private IP, loopback, or metadata."""
    host, _port = _parse_whitelist_entry(item)
    if is_loopback_or_private_host(host, resolve_dns=True):
        raise ValueError(
            f"Public whitelist entry '{item}' (host '{host}') cannot be private, loopback, or metadata."
        )


def _validate_local_whitelist_item(item: str) -> None:
    """Ensure local whitelist entry targets local/private endpoints and not link-local metadata."""
    host, _port = _parse_whitelist_entry(item)
    if is_cloud_metadata_host(host, resolve_dns=False):
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


def _build_collector_egress_rule() -> dict[str, Any]:
    """Build the egress rule to the OTel collector's pods, by namespace and pod labels, on OTLP."""
    return {
        "to": [
            {
                "namespaceSelector": {
                    "matchLabels": {"kubernetes.io/metadata.name": CONST_OTEL_COLLECTOR_NAMESPACE}
                },
                "podSelector": {"matchLabels": dict(CONST_OTEL_COLLECTOR_POD_LABELS)},
            }
        ],
        "ports": [
            {"protocol": "TCP", "port": CONST_OTEL_OTLP_GRPC_PORT},
            {"protocol": "TCP", "port": CONST_OTEL_OTLP_HTTP_PORT},
        ],
    }


def _resolve_public_dns(host: str) -> list[str]:
    """Resolve public domain name via DNS to validated public CIDRs."""
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
        if is_cloud_metadata_host(ip_obj, resolve_dns=False):
            raise ValueError(
                f"Public whitelist domain '{host}' resolves to cloud metadata address '{ip_str}'."
            )
        if is_non_public_ip(ip_obj):
            raise ValueError(
                f"Public whitelist domain '{host}' resolves to non-public address '{ip_str}'."
            )
        cidrs.append(ipaddress.ip_network(ip_obj).with_prefixlen)
    return cidrs


def _resolve_public_host(host: str) -> list[str]:
    """Resolve public host/domain to validated public IPv4/IPv6 address strings."""
    try:
        ip_net = ipaddress.ip_network(host, strict=False)
    except ValueError:
        return _resolve_public_dns(host)
    if is_cloud_metadata_host(ip_net, resolve_dns=False):
        raise ValueError(f"Public whitelist entry resolves to cloud metadata: {ip_net}")
    if is_non_public_ip(ip_net):
        raise ValueError(f"Public whitelist entry resolves to non-public network: {ip_net}")
    return [ip_net.with_prefixlen]


def _resolve_local_dns(host: str) -> list[str]:
    """Resolve local domain name via DNS to validated private/loopback CIDRs."""
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
        if _is_forbidden_local_ip(ip_obj):
            raise ValueError(
                f"Local whitelist hostname '{host}' resolves to forbidden link-local '{ip_str}'."
            )
        if not _is_private_or_loopback(ip_obj):
            raise ValueError(
                f"Local whitelist hostname '{host}' resolves to non-private address '{ip_str}'."
            )
        cidrs.append(ipaddress.ip_network(ip_obj).with_prefixlen)
    return cidrs


def _resolve_local_host(host: str) -> list[str]:
    """Resolve local host/domain to validated private/loopback IPv4/IPv6 address strings."""
    if host in ("localhost", "host.docker.internal"):
        return ["127.0.0.1/32"]
    if is_cloud_metadata_host(host, resolve_dns=False):
        raise ValueError(f"Link-local cloud metadata '{host}' is forbidden in local whitelist.")
    try:
        ip_net = ipaddress.ip_network(host, strict=False)
    except ValueError:
        return _resolve_local_dns(host)
    if _is_forbidden_local_ip(ip_net):
        raise ValueError(f"Link-local cloud metadata '{host}' is forbidden in local whitelist.")
    if not _is_private_or_loopback(ip_net):
        raise ValueError(f"Local whitelist entry '{host}' must be a private or loopback IP.")
    return [ip_net.with_prefixlen]


def _build_whitelist_egress(
    entries: list[str], resolve_host: Callable[[str], list[str]]
) -> list[dict[str, Any]]:
    """Build the kube-dns rule, then one rule per entry: its resolved addresses on its own port.

    Entries never share a rule, so no address is opened on another entry's port.
    """
    rules = [_build_dns_egress_rule()]
    for entry in entries:
        host, port = _parse_whitelist_entry(entry)
        rules.append(
            {
                "to": [{"ipBlock": {"cidr": cidr}} for cidr in resolve_host(host)],
                "ports": [{"protocol": "TCP", "port": port}],
            }
        )
    return rules


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

    def _k8s_ingress_and_egress(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """The NetworkPolicy ingress and egress rules of the network mode."""
        if self.mode == SandboxNetworkMode.ISOLATED:
            return [], []
        if self.mode == SandboxNetworkMode.SANDBOX_NAMESPACE:
            return [{"from": [{"podSelector": {}}]}], [
                {"to": [{"podSelector": {}}]},
                _build_dns_egress_rule(),
            ]
        if self.mode == SandboxNetworkMode.PUBLIC_WHITELIST:
            return [], _build_whitelist_egress(self.public_whitelist, _resolve_public_host)
        if self.mode == SandboxNetworkMode.LOCAL_WHITELIST:
            return [], _build_whitelist_egress(self.local_whitelist, _resolve_local_host)
        return [{"from": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}], [
            {"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}
        ]

    def to_k8s_network_policy(
        self,
        name: str = DEFAULT_SANDBOX_NAME,
        namespace: str | None = None,
        *,
        allow_collector: bool = False,
    ) -> dict[str, Any]:
        """Synthesize declarative Kubernetes NetworkPolicy manifest matching the network mode.

        `allow_collector` adds the egress rule to the OTel collector, in the modes that have
        egress rules to add it to.
        """
        if allow_collector and self.mode not in CONST_SANDBOX_COLLECTOR_LANE_MODES:
            raise ValueError(
                f"The collector lane applies only to network modes "
                f"{', '.join(CONST_SANDBOX_COLLECTOR_LANE_MODES)}, not '{self.mode.value}'."
            )
        ingress, egress = self._k8s_ingress_and_egress()
        if allow_collector:
            egress.append(_build_collector_egress_rule())
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{name}-network-policy",
                "namespace": namespace or self.sandbox_namespace,
            },
            "spec": {
                "podSelector": {"matchLabels": {"app.kubernetes.io/name": name}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": ingress,
                "egress": egress,
            },
        }


class SandboxPolicy(BaseModel):
    """Frozen declarative security policy for container and host sandbox isolation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges:true",)
    pids_limit: int = DEFAULT_SANDBOX_PIDS_LIMIT
    read_only: bool = True
    tmpfs: dict[str, str] = Field(
        default_factory=lambda: {"/tmp": "size=64m,noexec"}  # nosec B108
    )
    system_dirs: tuple[str, ...] = CONST_HOST_SANDBOX_SYSTEM_DIRS
    system_symlinks: tuple[str, ...] = CONST_HOST_SANDBOX_SYSTEM_SYMLINKS
    default_env: tuple[tuple[str, str], ...] = CONST_HOST_SANDBOX_DEFAULT_ENV
    forbidden_env_keys: frozenset[str] = frozenset()

    def to_docker_security_kwargs(self, read_only: bool | None = None) -> dict[str, Any]:
        """Render identical security options for Docker container creation."""
        effective_ro = self.read_only if read_only is None else read_only
        return {
            "cap_drop": list(self.cap_drop),
            "security_opt": list(self.security_opt),
            "pids_limit": self.pids_limit,
            "read_only": effective_ro,
            "tmpfs": dict(self.tmpfs),
        }

    def declared_security_summary(self, read_only: bool | None = None) -> dict[str, Any]:
        """Render declared security control dictionary for dry-run rendering and audit."""
        return self.to_docker_security_kwargs(read_only=read_only)


DEFAULT_SANDBOX_POLICY: Final[SandboxPolicy] = SandboxPolicy()


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
    policy: SandboxPolicy = Field(default_factory=lambda: DEFAULT_SANDBOX_POLICY)
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
