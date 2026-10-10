"""Tests verifying Kubernetes monitoring stack integration and dashboard metric invariants."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml

from devops_cli.commands.k8s.networking import _collect_port_forward_services
from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK
from tests.k8s_manifests import kustomized_objects

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"

# The host units whose journal reaches Loki at info and above and whose state Prometheus keeps (#1080).
HOST_UNITS = ("k3s", "k3s-agent", "nvidia-power-limit", "containerd", "systemd-journald")
HOST_UNIT_PATTERN = f"({'|'.join(HOST_UNITS)})\\.service"

# The k8s-monitoring chart's presets that set an Alloy collector's controller (`collectors/presets/`).
CONTROLLER_PRESETS = {"singleton", "daemonset", "statefulset", "deployment"}

# The scrape jobs prometheus 29.35.0's values.yaml defines. The chart renders each one unless its
# `scrapeConfigs` entry sets `enabled: false`, so a job the values leave out is on.
PROMETHEUS_DEFAULT_JOBS = (
    "prometheus",
    "kubernetes-api-servers",
    "kubernetes-nodes",
    "kubernetes-nodes-cadvisor",
    "kubernetes-service-endpoints",
    "kubernetes-service-endpoints-slow",
    "prometheus-pushgateway",
    "kubernetes-services",
    "kubernetes-pods",
    "kubernetes-pods-slow",
)

# The Alloy discovery rules that copy a pod's node name to `node` and to `instance`, with their
# whitespace normalised.
NODE_RULE = 'source_labels = ["__meta_kubernetes_pod_node_name"] target_label = "node"'
INSTANCE_RULE = 'source_labels = ["__meta_kubernetes_pod_node_name"] target_label = "instance"'

# Pod labels the charts put on the components they install; the repo's values do not hold them.
LOKI_POD_LABELS = {"app.kubernetes.io/name": "loki", "app.kubernetes.io/component": "single-binary"}
DCGM_POD_LABELS = {"app.kubernetes.io/name": "dcgm-exporter"}
ALERTMANAGER_POD_LABELS = {"app.kubernetes.io/name": "alertmanager"}
COLLECTOR_POD_LABELS = {"app.kubernetes.io/name": "opentelemetry-collector"}

# Metrics ports k3s and the charts set, which the repo's values do not hold.
COREDNS_NAMESPACE = "kube-system"
COREDNS_METRICS_PORT = 9153
LOKI_METRICS_PORT = 3100  # Loki's http-metrics port, which the Loki integration scrapes
DCGM_METRICS_PORT = 9400


def _k8s_yaml(relative: str) -> Any:
    with open(K8S_DIR / relative, encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.CSafeLoader)


def _k8s_monitoring_values() -> Any:
    return _k8s_yaml("monitoring/k8s-monitoring-values.yaml")


def _squashed(text: str) -> str:
    """Alloy configuration with its whitespace normalised, for substring checks."""
    return " ".join(text.split())


def _argo_namespace(app: str) -> str:
    """The namespace Argo CD installs an Application into."""
    namespace: str = _k8s_yaml(f"argocd/apps/{app}.yaml")["spec"]["destination"]["namespace"]
    return namespace


def _integration(values: dict[str, Any], kind: str) -> dict[str, Any]:
    """The one instance of a k8s-monitoring service integration."""
    (instance,) = values["integrations"][kind]["instances"]
    return dict(instance)


def _server_jobs(prometheus: dict[str, Any]) -> tuple[str, ...]:
    """The scrape jobs the Prometheus chart renders: its defaults unless turned off, and any added."""
    jobs = prometheus.get("scrapeConfigs", {})
    return tuple(
        sorted(
            job
            for job in {*PROMETHEUS_DEFAULT_JOBS, *jobs}
            if jobs.get(job, {}).get("enabled", True)
        )
    )


def _server_pod_namespaces(prometheus: dict[str, Any]) -> str:
    """The namespace regex the server's kubernetes-pods job keeps before the chart's own rules."""
    rules = yaml.safe_load(prometheus["scrapeConfigs"]["kubernetes-pods"]["pre_relabel_configs"])
    (regex,) = [
        rule["regex"]
        for rule in rules
        if rule.get("action") == "keep"
        and rule.get("source_labels") == ["__meta_kubernetes_namespace"]
    ]
    return str(regex)


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
        "kube_pod_container_status_ready",
        "kube_pod_container_status_last_terminated_exitcode",
        "kube_pod_container_status_terminated",
        "kube_pod_container_status_waiting",
        "kube_deployment_status_replicas_unavailable",
    }

    assert (required_cadvisor.issubset(cadvisor_inc), required_ksm.issubset(ksm_inc)) == (
        True,
        True,
    )


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
    """Host metrics have no keep rule: node-exporter's collector flags decide what is collected,
    and Prometheus keeps every series it serves (#1129). The series that explain a host failure
    (#1080: boot time, temperatures with their chip names, pressure, EDAC memory errors, NVMe,
    filesystem space and the host units' state) come through because node-exporter serves them.
    The systemd collector is turned on here for the host units only: it reads unit state over
    the host's D-Bus socket, which the node's root mount already exposes.

    The keep sources are rebuilt the way the chart's `_linux_hosts.alloy.tpl` concatenates them
    (the default list unless `useDefaultAllowList` is false, the integration list when
    `useIntegrationAllowList` is true, then `includeMetrics`), without the lists' contents."""
    values = _k8s_monitoring_values()
    tuning = values["hostMetrics"]["linuxHosts"]["metricsTuning"]
    exporter = values["telemetryServices"]["node-exporter"]
    keep_sources = [
        source
        for source, on in (
            ("default", tuning.get("useDefaultAllowList", True)),
            ("integration", tuning.get("useIntegrationAllowList", False)),
            ("includeMetrics", bool(tuning.get("includeMetrics"))),
        )
        if on
    ]

    assert (keep_sources, exporter["extraArgs"], exporter["env"]) == (
        [],
        [
            "--collector.filesystem.fs-types-exclude=^(autofs|binfmt_misc|bpf|cgroup2?|configfs"
            "|debugfs|devpts|devtmpfs|fusectl|hugetlbfs|iso9660|mqueue|nsfs|overlay|proc|procfs"
            "|pstore|rpc_pipefs|securityfs|selinuxfs|squashfs|erofs|sysfs|tracefs|tmpfs|ramfs)$",
            "--collector.systemd",
            f"--collector.systemd.unit-include={HOST_UNIT_PATTERN}",
        ],
        {"DBUS_SYSTEM_BUS_ADDRESS": "unix:path=/host/root/run/dbus/system_bus_socket"},
    )


def test_each_alloy_collector_runs_in_one_controller_preset() -> None:
    """Each Alloy collector names exactly one of the chart's controller presets (#1129).
    `clusterEvents` runs unclustered, so its collector must be one pod: the chart's `singleton`
    preset makes it a one-replica Deployment, and without a preset the Alloy chart defaults to a
    DaemonSet, where every node's pod watches and ships the whole event stream."""
    values = _k8s_monitoring_values()
    controllers = {
        name: sorted(CONTROLLER_PRESETS.intersection(collector.get("presets", [])))
        for name, collector in values["collectors"].items()
    }
    events = values["clusterEvents"]

    assert (
        controllers,
        controllers[events["collector"]],
        events.get("clustering", False),
    ) == (
        {
            "alloy-metrics": ["statefulset"],
            "alloy-singleton": ["singleton"],
            "alloy-logs": ["daemonset"],
        },
        ["singleton"],
        False,
    )


def test_alloy_writes_the_cluster_name_once() -> None:
    """Alloy labels what it writes to Prometheus with the cluster name as `cluster` only (#1129).
    Dashboards and rules key on `cluster`; the chart default also writes `k8s_cluster_name`."""
    values = _k8s_monitoring_values()

    assert values["destinations"]["localPrometheus"]["clusterLabels"] == ["cluster"]


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


def test_deploy_stack_applies_the_monitoring_services_the_stack_addresses() -> None:
    """deploy-stack applies the root kustomization (`kubectl apply -k k8s/`) for every stack. No
    chart creates the `prometheus` Service that Alloy writes to and Grafana queries, or the Services
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

    helm_services = {(r["namespace"], r["name"]) for r in _HELM_RELEASES_BY_STACK.get("infra", [])}
    assert sorted(addressed - kustomized_objects(K8S_DIR, "Service") - helm_services) == []


def test_dcgm_exporter_is_scraped_by_the_integration_and_holds_sys_admin() -> None:
    """The k8s-monitoring dcgm-exporter integration scrapes the exporter every 15s (#1130), so the
    chart's own ServiceMonitor, on by chart default, stays off. Datacenter GPUs need SYS_ADMIN for
    the DCGM host engine's hardware counters."""
    data = _k8s_yaml("monitoring/dcgm-exporter-values.yaml")
    caps = data.get("securityContext", {}).get("capabilities", {}).get("add", [])
    integration = _integration(_k8s_monitoring_values(), "dcgm-exporter")

    assert (
        "SYS_ADMIN" in caps,
        data.get("serviceMonitor"),
        integration["metrics"]["scrapeInterval"],
    ) == (True, {"enabled": False}, "15s")


def test_scrape_ownership_moves_to_k8s_monitoring() -> None:
    """The Prometheus server scrapes only itself and the otel collector, and k8s-monitoring
    discovers every other target (#1130).

    The collector stays on the server so its export failures stay visible when Alloy is what
    fails. Both server jobs take the cluster label from one anchor, equal to k8s-monitoring's
    `cluster.name`. Alloy finds the other annotated pods through annotation autodiscovery, with
    the `prometheus.io/*` keys they already carry and without the ServiceAccount token. CoreDNS,
    Loki and DCGM come through the chart's kubeDNS job and integrations. Every Alloy job that
    replaces a server job keeps the pod's node as `node`, which the node silence matches.
    Alertmanager names its container, so the config-reloader sidecar's target, rewritten to the
    annotated port, does not scrape it twice."""
    prometheus = _k8s_yaml("monitoring/prometheus-values.yaml")
    values = _k8s_monitoring_values()
    jobs = prometheus["scrapeConfigs"]
    (cluster_rule,) = yaml.safe_load(jobs["prometheus"]["post_relabel_configs"])
    autodiscovery = values["annotationAutodiscovery"]
    kube_dns = values["clusterMetrics"]["kubeDNS"]
    loki = _integration(values, "loki")
    dcgm = _integration(values, "dcgm-exporter")
    dcgm_rules = _squashed(dcgm["extraDiscoveryRules"])
    loki_annotations = _k8s_yaml("logging/loki-values.yaml")["singleBinary"].get("podAnnotations")

    assert (
        _server_jobs(prometheus),
        _server_pod_namespaces(prometheus),
        jobs["kubernetes-pods"]["post_relabel_configs"]
        == jobs["prometheus"]["post_relabel_configs"],
        (cluster_rule["action"], cluster_rule["target_label"], cluster_rule["replacement"]),
        (autodiscovery["enabled"], autodiscovery["collector"]),
        autodiscovery["annotations"],
        (
            autodiscovery["excludeNamespaces"],
            autodiscovery["services"]["enabled"],
            autodiscovery["bearerToken"]["enabled"],
        ),
        NODE_RULE in _squashed(autodiscovery["extraDiscoveryRules"]),
        (kube_dns["enabled"], NODE_RULE in _squashed(kube_dns["extraDiscoveryRules"])),
        values["integrations"]["collector"],
        (loki["labelSelectors"], loki["logs"]["enabled"], "tuning" in loki.get("metrics", {})),
        (
            dcgm["labelSelectors"],
            dcgm["metrics"]["scrapeInterval"],
            NODE_RULE in dcgm_rules,
            INSTANCE_RULE in dcgm_rules,
        ),
        sorted(key for key in loki_annotations or {} if key.startswith("prometheus.io/")),
        _k8s_yaml("monitoring/dcgm-exporter-values.yaml")["serviceMonitor"],
        prometheus["alertmanager"]["podAnnotations"],
    ) == (
        ("kubernetes-pods", "prometheus"),
        "otel",
        True,
        ("replace", "cluster", values["cluster"]["name"]),
        (True, "alloy-metrics"),
        {
            "scrape": "prometheus.io/scrape",
            "metricsPortNumber": "prometheus.io/port",
            "metricsPath": "prometheus.io/path",
        },
        (["otel"], False, False),
        True,
        (True, True),
        "alloy-metrics",
        (LOKI_POD_LABELS, False, False),
        (DCGM_POD_LABELS, "15s", True, True),
        [],
        {"enabled": False},
        {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "9093",
            "k8s.grafana.com/metrics.container": "alertmanager",
        },
    )


@dataclass(frozen=True)
class _Pods:
    """A component's pods as a scrape sees them."""

    namespace: str
    labels: dict[str, str]
    annotations: dict[str, str]
    chart_monitor: bool = False  # the component's own chart renders a ServiceMonitor for it


def _repo_scrape_sources() -> dict[str, Any]:
    """The values and manifests that decide what scrapes each annotated component."""
    return {
        "prometheus": _k8s_yaml("monitoring/prometheus-values.yaml"),
        "k8s-monitoring": _k8s_monitoring_values(),
        "dcgm-exporter": _k8s_yaml("monitoring/dcgm-exporter-values.yaml"),
        "otel": _k8s_yaml("otel/values.yaml"),
        "loki": _k8s_yaml("logging/loki-values.yaml"),
        "cloudflared": _k8s_yaml("cloudflared/deployment.yaml"),
        "roadmap-service": _k8s_yaml("devops/roadmap-service/deployment.yaml"),
    }


def _deployment_pods(deployment: dict[str, Any]) -> _Pods:
    template = deployment["spec"]["template"]["metadata"]
    return _Pods(
        deployment["metadata"]["namespace"], template["labels"], template.get("annotations", {})
    )


def _annotated_components(sources: dict[str, Any]) -> dict[str, _Pods]:
    """The components the server's pod discovery scraped before #1130, and DCGM."""
    return {
        "cloudflared": _deployment_pods(sources["cloudflared"]),
        "roadmap-service": _deployment_pods(sources["roadmap-service"]),
        "alertmanager": _Pods(
            _argo_namespace("prometheus"),
            ALERTMANAGER_POD_LABELS,
            sources["prometheus"]["alertmanager"].get("podAnnotations", {}),
        ),
        "otel-collector": _Pods(
            _argo_namespace("otel-collector"),
            COLLECTOR_POD_LABELS,
            sources["otel"].get("podAnnotations", {}),
        ),
        "loki": _Pods(
            _argo_namespace("loki"),
            LOKI_POD_LABELS,
            sources["loki"]["singleBinary"].get("podAnnotations") or {},
        ),
        "dcgm-exporter": _Pods(
            _argo_namespace("dcgm-exporter"),
            DCGM_POD_LABELS,
            {},
            # The chart renders its ServiceMonitor unless the values turn it off.
            chart_monitor=sources["dcgm-exporter"].get("serviceMonitor", {}).get("enabled", True),
        ),
    }


def _scrape_owners(sources: dict[str, Any]) -> dict[str, list[str]]:
    """Every scrape that claims each annotated component."""
    server_namespaces = _server_pod_namespaces(sources["prometheus"])
    values = sources["k8s-monitoring"]
    autodiscovery = values["annotationAutodiscovery"]
    instances = [
        (f"integrations/{kind}", instance["labelSelectors"])
        for kind, integration in values["integrations"].items()
        if isinstance(integration, dict)
        for instance in integration.get("instances", [])
    ]

    def owners(pods: _Pods) -> list[str]:
        server = pods.annotations.get("prometheus.io/scrape") == "true" and bool(
            re.fullmatch(server_namespaces, pods.namespace)
        )
        autodiscovered = (
            autodiscovery["enabled"] is True
            and pods.annotations.get(autodiscovery["annotations"]["scrape"]) == "true"
            and pods.namespace not in autodiscovery["excludeNamespaces"]
        )
        return [
            *(["kubernetes-pods"] if server else []),
            *(["annotationAutodiscovery"] if autodiscovered else []),
            *(owner for owner, selectors in instances if selectors.items() <= pods.labels.items()),
            *(["chart ServiceMonitor"] if pods.chart_monitor else []),
        ]

    return {name: owners(pods) for name, pods in _annotated_components(sources).items()}


def test_each_annotated_component_has_one_scrape_owner() -> None:
    """Each component the server's pod discovery found before #1130 has exactly one scrape: none
    leaves a gap in its series, and two would double every series on its dashboards."""
    assert _scrape_owners(_repo_scrape_sources()) == {
        "cloudflared": ["annotationAutodiscovery"],
        "roadmap-service": ["annotationAutodiscovery"],
        "alertmanager": ["annotationAutodiscovery"],
        "otel-collector": ["kubernetes-pods"],
        "loki": ["integrations/loki"],
        "dcgm-exporter": ["integrations/dcgm-exporter"],
    }


def _drop_alertmanager_scrape_annotation(sources: dict[str, Any]) -> None:
    del sources["prometheus"]["alertmanager"]["podAnnotations"]["prometheus.io/scrape"]


def _drop_collector_annotations(sources: dict[str, Any]) -> None:
    del sources["otel"]["podAnnotations"]


def _autodiscover_the_otel_namespace(sources: dict[str, Any]) -> None:
    sources["k8s-monitoring"]["annotationAutodiscovery"]["excludeNamespaces"].remove("otel")


def _annotate_loki_again(sources: dict[str, Any]) -> None:
    sources["loki"]["singleBinary"]["podAnnotations"] = {
        "prometheus.io/scrape": "true",
        "prometheus.io/port": str(LOKI_METRICS_PORT),
    }


@pytest.mark.parametrize(
    ("mutate", "unowned_or_twice_owned"),
    [
        (_drop_alertmanager_scrape_annotation, {"alertmanager": []}),
        (_drop_collector_annotations, {"otel-collector": []}),
        (
            _autodiscover_the_otel_namespace,
            {"otel-collector": ["kubernetes-pods", "annotationAutodiscovery"]},
        ),
        (_annotate_loki_again, {"loki": ["annotationAutodiscovery", "integrations/loki"]}),
    ],
    ids=[
        "alertmanager-unannotated",
        "collector-unannotated",
        "otel-autodiscovered",
        "loki-annotated",
    ],
)
def test_a_component_with_no_scrape_owner_or_two_fails(
    mutate: Callable[[dict[str, Any]], None], unowned_or_twice_owned: dict[str, list[str]]
) -> None:
    """Pin the ownership check on the mutations that break it."""
    sources = _repo_scrape_sources()
    mutate(sources)

    assert {
        name: owners for name, owners in _scrape_owners(sources).items() if len(owners) != 1
    } == unowned_or_twice_owned


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


def _peer_in(peer: dict[str, Any], policy_ns: str, target_ns: str) -> bool:
    """Whether a NetworkPolicy peer selects pods in `target_ns`.

    A bare `podSelector` selects pods in the policy's own namespace. An ipBlock peer names
    addresses rather than a namespace, so it is not counted.
    """
    if "namespaceSelector" in peer:
        selector = peer["namespaceSelector"].get("matchLabels", {})
        return bool(selector.get("kubernetes.io/metadata.name") == target_ns)
    return "podSelector" in peer and policy_ns == target_ns


def _egress_rules_to(rules: list[dict[str, Any]], policy_ns: str, target_ns: str, port: int) -> int:
    """How many egress rules of a policy in `policy_ns` admit `port` in `target_ns`."""
    return sum(
        1
        for rule in rules
        if any(_peer_in(peer, policy_ns, target_ns) for peer in rule.get("to", []))
        and ("ports" not in rule or any(p.get("port") == port for p in rule["ports"]))
    )


def test_every_scrape_port_has_one_egress_rule() -> None:
    """Alloy's collectors and the Prometheus server both run in `monitoring`, behind its
    perimeter, so each port they scrape needs an egress rule there (#1130). Without one the
    scrape is dropped; with two, narrowing one rule would leave the port open through the other.
    The ports are the annotated pods' own, Traefik's metrics entry point, and the ports the
    charts and k3s set for CoreDNS, Loki and DCGM."""
    policy = _k8s_yaml("monitoring/networkpolicy.yaml")
    egress = policy["spec"]["egress"]
    traefik_port = _k8s_yaml("ingress/traefik-values.yaml")["ports"]["metrics"]["port"]
    scrapes = {
        *(
            (pods.namespace, int(pods.annotations["prometheus.io/port"]))
            for pods in _annotated_components(_repo_scrape_sources()).values()
            if "prometheus.io/port" in pods.annotations
        ),
        (_argo_namespace("traefik"), traefik_port),
        (COREDNS_NAMESPACE, COREDNS_METRICS_PORT),
        (_argo_namespace("loki"), LOKI_METRICS_PORT),
        (_argo_namespace("dcgm-exporter"), DCGM_METRICS_PORT),
    }
    counts = {
        scrape: _egress_rules_to(egress, policy["metadata"]["namespace"], *scrape)
        for scrape in scrapes
    }

    assert sorted(counts.items()) == [
        (("cloudflared", 2000), 1),
        (("devops", 8000), 1),
        (("kube-system", 9100), 1),
        (("kube-system", 9153), 1),
        (("logging", 3100), 1),
        (("monitoring", 9093), 1),
        (("monitoring", 9400), 1),
        (("otel", 8888), 1),
    ]


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
        _egress_rules_to(otel_egress, "otel", "logging", 3100) > 0,
        _egress_rules_to(otel_egress, "otel", "monitoring", 9090) > 0,
    ) == (True, True, True)
