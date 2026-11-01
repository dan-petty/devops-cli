"""Tests for Kubernetes cluster deployment health diagnosis (devops k8s doctor)."""

from __future__ import annotations

import datetime
import json
from collections.abc import Callable
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
    CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
    CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
    CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL,
    CONST_K8S_DOCTOR_RULE_POD_NOT_READY,
    CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
    CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE,
    CONST_K8S_DOCTOR_RULE_VOLUME_RECLAIM_STUCK,
    CONST_K8S_DOCTOR_RULE_WARNING_EVENTS,
)
from devops_cli.config.defaults import DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS
from devops_cli.k8s.doctor import Snapshot, collect, diagnose
from devops_cli.k8s.service import KubernetesService
from devops_cli.models.k8s import Finding
from tests.support.fakes.kubernetes import (
    NOW,
    FakeCluster,
    FakeCoreV1,
    FakeVersion,
    crashlooping_pod,
    event,
    healthy_pod,
    node,
    pod,
    running,
    status,
    terminated,
    waiting,
)


def test_doctor_is_registered_with_its_options(cli: Callable[..., Any]) -> None:
    """Verify that doctor command is registered and exposes its expected CLI options."""
    result = cli("k8s", "doctor", "--help")
    expected_options = ("--namespace", "--context", "--tail", "--format", "--dry-run")
    options_present = tuple(opt in result.stdout for opt in expected_options)
    assert (result.exit_code, options_present) == (0, (True, True, True, True, True))


def test_doctor_attributes_crashloop_on_an_unready_node_to_the_node() -> None:
    """A crashlooping pod on an unready node is absorbed by the node-not-ready finding."""
    bad_node = node("worker-bad", ready="False", unschedulable=True)
    good_node = node("worker-good", ready="True", unschedulable=False)
    metrics_pod = crashlooping_pod(
        "metrics-server", "kube-system", node_name="worker-bad", restarts=6
    )
    app_pod = healthy_pod("app-0", "default", node_name="worker-good")

    report = diagnose(nodes=[bad_node, good_node], pods=[metrics_pod, app_pod])
    rule_ids = tuple(f.rule for f in report.findings)
    resource = report.findings[0].resource if report.findings else ""
    affected = tuple(report.findings[0].affected) if report.findings else ()
    assert (rule_ids, resource, affected) == (
        (CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,),
        "Node/worker-bad",
        ("metrics-server",),
    )


def test_doctor_reports_a_stuck_volume_reclaim() -> None:
    """VolumeFailedDelete event on PersistentVolume reports stuck volume reclaim and stuck pod."""
    pv_event = event(
        "VolumeFailedDelete",
        involved_kind="PersistentVolume",
        involved_name="pv-local-01",
        message="failed to delete local path directory",
    )
    stuck_time = NOW - datetime.timedelta(days=3)
    helper = pod(
        "helper-delete-pod",
        "kube-system",
        deletion_timestamp=stuck_time,
        finalizers=["kubernetes.io/pv-protection"],
    )
    report = diagnose(events=[pv_event], pods=[helper], now=NOW)
    actual = tuple((f.rule, f.class_, f.resource) for f in report.findings)
    assert actual == (
        (CONST_K8S_DOCTOR_RULE_VOLUME_RECLAIM_STUCK, "cluster", "PersistentVolume/pv-local-01"),
        (
            CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
            "workload",
            "Pod/kube-system/helper-delete-pod",
        ),
    )


