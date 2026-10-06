"""Tests for Kubernetes cluster deployment health diagnosis (devops k8s doctor)."""

from __future__ import annotations

import datetime
import json
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
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
from devops_cli.k8s.doctor import collect, diagnose
from devops_cli.models.k8s import Finding
from tests.k8s_fakes import (
    NOW,
    FakeCoreV1,
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


def test_doctor_is_registered_with_its_options() -> None:
    """Verify that doctor command is registered and exposes its expected CLI options."""
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--help"])
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

    from devops_cli.k8s.doctor import _sort_findings

    unordered = [workload_warn, cluster_warn, workload_crit, cluster_crit]
    sorted_findings = _sort_findings(unordered, pod_restarts={})
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


def test_doctor_json_output_round_trips() -> None:
    """JSON and YAML output formats serialize the DoctorReport correctly."""
    runner = CliRunner()
    fake_core = FakeCoreV1(nodes=[node("worker-broken", ready="False")])

    with patch("devops_cli.k8s.doctor.get_k8s_client", return_value=fake_core):
        res_json = runner.invoke(app, ["doctor", "--context", "test-cluster", "--format", "json"])
        res_yaml = runner.invoke(app, ["doctor", "--context", "test-cluster", "--format", "yaml"])

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


def test_doctor_exit_codes() -> None:
    """Exit codes are 0 (clean), 2 (findings), and 1 (unreachable/error with secret masking)."""
    runner = CliRunner()
    clean_core = FakeCoreV1(nodes=[node("worker-1", ready="True")], pods=[healthy_pod("app-1")])
    findings_core = FakeCoreV1(nodes=[node("worker-1", ready="False")], pods=[])
    secret_err = Exception("Auth failed: token=secret_token_xyz123 invalid credentials")
    error_core = FakeCoreV1(nodes=secret_err)

    with patch("devops_cli.k8s.doctor.get_k8s_client", return_value=clean_core):
        res_clean = runner.invoke(app, ["doctor"])
    with patch("devops_cli.k8s.doctor.get_k8s_client", return_value=findings_core):
        res_findings = runner.invoke(app, ["doctor"])
    with patch("devops_cli.k8s.doctor.get_k8s_client", return_value=error_core):
        res_err = runner.invoke(app, ["doctor"])

    assert (res_clean.exit_code, res_findings.exit_code, res_err.exit_code) == (0, 2, 1)
    assert "No problems were found." in res_clean.stdout
    assert "secret_token_xyz123" not in res_err.stdout + res_err.stderr

    # Format json and yaml also retain exit code 2 when findings are present
    with patch("devops_cli.k8s.doctor.get_k8s_client", return_value=findings_core):
        res_fmt_json = runner.invoke(app, ["doctor", "--format", "json"])
        res_fmt_yaml = runner.invoke(app, ["doctor", "--format", "yaml"])
    assert (res_fmt_json.exit_code, res_fmt_yaml.exit_code) == (2, 2)


def test_doctor_dry_run_makes_no_request() -> None:
    """Dry run performs no external requests, loads no kubeconfig, and renders the request plan."""
    runner = CliRunner()
    with patch(
        "kubernetes.config.load_kube_config",
        side_effect=AssertionError("Kubeconfig loaded in dry-run"),
    ):
        result = runner.invoke(app, ["doctor", "--dry-run"])

    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert (
        any("list_node cluster" in line for line in lines),
        any("list_pod_for_all_namespaces all namespaces" in line for line in lines),
        any("list_event_for_all_namespaces" in line for line in lines),
        any("read_namespaced_pod_log" in line for line in lines),
    ) == (True, True, True, True)
