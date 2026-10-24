"""Alertmanager, its receiver and the homelab alert rules (#549), with #550's retention rules.

The rules live in `k8s/monitoring/prometheus-values.yaml` (`serverFiles.alerting_rules.yml`).
A rule over a series nothing in the stack serves never fires, so every expression may name
only the series in `SERVED_SERIES`, each served by a scrape this repository defines. The k3s
server runs the controller manager, scheduler and proxy in its own process, so no scrape
targets them and none of their series is listed: a rule over them would fire on the missing
target, as `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` did.

The checks read files only.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER
from devops_cli.prometheus.promql import selectors
from tests.support.paths import FIXTURES, REPO_ROOT

K8S = REPO_ROOT / "k8s"
PROMETHEUS_VALUES = K8S / "monitoring" / "prometheus-values.yaml"
GRAFANA_VALUES = K8S / "monitoring" / "grafana-values.yaml"
K8S_MONITORING_VALUES = K8S / "monitoring" / "k8s-monitoring-values.yaml"
PYROSCOPE_VALUES = K8S / "monitoring" / "pyroscope-values.yaml"
ALLOY_ALLOW_LIST = FIXTURES / "k8s_monitoring" / "integrations" / "alloy.yaml"

# Every series an alert rule may select, by what serves it.
SERVED_SERIES = frozenset(
    {
        # Recorded by Prometheus for every scrape.
        "up",
        # kube-state-metrics, deployed and scraped by k8s-monitoring.
        "kube_node_status_condition",
        "kube_persistentvolumeclaim_info",
        "kube_persistentvolumeclaim_resource_requests_storage_bytes",
        "kube_pod_info",
        "kube_pod_spec_volumes_persistentvolumeclaims_info",
        "kube_secret_info",
        # Not in the chart's default allow list: `metricsTuning.includeMetrics` keeps it (#1817).
        "kube_ingress_path",
        # The kubelet, scraped by k8s-monitoring (its default allow list), reports these only for
        # volumes whose plugin measures them. No claim on this cluster does (local-path volumes
        # are host directories), so the rule over them stays silent until one does.
        "kubelet_volume_stats_available_bytes",
        "kubelet_volume_stats_capacity_bytes",
        # node-exporter, scraped by k8s-monitoring's host metrics with no allow list (#1129);
        # systemd unit state comes from the collector #1080 turned on.
        "node_boot_time_seconds",
        "node_filesystem_avail_bytes",
        "node_filesystem_size_bytes",
        "node_systemd_unit_state",
        "node_time_seconds",
        # The DCGM exporter on every GPU node, through k8s-monitoring's dcgm-exporter integration.
        "DCGM_FI_DEV_GPU_TEMP",
        "DCGM_FI_DEV_POWER_USAGE",
        # The Prometheus server's self-scrape (`scrapeConfigs.prometheus`).
        "prometheus_config_last_reload_successful",
        "prometheus_notifications_alertmanagers_discovered",
        "prometheus_notifications_dropped_total",
        "prometheus_rule_evaluation_failures_total",
        "prometheus_tsdb_compactions_failed_total",
        "prometheus_tsdb_head_chunks_storage_size_bytes",
        "prometheus_tsdb_retention_limit_bytes",
        "prometheus_tsdb_size_retentions_total",
        "prometheus_tsdb_storage_blocks_bytes",
        "prometheus_tsdb_wal_storage_size_bytes",
        # Alloy collectors, scraped by k8s-monitoring's Alloy integration within its default allow
        # list (#1131).
        "loki_write_dropped_entries_total",
        "loki_write_sent_entries_total",
        "prometheus_remote_storage_samples_failed_total",
        # Loki, scraped by k8s-monitoring's Loki integration within its default allow list, which
        # finds Loki's pods only where the logging stack runs.
        "loki_compactor_apply_retention_last_successful_run_timestamp_seconds",
        "loki_request_duration_seconds_count",
        # Pyroscope, scraped through its ServiceMonitor (#1131, #1134).
        "pyroscope_request_duration_seconds_count",
        # Alertmanager, found through its pod annotations by k8s-monitoring's annotation
        # autodiscovery.
        "alertmanager_config_last_reload_successful",
        "alertmanager_notifications_failed_total",
        # Argo CD, cloudflared, CoreDNS (#822), and Valkey redis_exporter (#551).
        "argocd_app_info",
        "cloudflared_tunnel_ha_connections",
        "coredns_dns_responses_total",
        "redis_rejected_connections_total",
        "redis_up",
    }
)
SEVERITIES = frozenset({"critical", "warning"})
# Git names every Ingress host under the placeholder domain, and deploy-stack replaces it with
# the configured domain on the Argo CD Applications (k8s/README.md, GitOps).
PLACEHOLDER_HOST_REGEX = rf"(.+\.)?{re.escape(CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER)}"
PLACEHOLDER_HOST_EXPRESSION = (
    'count by (namespace, ingress) (kube_ingress_path{host=~"'
    + PLACEHOLDER_HOST_REGEX.replace("\\", "\\\\")
    + '"}) > 0'
)


@cache
def _yaml(path: Path) -> dict[str, Any]:
    """A values file, read once; the tests only read it."""
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _rules() -> list[dict[str, Any]]:
    """Every alerting rule the Prometheus server loads."""
    groups = _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    return [rule for group in groups for rule in group["rules"]]


def _unserved(expression: str) -> list[str]:
    """Each selector in an expression that names no metric or one nothing serves."""
    return [
        f"{expression}: {selector.metric}"
        for selector in selectors(expression)
        if selector.metric not in SERVED_SERIES
    ]


@pytest.mark.parametrize(
    ("expression", "unserved"),
    [
        ("up == 0", 0),
        ('absent(kube_scheduler_schedule_attempts_total{job="kube-scheduler"})', 1),
        ('{__name__=~"node_.+"} > 0', 1),
    ],
    ids=["served", "k3s-component", "no-metric-name"],
)
def test_the_served_series_check_rejects_what_nothing_serves(
    expression: str, unserved: int
) -> None:
    """Pin the check on literal expressions: an unknown series, and a selector with no name."""
    assert len(_unserved(expression)) == unserved


def test_every_alert_rule_selects_only_series_the_stack_serves() -> None:
    """A rule over a series no scrape serves stays silent, or fires on the missing target."""
    rules = _rules()
    assert (len(rules) > 0, [v for rule in rules for v in _unserved(rule["expr"])]) == (True, [])


def test_the_baseline_rule_set() -> None:
    """The rules #549 names (nodes, k3s and power-cap units, GPUs, storage, and self-health),
    and #550's two volume rules (`LogOrMetricVolumeDiskLow`, `PrometheusNearRetentionSizeCap`).

    A rule with a warning and a critical threshold is one alert name at two severities, so
    Alertmanager's critical-over-warning inhibition hides the warning while both fire.
    """
    assert sorted((rule["alert"], rule["labels"]["severity"]) for rule in _rules()) == [
        ("AlertmanagerConfigReloadFailed", "warning"),
        ("AlertmanagerNotificationsFailing", "warning"),
        ("AlloyLogEntriesDropped", "warning"),
        ("AlloyRemoteWriteSamplesFailed", "warning"),
        ("ArgoCdApplicationOutOfSync", "warning"),
        ("ArgoCdApplicationUnhealthy", "warning"),
        ("ArgoCdAutoSyncDisabled", "warning"),
        ("ArgoCdSyncOperationStuck", "warning"),
        ("CloudflareTunnelDegraded", "warning"),
        ("ClusterMetricsMissing", "critical"),
        ("CoreDnsServfailResponses", "warning"),
        ("GpuPowerLimitServiceNotActive", "critical"),
        ("GpuPowerOverSiteBudget", "critical"),
        ("GpuTemperatureHigh", "critical"),
        ("GpuTemperatureHigh", "warning"),
        ("HostFilesystemSpaceLow", "critical"),
        ("HostFilesystemSpaceLow", "warning"),
        ("IngressServesPlaceholderHost", "critical"),
        ("K3sServiceNotActive", "critical"),
        ("LocalPathNodeDiskHigh", "warning"),
        ("LogOrMetricVolumeDiskLow", "warning"),
        ("LokiRequestErrors", "warning"),
        ("LokiRetentionNotRunning", "warning"),
        ("NodeNotReady", "critical"),
        ("NodeRebooted", "warning"),
        ("PersistentVolumeSpaceLow", "warning"),
        ("PodLogsNotShipped", "warning"),
        ("PrometheusCompactionsFailing", "warning"),
        ("PrometheusConfigReloadFailed", "warning"),
        ("PrometheusDroppingAlerts", "warning"),
        ("PrometheusNearRetentionSizeCap", "warning"),
        ("PrometheusNotConnectedToAlertmanager", "warning"),
        ("PrometheusRuleEvaluationFailures", "warning"),
        ("PrometheusSizeLimitCutHistory", "warning"),
        ("PrometheusStorageNearClaim", "warning"),
        ("PyroscopeQueryErrors", "warning"),
        ("TargetDown", "warning"),
        ("ValkeyCacheErrors", "warning"),
    ]


def test_every_rule_waits_routes_and_explains() -> None:
    """Each rule states how long it waits, carries a routed severity, and says what is wrong."""
    rules = _rules()
    assert [
        rule["alert"]
        for rule in rules
        if "for" not in rule
        or rule["labels"]["severity"] not in SEVERITIES
        or not {"summary", "description"} <= rule.get("annotations", {}).keys()
    ] == []


def test_every_node_scoped_rule_names_its_node() -> None:
    """One `node=<name>` silence covers a node in planned maintenance (k8s/README.md, Alerting).

    node-exporter names its node in `instance`, so its rules copy it into `node`, and so does
    `TargetDown` for a target without a `node` label. The other node-scoped rules keep the
    `node` label their series carry.
    """
    from_instance = "{{ $labels.instance }}"
    assert {
        (rule["alert"], rule["labels"]["severity"]): rule["labels"]["node"]
        for rule in _rules()
        if "node" in rule["labels"]
    } == {
        ("TargetDown", "warning"): "{{ or $labels.node $labels.instance }}",
        ("NodeRebooted", "warning"): from_instance,
        ("K3sServiceNotActive", "critical"): from_instance,
        ("GpuPowerLimitServiceNotActive", "critical"): from_instance,
        ("HostFilesystemSpaceLow", "warning"): from_instance,
        ("HostFilesystemSpaceLow", "critical"): from_instance,
        ("LocalPathNodeDiskHigh", "warning"): from_instance,
    }


def _alertmanager() -> dict[str, Any]:
    """The Alertmanager subchart's values."""
    alertmanager: dict[str, Any] = _yaml(PROMETHEUS_VALUES)["alertmanager"]
    return alertmanager