@pytest.mark.parametrize(
    ("rule_name", "fixture_factory", "expected_tuple"),
    [
        (
            "node-cordoned",
            lambda: (
                [node("node-maint", ready="True", unschedulable=True)],
                [healthy_pod("app-resident", "default", node_name="node-maint")],
                [],
                {},
            ),
            (CONST_K8S_DOCTOR_RULE_NODE_CORDONED, "warning", "cluster", "Node/node-maint", True),
        ),
        (
            "pod-stuck-terminating",
            lambda: (
                [],
                [
                    pod(
                        "pod-term",
                        "default",
                        deletion_timestamp=NOW - datetime.timedelta(seconds=400),
                        finalizers=["custom.io/cleanup"],
                    )
                ],
                [],
                {},
            ),
            (
                CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
                "warning",
                "workload",
                "Pod/default/pod-term",
                True,
            ),
        ),
        (
            "pod-crashloop",
            lambda: (
                [],
                [
                    pod(
                        "pod-oom",
                        "default",
                        statuses=[
                            status(
                                "c1",
                                waiting("CrashLoopBackOff"),
                                restarts=4,
                                last=terminated(137, "OOMKilled"),
                            )
                        ],
                    )
                ],
                [],
                {},
            ),
            (
                CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
                "critical",
                "workload",
                "Pod/default/pod-oom",
                True,
            ),
        ),
        (
            "pod-image-pull",
            lambda: (
                [],
                [
                    pod(
                        "pod-pull",
                        "default",
                        statuses=[status("c1", waiting("ImagePullBackOff"))],
                    )
                ],
                [],
                {},
            ),
            (
                CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL,
                "critical",
                "workload",
                "Pod/default/pod-pull",
                True,
            ),
        ),
        (
            "pod-unschedulable",
            lambda: (
                [],
                [pod("pod-pending", "default", phase="Pending")],
                [
                    event(
                        "FailedScheduling",
                        involved_kind="Pod",
                        involved_name="pod-pending",
                        message="0/2 nodes are available",
                    )
                ],
                {},
            ),
            (
                CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE,
                "warning",
                "workload",
                "Pod/default/pod-pending",
                True,
            ),
        ),
        (
            "pod-not-ready",
            lambda: (
                [],
                [
                    pod(
                        "pod-probe",
                        "default",
                        phase="Running",
                        creation_timestamp=NOW - datetime.timedelta(seconds=400),
                        statuses=[status("c1", running(), ready=False)],
                    )
                ],
                [
                    event(
                        "Unhealthy",
                        involved_kind="Pod",
                        involved_name="pod-probe",
                        message="Readiness probe failed",
                    )
                ],
                {},
            ),
            (
                CONST_K8S_DOCTOR_RULE_POD_NOT_READY,
                "warning",
                "workload",
                "Pod/default/pod-probe",
                True,
            ),
        ),
        (
            "warning-events",
            lambda: (
                [],
                [],
                [
                    event(
                        "FailedCreate",
                        involved_kind="ReplicaSet",
                        involved_name="worker-rs",
                        count=6,
                        message="quota exceeded",
                    )
                ],
                {},
            ),
            (
                CONST_K8S_DOCTOR_RULE_WARNING_EVENTS,
                "warning",
                "workload",
                "ReplicaSet/worker-rs",
                True,
            ),
        ),
        (
            "log-errors",
            lambda: (
                [],
                [crashlooping_pod("pod-crashed", "default")],
                [],
                {("default", "pod-crashed"): ["FATAL: database connection timeout"]},
            ),
            (
                CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
                "critical",
                "workload",
                "Pod/default/pod-crashed",
                True,
            ),
        ),
    ],
)
def test_doctor_rules(
    rule_name: str,
    fixture_factory: Any,
    expected_tuple: tuple[str, str, str, str, bool],
) -> None:
    """Fixture tests covering all remaining rules, verifying classifications and remediations."""
    nodes, pods, events, logs = fixture_factory()
    report = diagnose(nodes=nodes, pods=pods, events=events, logs=logs, now=NOW)
    assert len(report.findings) >= 1
    f = report.findings[0]
    actual_tuple = (f.rule, f.severity, f.class_, f.resource, bool(f.remediation))
    assert actual_tuple == expected_tuple

    if rule_name == "log-errors":
        assert any("database connection timeout" in line for line in f.evidence)
        assert all(f_item.rule != "log-errors" for f_item in report.findings)


def test_doctor_ranks_cluster_findings_first() -> None:
    """Deterministic ranking orders cluster critical, cluster warning, workload critical, workload warning."""
    cluster_crit = Finding(
        rule=CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
        severity="critical",
        class_="cluster",
        resource="Node/node-0",
        cause="unready",
        remediation="drain",
    )
    cluster_warn = Finding(
        rule=CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
        severity="warning",
        class_="cluster",
        resource="Node/node-1",
        cause="cordoned",
        remediation="uncordon",
    )
    workload_crit = Finding(
        rule=CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
        severity="critical",
        class_="workload",
        resource="Pod/default/pod-crit",
        cause="crash",
        remediation="fix",
    )
    workload_warn = Finding(
        rule=CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
        severity="warning",
        class_="workload",
        resource="Pod/default/pod-warn",
        cause="terminating",
        remediation="clear",
    )

    from devops_cli.k8s.doctor import sort_findings

    unordered = [workload_warn, cluster_warn, workload_crit, cluster_crit]
    sorted_findings = sort_findings(unordered, pod_restarts={})
    assert tuple(f.rule for f in sorted_findings) == (
        CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
        CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
        CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
        CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
    )


def test_doctor_reads_logs_only_for_flagged_pods() -> None:
    """Collect reads logs only for pods flagged by rules, passing the requested tail lines."""
    healthy = healthy_pod("app-ok", "default")
    crashed = crashlooping_pod("app-fail", "default")
    core = FakeCoreV1(pods=[healthy, crashed], nodes=[node("worker-1")])

    collect(core, tail=35)
    log_calls = {
        (kwargs["namespace"], kwargs["name"], kwargs["tail_lines"])
        for method, kwargs in core.calls
        if method == "read_namespaced_pod_log"
    }
    assert log_calls == {("default", "app-fail", 35)}


