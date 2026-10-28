"""Alertmanager, its receiver and the homelab alert rules (#549), with #550's retention rules
and the roadmap Service's rules (#2472, #2475) and the rule of its webhook route (#2476).

The rules live in `k8s/monitoring/prometheus-values.yaml` (`serverFiles.alerting_rules.yml`).
A rule over a series nothing in the stack serves never fires, so every expression may name
only the series in `SERVED_SERIES`, each served by a scrape or by the OpenTelemetry collector
that this repository defines. The k3s
server runs the controller manager, scheduler and proxy in its own process, so no scrape
targets them and none of their series is listed: a rule over them would fire on the missing
target, as `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` did.

The checks read files only, except the two that run the pinned promtool (`tools.lock`):
`promtool check rules` over every rule, and `promtool test rules` over each group of the roadmap
Service with its unit tests in `tests/fixtures/prometheus_rules/`. Each skips where promtool is
not installed; CI's test job installs it.
"""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
)
from devops_cli.config.defaults import DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR
from devops_cli.prometheus.promql import selectors
from devops_cli.telemetry.instruments import (
    AI_REQUESTS_TOTAL,
    FIRECRAWL_SEARCHES_TOTAL,
    GITHUB_REQUESTS_TOTAL,
    GITHUB_THROTTLE_WAIT,
)
from tests.support.paths import FIXTURES, REPO_ROOT

K8S = REPO_ROOT / "k8s"
K8S_README = K8S / "README.md"
PROMETHEUS_VALUES = K8S / "monitoring" / "prometheus-values.yaml"
GRAFANA_VALUES = K8S / "monitoring" / "grafana-values.yaml"
K8S_MONITORING_VALUES = K8S / "monitoring" / "k8s-monitoring-values.yaml"
PYROSCOPE_VALUES = K8S / "monitoring" / "pyroscope-values.yaml"
ROADMAP_SERVICE_DEPLOYMENT = K8S / "devops" / "roadmap-service" / "deployment.yaml"
ALLOY_ALLOW_LIST = FIXTURES / "k8s_monitoring" / "integrations" / "alloy.yaml"
KUBE_STATE_METRICS_ALLOW_LIST = (
    FIXTURES / "k8s_monitoring" / "cluster_metrics" / "kube-state-metrics.yaml"
)
ROADMAP_SERVICE_RULE_TESTS = FIXTURES / "prometheus_rules" / "roadmap_service_tests.yaml"
ROADMAP_SERVICE_WEBHOOKS_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_webhooks_tests.yaml"
)
ROADMAP_SERVICE_ACTIVITY_RULE_TESTS = (
    FIXTURES / "prometheus_rules" / "roadmap_service_activity_tests.yaml"
)
OTEL_COLLECTOR_CAPTURE = FIXTURES / "metrics" / "otel-collector.yaml"
OTEL_COLLECTOR_RULE_TESTS = FIXTURES / "prometheus_rules" / "otel_collector_tests.yaml"

# The job of every series the roadmap Service sends, by the scrape and by OTLP alike (#2472).
ROADMAP_SERVICE_JOB = "roadmap-service"
ROADMAP_SERVICE_GROUP = "roadmap-service"
# The group of the Service's webhook route, apart from the Service's group (#2476).
ROADMAP_SERVICE_WEBHOOKS_GROUP = "roadmap-service-webhooks"
# The Service's writes, the deliveries of its own writes and its web search (#2475).
ROADMAP_SERVICE_ACTIVITY_GROUP = "roadmap-service-activity"
# Each group of the roadmap Service, with the promtool unit tests of its rules.
ROADMAP_SERVICE_GROUP_TESTS = (
    (ROADMAP_SERVICE_GROUP, ROADMAP_SERVICE_RULE_TESTS),
    (ROADMAP_SERVICE_WEBHOOKS_GROUP, ROADMAP_SERVICE_WEBHOOKS_RULE_TESTS),
    (ROADMAP_SERVICE_ACTIVITY_GROUP, ROADMAP_SERVICE_ACTIVITY_RULE_TESTS),
)
ROADMAP_SERVICE_GROUPS = tuple(group for group, _ in ROADMAP_SERVICE_GROUP_TESTS)
# The rules over the OpenTelemetry collector's own telemetry (#1642).
OTEL_COLLECTOR_GROUP = "otel-collector"
# Each group whose rules have promtool unit tests, with the file of its tests.
RULE_GROUP_TESTS = (
    *ROADMAP_SERVICE_GROUP_TESTS,
    (OTEL_COLLECTOR_GROUP, OTEL_COLLECTOR_RULE_TESTS),
)

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
        # The roadmap Service's restarts and replicas (#2472).
        "kube_deployment_status_replicas_available",
        "kube_deployment_status_replicas_unavailable",
        "kube_pod_container_status_restarts_total",
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
        # The OpenTelemetry collector's own telemetry, scraped by the server's kubernetes-pods
        # job (#1642). Each send_failed counter starts at the first send that fails.
        "otelcol_exporter_queue_capacity",
        "otelcol_exporter_queue_size",
        "otelcol_exporter_send_failed_log_records",
        "otelcol_exporter_send_failed_metric_points",
        "otelcol_exporter_send_failed_spans",
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
        # The roadmap Service (#2472): the series of its /metrics, which k8s-monitoring's
        # annotation autodiscovery scrapes, and the instruments it sends over OTLP. A histogram
        # is a native histogram under the instrument's own name.
        CONST_SERVICE_METRIC_IDENTITY_REFUSED,
        CONST_SERVICE_METRIC_JOBS,
        CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
        CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
        AI_REQUESTS_TOTAL.name,
        FIRECRAWL_SEARCHES_TOTAL.name,
        GITHUB_REQUESTS_TOTAL.name,
        GITHUB_THROTTLE_WAIT.name,
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


