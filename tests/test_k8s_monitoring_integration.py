"""Tests verifying Kubernetes monitoring stack integration and dashboard metric invariants."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"


def test_k8s_monitoring_cadvisor_and_ksm_metrics_tuning() -> None:
    """Verify that cAdvisor and kube-state-metrics includeMetrics contain all dashboard metrics."""
    values_path = K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cm = data.get("clusterMetrics", {})
    cadvisor_inc = set(cm.get("cadvisor", {}).get("metricsTuning", {}).get("includeMetrics", []))
    ksm_inc = set(
        cm.get("kube-state-metrics", {}).get("metricsTuning", {}).get("includeMetrics", [])
    )

    required_cadvisor = {
        "machine_cpu_cores",
        "container_cpu_cfs_throttled_seconds_total",
        "container_oom_events_total",
        "container_network_receive_errors_total",
        "container_network_transmit_errors_total",
    }
    required_ksm = {
        "kube_deployment_labels",
        "kube_daemonset_labels",
        "kube_statefulset_labels",
        "kube_service_info",
        "kube_ingress_info",
        "kube_namespace_created",
        "kube_namespace_labels",
        "kube_networkpolicy_labels",
        "kube_endpoint_info",
        "kube_secret_info",
        "kube_pod_container_status_running",
        "kube_pod_status_qos_class",
        "kube_pod_status_reason",
        "kube_hpa_labels",
        "kube_pod_container_status_ready",
        "kube_pod_container_status_last_terminated_exitcode",
        "kube_pod_container_status_terminated",
        "kube_pod_container_status_waiting",
        "kube_deployment_status_replicas_unavailable",
    }

    assert (
        required_cadvisor.issubset(cadvisor_inc),
        required_ksm.issubset(ksm_inc),
    ) == (True, True)


def test_k8s_monitoring_ksm_telemetry_service_config() -> None:
    """Verify kube-state-metrics telemetry service enables endpoints collector and resource labels."""
    values_path = K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml"
    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ksm_svc = data.get("telemetryServices", {}).get("kube-state-metrics", {})
    deploy_enabled = ksm_svc.get("deploy")
    collectors_extra = ksm_svc.get("collectorsExtra", [])
    labels_allowlist = ksm_svc.get("metricLabelsAllowlist", [])

    has_endpoints = "endpoints" in collectors_extra
    has_namespaces = any(item.startswith("namespaces=") for item in labels_allowlist)
    has_deployments = any(item.startswith("deployments=") for item in labels_allowlist)
    has_statefulsets = any(item.startswith("statefulsets=") for item in labels_allowlist)
    has_daemonsets = any(item.startswith("daemonsets=") for item in labels_allowlist)
    has_hpas = any(item.startswith("horizontalpodautoscalers=") for item in labels_allowlist)
    has_netpols = any(item.startswith("networkpolicies=") for item in labels_allowlist)

    actual = (
        deploy_enabled,
        has_endpoints,
        has_namespaces,
        has_deployments,
        has_statefulsets,
        has_daemonsets,
        has_hpas,
        has_netpols,
    )
    expected = (True, True, True, True, True, True, True, True)
    assert actual == expected


def test_monitoring_networkpolicy_allows_coredns_metrics() -> None:
    """Verify monitoring NetworkPolicy egress permits CoreDNS metrics scraping on port 9153."""
    netpol_path = K8S_DIR / "monitoring" / "networkpolicy.yaml"
    with open(netpol_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    egress_rules = doc.get("spec", {}).get("egress", [])
    coredns_ports: set[int] = set()
    for rule in egress_rules:
        to_selectors = rule.get("to", [])
        is_kube_system = any(
            t.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
            == "kube-system"
            for t in to_selectors
        )
        if is_kube_system:
            for p in rule.get("ports", []):
                coredns_ports.add(p.get("port"))

    assert {53, 9153}.issubset(coredns_ports)


def test_otel_collector_is_scraped_once_through_its_pod_annotations() -> None:
    """The Prometheus server's kubernetes-pods job scrapes the collector through its pod
    annotations (#693). A ServiceMonitor would have Alloy scrape it a second time and double
    every collector series on the stack dashboards."""
    otel_values_path = K8S_DIR / "otel" / "values.yaml"
    with open(otel_values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    annotations = data.get("podAnnotations", {})
    assert (
        annotations.get("prometheus.io/scrape"),
        annotations.get("prometheus.io/port"),
        data.get("serviceMonitor", {}).get("enabled", False),
    ) == ("true", "8888", False)


def test_dcgm_exporter_values_timeout_and_capabilities() -> None:
    """Verify DCGM exporter has bounded scrapeTimeout and SYS_ADMIN capability for datacenter GPUs."""
    dcgm_values_path = K8S_DIR / "monitoring" / "dcgm-exporter-values.yaml"
    with open(dcgm_values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sm = data.get("serviceMonitor", {})
    sec = data.get("securityContext", {})
    caps = sec.get("capabilities", {}).get("add", [])

    assert (
        sm.get("enabled"),
        sm.get("interval"),
        sm.get("scrapeTimeout"),
        "SYS_ADMIN" in caps,
    ) == (True, "15s", "10s", True)
