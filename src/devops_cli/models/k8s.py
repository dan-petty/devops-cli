"""Pydantic resource models for Kubernetes subsystem operations and CLI functions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from devops_cli.config.constants import (
    CONST_FALCO_SEVERITY_LEVELS,
    CONST_K8S_CONDITION_INITIALIZED,
    CONST_K8S_CONDITION_READY,
    CONST_K8S_CONDITION_SCHEDULED,
    CONST_K8S_CONDITION_TRUE,
    CONST_K8S_CONTAINER_RUNNING,
    CONST_K8S_CONTAINER_TERMINATED,
    CONST_K8S_CONTAINER_WAITING,
    CONST_K8S_DEFAULT_CONTAINER_ANNOTATION,
    CONST_K8S_EXIT_CODE_STATUS_PREFIX,
    CONST_K8S_HEALTHY_POD_STATUSES,
    CONST_K8S_INIT_STATUS_PREFIX,
    CONST_K8S_POD_COMPLETED,
    CONST_K8S_POD_INITIALIZING,
    CONST_K8S_POD_NOT_READY,
    CONST_K8S_POD_REASON_NODE_LOST,
    CONST_K8S_POD_REASON_SCHEDULING_GATED,
    CONST_K8S_POD_RUNNING,
    CONST_K8S_POD_TERMINAL_PHASES,
    CONST_K8S_POD_TERMINATING,
    CONST_K8S_POD_UNKNOWN,
    CONST_K8S_RESTART_POLICY_ALWAYS,
    CONST_K8S_SIGNAL_STATUS_PREFIX,
    CONST_MAX_SECURITY_STREAM_DURATION,
    CONST_MAX_SECURITY_STREAM_TAIL_LINES,
    CONST_MIN_SECURITY_STREAM_DURATION,
    CONST_MIN_SECURITY_STREAM_TAIL_LINES,
)
from devops_cli.config.defaults import (
    DEFAULT_SECURITY_STREAM_DURATION_SECONDS,
    DEFAULT_SECURITY_STREAM_TAIL_LINES,
)
from devops_cli.dry_run.requests import PlannedRequest

# =============================================================================
# Pod Status
# =============================================================================
#
# A port of the STATUS, READY and RESTARTS columns of kubectl's `printPod`
# (k8s.io/kubernetes pkg/printers/internalversion/printers.go). The phase alone hides
# failures: a container crashlooping in a pod whose phase is still Running reads as
# Running. The helpers below read the SDK's objects attribute by attribute, so a pod
# missing an optional field reads as kubectl reads it rather than raising.


class _InitProgress(NamedTuple):
    """How far a pod's init containers got: the status they impose, if any, and counts."""

    status: str | None
    ready: int
    restarts: int
    sidecar_restarts: int


class _AppProgress(NamedTuple):
    """What a pod's app containers say: the status, and ready and restart counts."""

    status: str
    ready: int
    restarts: int
    running: bool


def _items(value: Any) -> list[Any]:
    """Return a list field, treating an unset one as empty."""
    return list(value or [])


def _text(obj: Any, field: str) -> str:
    """Return a string field, treating an unset one as empty."""
    return str(getattr(obj, field, None) or "")


def _restarts(status: Any) -> int:
    """Return a container status's restart count."""
    return int(getattr(status, "restart_count", 0) or 0)


def _condition_true(object_status: Any, kind: str) -> bool:
    """Report whether a pod or node condition of this type is met."""
    return any(
        getattr(condition, "type", None) == kind
        and getattr(condition, "status", None) == CONST_K8S_CONDITION_TRUE
        for condition in _items(getattr(object_status, "conditions", None))
    )


def node_is_ready(node: Any) -> bool:
    """Report whether a node's Ready condition is True, as `kubectl get nodes` reads it."""
    return _condition_true(getattr(node, "status", None), CONST_K8S_CONDITION_READY)