def test_alertmanager_sends_nowhere_until_the_webhook_secret_exists() -> None:
    """The default receiver has no integration, and critical and warning alerts go to a webhook.

    The webhook reads its URL from a file in the optional `alertmanager-webhook` Secret, mounted
    as a directory (no `subPath`), so creating that Secret later wires a channel without a
    restart, and a missing Secret does not keep the pod from starting.
    """
    alertmanager = _alertmanager()
    config = alertmanager["config"]
    receivers = {receiver["name"]: receiver for receiver in config["receivers"]}
    webhook = receivers["webhook"]["webhook_configs"]
    mounts = {mount["secretName"]: mount for mount in alertmanager["extraSecretMounts"]}
    mount = mounts["alertmanager-webhook"]
    url_file = PurePosixPath(webhook[0]["url_file"])

    assert (
        alertmanager["enabled"],
        config["route"]["receiver"],
        sorted(receivers),
        set(receivers["null"]),
        [set(entry) for entry in webhook],
        [(r["receiver"], r["matchers"]) for r in config["route"]["routes"]],
        (str(url_file.parent), url_file.name),
        (mount["readOnly"], mount["optional"], "subPath" in mount),
    ) == (
        True,
        "null",
        ["null", "webhook"],
        {"name"},
        [{"url_file", "send_resolved"}],
        [("webhook", ['severity=~"critical|warning"'])],
        (mount["mountPath"], "url"),
        (True, True, False),
    )


