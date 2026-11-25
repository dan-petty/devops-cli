"""Kubernetes cluster deployment health diagnosis and symptom correlation engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from packaging.version import InvalidVersion, Version

from devops_cli.config.commands import BIN_KONMON, BIN_KUBECTL
from devops_cli.config.constants import (
    CONST_EXIT_COMMAND_NOT_FOUND,
    CONST_K8S_CONDITION_READY,
    CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR,
    CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
    CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
    CONST_K8S_DOCTOR_RULE_ORPHANED_WORKLOAD,
    CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
    CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL,
    CONST_K8S_DOCTOR_RULE_POD_NOT_READY,
    CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
    CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE,
    CONST_K8S_DOCTOR_RULE_VERSION_SKEW,
    CONST_K8S_DOCTOR_RULE_VOLUME_RECLAIM_STUCK,
    CONST_K8S_DOCTOR_RULE_WARNING_EVENTS,
    CONST_K8S_KIND_PERSISTENT_VOLUME,
    CONST_K8S_REASON_CRASH_LOOP_BACKOFF,
    CONST_K8S_REASON_ERR_IMAGE_PULL,
    CONST_K8S_REASON_ERROR,
    CONST_K8S_REASON_FAILED_SCHEDULING,
    CONST_K8S_REASON_IMAGE_PULL_BACKOFF,
    CONST_K8S_REASON_OOM_KILLED,
    CONST_K8S_REASON_UNHEALTHY,
    CONST_K8S_REASON_VOLUME_FAILED_DELETE,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_K8S_DOCTOR_EVENT_COUNT_THRESHOLD,
    DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
    DEFAULT_K8S_DOCTOR_RESTART_THRESHOLD,
    DEFAULT_K8S_DOCTOR_STUCK_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.k8s.service import read_pod_log_text
from devops_cli.models.k8s import DoctorReport, Finding, node_is_ready
from devops_cli.security.sanitizer import mask_secrets

# The local read of the version of the kubectl on PATH; it reaches no cluster.
KUBECTL_CLIENT_VERSION: Final[tuple[str, ...]] = (BIN_KUBECTL, "version", "--client", "-o", "json")
_ORPHAN_WORKLOAD_KINDS: Final[frozenset[str]] = frozenset(
    {"Deployment", "StatefulSet", "DaemonSet", "CronJob"}
)


@dataclass(frozen=True)
class OrphanedWorkload:
    """One unmanaged workload finding reported by `konmon check orphaned -o json` (#5480)."""

    kind: str
    namespace: str
    name: str
    message: str = ""


@dataclass
class Snapshot:
    """Raw objects collected from the Kubernetes API for health diagnosis."""

    context: str = ""
    server_version: str = ""
    # The version of the kubectl on PATH (`kubectl_client_version`), empty when none answers.
    kubectl_version: str = ""
    nodes: list[Any] = field(default_factory=list)
    pods: list[Any] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)
    logs: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    orphaned_workloads: list[OrphanedWorkload] = field(default_factory=list)
    konmon_error: str | None = None
    errors: list[str] = field(default_factory=list)


def build_konmon_orphaned_cmd(
    namespace: str | None = None,
    context: str | None = None,
) -> list[str]:
    """Build the read-only `konmon check orphaned -o json` invocation (#5480)."""
    cmd = [BIN_KONMON, "check", "orphaned", "-o", "json"]
    if namespace:
        cmd.extend(["-n", namespace])
    if context:
        cmd.extend(["--context", context])
    return cmd


def plan_doctor_requests(
    namespace: str | None = None,
    tail: int = DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
    context: str | None = None,
) -> list[PlannedRequest]:
    """Build the ordered list of planned external requests for dry-run simulation."""
    pod_method = "list_namespaced_pod" if namespace else "list_pod_for_all_namespaces"
    pod_target = f"namespace={namespace}" if namespace else "all namespaces"
    evt_method = "list_namespaced_event" if namespace else "list_event_for_all_namespaces"
    evt_target = (
        f"namespace={namespace}, field_selector={CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR}"
        if namespace
        else f"all namespaces, field_selector={CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR}"
    )
    konmon_cmd = build_konmon_orphaned_cmd(namespace=namespace, context=context)
    return [
        PlannedRequest(method="get_code", target="cluster"),
        PlannedRequest(method="list_node", target="cluster"),
        PlannedRequest(method=pod_method, target=pod_target),
        PlannedRequest(method=evt_method, target=evt_target),
        PlannedRequest(
            method="read_namespaced_pod_log",
            target=f"tail_lines={tail}",
            condition="a rule flags the pod",
            repeat="per flagged container",
        ),
        PlannedRequest(method=BIN_KONMON, target=" ".join(konmon_cmd[1:])),
    ]