def _is_restartable(container: Any) -> bool:
    """Report whether an init container is a sidecar, which keeps running beside the app."""
    return getattr(container, "restart_policy", None) == CONST_K8S_RESTART_POLICY_ALWAYS


def _terminated_reason(terminated: Any) -> str:
    """Name a termination by its reason, or else by its signal or exit code."""
    reason = getattr(terminated, "reason", None)
    if reason:
        return str(reason)
    signal = getattr(terminated, "signal", None)
    if signal:
        return f"{CONST_K8S_SIGNAL_STATUS_PREFIX}{signal}"
    return f"{CONST_K8S_EXIT_CODE_STATUS_PREFIX}{getattr(terminated, 'exit_code', 0)}"


def _pod_reason(pod_status: Any) -> str:
    """Start from the pod's reason, such as Evicted, or else its phase."""
    reason = getattr(pod_status, "reason", None) or getattr(pod_status, "phase", None) or ""
    gated = any(
        getattr(condition, "type", None) == CONST_K8S_CONDITION_SCHEDULED
        and getattr(condition, "reason", None) == CONST_K8S_POD_REASON_SCHEDULING_GATED
        for condition in _items(getattr(pod_status, "conditions", None))
    )
    return CONST_K8S_POD_REASON_SCHEDULING_GATED if gated else str(reason)


def _init_reason(status: Any, index: int, total: int) -> str:
    """Name the init container a pod is stuck on, or how many of them have finished."""
    state = getattr(status, "state", None)
    terminated = getattr(state, "terminated", None)
    if terminated is not None:
        return f"{CONST_K8S_INIT_STATUS_PREFIX}{_terminated_reason(terminated)}"
    waiting_reason = getattr(getattr(state, "waiting", None), "reason", None)
    if waiting_reason and waiting_reason != CONST_K8S_POD_INITIALIZING:
        return f"{CONST_K8S_INIT_STATUS_PREFIX}{waiting_reason}"
    return f"{CONST_K8S_INIT_STATUS_PREFIX}{index}/{total}"


def _walk_init_containers(specs: list[Any], statuses: list[Any]) -> _InitProgress:
    """Check the init containers in order, stopping at the first that has not finished.

    One that exited 0 is done, and so is a sidecar that has started: it counts toward
    READY instead.
    """
    sidecars = {getattr(spec, "name", None) for spec in specs if _is_restartable(spec)}
    ready = restarts = sidecar_restarts = 0
    for index, status in enumerate(statuses):
        count = _restarts(status)
        restarts += count
        sidecar = getattr(status, "name", None) in sidecars
        sidecar_restarts += count if sidecar else 0
        terminated = getattr(getattr(status, "state", None), "terminated", None)
        if terminated is not None and getattr(terminated, "exit_code", None) == 0:
            continue
        if sidecar and getattr(status, "started", None):
            ready += bool(getattr(status, "ready", False))
            continue
        status_text = _init_reason(status, index, len(specs))
        return _InitProgress(status_text, ready, restarts, sidecar_restarts)
    return _InitProgress(None, ready, restarts, sidecar_restarts)


def _stopped_reason(state: Any) -> str | None:
    """Return the reason a waiting or terminated container gives, or None if running."""
    waiting_reason = getattr(getattr(state, "waiting", None), "reason", None)
    if waiting_reason:
        return str(waiting_reason)
    terminated = getattr(state, "terminated", None)
    return _terminated_reason(terminated) if terminated is not None else None


def _walk_app_containers(statuses: list[Any], reason: str) -> _AppProgress:
    """Check the app containers last to first: a waiting or terminated reason wins."""
    ready = restarts = 0
    running = False
    for status in reversed(statuses):
        restarts += _restarts(status)
        state = getattr(status, "state", None)
        stopped = _stopped_reason(state)
        if stopped is not None:
            reason = stopped
        elif getattr(status, "ready", False) and getattr(state, "running", None) is not None:
            running = True
            ready += 1
    return _AppProgress(reason, ready, restarts, running)