def test_alertmanager_inhibits_follow_on_alerts() -> None:
    """A Not Ready node hides its own targets' TargetDown; a critical hides its own warning."""
    assert _alertmanager()["config"]["inhibit_rules"] == [
        {
            "source_matchers": ['alertname="NodeNotReady"'],
            "target_matchers": ['alertname="TargetDown"'],
            "equal": ["node"],
        },
        {
            "source_matchers": ['severity="critical"'],
            "target_matchers": ['severity="warning"'],
            "equal": ["alertname", "node", "gpu", "mountpoint"],
        },
    ]


def test_k8s_monitoring_scrapes_loki_and_alertmanager_for_their_health() -> None:
    """Loki and Alertmanager are found by k8s-monitoring where they run, with their stacks (#1130).

    The Prometheus values belong to the infra stack, and Loki only to the logging stack, so a
    static Loki target in them would be down for good on an infra-only cluster and keep
    `TargetDown` firing. The Loki integration selects Loki's pods by label, and annotation
    autodiscovery finds Alertmanager through its pod annotations; the container annotation keeps
    the config-reloader sidecar from being scraped on Alertmanager's port a second time.
    """
    values = _yaml(PROMETHEUS_VALUES)
    (loki,) = _yaml(K8S_MONITORING_VALUES)["integrations"]["loki"]["instances"]
    alertmanager = values["alertmanager"]["podAnnotations"]

    assert (
        loki["labelSelectors"],
        alertmanager,
        "extraScrapeConfigs" in values,
    ) == (
        {"app.kubernetes.io/name": "loki", "app.kubernetes.io/component": "single-binary"},
        {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "9093",
            "k8s.grafana.com/metrics.container": "alertmanager",
        },
        False,
    )


