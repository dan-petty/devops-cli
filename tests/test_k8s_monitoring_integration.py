"""Tests verifying Kubernetes monitoring stack integration and dashboard metric invariants."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from devops_cli.commands.k8s.networking import _collect_port_forward_services

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"

# The host units whose journal reaches Loki at info and above and whose state Prometheus keeps (#1080).
HOST_UNITS = ("k3s", "k3s-agent", "nvidia-power-limit", "containerd", "systemd-journald")
HOST_UNIT_PATTERN = f"({'|'.join(HOST_UNITS)})\\.service"


def _k8s_monitoring_values() -> Any:
    with open(K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    hm_tuning = data.get("hostMetrics", {}).get("linuxHosts", {}).get("metricsTuning", {})
    use_integration_allow_list = hm_tuning.get("useIntegrationAllowList")

    required_cadvisor = {
        "machine_cpu_cores",
        "container_cpu_cfs_throttled_seconds_total",
        "container_oom_events_total",
        "container_network_receive_errors_total",
        "container_network_transmit_errors_total",
        "container_cpu_usage_seconds_total",
        "container_memory_working_set_bytes",
        "container_network_receive_packets_total",
        "container_network_transmit_packets_total",
        "container_network_receive_packets_dropped_total",
        "container_network_transmit_packets_dropped_total",
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
        use_integration_allow_list,
    ) == (True, True, True)


def test_node_journals_reach_loki_through_the_alloy_logs_daemonset() -> None:
    """Each node's journal reaches Loki through the alloy-logs DaemonSet that already reads pod
    logs, with no other agent (#1080). Kernel lines are kept at every priority (GPU Xid, MCE and
    thermal lines), the host units and systemd's own lines about them at info and above, and every
    other line at warning and above. Each unit has its own rate limit; kernel lines have none."""
    values = _k8s_monitoring_values()
    node_logs = values["nodeLogs"]
    rules = " ".join(node_logs["extraDiscoveryRules"].split())
    stages = " ".join(node_logs["extraLogProcessingStages"].split())
    alloy_unit_pattern = HOST_UNIT_PATTERN.replace("\\", "\\\\")  # Alloy strings escape "\"

    assert (
        node_logs["enabled"],
        node_logs["collector"],
        values["collectors"][node_logs["collector"]]["presets"],
        node_logs.get("journal", {}).get("units", []),
        node_logs["journalLabels"],
        node_logs["structuredMetadata"],
        'source_labels = ["__journal__transport"] regex = "kernel" target_label = "__tmp_keep"'
        in rules,
        'source_labels = ["__journal_priority", "__journal__systemd_unit", "__journal_unit"]'
        f' separator = ";" regex = "[0-6];(.*;)?{alloy_unit_pattern}(;.*)?"'
        ' target_label = "__tmp_keep"' in rules,
        'source_labels = ["__journal_priority"] regex = "[0-4]" target_label = "__tmp_keep"'
        in rules,
        'source_labels = ["__tmp_keep"] regex = "true" action = "keep"' in rules,
        stages,
    ) == (
        True,
        "alloy-logs",
        ["daemonset", "filesystem-log-reader"],
        [],
        {"transport": "transport"},
        {"boot_id": "boot_id"},
        True,
        True,
        True,
        True,
        'stage.limit { rate = 1 burst = 10000 by_label_name = "unit" drop = true }',
    )


def test_host_metrics_keep_the_series_that_explain_a_host_failure() -> None:
    """Prometheus keeps each node's boot time, temperatures, pressure, memory and NVMe health,
    filesystem space and the host units' state (#1080). The systemd collector is the one the
    chart's node-exporter leaves off: it reads unit state over the host's D-Bus socket, which the
    node's root mount already exposes, and only for the host units."""
    values = _k8s_monitoring_values()
    tuning = values["hostMetrics"]["linuxHosts"]["metricsTuning"]
    exporter = values["telemetryServices"]["node-exporter"]

    assert (
        tuning["useIntegrationAllowList"],
        tuning["includeMetrics"],
        exporter["extraArgs"],
        exporter["env"],
    ) == (
        True,
        [
            "node_time_seconds",
            "node_boot_time_seconds",
            "node_hwmon_temp_celsius",
            "node_hwmon_chip_names",
            "node_systemd_unit_state",
            "node_pressure_.*",
            "node_edac_correctable_errors_total",
            "node_edac_uncorrectable_errors_total",
            "node_nvme_info",
            "node_filesystem_avail_bytes",
            "node_filesystem_size_bytes",
            "node_uname_info",
            "node_load.*",
            "node_disk_io_now",
            "node_netstat_Tcp_CurrEstab",
        ],
        [
            "--collector.filesystem.fs-types-exclude=^(autofs|binfmt_misc|bpf|cgroup2?|configfs"
            "|debugfs|devpts|devtmpfs|fusectl|hugetlbfs|iso9660|mqueue|nsfs|overlay|proc|procfs"
            "|pstore|rpc_pipefs|securityfs|selinuxfs|squashfs|erofs|sysfs|tracefs|tmpfs|ramfs)$",
            "--collector.systemd",
            f"--collector.systemd.unit-include={HOST_UNIT_PATTERN}",
        ],
        {"DBUS_SYSTEM_BUS_ADDRESS": "unix:path=/host/root/run/dbus/system_bus_socket"},
    )


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