def _calc_age_seconds(ts: Any, now: datetime | None = None) -> int:
    """Calculate age in seconds from a timestamp."""
    if not isinstance(ts, datetime):
        return 0
    ref_now = now or (datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now(UTC))
    if ts.tzinfo is not None and ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=UTC)
    elif ts.tzinfo is None and ref_now.tzinfo is not None:
        ts = ts.replace(tzinfo=UTC)
    return max(0, int((ref_now - ts).total_seconds()))


def _pod_node(pod: Any) -> str:
    """Return node_name for a pod."""
    spec = getattr(pod, "spec", None)
    return str(getattr(spec, "node_name", "") or "")


def _pod_restarts(pod: Any) -> int:
    """Calculate total restarts across all container statuses of a pod."""
    status = getattr(pod, "status", None)
    return sum(
        int(getattr(cs, "restart_count", 0) or 0)
        for cs in getattr(status, "container_statuses", None) or []
    )


def _diagnose_nodes(nodes: list[Any], pods: list[Any]) -> tuple[list[Finding], set[str]]:
    """Diagnose node-level issues (node-not-ready, node-cordoned) and absorb resident pods."""
    findings: list[Finding] = []
    claimed_pods: set[str] = set()

    for n in nodes:
        name = str(getattr(getattr(n, "metadata", None), "name", "") or "")
        spec = getattr(n, "spec", None)
        unschedulable = bool(getattr(spec, "unschedulable", False))
        ready = node_is_ready(n)

        resident_pods = [p for p in pods if _pod_node(p) == name]
        resident_names = [
            str(getattr(getattr(p, "metadata", None), "name", "") or "") for p in resident_pods
        ]

        if not ready:
            findings.append(_build_node_not_ready_finding(n, name, resident_names))
            claimed_pods.update(resident_names)
        elif unschedulable and resident_names:
            findings.append(_build_node_cordoned_finding(name, resident_names))
            claimed_pods.update(resident_names)

    return findings, claimed_pods


def _build_node_not_ready_finding(node: Any, name: str, resident_names: list[str]) -> Finding:
    """Build a node-not-ready finding."""
    status = getattr(node, "status", None)
    ready_cond = None
    for cond in getattr(status, "conditions", None) or []:
        if getattr(cond, "type", None) == CONST_K8S_CONDITION_READY:
            ready_cond = cond
            break
    reason = str(getattr(ready_cond, "reason", "") or "KubeletNotReady")
    msg = str(getattr(ready_cond, "message", "") or "")
    evidence = [f"Node condition Ready is False: {reason} ({msg})".strip()]
    return Finding(
        rule=CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
        severity="critical",
        class_="cluster",
        resource=f"Node/{name}",
        cause="node unreachable or kubelet down; pods on it are affected; check the node, or drain it",
        evidence=evidence,
        remediation="Check node connectivity, kubelet service status, or drain workloads from the node.",
        affected=resident_names,
    )


def _build_node_cordoned_finding(name: str, resident_names: list[str]) -> Finding:
    """Build a node-cordoned finding."""
    return Finding(
        rule=CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
        severity="warning",
        class_="cluster",
        resource=f"Node/{name}",
        cause="scheduling disabled; uncordon when maintenance ends",
        evidence=[
            f"Node is marked Unschedulable (cordoned) with {len(resident_names)} pods resident"
        ],
        remediation="Uncordon the node with `kubectl uncordon` once maintenance completes, or drain remaining pods.",
        affected=resident_names,
    )


def _diagnose_volumes(events: list[Any]) -> list[Finding]:
    """Diagnose stuck persistent volume reclaims (volume-reclaim-stuck)."""
    findings: list[Finding] = []
    seen_pvs: set[str] = set()

    for evt in events:
        reason = str(getattr(evt, "reason", "") or "")
        inv = getattr(evt, "involved_object", None)
        kind = str(getattr(inv, "kind", "") or "")
        name = str(getattr(inv, "name", "") or "")

        if (
            kind == CONST_K8S_KIND_PERSISTENT_VOLUME
            and reason == CONST_K8S_REASON_VOLUME_FAILED_DELETE
        ):
            if name not in seen_pvs:
                seen_pvs.add(name)
                msg = str(getattr(evt, "message", "") or "")
                findings.append(
                    Finding(
                        rule=CONST_K8S_DOCTOR_RULE_VOLUME_RECLAIM_STUCK,
                        severity="critical",
                        class_="cluster",
                        resource=f"PersistentVolume/{name}",
                        cause="provisioner cannot delete the volume",
                        evidence=[f"Event VolumeFailedDelete: {msg}".strip()],
                        remediation="Inspect storage provisioner logs, volume finalizers, and underlying storage system.",
                        affected=[],
                    )
                )

    return findings