def test_the_claim_rule_divides_one_series_by_one() -> None:
    """`PrometheusStorageNearClaim` reads this server's own TSDB series, by `job`.

    `on ()` fails to evaluate when either side has a second series, as it did for hours on
    2026-10-01/02 while a leftover kube-prometheus-stack Prometheus and kube-state-metrics were
    scraped next to these. The left side is this server's self-scrape, and the claim size on the
    right is reduced with `max`.
    """
    (rule,) = [rule for rule in _rules() if rule["alert"] == "PrometheusStorageNearClaim"]
    assert [(s.metric, "job" in s.labels) for s in selectors(rule["expr"])] == [
        ("prometheus_tsdb_storage_blocks_bytes", True),
        ("prometheus_tsdb_wal_storage_size_bytes", True),
        ("prometheus_tsdb_head_chunks_storage_size_bytes", True),
        ("kube_persistentvolumeclaim_resource_requests_storage_bytes", False),
    ]


def test_the_image_gc_rule_warns_on_the_root_disk_of_nodes_with_local_path_pods() -> None:
    """`LocalPathNodeDiskHigh` warns at 85% used, where the kubelet starts image GC (#1634).

    It reads the root filesystem of each node that runs a pod on a `local-path` claim: the claim
    gives the storage class, the pod's volumes give the claim, and `kube_pod_info` gives the node.
    A pod on a local-path volume cannot start on another node, so DiskPressure on its node stops
    it. `HostFilesystemSpaceLow` fires later, at 10% free, on every node. Each join is `and`, not
    `group_left`: for a few minutes after a pod moves, `kube_pod_info` holds a series for each of
    its nodes, which a one-to-one join on the pod refuses to evaluate.
    """
    (rule,) = [rule for rule in _rules() if rule["alert"] == "LocalPathNodeDiskHigh"]
    assert (
        [(s.metric, s.labels) for s in selectors(rule["expr"])],
        '{storageclass="local-path"}' in rule["expr"],
        "> 0.85" in rule["expr"],
        "group_left" in rule["expr"] or "group_right" in rule["expr"],
        rule["for"],
    ) == (
        [
            ("node_filesystem_avail_bytes", frozenset({"mountpoint"})),
            ("node_filesystem_size_bytes", frozenset({"mountpoint"})),
            ("kube_pod_info", frozenset()),
            ("kube_pod_spec_volumes_persistentvolumeclaims_info", frozenset()),
            ("kube_persistentvolumeclaim_info", frozenset({"storageclass"})),
        ],
        True,
        True,
        False,
        "15m",
    )