def _settled_status(pod_status: Any, app: _AppProgress) -> str:
    """A pod whose finished container sits beside a running one is Running or NotReady."""
    if app.status != CONST_K8S_POD_COMPLETED or not app.running:
        return app.status
    if _condition_true(pod_status, CONST_K8S_CONDITION_READY):
        return CONST_K8S_POD_RUNNING
    return CONST_K8S_POD_NOT_READY


def _deleted_status(pod: Any, status: str) -> str:
    """A pod being deleted is Terminating, or Unknown when its node was lost."""
    if getattr(getattr(pod, "metadata", None), "deletion_timestamp", None) is None:
        return status
    pod_status = getattr(pod, "status", None)
    if getattr(pod_status, "reason", None) == CONST_K8S_POD_REASON_NODE_LOST:
        return CONST_K8S_POD_UNKNOWN
    if getattr(pod_status, "phase", None) in CONST_K8S_POD_TERMINAL_PHASES:
        return status
    return CONST_K8S_POD_TERMINATING


def _pod_status(pod: Any) -> tuple[str, int, int]:
    """Return the STATUS, ready container count and RESTARTS kubectl prints for a pod."""
    spec, pod_status = getattr(pod, "spec", None), getattr(pod, "status", None)
    init = _walk_init_containers(
        _items(getattr(spec, "init_containers", None)),
        _items(getattr(pod_status, "init_container_statuses", None)),
    )
    status, ready, restarts = init.status or _pod_reason(pod_status), init.ready, init.restarts
    if init.status is None or _condition_true(pod_status, CONST_K8S_CONDITION_INITIALIZED):
        app = _walk_app_containers(_items(getattr(pod_status, "container_statuses", None)), status)
        status = _settled_status(pod_status, app)
        ready, restarts = ready + app.ready, init.sidecar_restarts + app.restarts
    return _deleted_status(pod, status), ready, restarts


# =============================================================================
# Containers
# =============================================================================


def _container_state(state: Any) -> tuple[str, str]:
    """Name a container's current state and the reason it gives, if any."""
    if getattr(state, "running", None) is not None:
        return CONST_K8S_CONTAINER_RUNNING, ""
    waiting = getattr(state, "waiting", None)
    if waiting is not None:
        return CONST_K8S_CONTAINER_WAITING, _text(waiting, "reason")
    terminated = getattr(state, "terminated", None)
    if terminated is not None:
        return CONST_K8S_CONTAINER_TERMINATED, _terminated_reason(terminated)
    return "", ""


class ContainerInfo(BaseModel):
    """One container of a pod, from its spec and the status the kubelet reports for it."""

    name: str = Field(..., description="Container name")
    image: str = Field(default="", description="Image the container runs")
    ready: bool = Field(default=False, description="Whether the container passes readiness")
    restarts: int = Field(default=0, description="Restarts of this container")
    state: str = Field(
        default="", description="Running, Waiting or Terminated; empty before it is reported"
    )
    reason: str = Field(default="", description="Reason the current state gives")
    last_termination_reason: str = Field(
        default="", description="Reason the previous run of the container ended"
    )
    last_exit_code: int | None = Field(
        default=None, description="Exit code of the previous run of the container"
    )
    restartable: bool = Field(
        default=False, description="Whether this is an init container kept running as a sidecar"
    )

    @classmethod
    def from_spec(cls, spec: Any, status: Any) -> ContainerInfo:
        """Describe a container from its spec and its status, which may not exist yet."""
        state, reason = _container_state(getattr(status, "state", None))
        last = getattr(getattr(status, "last_state", None), "terminated", None)
        return cls(
            name=str(getattr(spec, "name", "")),
            image=str(getattr(spec, "image", None) or getattr(status, "image", None) or ""),
            ready=bool(getattr(status, "ready", False)),
            restarts=_restarts(status),
            state=state,
            reason=reason,
            last_termination_reason=_text(last, "reason"),
            last_exit_code=getattr(last, "exit_code", None),
            restartable=_is_restartable(spec),
        )