def _check_pod_terminating(pod: Any, now: datetime | None) -> Finding | None:
    """Check if a pod is stuck in Terminating phase."""
    meta = getattr(pod, "metadata", None)
    del_ts = getattr(meta, "deletion_timestamp", None)
    if del_ts is None:
        return None
    age = _calc_age_seconds(del_ts, now)
    if age <= DEFAULT_K8S_DOCTOR_STUCK_SECONDS:
        return None
    ns = str(getattr(meta, "namespace", "") or "default")
    name = str(getattr(meta, "name", "") or "")
    finalizers = list(getattr(meta, "finalizers", []) or [])
    evidence = [
        f"Pod has deletionTimestamp {del_ts} (age {age}s > {DEFAULT_K8S_DOCTOR_STUCK_SECONDS}s)"
        f" and finalizers: {', '.join(finalizers) if finalizers else 'none'}"
    ]
    return Finding(
        rule=CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
        severity="warning",
        class_="workload",
        resource=f"Pod/{ns}/{name}",
        cause="finalizer or node not responding; name the finalizers",
        evidence=evidence,
        remediation="Inspect pod finalizers or underlying node kubelet; remove hanging finalizers if safe.",
    )


def _check_pod_crashloop(pod: Any, logs: dict[tuple[str, str], list[str]]) -> Finding | None:
    """Check if any container in the pod is in CrashLoopBackOff or restarting with errors."""
    meta = getattr(pod, "metadata", None)
    status = getattr(pod, "status", None)
    ns = str(getattr(meta, "namespace", "") or "default")
    name = str(getattr(meta, "name", "") or "")

    for cs in getattr(status, "container_statuses", None) or []:
        c_name = str(getattr(cs, "name", "") or "")
        restarts = int(getattr(cs, "restart_count", 0) or 0)
        state = getattr(cs, "state", None)
        waiting = getattr(state, "waiting", None)
        waiting_reason = str(getattr(waiting, "reason", "") or "")
        last_state = getattr(cs, "last_state", None)
        term = getattr(last_state, "terminated", None)
        last_reason = str(getattr(term, "reason", "") or "")

        is_crashloop = waiting_reason == CONST_K8S_REASON_CRASH_LOOP_BACKOFF
        is_error_threshold = (
            last_reason in {CONST_K8S_REASON_OOM_KILLED, CONST_K8S_REASON_ERROR}
            and restarts > DEFAULT_K8S_DOCTOR_RESTART_THRESHOLD
        )

        if is_crashloop or is_error_threshold:
            oom = (
                last_reason == CONST_K8S_REASON_OOM_KILLED
                or waiting_reason == CONST_K8S_REASON_OOM_KILLED
            )
            cause = (
                "container exceeded memory limit (OOMKilled); increase container resources.limits.memory"
                if oom
                else "application process failing repeatedly in container"
            )
            remediation = (
                "Increase memory limits in container spec or optimize memory usage."
                if oom
                else "Inspect application crash logs and resolve startup failure."
            )
            evidence = [
                f"Container {c_name} restart count {restarts}, waiting reason {waiting_reason},"
                f" last termination {last_reason}"
            ]
            tail_lines = logs.get((ns, name), [])
            evidence.extend(tail_lines)
            return Finding(
                rule=CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
                severity="critical",
                class_="workload",
                resource=f"Pod/{ns}/{name}",
                cause=cause,
                evidence=evidence,
                remediation=remediation,
            )

    return None


def _check_pod_image_pull(pod: Any) -> Finding | None:
    """Check if any container in the pod has an image pull failure."""
    meta = getattr(pod, "metadata", None)
    status = getattr(pod, "status", None)
    ns = str(getattr(meta, "namespace", "") or "default")
    name = str(getattr(meta, "name", "") or "")

    for cs in getattr(status, "container_statuses", None) or []:
        c_name = str(getattr(cs, "name", "") or "")
        state = getattr(cs, "state", None)
        waiting = getattr(state, "waiting", None)
        waiting_reason = str(getattr(waiting, "reason", "") or "")

        if waiting_reason in {
            CONST_K8S_REASON_IMAGE_PULL_BACKOFF,
            CONST_K8S_REASON_ERR_IMAGE_PULL,
        }:
            msg = str(getattr(waiting, "message", "") or "")
            evidence = [f"Container {c_name} waiting reason {waiting_reason}: {msg}".strip()]
            return Finding(
                rule=CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL,
                severity="critical",
                class_="workload",
                resource=f"Pod/{ns}/{name}",
                cause="image, tag or registry credentials",
                evidence=evidence,
                remediation="Verify container image name, tag existence, and imagePullSecrets credentials.",
            )

    return None