def test_the_size_cap_rule_reads_this_server_only() -> None:
    """#550's `PrometheusNearRetentionSizeCap` reads this server's self-scrape, by `job`.

    Its matching is one-to-one, so a second Prometheus cannot stop it from evaluating, but
    unpinned it would hold that server to this one's `server.retentionSize` in its alert.
    """
    (rule,) = [rule for rule in _rules() if rule["alert"] == "PrometheusNearRetentionSizeCap"]
    found = [(s.metric, s.labels) for s in selectors(rule["expr"])]
    assert (found, rule["expr"].count('{job="prometheus"}')) == (
        [
            ("prometheus_tsdb_storage_blocks_bytes", frozenset({"job"})),
            ("prometheus_tsdb_wal_storage_size_bytes", frozenset({"job"})),
            ("prometheus_tsdb_head_chunks_storage_size_bytes", frozenset({"job"})),
            ("prometheus_tsdb_retention_limit_bytes", frozenset({"job"})),
            ("prometheus_tsdb_retention_limit_bytes", frozenset({"job"})),
        ],
        5,
    )


def test_grafana_provisions_the_alertmanager_datasource() -> None:
    """Grafana reads alerts and silences from the chart's Alertmanager Service."""
    datasources = _yaml(GRAFANA_VALUES)["datasources"]["datasources.yaml"]["datasources"]
    alertmanager = [ds for ds in datasources if ds["type"] == "alertmanager"]

    assert [
        (ds["uid"], ds["url"], ds["access"], ds["jsonData"]["implementation"])
        for ds in alertmanager
    ] == [
        (
            "alertmanager",
            "http://prometheus-alertmanager.monitoring.svc.cluster.local:9093",
            "proxy",
            "prometheus",
        )
    ]


def test_no_scrape_targets_the_components_k3s_runs_in_process() -> None:
    """Guard: k8s-monitoring scrapes no controller manager, scheduler or proxy, so `up` has none."""
    cluster_metrics = _yaml(K8S_MONITORING_VALUES)["clusterMetrics"]
    assert [
        component
        for component in ("controlPlane", "kubeControllerManager", "kubeScheduler", "kubeProxy")
        if cluster_metrics.get(component, {}).get("enabled") is True
    ] == []


def _allow_list(path: Path) -> tuple[str, frozenset[str]]:
    """A chart allow-list fixture's `(chart_version, metric_names)`."""
    text = path.read_text(encoding="utf-8")
    (version,) = [
        line.removeprefix("# chart: grafana/k8s-monitoring ").strip()
        for line in text.splitlines()
        if line.startswith("# chart: grafana/k8s-monitoring ")
    ]
    return version, frozenset(yaml.safe_load(text))


