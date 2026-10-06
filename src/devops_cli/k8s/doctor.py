"""Kubernetes cluster deployment health diagnosis and symptom correlation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from devops_cli.config.constants import (
    CONST_K8S_CONDITION_READY,
    CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR,
    CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
    CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
    CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
    CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL,
    CONST_K8S_DOCTOR_RULE_POD_NOT_READY,
    CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
    CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE,
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
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.models.k8s import DoctorReport, Finding, node_is_ready
from devops_cli.security.sanitizer import mask_secrets


@dataclass
class Snapshot:
    """Raw objects collected from the Kubernetes API for health diagnosis."""

    context: str = ""
    nodes: list[Any] = field(default_factory=list)
    pods: list[Any] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)
    logs: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def plan_doctor_requests(
    namespace: str | None = None,
    tail: int = DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
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
    return [
        PlannedRequest(method="list_node", target="cluster"),
        PlannedRequest(method=pod_method, target=pod_target),
        PlannedRequest(method=evt_method, target=evt_target),
        PlannedRequest(
            method="read_namespaced_pod_log",
            target=f"tail_lines={tail}",
            condition="a rule flags the pod",
            repeat="per flagged container",
        ),
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


def _sort_findings(findings: list[Finding], pod_restarts: dict[str, int]) -> list[Finding]:
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

    # Restarts map for ranking
    pod_restarts: dict[str, int] = {}
    for p in s.pods:
        meta = getattr(p, "metadata", None)
        ns = str(getattr(meta, "namespace", "") or "default")
        name = str(getattr(meta, "name", "") or "")
        pod_restarts[f"Pod/{ns}/{name}"] = _pod_restarts(p)

    ranked_findings = _sort_findings(findings, pod_restarts)

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


def collect(
    core: Any,
    namespace: str | None = None,
    tail: int = DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
    context: str = "",
) -> Snapshot:
    """Collect nodes, pods, warning events, and logs for flagged pods from the Kubernetes API."""
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
    pre_report = diagnose(Snapshot(context=context, nodes=nodes, pods=pods, events=events))
    flagged_pod_keys: set[tuple[str, str]] = set()
    for f in pre_report.findings:
        if f.class_ == "workload" and f.resource.startswith("Pod/"):
            parts = f.resource.split("/")
            if len(parts) == 3:
                flagged_pod_keys.add((parts[1], parts[2]))

    logs: dict[tuple[str, str], list[str]] = {}
    for pod_ns, pod_name in sorted(flagged_pod_keys):
        try:
            raw_log = core.read_namespaced_pod_log(
                pod_name,
                pod_ns,
                tail_lines=tail,
                _request_timeout=DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
            )
            if isinstance(raw_log, str) and raw_log:
                masked = [mask_secrets(line) for line in raw_log.splitlines() if line.strip()]
                logs[(pod_ns, pod_name)] = masked[-tail:]
        except Exception:
            pass

    return Snapshot(
        context=context,
        nodes=nodes,
        pods=pods,
        events=events,
        logs=logs,
        errors=[],
    )


def get_k8s_client(context: str | None = None) -> Any:
    """Retrieve an initialized Kubernetes CoreV1Api client for the specified context."""
    from kubernetes import client, config  # type: ignore[import-untyped]

    from devops_cli.k8s.context import resolve_context

    target_context = resolve_context(context)
    config.load_kube_config(context=target_context)
    return client.CoreV1Api()


__all__ = [
    "Snapshot",
    "collect",
    "diagnose",
    "get_k8s_client",
    "plan_doctor_requests",
]