def _containers(specs: list[Any], statuses: list[Any]) -> list[ContainerInfo]:
    """Describe each container in spec order, matching its status by name."""
    by_name = {getattr(status, "name", None): status for status in statuses}
    return [
        ContainerInfo.from_spec(spec, by_name.get(getattr(spec, "name", None))) for spec in specs
    ]


def _default_container(pod: Any, names: list[str]) -> str:
    """Pick the container kubectl reads logs from: the annotated one, else the first."""
    annotations = getattr(getattr(pod, "metadata", None), "annotations", None) or {}
    annotated = annotations.get(CONST_K8S_DEFAULT_CONTAINER_ANNOTATION)
    if annotated in names:
        return str(annotated)
    return names[0] if names else ""


def _age_seconds(created: Any) -> int:
    """Return the seconds since a timestamp, or 0 when there is none."""
    if not isinstance(created, datetime):
        return 0
    return max(0, int((datetime.now(created.tzinfo) - created).total_seconds()))


class PodInfo(BaseModel):
    """Information for a Kubernetes Pod."""

    name: str = Field(..., description="Pod name")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    status: str = Field(
        default="Unknown",
        description="The STATUS kubectl prints (Running, CrashLoopBackOff, Init:0/2, ...)",
    )
    ready_containers: str = Field(default="0/0", description="Fraction of ready containers")
    restart_count: int = Field(default=0, description="Total container restarts count")
    node_name: str | None = Field(default=None, description="Assigned Kubernetes node name")
    ip_address: str | None = Field(default=None, description="Assigned Pod IP address")
    age_seconds: int = Field(default=0, description="Pod uptime in seconds")
    uid: str = Field(default="", description="Pod uid, which tells apart pods of one name")
    containers: list[ContainerInfo] = Field(default_factory=list, description="App containers")
    init_containers: list[ContainerInfo] = Field(
        default_factory=list, description="Init containers, sidecars included"
    )
    default_container: str = Field(
        default="", description="The container `kubectl logs` reads when none is named"
    )
    unhealthy: bool = Field(
        default=False, description="Whether the status or a short READY count needs attention"
    )

    @classmethod
    def from_pod(cls, pod: Any) -> PodInfo:
        """Describe a pod from the Kubernetes API, with the STATUS and READY kubectl prints.

        READY counts ready containers over the containers in the spec, sidecars included in
        both, so a pod still creating its one container reads 0/1 rather than 0/0.
        """
        metadata, spec = getattr(pod, "metadata", None), getattr(pod, "spec", None)
        pod_status = getattr(pod, "status", None)
        status, ready, restarts = _pod_status(pod)
        init_specs = _items(getattr(spec, "init_containers", None))
        containers = _containers(
            _items(getattr(spec, "containers", None)),
            _items(getattr(pod_status, "container_statuses", None)),
        )
        total = len(containers) + sum(map(_is_restartable, init_specs))
        created = getattr(metadata, "creation_timestamp", None)
        return cls(
            name=_text(metadata, "name"),
            namespace=_text(metadata, "namespace") or "default",
            uid=_text(metadata, "uid"),
            status=status,
            ready_containers=f"{ready}/{total}",
            restart_count=restarts,
            node_name=getattr(spec, "node_name", None),
            ip_address=getattr(pod_status, "pod_ip", None),
            age_seconds=_age_seconds(created),
            containers=containers,
            init_containers=_containers(
                init_specs, _items(getattr(pod_status, "init_container_statuses", None))
            ),
            default_container=_default_container(pod, [c.name for c in containers]),
            unhealthy=status not in CONST_K8S_HEALTHY_POD_STATUSES
            or (status == CONST_K8S_POD_RUNNING and ready < total),
        )