def _check_pod_unschedulable(pod: Any, events: list[Any]) -> Finding | None:
    """Check if a pending pod cannot be scheduled."""
    meta = getattr(pod, "metadata", None)
    status = getattr(pod, "status", None)
    if getattr(status, "phase", None) != "Pending":
        return None

    ns = str(getattr(meta, "namespace", "") or "default")
    name = str(getattr(meta, "name", "") or "")

    for evt in events:
        reason = str(getattr(evt, "reason", "") or "")
        inv = getattr(evt, "involved_object", None)
        if (
            reason == CONST_K8S_REASON_FAILED_SCHEDULING
            and str(getattr(inv, "name", "") or "") == name
        ):
            msg = str(getattr(evt, "message", "") or "")
            return Finding(
                rule=CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE,
                severity="warning",
                class_="workload",
                resource=f"Pod/{ns}/{name}",
                cause=f"insufficient cluster resources or scheduling constraints: {msg}",
                evidence=[f"FailedScheduling event: {msg}".strip()],
                remediation="Adjust pod resource requests, cluster capacity, or node affinities/tolerations.",
            )

    return None


def _check_pod_not_ready(pod: Any, events: list[Any], now: datetime | None) -> Finding | None:
    """Check if a running pod is failing its readiness probe beyond threshold age."""
    meta = getattr(pod, "metadata", None)
    status = getattr(pod, "status", None)
    if getattr(status, "phase", None) != "Running":
        return None

    created = getattr(meta, "creation_timestamp", None)
    age = _calc_age_seconds(created, now)
    if age <= DEFAULT_K8S_DOCTOR_STUCK_SECONDS:
        return None

    spec = getattr(pod, "spec", None)
    total_containers = len(getattr(spec, "containers", None) or [])
    ready_containers = sum(
        1 for cs in getattr(status, "container_statuses", None) or [] if getattr(cs, "ready", False)
    )

    if ready_containers >= total_containers:
        return None

    ns = str(getattr(meta, "namespace", "") or "default")
    name = str(getattr(meta, "name", "") or "")

    unhealthy_msg = ""
    for evt in events:
        if (
            str(getattr(evt, "reason", "") or "") == CONST_K8S_REASON_UNHEALTHY
            and str(getattr(getattr(evt, "involved_object", None), "name", "") or "") == name
        ):
            unhealthy_msg = str(getattr(evt, "message", "") or "")
            break

    evidence = (
        [f"Unhealthy event: {unhealthy_msg}".strip()]
        if unhealthy_msg
        else [
            f"Pod running for {age}s but containers not ready ({ready_containers}/{total_containers})"
        ]
    )

    return Finding(
        rule=CONST_K8S_DOCTOR_RULE_POD_NOT_READY,
        severity="warning",
        class_="workload",
        resource=f"Pod/{ns}/{name}",
        cause="readiness probe failing; evidence is the Unhealthy event",
        evidence=evidence,
        remediation="Inspect readiness probe configuration, health endpoints, and container logs.",
    )


def _diagnose_workload_pods(
    pods: list[Any],
    claimed_pods: set[str],
    events: list[Any],
    logs: dict[tuple[str, str], list[str]],
    now: datetime | None,
) -> list[Finding]:
    """Diagnose workload pod issues for pods not absorbed by cluster rules."""
    findings: list[Finding] = []

    for pod in pods:
        meta = getattr(pod, "metadata", None)
        name = str(getattr(meta, "name", "") or "")
        if name in claimed_pods:
            continue

        finding = (
            _check_pod_terminating(pod, now)
            or _check_pod_crashloop(pod, logs)
            or _check_pod_image_pull(pod)
            or _check_pod_unschedulable(pod, events)
            or _check_pod_not_ready(pod, events, now)
        )
        if finding is not None:
            findings.append(finding)
            claimed_pods.add(name)

    return findings