def test_alloy_grafana_and_pyroscope_are_scraped_and_pipeline_drops_alert() -> None:
    """The Alloy collectors, Grafana and Pyroscope are scraped, and dropped samples or log
    entries alert (#1131)."""
    groups = {
        group["name"]: group["rules"]
        for group in _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    }
    drop_alerts = {"AlloyRemoteWriteSamplesFailed", "AlloyLogEntriesDropped"}
    pipeline_rules = [
        (rule["alert"], rule["expr"], rule["for"], rule["labels"]["severity"])
        for rule in groups["homelab-telemetry-pipeline"]
        if rule["alert"] in drop_alerts
    ]
    integrations = _yaml(K8S_MONITORING_VALUES)["integrations"]
    (alloy,) = integrations["alloy"]["instances"]
    (grafana,) = integrations["grafana"]["instances"]
    pyroscope_monitor = _yaml(PYROSCOPE_VALUES)["serviceMonitor"]["enabled"]

    assert (
        pipeline_rules,
        alloy["name"],
        alloy["labelSelectors"],
        grafana,
        pyroscope_monitor,
    ) == (
        [
            (
                "AlloyRemoteWriteSamplesFailed",
                'increase(prometheus_remote_storage_samples_failed_total{job="integrations/alloy"}[15m]) > 0',
                "15m",
                "warning",
            ),
            (
                "AlloyLogEntriesDropped",
                'increase(loki_write_dropped_entries_total{job="integrations/alloy"}[15m]) > 0',
                "15m",
                "warning",
            ),
        ],
        "k8s-monitoring",
        {
            "app.kubernetes.io/name": [
                "alloy-metrics",
                "alloy-logs",
                "alloy-singleton",
                "alloy-profiles",
            ]
        },
        {"name": "grafana"},
        True,
    )


def test_pod_logs_not_shipped_alerts_with_node_from_pod_info() -> None:
    """`PodLogsNotShipped` alerts when an `alloy-logs` pod sends no entries to Loki for 30m,
    joining `node` from `kube_pod_info` so a node-maintenance silence covers it (#890)."""
    groups = {
        group["name"]: group["rules"]
        for group in _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    }
    (rule,) = [
        rule
        for rule in groups["homelab-telemetry-pipeline"]
        if rule["alert"] == "PodLogsNotShipped"
    ]

    assert (
        rule["alert"],
        rule["expr"],
        rule["for"],
        rule["labels"]["severity"],
    ) == (
        "PodLogsNotShipped",
        'sum by (namespace, pod) (rate(loki_write_sent_entries_total{job="integrations/alloy", pod=~".*alloy-logs.*"}[5m]))'
        " * on (namespace, pod) group_left (node)"
        " max by (namespace, pod, node) (kube_pod_info)"
        " == 0",
        "30m",
        "warning",
    )


def test_telemetry_pipeline_rules_use_metrics_in_the_alloy_integration_allow_list() -> None:
    """Every Alloy metric in `homelab-telemetry-pipeline` is kept by the Alloy integration's
    default allow list, whose fixture matches the `k8s-monitoring` chart pin (#1131)."""
    from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK

    (k8s_monitoring,) = [
        release
        for release in _HELM_RELEASES_BY_STACK["infra"]
        if release["name"] == "k8s-monitoring"
    ]
    fixture_version, allow_list = _allow_list(ALLOY_ALLOW_LIST)
    groups = {
        group["name"]: group["rules"]
        for group in _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    }
    rule_metrics = {
        selector.metric
        for rule in groups["homelab-telemetry-pipeline"]
        for selector in selectors(rule["expr"])
        if "job" in selector.labels
    }

    assert (
        fixture_version,
        len(rule_metrics) > 0,
        sorted(metric or "" for metric in rule_metrics - allow_list),
    ) == (
        k8s_monitoring["version"],
        True,
        [],
    )


def test_pyroscope_query_errors_alerts_on_5xx_rate() -> None:
    """`PyroscopeQueryErrors` alerts when Pyroscope's 5xx request rate over 15m is above 0 for 15m (#1134)."""
    (rule,) = [rule for rule in _rules() if rule["alert"] == "PyroscopeQueryErrors"]

    assert (
        rule["alert"],
        rule["expr"],
        rule["for"],
        rule["labels"]["severity"],
    ) == (
        "PyroscopeQueryErrors",
        'sum by (route) (rate(pyroscope_request_duration_seconds_count{status_code=~"5.."}[15m])) > 0',
        "15m",
        "warning",
    )