class PodEventInfo(BaseModel):
    """One Kubernetes event about a pod, as the pod inspector lists it."""

    type: str = Field(default="", description="Normal or Warning")
    reason: str = Field(default="", description="Short machine-readable reason")
    message: str = Field(default="", description="What the reporting component said")
    count: int = Field(default=1, description="How many times the event occurred")
    last_seen: datetime | None = Field(default=None, description="When it last occurred")

    @classmethod
    def from_event(cls, event: Any) -> PodEventInfo:
        """Read an event, whichever API wrote it.

        An event written through events.k8s.io/v1 leaves `last_timestamp` and `count`
        empty and sets `event_time` and `series` instead, so each is read in turn.
        """
        seen = (
            getattr(event, "last_timestamp", None)
            or getattr(event, "event_time", None)
            or getattr(event, "first_timestamp", None)
            or getattr(getattr(event, "metadata", None), "creation_timestamp", None)
        )
        count = (
            getattr(event, "count", None)
            or getattr(getattr(event, "series", None), "count", None)
            or 1
        )
        return cls(
            type=_text(event, "type"),
            reason=_text(event, "reason"),
            message=_text(event, "message"),
            count=int(count),
            last_seen=seen if isinstance(seen, datetime) else None,
        )


class K8sPodsRequest(BaseModel):
    """Request parameters for querying Kubernetes Pods."""

    namespace: str = Field(default="", description="Namespace filter (empty for all namespaces)")
    label_selector: str = Field(default="", description="Kubernetes label selector filter")
    field_selector: str = Field(default="", description="Kubernetes field selector filter")


class K8sPodsResult(BaseModel):
    """Result payload for Kubernetes Pod queries."""

    pods: list[PodInfo] = Field(
        default_factory=list, description="List of matching Kubernetes Pods"
    )
    total_pods: int = Field(default=0, description="Total number of Pods discovered")
    running_pods: int = Field(default=0, description="Number of Pods in Running state")
    failed_pods: int = Field(default=0, description="Number of Pods in Failed or CrashLoop state")


class K8sClusterStatusRequest(BaseModel):
    """Request parameters for Kubernetes cluster health check."""

    timeout_seconds: float = Field(default=10.0, description="API server response timeout")


class K8sClusterStatusResult(BaseModel):
    """Health check status and connectivity summary for active Kubernetes cluster."""

    connected: bool = Field(default=False, description="Whether the cluster API is reachable")
    cluster_name: str = Field(default="", description="Active Kubernetes cluster name")
    api_server_url: str = Field(default="", description="API server endpoint URL")
    server_version: str = Field(default="", description="Kubernetes control plane version")
    node_count: int = Field(default=0, description="Total number of cluster nodes")
    ready_nodes: int = Field(default=0, description="Number of nodes in Ready condition")
    namespaces_count: int = Field(default=0, description="Total count of active namespaces")
    healthy: bool = Field(default=False, description="Overall cluster operational health status")
    components: dict[str, str] = Field(
        default_factory=dict, description="Control plane component health states"
    )


class K8sBootstrapRequest(BaseModel):
    """Request parameters for bootstrapping a local Minikube / K8s cluster."""

    driver: str = Field(default="docker", description="Minikube driver (docker, kvm2, hyperkit)")
    cpus: int = Field(default=4, description="Allocated CPU cores")
    memory_mb: int = Field(default=8192, description="Allocated memory in MB")
    enable_gpu: bool = Field(default=False, description="Request GPU passthrough if available")
    profile: str = Field(default="minikube", description="Minikube cluster profile name")


class K8sBootstrapResult(BaseModel):
    """Result from local Kubernetes bootstrap operation."""

    success: bool = Field(default=True, description="Whether bootstrap succeeded")
    cluster_name: str = Field(default="minikube", description="Created cluster profile name")
    driver: str = Field(default="docker", description="Underlying virtualization driver")
    ip_address: str = Field(default="", description="Cluster node IP address")
    kubeconfig_path: str = Field(default="", description="Path to active kubeconfig")
    duration_seconds: float = Field(default=0.0, description="Elapsed provisioning runtime")