def _diagnose_warning_events(events: list[Any], claimed_resources: set[str]) -> list[Finding]:
    """Diagnose repeated warning events on otherwise unclaimed resources."""
    findings: list[Finding] = []

    for evt in events:
        count = (
            getattr(evt, "count", None) or getattr(getattr(evt, "series", None), "count", None) or 1
        )
        if count < DEFAULT_K8S_DOCTOR_EVENT_COUNT_THRESHOLD:
            continue

        reason = str(getattr(evt, "reason", "") or "")
        inv = getattr(evt, "involved_object", None)
        kind = str(getattr(inv, "kind", "") or "")
        name = str(getattr(inv, "name", "") or "")
        ns = str(getattr(inv, "namespace", "") or "")

        res_str = f"{kind}/{ns}/{name}" if ns else f"{kind}/{name}"
        if name in claimed_resources or res_str in claimed_resources:
            continue

        msg = str(getattr(evt, "message", "") or "")
        findings.append(
            Finding(
                rule=CONST_K8S_DOCTOR_RULE_WARNING_EVENTS,
                severity="warning",
                class_="workload",
                resource=res_str,
                cause=f"repeated warning event: {reason}",
                evidence=[f"Warning event {reason} occurred {count} times: {msg}".strip()],
                remediation="Review cluster events and address underlying component warnings.",
            )
        )
        claimed_resources.add(name)
        claimed_resources.add(res_str)

    return findings


def _node_kubelet_version(node: Any) -> str:
    """Extract kubelet version string from a Kubernetes node object or dictionary."""
    status = getattr(node, "status", None) if not isinstance(node, dict) else node.get("status")
    if status is None:
        return ""
    node_info = getattr(status, "node_info", None)
    if node_info is None and hasattr(status, "nodeInfo"):
        node_info = getattr(status, "nodeInfo", None)
    if node_info is None and isinstance(status, dict):
        node_info = status.get("node_info") or status.get("nodeInfo")
    if node_info is None:
        return ""
    if isinstance(node_info, dict):
        return str(node_info.get("kubelet_version") or node_info.get("kubeletVersion") or "")
    return str(
        getattr(node_info, "kubelet_version", None)
        or getattr(node_info, "kubeletVersion", None)
        or ""
    )


def _parse_version(ver_str: str) -> Version | None:
    """Parse a version string using packaging.version.Version."""
    clean = ver_str.strip()
    if not clean:
        return None
    try:
        return Version(clean)
    except InvalidVersion:
        return None


def kubectl_client_version() -> str | None:
    """The version of the kubectl on PATH: `clientVersion.gitVersion` of
    `kubectl version --client -o json`, with no leading `v` (#4388). None when no kubectl answers
    with a version. The run is a local read and reaches no cluster."""
    result = run_subprocess(list(KUBECTL_CLIENT_VERSION), check=False, local_read=True)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except ValueError:
        return None
    client = data.get("clientVersion") if isinstance(data, dict) else None
    version = client.get("gitVersion") if isinstance(client, dict) else None
    return version.removeprefix("v") if isinstance(version, str) and version else None


def check_kubectl_version_skew(server_version: str, kubectl_version: str | None) -> str | None:
    """Check version skew between kubectl and server, returning a warning message if skewed."""
    if not server_version:
        return None

    k_version = kubectl_version
    if not k_version:
        return None

    s_ver = _parse_version(server_version)
    k_ver = _parse_version(k_version)
    if s_ver is None or k_ver is None:
        return None

    if s_ver.major != k_ver.major or abs(s_ver.minor - k_ver.minor) > 1:
        min_minor = max(0, k_ver.minor - 1)
        max_minor = k_ver.minor + 1
        return (
            f"kubectl version {k_version} is outside the supported skew for Kubernetes API server "
            f"{server_version}. The supported server range is 1.{min_minor} to 1.{max_minor}."
        )
    return None