def test_homelab_services_rules_cover_argocd_tunnel_coredns_and_valkey_health() -> None:
    """`homelab-services` alerts on Argo CD sync/health, Cloudflare Tunnel HA connections,
    CoreDNS SERVFAIL rate (#822), and Valkey cache errors (#551)."""
    groups = {
        group["name"]: group["rules"]
        for group in _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    }
    rules = [
        (r["alert"], r["expr"], r["for"], r["labels"]["severity"])
        for r in groups["homelab-services"]
    ]

    assert rules == [
        (
            "ArgoCdApplicationOutOfSync",
            'argocd_app_info{sync_status!="Synced"} == 1',
            "15m",
            "warning",
        ),
        (
            "ArgoCdApplicationUnhealthy",
            'argocd_app_info{health_status!~"Healthy|Progressing"} == 1',
            "15m",
            "warning",
        ),
        (
            "ArgoCdAutoSyncDisabled",
            'argocd_app_info{autosync_enabled="false"} == 1',
            "15m",
            "warning",
        ),
        (
            "ArgoCdSyncOperationStuck",
            'argocd_app_info{operation!=""} == 1',
            "1h",
            "warning",
        ),
        (
            "IngressServesPlaceholderHost",
            PLACEHOLDER_HOST_EXPRESSION,
            "5m",
            "critical",
        ),
        (
            "CloudflareTunnelDegraded",
            "sum(cloudflared_tunnel_ha_connections) < 2",
            "5m",
            "warning",
        ),
        (
            "CoreDnsServfailResponses",
            'sum(rate(coredns_dns_responses_total{job="integrations/kubernetes/kube-dns", rcode="SERVFAIL"}[5m])) / sum(rate(coredns_dns_responses_total{job="integrations/kubernetes/kube-dns"}[5m])) > 0.05',
            "5m",
            "warning",
        ),
        (
            "ValkeyCacheErrors",
            "redis_up == 0 or increase(redis_rejected_connections_total[5m]) > 0",
            "5m",
            "warning",
        ),
    ]


def _committed_ingress_hosts() -> list[str]:
    """Every host that an Ingress in a YAML file under `k8s/` routes, as git holds it."""
    return sorted(
        rule["host"]
        for path in K8S.rglob("*.yaml")
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("kind") == "Ingress"
        for rule in (doc.get("spec") or {}).get("rules") or []
        if "host" in rule
    )


def test_an_ingress_that_routes_a_placeholder_host_alerts() -> None:
    """`IngressServesPlaceholderHost` fires for each Ingress with a host under the placeholder
    domain (#1817).

    Traefik matches hosts exactly, so such an Ingress answers 404 for the real host. The cluster
    serves these hosts when the host overrides are lost and Argo CD renders git as it is. The
    rule matches every host that git holds and no host under another domain. kube-state-metrics
    serves `kube_ingress_path` with its host, and `includeMetrics` keeps the series, because the
    chart's default allow list does not.
    """
    placeholder = re.compile(PLACEHOLDER_HOST_REGEX)
    hosts = _committed_ingress_hosts()
    other_domains = ("argocd.example.org", "example.com.example.net", "notexample.com")
    tuning = _yaml(K8S_MONITORING_VALUES)["clusterMetrics"]["kube-state-metrics"]["metricsTuning"]
    capture = _yaml(FIXTURES / "metrics" / "kube-state-metrics.yaml")["families"]

    assert (
        len(hosts) > 0,
        [host for host in hosts if not placeholder.fullmatch(host)],
        [host for host in other_domains if placeholder.fullmatch(host)],
        "kube_ingress_path" in tuning["includeMetrics"],
        {"host", "ingress", "namespace"} <= set(capture["kube_ingress_path"]["labels"]),
    ) == (True, [], [], True, True)