def _group(name: str) -> list[dict[str, Any]]:
    """The alerting rules of one group, in file order."""
    groups = _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    (rules,) = [group["rules"] for group in groups if group["name"] == name]
    return list(rules)


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
    #550's two volume rules (`LogOrMetricVolumeDiskLow`, `PrometheusNearRetentionSizeCap`), and
    the roadmap Service's rules (#2472, #2475) with the rule of its webhook route (#2476), and the
    OpenTelemetry collector's export rules (#1642).

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
        ("OtelCollectorExportFailing", "warning"),
        ("OtelCollectorExportQueueFull", "warning"),
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
        ("RoadmapServiceFirecrawlRefused", "warning"),
        ("RoadmapServiceGitHubRequestsHigh", "warning"),
        ("RoadmapServiceGitHubThrottled", "critical"),
        ("RoadmapServiceGitHubWritesHigh", "warning"),
        ("RoadmapServiceIdentityRefused", "critical"),
        ("RoadmapServiceJobsFailing", "warning"),
        ("RoadmapServiceLaneStalled", "warning"),
        ("RoadmapServiceModelRequestsHigh", "warning"),
        ("RoadmapServiceRestarted", "warning"),
        ("RoadmapServiceSelfDeliveriesHigh", "warning"),
        ("RoadmapServiceUnavailable", "warning"),
        ("RoadmapServiceWebhooksRejected", "warning"),
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