def _diagnose_kubelet_skew(
    server_ver_parsed: Version,
    server_version_raw: str,
    nodes: list[Any],
) -> list[Finding]:
    """Diagnose kubelets outside supported version skew relative to API server."""
    findings: list[Finding] = []
    min_supported_minor = max(0, server_ver_parsed.minor - 3)
    max_supported_minor = server_ver_parsed.minor

    for n in nodes:
        k_ver_raw = _node_kubelet_version(n)
        if not k_ver_raw:
            continue
        k_ver_parsed = _parse_version(k_ver_raw)
        if k_ver_parsed is None:
            continue

        is_skewed = (
            k_ver_parsed.major != server_ver_parsed.major
            or k_ver_parsed.minor < min_supported_minor
            or k_ver_parsed.minor > max_supported_minor
        )
        if is_skewed:
            name = str(getattr(getattr(n, "metadata", None), "name", "") or "")
            if not name and isinstance(n, dict):
                name = str(n.get("metadata", {}).get("name", "") or "")
            findings.append(
                Finding(
                    rule=CONST_K8S_DOCTOR_RULE_VERSION_SKEW,
                    severity="warning",
                    class_="cluster",
                    resource=f"Node/{name}",
                    cause=(
                        f"kubelet version {k_ver_raw} on node {name} is outside the supported "
                        f"skew for API server {server_version_raw}"
                    ),
                    evidence=[
                        f"kubelet version: {k_ver_raw}",
                        f"server version: {server_version_raw}",
                        f"supported kubelet range: 1.{min_supported_minor} to 1.{max_supported_minor}",
                    ],
                    remediation=f"Upgrade the kubelet on node {name} to a supported version.",
                )
            )
    return findings


def diagnose_version_skew(
    server_version_str: str,
    nodes: list[Any],
    kubectl_version_str: str | None = None,
) -> list[Finding]:
    """Diagnose kubectl and kubelet version skew against Kubernetes API server."""
    if not server_version_str:
        return []

    s_ver_parsed = _parse_version(server_version_str)
    if s_ver_parsed is None:
        return []

    findings: list[Finding] = []

    # 1. Kubectl skew
    warn_msg = check_kubectl_version_skew(server_version_str, kubectl_version_str)
    if warn_msg:
        k_version = kubectl_version_str
        k_parsed = _parse_version(k_version or "")
        k_minor = k_parsed.minor if k_parsed else 0
        min_minor = max(0, k_minor - 1)
        max_minor = k_minor + 1
        findings.append(
            Finding(
                rule=CONST_K8S_DOCTOR_RULE_VERSION_SKEW,
                severity="warning",
                class_="cluster",
                resource="kubectl",
                cause=warn_msg,
                evidence=[
                    f"kubectl version: {k_version or 'unknown'}",
                    f"server version: {server_version_str}",
                    f"supported server range: 1.{min_minor} to 1.{max_minor}",
                ],
                remediation="Upgrade the Kubernetes cluster to a supported version.",
            )
        )

    # 2. Node kubelet skew
    findings.extend(_diagnose_kubelet_skew(s_ver_parsed, server_version_str, nodes))

    return findings


def sort_findings(findings: list[Finding], pod_restarts: dict[str, int]) -> list[Finding]:
    """Rank findings: cluster before workload, critical before warning, affected count, restarts, name."""

    def sort_key(f: Finding) -> tuple[int, int, int, int, str]:
        class_order = 0 if f.class_ == "cluster" else 1
        sev_order = 0 if f.severity == "critical" else 1
        affected_order = -len(f.affected)
        restarts = pod_restarts.get(f.resource, 0)
        restarts_order = -restarts
        name_order = f.resource
        return (class_order, sev_order, affected_order, restarts_order, name_order)

    return sorted(findings, key=sort_key)


def diagnose(
    snapshot: Snapshot | None = None,
    *,
    server_version: str = "",
    nodes: list[Any] | None = None,
    pods: list[Any] | None = None,
    events: list[Any] | None = None,
    logs: dict[tuple[str, str], list[str]] | None = None,
    context: str = "",
    now: datetime | None = None,
) -> DoctorReport:
    """Apply the fixed diagnostic rule table over cluster snapshot and return DoctorReport."""
    s = snapshot or Snapshot(
        context=context,
        server_version=server_version,
        nodes=nodes or [],
        pods=pods or [],
        events=events or [],
        logs=logs or {},
    )

    findings: list[Finding] = []
    claimed_resources: set[str] = set()

    # 1. Cluster rules: nodes
    node_findings, claimed_pods = _diagnose_nodes(s.nodes, s.pods)
    findings.extend(node_findings)
    claimed_resources.update(claimed_pods)
    for nf in node_findings:
        claimed_resources.add(nf.resource)
        claimed_resources.add(nf.resource.split("/")[-1])

    # 2. Cluster rules: volumes
    vol_findings = _diagnose_volumes(s.events)
    findings.extend(vol_findings)
    for vf in vol_findings:
        claimed_resources.add(vf.resource)
        claimed_resources.add(vf.resource.split("/")[-1])

    # 3. Workload rules: pods
    pod_findings = _diagnose_workload_pods(s.pods, claimed_pods, s.events, s.logs, now)
    findings.extend(pod_findings)
    for pf in pod_findings:
        claimed_resources.add(pf.resource)
        claimed_resources.add(pf.resource.split("/")[-1])

    # 4. Workload rules: warning events
    event_findings = _diagnose_warning_events(s.events, claimed_resources)
    findings.extend(event_findings)

    # 5. Cluster rules: version skew
    effective_server_ver = getattr(s, "server_version", "") or server_version
    skew_findings = diagnose_version_skew(effective_server_ver, s.nodes, s.kubectl_version or None)
    findings.extend(skew_findings)

    # 6. Workload rules: unmanaged workloads from konmon
    findings.extend(diagnose_orphaned_workloads(s.orphaned_workloads, s.konmon_error))

    # Restarts map for ranking
    pod_restarts: dict[str, int] = {}
    for p in s.pods:
        meta = getattr(p, "metadata", None)
        ns = str(getattr(meta, "namespace", "") or "default")
        name = str(getattr(meta, "name", "") or "")
        pod_restarts[f"Pod/{ns}/{name}"] = _pod_restarts(p)

    ranked_findings = sort_findings(findings, pod_restarts)

    return DoctorReport(
        context=s.context,
        counts={
            "nodes": len(s.nodes),
            "pods": len(s.pods),
            "events": len(s.events),
            "findings": len(ranked_findings),
        },
        findings=ranked_findings,
        errors=list(s.errors),
        requests=[],
    )