def test_doctor_logs_are_decoded_text_with_one_entry_for_each_line() -> None:
    """The log of a flagged pod is UTF-8 text: its lines are separate and its secrets are masked."""
    token = "ghs_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"  # a fake token for the masking test
    written = f"start\n\N{CHECK MARK} ready\nauthorization: {token}\n".encode()
    crashed = crashlooping_pod("app-fail", "default")
    core = FakeCoreV1(pods=[crashed], nodes=[node("worker-1")], logs=written)

    lines = collect(core, tail=35).logs[("default", "app-fail")]

    assert (len(lines), lines[:2], any(token in line for line in lines)) == (
        3,
        ["start", "\N{CHECK MARK} ready"],
        False,
    )


def test_doctor_calls_carry_a_timeout() -> None:
    """Every Kubernetes API invocation carries a bounded client-side request timeout."""
    crashed = crashlooping_pod("app-crash", "default")
    core = FakeCoreV1(pods=[crashed], nodes=[node("worker-1")])

    collect(core, tail=20)
    timeouts = [kwargs.get("_request_timeout") for _, kwargs in core.calls]
    assert len(timeouts) >= 3
    assert all(t == DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS for t in timeouts)


def test_doctor_uses_the_kubernetes_api_only() -> None:
    """Doctor relies exclusively on the Kubernetes API, never importing Prometheus or LogQL."""
    import inspect

    import devops_cli.k8s.doctor as doctor_mod

    core = FakeCoreV1(pods=[healthy_pod("app-1")], nodes=[node("worker-1")])
    collect(core)

    allowed_methods = {
        "list_node",
        "list_pod_for_all_namespaces",
        "list_namespaced_pod",
        "list_event_for_all_namespaces",
        "list_namespaced_event",
        "read_namespaced_pod_log",
    }
    recorded_methods = {method for method, _ in core.calls}
    assert recorded_methods.issubset(allowed_methods)

    src = inspect.getsource(doctor_mod)
    assert "devops_cli.commands.prometheus" not in src
    assert "devops_cli.k8s.logql" not in src


def test_doctor_namespace_narrows_the_calls() -> None:
    """Specifying --namespace scopes pod and event listing to the selected namespace."""
    core = FakeCoreV1()
    collect(core, namespace="production")

    recorded = [(method, kwargs.get("namespace")) for method, kwargs in core.calls]
    assert ("list_node", None) in recorded
    assert ("list_namespaced_pod", "production") in recorded
    assert ("list_namespaced_event", "production") in recorded
    assert not any(
        m in {"list_pod_for_all_namespaces", "list_event_for_all_namespaces"} for m, _ in recorded
    )


def test_doctor_json_output_round_trips(cluster: FakeCluster, cli: Callable[..., Any]) -> None:
    """JSON and YAML output formats serialize the DoctorReport correctly."""
    cluster.context_names.append("test-cluster")
    cluster.core = FakeCoreV1(nodes=[node("worker-broken", ready="False")])
    cluster.version = FakeVersion("v1.37.1")
    KubernetesService.install(cluster)

    res_json = cli("k8s", "doctor", "--context", "test-cluster", "--format", "json")
    res_yaml = cli("k8s", "doctor", "--context", "test-cluster", "--format", "yaml")

    assert (res_json.exit_code, res_yaml.exit_code) == (2, 2)
    data_json = json.loads(res_json.stdout)
    data_yaml = yaml.safe_load(res_yaml.stdout)

    json_tuple = (
        data_json["context"],
        len(data_json["findings"]),
        data_json["findings"][0]["rule"],
    )
    yaml_tuple = (
        data_yaml["context"],
        len(data_yaml["findings"]),
        data_yaml["findings"][0]["rule"],
    )
    assert (json_tuple, yaml_tuple, data_yaml) == (
        ("test-cluster", 1, CONST_K8S_DOCTOR_RULE_NODE_NOT_READY),
        ("test-cluster", 1, CONST_K8S_DOCTOR_RULE_NODE_NOT_READY),
        data_json,
    )


