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

from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.prometheus.promql import selectors

K8S = Path(__file__).resolve().parents[1] / "k8s"
PROMETHEUS_VALUES = K8S / "monitoring" / "prometheus-values.yaml"
GRAFANA_VALUES = K8S / "monitoring" / "grafana-values.yaml"
K8S_MONITORING_VALUES = K8S / "monitoring" / "k8s-monitoring-values.yaml"

# Every series an alert rule may select, by what serves it.
SERVED_SERIES = frozenset(
    {
        # Recorded by Prometheus for every scrape.
        "up",
        # kube-state-metrics, deployed and scraped by k8s-monitoring.
        "kube_node_status_condition",
        "kube_persistentvolumeclaim_resource_requests_storage_bytes",
        "kube_pod_info",
        "kube_pod_spec_volumes_persistentvolumeclaims_info",
        "kube_secret_info",
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
        # Loki, scraped by k8s-monitoring's Loki integration within its default allow list, which
        # finds Loki's pods only where the logging stack runs.
        "loki_compactor_apply_retention_last_successful_run_timestamp_seconds",
        "loki_request_duration_seconds_count",
        # Alertmanager, found through its pod annotations by k8s-monitoring's annotation
        # autodiscovery.
        "alertmanager_config_last_reload_successful",
        "alertmanager_notifications_failed_total",
    }
)
SEVERITIES = frozenset({"critical", "warning"})


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
        ("ClusterMetricsMissing", "critical"),
        ("GpuPowerLimitServiceNotActive", "critical"),
        ("GpuPowerOverSiteBudget", "critical"),
        ("GpuTemperatureHigh", "critical"),
        ("GpuTemperatureHigh", "warning"),
        ("HostFilesystemSpaceLow", "critical"),
        ("HostFilesystemSpaceLow", "warning"),
        ("K3sServiceNotActive", "critical"),
        ("LogOrMetricVolumeDiskLow", "warning"),
        ("LokiRequestErrors", "warning"),
        ("LokiRetentionNotRunning", "warning"),
        ("NodeNotReady", "critical"),
        ("NodeRebooted", "warning"),
        ("PersistentVolumeSpaceLow", "warning"),
        ("PrometheusCompactionsFailing", "warning"),
        ("PrometheusConfigReloadFailed", "warning"),
        ("PrometheusDroppingAlerts", "warning"),
        ("PrometheusNearRetentionSizeCap", "warning"),
        ("PrometheusNotConnectedToAlertmanager", "warning"),
        ("PrometheusRuleEvaluationFailures", "warning"),
        ("PrometheusSizeLimitCutHistory", "warning"),
        ("PrometheusStorageNearClaim", "warning"),
        ("TargetDown", "warning"),
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