def _resolve_version_api(core: Any, version_api: Any = None) -> Any:
    """Resolve an API client exposing get_code for Kubernetes version detection."""
    if version_api is not None:
        return version_api
    if hasattr(core, "version_api"):
        return getattr(core, "version_api")
    if hasattr(core, "get_code"):
        return core
    if hasattr(core, "api_client"):
        from kubernetes import client as k8s_client

        return k8s_client.VersionApi(core.api_client)
    return None


def _fetch_server_version(core: Any, version_api: Any = None, context: str = "") -> str:
    """Fetch the Kubernetes server version string using VersionApi or KubernetesService."""
    v_api = _resolve_version_api(core, version_api)
    if v_api is not None:
        try:
            info = v_api.get_code(_request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS)
            if isinstance(info, dict):
                return str(info.get("git_version") or "")
            return str(getattr(info, "git_version", "") or "")
        except AttributeError, OSError, TypeError, ValueError:
            return ""
    if context:
        from devops_cli.k8s.service import KubernetesService

        return str(KubernetesService.get_instance().server_version(context=context) or "")
    return ""


def _parse_konmon_payload(raw_stdout: str) -> tuple[list[OrphanedWorkload], list[Any]] | None:
    """Parse `konmon check orphaned -o json` stdout into filtered workloads and `notChecked`."""
    try:
        payload = json.loads(raw_stdout)
    except ValueError:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
        return None
    workloads = [
        OrphanedWorkload(
            kind=str(item.get("kind") or ""),
            namespace=str(item.get("namespace") or ""),
            name=str(item.get("name") or ""),
            message=str(item.get("message") or ""),
        )
        for item in payload["findings"]
        if isinstance(item, dict)
        and str(item.get("kind") or "") in _ORPHAN_WORKLOAD_KINDS
        and str(item.get("name") or "")
    ]
    not_checked = payload.get("notChecked")
    return workloads, not_checked if isinstance(not_checked, list) else []


def collect_konmon_orphans(
    namespace: str | None = None,
    context: str | None = None,
) -> tuple[list[OrphanedWorkload], str | None]:
    """Run `konmon check orphaned -o json` and filter findings to Kubernetes workload kinds (#5480)."""
    cmd = build_konmon_orphaned_cmd(namespace=namespace, context=context)
    try:
        result = run_subprocess(cmd, check=False, intent="read")
    except FileNotFoundError:
        return [], "konmon executable is missing from PATH; unmanaged workloads were not checked."

    if result.returncode == CONST_EXIT_COMMAND_NOT_FOUND:
        return [], "konmon executable is missing from PATH; unmanaged workloads were not checked."

    raw_stdout = (result.stdout or "").strip()
    if result.returncode in (0, 1, 2) and raw_stdout:
        parsed = _parse_konmon_payload(raw_stdout)
        if parsed is not None:
            workloads, not_checked = parsed
            if result.returncode == 2 and not_checked:
                detail = mask_secrets(", ".join(str(entry) for entry in not_checked))
                return workloads, f"konmon could not check some resource types: {detail}"
            return workloads, None

    detail = mask_secrets((result.stderr or raw_stdout).strip())
    if result.returncode != 0:
        msg = (
            f"konmon orphaned check failed (exit {result.returncode}): {detail}"
            if detail
            else f"konmon orphaned check failed (exit {result.returncode})."
        )
    else:
        msg = "konmon orphaned check returned invalid JSON output."
    return [], msg