def test_doctor_exit_codes(cluster: FakeCluster, cli: Callable[..., Any]) -> None:
    """Exit codes are 0 (clean), 2 (findings), and 1 (unreachable/error with secret masking)."""
    clean_core = FakeCoreV1(nodes=[node("worker-1", ready="True")], pods=[healthy_pod("app-1")])
    findings_core = FakeCoreV1(nodes=[node("worker-1", ready="False")], pods=[])
    secret_err = Exception("Auth failed: token=secret_token_xyz123 invalid credentials")
    error_core = FakeCoreV1(nodes=secret_err)

    cluster.version = FakeVersion("v1.37.1")

    cluster.core = clean_core
    KubernetesService.install(cluster)
    res_clean = cli("k8s", "doctor")

    cluster.core = findings_core
    KubernetesService.install(cluster)
    res_findings = cli("k8s", "doctor")

    cluster.core = error_core
    KubernetesService.install(cluster)
    res_err = cli("k8s", "doctor")

    assert (res_clean.exit_code, res_findings.exit_code, res_err.exit_code) == (0, 2, 1)
    assert "No problems were found." in res_clean.stdout
    assert "secret_token_xyz123" not in res_err.stdout + res_err.stderr

    # Format json and yaml also retain exit code 2 when findings are present
    cluster.core = findings_core
    KubernetesService.install(cluster)
    res_fmt_json = cli("k8s", "doctor", "--format", "json")
    res_fmt_yaml = cli("k8s", "doctor", "--format", "yaml")
    assert (res_fmt_json.exit_code, res_fmt_yaml.exit_code) == (2, 2)


def test_doctor_dry_run_makes_no_request(cli: Callable[..., Any]) -> None:
    """Dry run performs no external requests, loads no kubeconfig, and renders the request plan."""
    result = cli("k8s", "doctor", "--dry-run")

    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert (
        any("list_node cluster" in line for line in lines),
        any("list_pod_for_all_namespaces all namespaces" in line for line in lines),
        any("list_event_for_all_namespaces" in line for line in lines),
        any("read_namespaced_pod_log" in line for line in lines),
    ) == (True, True, True, True)


def test_doctor_dry_run_includes_get_code() -> None:
    """Doctor dry-run request plan includes VersionApi.get_code."""
    from devops_cli.k8s.doctor import plan_doctor_requests

    planned = plan_doctor_requests()
    methods = [req.method for req in planned]
    assert "get_code" in methods


def test_doctor_warns_on_kubectl_version_skew() -> None:
    """A snapshot whose server minor is more than one away from locked kubectl minor yields one warning finding."""
    snap = Snapshot(nodes=[node("worker-1")])
    setattr(snap, "server_version", "v1.31.4+k3s1")
    report = diagnose(snap)
    findings = [f for f in report.findings if f.rule == "version-skew"]
    assert len(findings) == 1
    f = findings[0]
    assert (f.severity, f.class_, f.resource) == ("warning", "cluster", "kubectl")
    assert "1.37.1" in f.cause
    assert "v1.31.4+k3s1" in f.cause or "1.31.4" in f.cause or "1.31" in f.cause
    assert any("1.36" in ev or "1.38" in ev for ev in f.evidence) or "1.36" in f.cause


def test_doctor_accepts_kubectl_within_supported_skew() -> None:
    """A snapshot whose server minor is within one minor of locked kubectl yields no kubectl skew finding."""
    snap = Snapshot(nodes=[node("worker-1")])
    setattr(snap, "server_version", "v1.37.0")
    report = diagnose(snap)
    findings = [f for f in report.findings if f.rule == "version-skew" and f.resource == "kubectl"]
    assert findings == []


def test_doctor_warns_on_kubelet_older_than_skew_policy() -> None:
    """Kubelets older than the API server by more than the skew policy allow yield a finding per node."""
    from kubernetes import client as k8s_client

    n1 = node("worker-ok")
    n1.status.node_info = k8s_client.V1NodeSystemInfo(
        architecture="amd64",
        boot_id="",
        container_runtime_version="containerd://1.7.0",
        kernel_version="",
        kube_proxy_version="v1.35.0",
        kubelet_version="v1.35.0",
        machine_id="",
        operating_system="linux",
        os_image="",
        system_uuid="",
    )
    n2 = node("worker-old")
    n2.status.node_info = k8s_client.V1NodeSystemInfo(
        architecture="amd64",
        boot_id="",
        container_runtime_version="containerd://1.7.0",
        kernel_version="",
        kube_proxy_version="v1.31.0",
        kubelet_version="v1.31.0",
        machine_id="",
        operating_system="linux",
        os_image="",
        system_uuid="",
    )
    snap = Snapshot(nodes=[n1, n2])
    setattr(snap, "server_version", "v1.35.0")
    report = diagnose(snap)
    kubelet_findings = [
        f for f in report.findings if f.rule == "version-skew" and f.resource.startswith("Node/")
    ]
    assert len(kubelet_findings) == 1
    f = kubelet_findings[0]
    assert (f.severity, f.class_, f.resource) == ("warning", "cluster", "Node/worker-old")
    assert "1.31.0" in f.cause