class K8sDeployStackRequest(BaseModel):
    """Request parameters for deploying infrastructure stacks to Kubernetes."""

    stack_name: str = Field(
        ..., description="Stack identifier (llm, telemetry, ingress, argocd, devops)"
    )
    namespace: str = Field(default="default", description="Target deployment namespace")
    values_override: dict[str, Any] = Field(
        default_factory=dict, description="Custom Helm values overrides"
    )


class K8sDeployStackResult(BaseModel):
    """Deployment result for a Kubernetes application stack."""

    stack_name: str = Field(..., description="Stack identifier deployed")
    namespace: str = Field(default="default", description="Target namespace")
    resources_created: list[str] = Field(
        default_factory=list, description="Manifest resources applied"
    )
    endpoints: dict[str, str] = Field(
        default_factory=dict, description="Discovered service endpoints and ports"
    )
    success: bool = Field(default=True, description="Whether all stack resources deployed cleanly")


class K8sTeardownStackRequest(BaseModel):
    """Request parameters for tearing down an infrastructure stack."""

    stack_name: str = Field(..., description="Stack identifier to teardown")
    namespace: str = Field(default="default", description="Target namespace")
    delete_pvc: bool = Field(default=False, description="Purge persistent volume claims")


class K8sTeardownStackResult(BaseModel):
    """Teardown result for a Kubernetes application stack."""

    stack_name: str = Field(..., description="Stack identifier torn down")
    namespace: str = Field(default="default", description="Target namespace")
    resources_deleted: list[str] = Field(
        default_factory=list, description="Manifest resources removed"
    )
    success: bool = Field(default=True, description="Whether teardown completed cleanly")


class PolicyRuleViolation(BaseModel):
    """Detailed violation record for a failed Kubernetes admission policy rule."""

    policy_name: str = Field(..., description="Kyverno or OPA Gatekeeper policy name")
    rule_name: str = Field(..., description="Evaluated policy rule name")
    resource_kind: str = Field(..., description="Target Kubernetes resource kind")
    resource_name: str = Field(..., description="Target Kubernetes resource name")
    severity: str = Field(default="HIGH", description="Violation severity rating")
    message: str = Field(..., description="Detailed violation message and remediation advice")


class K8sPolicyValidateRequest(BaseModel):
    """Request parameters for validating Kubernetes manifests against admission policies."""

    manifest_path: str = Field(..., description="Path to manifest file or directory")
    policy_engine: str = Field(default="kyverno", description="Engine to use (kyverno | opa)")


class K8sPolicyValidateResult(BaseModel):
    """Validation report from Kubernetes admission policy evaluation."""

    manifest_path: str = Field(..., description="Validated manifest path")
    passed: bool = Field(default=True, description="Whether all manifests comply with policies")
    total_rules_evaluated: int = Field(default=0, description="Number of rules evaluated")
    violations_count: int = Field(default=0, description="Total count of policy violations")
    violations: list[PolicyRuleViolation] = Field(
        default_factory=list, description="Policy violation details"
    )


class K8sJaegerInfoRequest(BaseModel):
    """Request parameters for querying Jaeger tracing instance details in Kubernetes."""

    namespace: str = Field(default="telemetry", description="Namespace containing Jaeger")


class K8sJaegerInfoResult(BaseModel):
    """Information for Jaeger distributed tracing collector and UI endpoints."""

    ui_url: str = Field(default="", description="Jaeger Web UI endpoint URL")
    collector_otlp_grpc: str = Field(
        default="", description="OTLP gRPC collector endpoint (e.g. host:4317)"
    )
    collector_otlp_http: str = Field(
        default="", description="OTLP HTTP collector endpoint (e.g. host:4318)"
    )
    status: str = Field(default="Running", description="Collector deployment status")
    available: bool = Field(default=False, description="Whether Jaeger endpoints are accessible")