def diagnose_orphaned_workloads(
    orphaned_workloads: list[OrphanedWorkload],
    konmon_error: str | None = None,
) -> list[Finding]:
    """Convert collected konmon orphan findings and runner errors into Doctor `Finding` objects."""
    out: list[Finding] = []
    if konmon_error:
        out.append(
            Finding(
                rule=CONST_K8S_DOCTOR_RULE_ORPHANED_WORKLOAD,
                severity="warning",
                class_="cluster",
                resource="konmon",
                cause=konmon_error,
                evidence=[konmon_error],
                remediation="Ensure `konmon` is installed on PATH and can reach the Kubernetes API.",
            )
        )
    for item in orphaned_workloads:
        resource = (
            f"{item.kind}/{item.namespace}/{item.name}"
            if item.namespace
            else f"{item.kind}/{item.name}"
        )
        cause = (
            item.message or "Workload has no Argo CD tracking label/annotation or controller owner."
        )
        out.append(
            Finding(
                rule=CONST_K8S_DOCTOR_RULE_ORPHANED_WORKLOAD,
                severity="warning",
                class_="workload",
                resource=resource,
                cause=cause,
                evidence=[f"konmon orphaned check flagged {resource}"],
                remediation=(
                    "Add the workload to an Argo CD Application in git or remove it from the cluster."
                ),
            )
        )
    return out


def collect(
    core: Any,
    namespace: str | None = None,
    tail: int = DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
    context: str = "",
    version_api: Any = None,
) -> Snapshot:
    """Collect nodes, pods, warning events, and logs for flagged pods from the Kubernetes API."""
    server_version = _fetch_server_version(core, version_api=version_api, context=context)

    node_resp = core.list_node(_request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS)
    nodes = list(getattr(node_resp, "items", []))

    if namespace:
        pod_resp = core.list_namespaced_pod(
            namespace, _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS
        )
        evt_resp = core.list_namespaced_event(
            namespace,
            field_selector=CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR,
            _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
        )
    else:
        pod_resp = core.list_pod_for_all_namespaces(
            _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS
        )
        evt_resp = core.list_event_for_all_namespaces(
            field_selector=CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR,
            _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
        )

    pods = list(getattr(pod_resp, "items", []))
    events = list(getattr(evt_resp, "items", []))

    # Pre-diagnose to identify pods flagged by workload rules
    pre_report = diagnose(
        Snapshot(
            context=context,
            server_version=server_version,
            nodes=nodes,
            pods=pods,
            events=events,
        )
    )
    flagged_pod_keys: set[tuple[str, str]] = set()
    for f in pre_report.findings:
        if f.class_ == "workload" and f.resource.startswith("Pod/"):
            parts = f.resource.split("/")
            if len(parts) == 3:
                flagged_pod_keys.add((parts[1], parts[2]))

    logs: dict[tuple[str, str], list[str]] = {}
    for pod_ns, pod_name in sorted(flagged_pod_keys):
        try:
            raw_log = read_pod_log_text(
                core,
                pod_name,
                pod_ns,
                tail_lines=tail,
                _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
            )
            if raw_log:
                masked = [mask_secrets(line) for line in raw_log.splitlines() if line.strip()]
                logs[(pod_ns, pod_name)] = masked[-tail:]
        except Exception:
            pass

    orphaned_workloads, konmon_error = collect_konmon_orphans(
        namespace=namespace, context=context or None
    )

    return Snapshot(
        context=context,
        server_version=server_version,
        kubectl_version=kubectl_client_version() or "",
        nodes=nodes,
        pods=pods,
        events=events,
        logs=logs,
        orphaned_workloads=orphaned_workloads,
        konmon_error=konmon_error,
        errors=[],
    )


def get_k8s_client(context: str | None = None) -> Any:
    """Retrieve an initialized Kubernetes core API client for the specified context."""
    from devops_cli.k8s.service import KubernetesService

    return KubernetesService.get_instance().core_api(context=context)


__all__ = [
    "OrphanedWorkload",
    "Snapshot",
    "build_konmon_orphaned_cmd",
    "check_kubectl_version_skew",
    "collect",
    "collect_konmon_orphans",
    "diagnose",
    "diagnose_orphaned_workloads",
    "diagnose_version_skew",
    "get_k8s_client",
    "kubectl_client_version",
    "plan_doctor_requests",
    "sort_findings",
]