def test_otel_collector_remote_writes_to_the_path_alloy_serves() -> None:
    """Alloy's prometheus.receive_http serves only POST /api/v1/metrics/write, on the receiver
    feature's port (9090 in k8s-monitoring 4.5.2). It answers 404 on /api/v1/write, and the
    collector drops every devops-cli point as a permanent error (#829)."""
    with open(K8S_DIR / "otel" / "values.yaml", encoding="utf-8") as f:
        otel = yaml.safe_load(f)
    with open(K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml", encoding="utf-8") as f:
        receiver = yaml.safe_load(f)["prometheusMetricsReceiver"]

    endpoint = urlsplit(otel["config"]["exporters"]["prometheusremotewrite"]["endpoint"])
    assert (receiver.get("enabled"), endpoint.hostname, endpoint.port, endpoint.path) == (
        True,
        f"k8s-monitoring-{receiver['collector']}.monitoring.svc.cluster.local",
        receiver.get("port", 9090),
        "/api/v1/metrics/write",
    )


def _kustomize_services(kustomization_dir: Path) -> set[tuple[str, str]]:
    """(namespace, name) of every Service `kubectl apply -k` applies from this kustomization."""
    with open(kustomization_dir / "kustomization.yaml", encoding="utf-8") as f:
        kustomization = yaml.safe_load(f)
    services: set[tuple[str, str]] = set()
    for entry in kustomization.get("resources", []):
        path = kustomization_dir / entry
        if path.is_dir():
            services |= _kustomize_services(path)
            continue
        with open(path, encoding="utf-8") as f:
            for doc in yaml.safe_load_all(f):
                if doc and doc.get("kind") == "Service":
                    meta = doc["metadata"]
                    namespace = meta.get("namespace", kustomization.get("namespace", ""))
                    services.add((namespace, meta["name"]))
    return services


def test_deploy_stack_applies_the_monitoring_services_the_stack_addresses() -> None:
    """deploy-stack applies only the root kustomization (`kubectl apply -k k8s/`). No chart creates
    the `prometheus` Service that Alloy writes to and Grafana queries, or the Services
    `devops k8s port-forward` targets, so the root kustomization must apply them (#912)."""
    with open(K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml", encoding="utf-8") as f:
        alloy_url = yaml.safe_load(f)["destinations"]["localPrometheus"]["url"]
    with open(K8S_DIR / "monitoring" / "grafana-values.yaml", encoding="utf-8") as f:
        datasources = yaml.safe_load(f)["datasources"]["datasources.yaml"]["datasources"]
    grafana_url = next(d["url"] for d in datasources if d["type"] == "prometheus")

    addressed = {
        tuple(reversed(str(urlsplit(url).hostname).split(".")[:2]))
        for url in (alloy_url, grafana_url)
    }
    addressed |= {
        (namespace, service.removeprefix("svc/"))
        for namespace, service, _, _ in _collect_port_forward_services(["infra"], defaultdict(int))
        if namespace == "monitoring"
    }

    assert sorted(addressed - _kustomize_services(K8S_DIR)) == []


def test_dcgm_exporter_values_timeout_and_capabilities() -> None:
    """Verify DCGM exporter has bounded scrapeTimeout and SYS_ADMIN capability for datacenter GPUs."""
    dcgm_values_path = K8S_DIR / "monitoring" / "dcgm-exporter-values.yaml"
    with open(dcgm_values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sm = data.get("serviceMonitor", {})
    sec = data.get("securityContext", {})
    caps = sec.get("capabilities", {}).get("add", [])

    relabelings = sm.get("relabelings", [])
    target_labels = [r.get("targetLabel") for r in relabelings]

    assert (
        sm.get("enabled"),
        sm.get("interval"),
        sm.get("scrapeTimeout"),
        "SYS_ADMIN" in caps,
        target_labels,
    ) == (True, "15s", "10s", True, ["node", "instance"])


def _has_ingress_port_from_namespace(
    rules: list[dict[str, Any]], target_ns: str, target_port: int
) -> bool:
    """Predicate checking whether an ingress rule allows target_port from target_ns."""
    for rule in rules:
        ns_matches = any(
            src.get("namespaceSelector", {})
            .get("matchLabels", {})
            .get("kubernetes.io/metadata.name")
            == target_ns
            for src in rule.get("from", [])
        )
        port_matches = any(p.get("port") == target_port for p in rule.get("ports", []))
        if ns_matches and port_matches:
            return True
    return False


def _has_egress_port_to_namespace(
    rules: list[dict[str, Any]], target_ns: str, target_port: int
) -> bool:
    """Predicate checking whether an egress rule allows target_port to target_ns."""
    for rule in rules:
        ns_matches = any(
            dst.get("namespaceSelector", {})
            .get("matchLabels", {})
            .get("kubernetes.io/metadata.name")
            == target_ns
            for dst in rule.get("to", [])
        )
        port_matches = any(p.get("port") == target_port for p in rule.get("ports", []))
        if ns_matches and port_matches:
            return True
    return False


def test_otel_collector_logs_pipeline_exports_to_loki() -> None:
    """Verify that OTel collector logs pipeline exports to Loki push endpoint."""
    otel_values_path = K8S_DIR / "otel" / "values.yaml"
    with open(otel_values_path, encoding="utf-8") as f:
        otel = yaml.safe_load(f)

    loki_exp = otel["config"]["exporters"].get("otlp_http/loki", {})
    endpoint = loki_exp.get("endpoint")
    log_exporters = otel["config"]["service"]["pipelines"]["logs"]["exporters"]

    assert (
        endpoint,
        "otlp_http/loki" in log_exporters,
    ) == (
        "http://loki.logging.svc.cluster.local:3100/otlp",
        True,
    )


def test_otel_and_logging_network_policies_allow_telemetry_flow() -> None:
    """Verify network policies permit OTel collector egress to Loki/Alloy and Loki ingress from OTel."""
    logging_netpol = K8S_DIR / "logging" / "networkpolicy.yaml"
    with open(logging_netpol, encoding="utf-8") as f:
        log_doc = yaml.safe_load(f)

    otel_netpol = K8S_DIR / "otel" / "networkpolicy.yaml"
    with open(otel_netpol, encoding="utf-8") as f:
        otel_doc = yaml.safe_load(f)

    log_ingress = log_doc.get("spec", {}).get("ingress", [])
    otel_egress = otel_doc.get("spec", {}).get("egress", [])

    assert (
        _has_ingress_port_from_namespace(log_ingress, "otel", 3100),
        _has_egress_port_to_namespace(otel_egress, "logging", 3100),
        _has_egress_port_to_namespace(otel_egress, "monitoring", 9090),
    ) == (True, True, True)