class FalcoAlert(BaseModel):
    """Structured Falco eBPF runtime security syscall alert event."""

    time: str = Field(default="", description="Alert timestamp ISO 8601")
    rule: str = Field(default="", description="Falco security rule name triggered")
    priority: str = Field(
        default="Warning", description="Severity priority (Critical, Error, Warning, Notice, Info)"
    )
    source: str = Field(default="syscall", description="Event source probe (syscall, k8s_audit)")
    output: str = Field(default="", description="Formatted alert description string")
    output_fields: dict[str, Any] = Field(
        default_factory=dict, description="Extracted event metadata fields"
    )
    tags: list[str] = Field(default_factory=list, description="Rule taxonomy and MITRE ATT&CK tags")


class SecurityStreamRequest(BaseModel):
    """Request parameters for streaming Kubernetes Falco runtime security events."""

    namespace: str = Field(default="falco", description="Namespace containing Falco DaemonSet")
    label_selector: str = Field(
        default="app.kubernetes.io/name=falco", description="Kubernetes pod label selector"
    )
    severity: str | None = Field(default=None, description="Minimum severity filter")
    duration_seconds: int = Field(
        default=DEFAULT_SECURITY_STREAM_DURATION_SECONDS,
        ge=CONST_MIN_SECURITY_STREAM_DURATION,
        le=CONST_MAX_SECURITY_STREAM_DURATION,
        description="Streaming observation window in seconds",
    )
    follow: bool = False
    tail_lines: int = Field(
        default=DEFAULT_SECURITY_STREAM_TAIL_LINES,
        ge=CONST_MIN_SECURITY_STREAM_TAIL_LINES,
        le=CONST_MAX_SECURITY_STREAM_TAIL_LINES,
        description="Log lines to read per pod",
    )
    simulate: bool = Field(default=False, description="Generate simulated security anomalies")

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        """Validate and canonicalize user-supplied severity filter."""
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        if cleaned.upper() not in CONST_FALCO_SEVERITY_LEVELS:
            valid_levels = ", ".join(sorted(CONST_FALCO_SEVERITY_LEVELS.keys()))
            raise ValueError(f"Invalid severity '{v}'. Must be one of: {valid_levels}")
        return cleaned.upper()


class SecurityStreamResult(BaseModel):
    """Result payload from Kubernetes runtime security event stream."""

    alerts: list[FalcoAlert] = Field(
        default_factory=list, description="Discovered security alert events"
    )
    total_alerts: int = Field(default=0, description="Total number of alert events matched")
    critical_count: int = Field(default=0, description="Count of Critical/Emergency alerts")
    warning_count: int = Field(default=0, description="Count of Warning/Error alerts")
    notice_count: int = Field(default=0, description="Count of Notice/Informational alerts")
    duration_seconds: float = Field(default=0.0, description="Elapsed streaming duration")


class K8sEvent(BaseModel):
    """Normalized Kubernetes cluster event from Watch stream."""

    event_type: str = Field(..., description="Event action type (ADDED, MODIFIED, DELETED, ERROR)")
    resource_kind: str = Field(default="Pod", description="Resource kind")
    name: str = Field(..., description="Target resource name")
    namespace: str = Field(default="default", description="Target resource namespace")
    status: str = Field(default="Unknown", description="Current phase or status")
    message: str = Field(default="", description="Optional event message or diagnostic detail")
    reason: str = Field(default="", description="Reason for event transition")
    timestamp: str | None = Field(default=None, description="Event timestamp ISO 8601")


class K8sInformerState(BaseModel):
    """In-memory cache and synchronization state for Kubernetes resource informers."""

    resource_kind: str = Field(default="Pod", description="Observed resource kind")
    namespace: str = Field(default="default", description="Observed namespace or empty for all")
    resource_count: int = Field(default=0, description="Total cached resource instances")
    synced: bool = Field(default=False, description="Whether informer has synced with API server")
    last_event_time: str | None = Field(
        default=None, description="Timestamp of latest processed event"
    )