def test_the_log_or_metric_volume_disk_rule_evaluates_while_a_pod_moves() -> None:
    """`LogOrMetricVolumeDiskLow` evaluates while a pod moves between nodes (#2148).

    Joining `kube_pod_info` on the left of `group_left (persistentvolumeclaim)` ensures that
    when a moving pod has series on multiple nodes in `kube_pod_info`, Prometheus allows the
    many-to-one match because the right-hand side has at most one series for the pod's claim.
    """
    (rule,) = [rule for rule in _rules() if rule["alert"] == "LogOrMetricVolumeDiskLow"]
    assert (
        [(s.metric, s.labels) for s in selectors(rule["expr"])],
        "group_left (node)" in rule["expr"],
        "group_left (persistentvolumeclaim)" in rule["expr"],
        rule["for"],
    ) == (
        [
            ("node_filesystem_avail_bytes", frozenset({"mountpoint"})),
            ("node_filesystem_size_bytes", frozenset({"mountpoint"})),
            ("kube_pod_info", frozenset()),
            (
                "kube_pod_spec_volumes_persistentvolumeclaims_info",
                frozenset({"persistentvolumeclaim", "namespace"}),
            ),
        ],
        False,
        True,
        "30m",
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


def _window_count(series: str, window: str) -> str:
    """The count of a counter of the roadmap Service in the last `window` (#2505).

    A series with no sample in the window before started in the window, so its last value is all
    of its count: `increase()` does not count the first value of a series. Every other series
    counts its `increase()`. Neither part reads one sample near the start of the window, so a
    sparse series from before the window adds none of its earlier count.
    """
    return (
        f"(last_over_time({series}[{window}])"
        f" unless last_over_time({series}[{window}] offset {window}))"
        f" or increase({series}[{window}])"
    )


# The roadmap Service's rules (#2472), in file order: (alert, expression, wait, severity). The
# GitHub request rule warns at 90% of the default hourly budget of the Service.
ROADMAP_SERVICE_RULES = [
    (
        "RoadmapServiceIdentityRefused",
        'max by (identity) (devops_cli_service_identity_refused_total{job="roadmap-service"}) > 0',
        "0m",
        "critical",
    ),
    (
        "RoadmapServiceGitHubThrottled",
        "sum by (resource) ("
        'count_over_time(devops_cli_github_throttle_wait_seconds{job="roadmap-service"}[15m])'
        ") > 0",
        "0m",
        "critical",
    ),
    (
        "RoadmapServiceJobsFailing",
        "sum by (repo, lane) ( "
        + _window_count(
            'devops_cli_service_jobs_total{job="roadmap-service", result="error"}', "1h"
        )
        + " ) >= 3",
        "0m",
        "warning",
    ),
    (
        "RoadmapServiceLaneStalled",
        "time() - max by (repo, lane) ("
        'devops_cli_service_job_start_timestamp_seconds{job="roadmap-service"}) > 7200'
        " and on () max("
        'kube_deployment_status_replicas_available{namespace="devops", deployment="roadmap-service"}'
        ") > 0",
        "10m",
        "warning",
    ),
    (
        "RoadmapServiceRestarted",
        "max by (namespace, pod, container) (increase(kube_pod_container_status_restarts_total"
        '{namespace="devops", pod=~"roadmap-service-.+", container="service"}[1h])) > 0',
        "0m",
        "warning",
    ),
    (
        "RoadmapServiceUnavailable",
        "max by (namespace, deployment) (kube_deployment_status_replicas_unavailable"
        '{namespace="devops", deployment="roadmap-service"}) > 0',
        "10m",
        "warning",
    ),
    (
        "RoadmapServiceGitHubRequestsHigh",
        "sum( "
        + _window_count('devops_cli_github_requests_total{job="roadmap-service"}', "1h")
        + f" ) > {DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR * 9 // 10}",
        "0m",
        "warning",
    ),
    (
        "RoadmapServiceModelRequestsHigh",
        "sum( "
        + _window_count('devops_cli_ai_requests_total{job="roadmap-service", cached!="true"}', "1h")
        + " ) > 352",
        "0m",
        "warning",
    ),
]
# The rules of `roadmap-service-activity` (#2475), in file order, as `ROADMAP_SERVICE_RULES`.
ROADMAP_SERVICE_ACTIVITY_RULES = [
    (
        "RoadmapServiceGitHubWritesHigh",
        "sum( "
        + _window_count(
            'devops_cli_github_requests_total{job="roadmap-service", method!="GET", '
            'resource!="graphql"}',
            "1h",
        )
        + " ) > 300",
        "0m",
        "warning",
    ),
    (
        "RoadmapServiceSelfDeliveriesHigh",
        "sum( "
        + _window_count(
            'devops_cli_service_webhook_deliveries_total{job="roadmap-service", outcome="self"}',
            "1h",
        )
        + " ) > 150",
        "0m",
        "warning",
    ),
    (
        "RoadmapServiceFirecrawlRefused",
        "sum by (result) ( "
        + _window_count(
            'devops_cli_firecrawl_searches_total{job="roadmap-service", result=~"402|429"}',
            "1h",
        )
        + " ) > 0",
        "0m",
        "warning",
    ),
]
# A series selector and the matchers in its braces.
_SELECTOR_MATCHERS = re.compile(r"([A-Za-z_:][\w:]*)\{([^}]*)\}")


def test_the_roadmap_service_rules_watch_identity_jobs_lanes_pods_and_request_volume() -> None:
    """`roadmap-service` alerts when GitHub refuses the Service's identity or throttles it, when
    jobs fail or a lane stalls, when the pod restarts or is unavailable, and when its GitHub or
    model requests in an hour are high (#2472).

    A refused identity stops every round until a person removes the halt record, and the
    refusal counter stays above 0 for as long, a restart included, so the critical alert holds
    for the whole stop (#2474). A throttle sample is
    written only when the Service sends one, so a sample in 15 minutes is a throttle; increase()
    needs two samples. The failed jobs and the GitHub and model requests count a series that
    starts in the hour from zero (#2505).
    """
    assert [
        (rule["alert"], rule["expr"], rule["for"], rule["labels"]["severity"])
        for rule in _group(ROADMAP_SERVICE_GROUP)
    ] == ROADMAP_SERVICE_RULES


def test_the_webhook_rule_warns_on_more_than_20_rejected_deliveries_in_15_minutes() -> None:
    """`roadmap-service-webhooks`, a group apart from `roadmap-service`, warns when the webhook
    route of the Service rejects more than 20 deliveries in 15 minutes (#2476). A flood can start
    a new label set, so the count reads a series that starts in the 15 minutes from zero (#2505).
    """
    rejected = (
        f'{CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES}{{job="roadmap-service", outcome="rejected"}}'
    )
    assert [
        (rule["alert"], rule["expr"], rule["for"], rule["labels"]["severity"])
        for rule in _group(ROADMAP_SERVICE_WEBHOOKS_GROUP)
    ] == [
        (
            "RoadmapServiceWebhooksRejected",
            "sum( " + _window_count(rejected, "15m") + " ) > 20",
            "0m",
            "warning",
        )
    ]


def test_the_roadmap_service_activity_rules_watch_writes_own_deliveries_and_web_search() -> None:
    """`roadmap-service-activity` warns at more than 300 GitHub writes of the Service in an hour,
    more than 150 deliveries of its own writes in an hour, and any Firecrawl search refused for
    credits (402) or its rate limit (429) (#2475). Each counts a series that starts in the hour
    from zero (#2505)."""
    assert [
        (rule["alert"], rule["expr"], rule["for"], rule["labels"]["severity"])
        for rule in _group(ROADMAP_SERVICE_ACTIVITY_GROUP)
    ] == ROADMAP_SERVICE_ACTIVITY_RULES


@pytest.mark.parametrize("group", ROADMAP_SERVICE_GROUPS)
def test_each_roadmap_service_rule_selects_only_the_service(group: str) -> None:
    """Each `devops_cli_` selector filters the Service's job, and each kube-state-metrics
    selector its namespace and its deployment or pods (#2472, #2476).

    The same series with another job, such as the pod as `kubernetes-pods` before #1130 or a
    workstation as `devops-cli`, never counts.
    """
    found = [
        (metric, frozenset(part.strip() for part in matchers.split(",")))
        for rule in _group(group)
        for metric, matchers in _SELECTOR_MATCHERS.findall(rule["expr"])
    ]
    service = f'job="{ROADMAP_SERVICE_JOB}"'
    owned = {'deployment="roadmap-service"', 'pod=~"roadmap-service-.+"'}
    assert (
        [metric for metric, _ in found],
        [
            metric
            for metric, matchers in found
            if not (
                service in matchers
                if metric.startswith("devops_cli_")
                else 'namespace="devops"' in matchers and bool(owned & matchers)
            )
        ],
    ) == (
        [selector.metric for rule in _group(group) for selector in selectors(rule["expr"])],
        [],
    )


def test_both_paths_name_the_roadmap_service_job() -> None:
    """The scrape and the OTLP export both give the Service's series `job="roadmap-service"`.

    k8s-monitoring's annotation autodiscovery scrapes the annotated pod's /metrics and names the
    job after the pod's `app.kubernetes.io/name`; the OpenTelemetry collector names the job after
    `OTEL_SERVICE_NAME`.
    """
    template = _yaml(ROADMAP_SERVICE_DEPLOYMENT)["spec"]["template"]
    (container,) = template["spec"]["containers"]
    environment = {item["name"]: item.get("value") for item in container["env"]}
    (port,) = container["ports"]
    assert (
        template["metadata"]["labels"]["app.kubernetes.io/name"],
        environment["OTEL_SERVICE_NAME"],
        template["metadata"]["annotations"],
    ) == (
        ROADMAP_SERVICE_JOB,
        ROADMAP_SERVICE_JOB,
        {"prometheus.io/scrape": "true", "prometheus.io/port": str(port["containerPort"])},
    )


def test_the_roadmap_service_rules_read_kube_state_metrics_that_the_chart_keeps() -> None:
    """The restart and replica series are in the chart's default allow list or in
    `metricsTuning.includeMetrics`, so they reach Prometheus (#2472)."""
    allow_list = yaml.safe_load(KUBE_STATE_METRICS_ALLOW_LIST.read_text(encoding="utf-8"))
    tuning = _yaml(K8S_MONITORING_VALUES)["clusterMetrics"]["kube-state-metrics"]["metricsTuning"]
    kept = re.compile("|".join([*allow_list["metrics"], *tuning["includeMetrics"]]))
    metrics = {
        selector.metric or ""
        for rule in _group(ROADMAP_SERVICE_GROUP)
        for selector in selectors(rule["expr"])
        if (selector.metric or "").startswith("kube_")
    }
    assert (len(metrics), sorted(m for m in metrics if not kept.fullmatch(m))) == (3, [])


def test_the_otel_collector_rules_warn_after_15_minutes_and_name_no_node() -> None:
    """Both rules wait 15 minutes and warn. They carry no `node` label: a failing export is the
    collector's, and the collector's pod can move to any node (#1642)."""
    assert [
        (rule["alert"], rule["labels"], rule["for"]) for rule in _group(OTEL_COLLECTOR_GROUP)
    ] == [
        ("OtelCollectorExportFailing", {"severity": "warning"}, "15m"),
        ("OtelCollectorExportQueueFull", {"severity": "warning"}, "15m"),
    ]


def test_the_otel_collector_rules_read_families_of_the_collector_capture() -> None:
    """Each series that the `otel-collector` group selects is a family that the deployed
    collector printed, or one that it prints from its first event, read from its source (#1642).
    """
    capture = _yaml(OTEL_COLLECTOR_CAPTURE)
    families = {**capture["families"], **capture.get("from_source", {})}
    metrics = {
        selector.metric or ""
        for rule in _group(OTEL_COLLECTOR_GROUP)
        for selector in selectors(rule["expr"])
    }
    assert (len(metrics), sorted(metrics - families.keys())) == (5, [])


def _readme_section(heading: str) -> str:
    """The text of one `###` section of k8s/README.md, its subsections included."""
    text = K8S_README.read_text(encoding="utf-8")
    start = text.index(f"\n### {heading}\n")
    end = text.find("\n### ", start + 1)
    return text[start : end if end != -1 else len(text)]


@pytest.mark.parametrize("group", ROADMAP_SERVICE_GROUPS)
def test_each_roadmap_service_alert_points_to_its_step_in_the_readme(group: str) -> None:
    """Each description names `k8s/README.md, Roadmap service`, that section says what to do for
    each alert, and it says that no alert leaves the cluster without the webhook Secret (#2472,
    #2476)."""
    section = _readme_section("Roadmap service")
    rules = _group(group)
    pointer = "(k8s/README.md, Roadmap service)"
    assert (
        [r["alert"] for r in rules if pointer not in r["annotations"]["description"]],
        [r["alert"] for r in rules if f"`{r['alert']}`" not in section],
        "`monitoring/alertmanager-webhook`" in section,
    ) == ([], [], True)


def _promtool(*args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run the promtool on PATH and keep its output for the failure message."""
    return subprocess.run(
        ["promtool", *map(str, args)], capture_output=True, text=True, check=False
    )


@pytest.mark.live("promtool")
def test_promtool_accepts_every_alert_rule(tmp_path: Path) -> None:
    """`promtool check rules` accepts the rule file the server loads, with each expression and
    each annotation template (#2472)."""
    rules = tmp_path / "alerting_rules.yml"
    rules.write_text(
        yaml.safe_dump(_yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]),
        encoding="utf-8",
    )
    result = _promtool("check", "rules", rules)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.live("promtool")
@pytest.mark.parametrize(
    ("group", "rule_tests"),
    RULE_GROUP_TESTS,
    ids=[group for group, _ in RULE_GROUP_TESTS],
)
def test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series(
    group: str, rule_tests: Path, tmp_path: Path
) -> None:
    """`promtool test rules` passes the unit tests of each rule of `roadmap-service` (#2472), of
    `roadmap-service-webhooks` (#2476), of `roadmap-service-activity` (#2475) and of
    `otel-collector` (#1642).

    Each alert fires on a sample series with the labels and annotations it pins, and stays quiet
    on a normal series, before its wait ends, and on the series it must not count.
    """
    unit_tests = yaml.safe_load(rule_tests.read_text(encoding="utf-8"))
    (rule_file,) = unit_tests["rule_files"]
    groups = _yaml(PROMETHEUS_VALUES)["serverFiles"]["alerting_rules.yml"]["groups"]
    (tmp_path / rule_file).write_text(
        yaml.safe_dump({"groups": [g for g in groups if g["name"] == group]}),
        encoding="utf-8",
    )
    tested = {case["alertname"] for test in unit_tests["tests"] for case in test["alert_rule_test"]}
    copy = tmp_path / rule_tests.name
    copy.write_text(rule_tests.read_text(encoding="utf-8"), encoding="utf-8")
    result = _promtool("test", "rules", copy)
    assert (sorted(tested), result.returncode) == (
        sorted(rule["alert"] for rule in _group(group)),
        0,
    ), result.stdout + result.stderr