class NodeInfo(BaseModel):
    """Summarized status and metadata for a Kubernetes node."""

    name: str = Field(description="Node name")
    ready: bool = Field(default=False, description="Whether Ready condition is True")
    unschedulable: bool = Field(
        default=False, description="Whether node is cordoned (spec.unschedulable)"
    )
    reason: str = Field(default="", description="Reason string from Ready condition")
    message: str = Field(default="", description="Message from Ready condition")
    pod_count: int = Field(default=0, description="Count of pods scheduled on this node")

    @classmethod
    def from_node(cls, node: Any, pod_count: int = 0) -> NodeInfo:
        """Construct a NodeInfo from a Kubernetes V1Node object."""
        metadata = getattr(node, "metadata", None)
        spec = getattr(node, "spec", None)
        status = getattr(node, "status", None)
        ready_cond = None
        for cond in _items(getattr(status, "conditions", None)):
            if getattr(cond, "type", None) == CONST_K8S_CONDITION_READY:
                ready_cond = cond
                break
        return cls(
            name=_text(metadata, "name"),
            ready=node_is_ready(node),
            unschedulable=bool(getattr(spec, "unschedulable", False)),
            reason=_text(ready_cond, "reason"),
            message=_text(ready_cond, "message"),
            pod_count=pod_count,
        )


class ClusterEventInfo(BaseModel):
    """A cluster-wide or namespaced Kubernetes event with involved object reference."""

    type: str = Field(default="", description="Event type (Normal or Warning)")
    reason: str = Field(default="", description="Machine-readable event reason")
    message: str = Field(default="", description="Event description message")
    count: int = Field(default=1, description="Event occurrence count")
    last_seen: datetime | None = Field(default=None, description="When the event last occurred")
    involved_kind: str = Field(
        default="", description="Kind of the involved object (e.g. Pod, Node, PersistentVolume)"
    )
    involved_namespace: str | None = Field(default=None, description="Namespace of involved object")
    involved_name: str = Field(default="", description="Name of involved object")
    involved_uid: str | None = Field(default=None, description="UID of involved object")

    @classmethod
    def from_event(cls, event: Any) -> ClusterEventInfo:
        """Construct a ClusterEventInfo from a Kubernetes CoreV1Event object."""
        pod_evt = PodEventInfo.from_event(event)
        inv = getattr(event, "involved_object", None)
        return cls(
            type=pod_evt.type,
            reason=pod_evt.reason,
            message=pod_evt.message,
            count=pod_evt.count,
            last_seen=pod_evt.last_seen,
            involved_kind=_text(inv, "kind"),
            involved_namespace=getattr(inv, "namespace", None) or None,
            involved_name=_text(inv, "name"),
            involved_uid=getattr(inv, "uid", None),
        )


class Finding(BaseModel):
    """A diagnosed Kubernetes cluster or workload finding."""

    rule: str = Field(description="Rule identifier, e.g. node-not-ready")
    severity: Literal["critical", "warning"] = Field(description="Severity: critical or warning")
    class_: Literal["cluster", "workload"] = Field(
        alias="class", description="Finding class: cluster or workload"
    )
    resource: str = Field(
        description="Target resource identifier, e.g. Node/node-1 or Pod/default/api-0"
    )
    cause: str = Field(description="Likely cause of the issue")
    evidence: list[str] = Field(
        default_factory=list, description="Evidence lines supporting the finding"
    )
    remediation: str = Field(description="Actionable steps to resolve the issue")
    affected: list[str] = Field(
        default_factory=list, description="Resources affected by or absorbed into this finding"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @property
    def classification(self) -> Literal["cluster", "workload"]:
        """Alias for class_."""
        return self.class_


class DoctorReport(BaseModel):
    """Comprehensive diagnosis report produced by `devops k8s doctor`."""

    context: str = Field(default="", description="Active Kubernetes context name")
    counts: dict[str, int] = Field(
        default_factory=dict, description="Summary counts of resources scanned"
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Ranked list of diagnosed findings"
    )
    errors: list[str] = Field(
        default_factory=list, description="API errors encountered during diagnosis"
    )
    requests: list[PlannedRequest] = Field(
        default_factory=list, description="Ordered dry-run request plan"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
