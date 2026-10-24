"""Stack dashboards query only the series their exporters serve (#693, #1136).

`llm-stack.json`, `otel-collector.json`, `prometheus-server.json`, `coredns.json`,
`ingress-tunnel.json`, `k8s-views-global.json`, `k8s-views-namespaces.json` and
`k8s-views-nodes.json` are checked against the metric families captured from the exporters behind
them (`tests/fixtures/metrics/`): every series a query selects, every label it matches or groups
by, and the scrape that brings each exporter's series into Prometheus. A query naming a series
nothing serves renders an empty panel, and an `or vector(0)` fallback turns that empty panel into
a false zero, so a broken export reads as a quiet system. A panel drawn against a limit must also
reach it on its axis, or the limit line is never seen.

The checks read files only.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK
from devops_cli.prometheus.promql import falls_back_to_constant, grouping_labels, selectors
from tests.support.paths import FIXTURES, REPO_ROOT

K8S = REPO_ROOT / "k8s"
DASHBOARDS = K8S / "monitoring" / "dashboards"
CAPTURES = FIXTURES / "metrics"
CLUSTER_METRICS_ALLOWLISTS = FIXTURES / "k8s_monitoring" / "cluster_metrics"
TUNED_CLUSTER_EXPORTERS = frozenset({"cadvisor", "kube-state-metrics", "kubelet"})

# Series Prometheus records about every scrape itself, whatever the target serves. Alloy
# forwards all of them for the gateway and Qdrant ServiceMonitors, the DCGM integration, the
# pods its annotation autodiscovery finds and kube-dns; its other cluster-metrics jobs keep
# only `up` and `scrape_samples_scraped`.
SYNTHETIC_SERIES = frozenset(
    {
        "up",
        "scrape_duration_seconds",
        "scrape_samples_scraped",
        "scrape_samples_post_metric_relabeling",
        "scrape_series_added",
    }
)
# The series a family puts in Prometheus, by the suffix on its name, each with the label it
# adds. A classic histogram serves only `_bucket` (with `le`), `_sum` and `_count`; a summary
# serves its own name (with `quantile`), `_sum` and `_count`; any other type its own name.
_OWN_SERIES: dict[str, frozenset[str]] = {"": frozenset()}
_TYPE_SERIES: dict[str, dict[str, frozenset[str]]] = {
    "histogram": {"_bucket": frozenset({"le"}), "_sum": frozenset(), "_count": frozenset()},
    "summary": {"": frozenset({"quantile"}), "_sum": frozenset(), "_count": frozenset()},
}


def _yaml(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    return loaded


def _gateway_monitored(monitor: dict[str, Any]) -> bool:
    """The gateway's ServiceMonitor selects `llm-gateway` on `/metrics/`, and Alloy reads ServiceMonitors."""
    monitoring = _yaml(K8S / "monitoring" / "k8s-monitoring-values.yaml")
    endpoints = monitor.get("spec", {}).get("endpoints", [])
    return (
        monitor.get("kind") == "ServiceMonitor"
        and monitor.get("metadata", {}).get("name") == "llm-gateway"
        and monitor.get("spec", {}).get("selector", {}).get("matchLabels")
        == {"app.kubernetes.io/name": "llm-gateway"}
        and any(ep.get("port") == "http" and ep.get("path") == "/metrics/" for ep in endpoints)
        and monitoring["prometheusOperatorObjects"]["enabled"] is True
        and "extraObjects" not in monitoring
    )


def _dcgm_monitored(values: dict[str, Any]) -> bool:
    """k8s-monitoring's dcgm-exporter integration has an instance that selects the exporter."""
    integrations = values.get("integrations", {})
    instances = integrations.get("dcgm-exporter", {}).get("instances", [])
    return bool(integrations.get("collector")) and any(
        instance.get("labelSelectors") for instance in instances
    )


def _qdrant_monitored(values: dict[str, Any]) -> bool:
    """Qdrant's chart ServiceMonitor is on and authenticates with the `qdrant-api-key` Secret,
    and Alloy reads ServiceMonitors."""
    monitor = values.get("metrics", {}).get("serviceMonitor", {})
    auth = monitor.get("authorization", {})
    monitoring = _yaml(K8S / "monitoring" / "k8s-monitoring-values.yaml")
    return (
        monitor.get("enabled") is True
        and auth.get("type") == "Bearer"
        and auth.get("credentials") == {"name": "qdrant-api-key", "key": "api-key"}
        and monitoring["prometheusOperatorObjects"]["enabled"] is True
    )


def _collector_annotated(values: dict[str, Any]) -> bool:
    """The server's kubernetes-pods job keeps the collector's namespace and its pods annotated
    for scraping, on their port."""
    wanted = {"prometheus.io/scrape": "true", "prometheus.io/port": "8888"}
    annotations = values.get("podAnnotations") or {}
    server = _yaml(K8S / "monitoring" / "prometheus-values.yaml")
    pods_job = server["scrapeConfigs"]["kubernetes-pods"]
    keeps = [
        rule.get("regex")
        for rule in yaml.safe_load(pods_job.get("pre_relabel_configs") or "[]")
        if rule.get("action") == "keep"
        and rule.get("source_labels") == ["__meta_kubernetes_namespace"]
    ]
    return (
        wanted.items() <= annotations.items()
        and values["ports"]["metrics"]["enabled"] is True
        and keeps == ["otel"]
    )


def _server_jobs_enabled(values: dict[str, Any]) -> bool:
    """The server scrapes itself and annotated pods, set explicitly rather than by chart default."""
    jobs = values.get("scrapeConfigs", {})
    return all(
        jobs.get(job, {}).get("enabled") is True for job in ("prometheus", "kubernetes-pods")
    )


def _coredns_monitored(values: dict[str, Any]) -> bool:
    """k8s-monitoring's kubeDNS job is enabled and the server's service-endpoints job stays off (#822)."""
    cluster_metrics = values.get("clusterMetrics", {})
    server = _yaml(K8S / "monitoring" / "prometheus-values.yaml")
    endpoints_job = server.get("scrapeConfigs", {}).get("kubernetes-service-endpoints", {})
    return (
        cluster_metrics.get("enabled") is True
        and cluster_metrics.get("kubeDNS", {}).get("enabled") is True
        and endpoints_job.get("enabled") is False
    )


def _traefik_monitored(values: dict[str, Any]) -> bool:
    """Traefik exposes Prometheus metrics with router and service labels on port 9100 (#1136)."""
    prom = values.get("metrics", {}).get("prometheus", {})
    monitoring = _yaml(K8S / "monitoring" / "k8s-monitoring-values.yaml")
    return (
        prom
        == {
            "entryPoint": "metrics",
            "addRoutersLabels": True,
            "addServicesLabels": True,
        }
        and values.get("ports", {}).get("metrics", {}).get("port") == 9100
        and monitoring.get("annotationAutodiscovery", {}).get("enabled") is True
    )


def _cloudflared_monitored(values: dict[str, Any]) -> bool:
    """cloudflared pods carry Prometheus scrape annotations on port 2000 for Alloy autodiscovery (#1136)."""
    wanted = {"prometheus.io/scrape": "true", "prometheus.io/port": "2000"}
    annotations = (
        values.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations") or {}
    )
    monitoring = _yaml(K8S / "monitoring" / "k8s-monitoring-values.yaml")
    return (
        wanted.items() <= annotations.items()
        and monitoring.get("annotationAutodiscovery", {}).get("enabled") is True
    )


def _ksm_monitored(values: dict[str, Any]) -> bool:
    """k8s-monitoring deploys and scrapes kube-state-metrics (#1136)."""
    cm = values.get("clusterMetrics", {})
    return (
        cm.get("enabled") is True
        and cm.get("kube-state-metrics", {}).get("enabled", True) is True
        and values.get("telemetryServices", {}).get("kube-state-metrics", {}).get("deploy") is True
    )


def _node_exporter_monitored(values: dict[str, Any]) -> bool:
    """k8s-monitoring deploys and scrapes node-exporter (#1136)."""
    return (
        values.get("hostMetrics", {}).get("enabled") is True
        and values.get("telemetryServices", {}).get("node-exporter", {}).get("deploy") is True
    )


def _kubelet_monitored(values: dict[str, Any]) -> bool:
    """k8s-monitoring scrapes kubelet metrics (#1136)."""
    cm = values.get("clusterMetrics", {})
    return cm.get("enabled") is True and cm.get("kubelet", {}).get("enabled", True) is True


def _cadvisor_monitored(values: dict[str, Any]) -> bool:
    """k8s-monitoring scrapes cAdvisor metrics (#1136)."""
    cm = values.get("clusterMetrics", {})
    return cm.get("enabled") is True and cm.get("cadvisor", {}).get("enabled", True) is True


@dataclass(frozen=True)
class Exporter:
    """Where an exporter's scrape is defined in `k8s/`, and the check that it is."""

    values: Path
    scraped: Callable[[dict[str, Any]], bool]


EXPORTERS = {
    "litellm": Exporter(K8S / "llm" / "gateway" / "servicemonitor.yaml", _gateway_monitored),
    "dcgm-exporter": Exporter(K8S / "monitoring" / "k8s-monitoring-values.yaml", _dcgm_monitored),
    "qdrant": Exporter(K8S / "llm" / "values-qdrant.yaml", _qdrant_monitored),
    "otel-collector": Exporter(K8S / "otel" / "values.yaml", _collector_annotated),
    "prometheus-server": Exporter(
        K8S / "monitoring" / "prometheus-values.yaml", _server_jobs_enabled
    ),
    "coredns": Exporter(K8S / "monitoring" / "k8s-monitoring-values.yaml", _coredns_monitored),
    "traefik": Exporter(K8S / "ingress" / "traefik-values.yaml", _traefik_monitored),
    "cloudflared": Exporter(K8S / "cloudflared" / "deployment.yaml", _cloudflared_monitored),
    "kube-state-metrics": Exporter(
        K8S / "monitoring" / "k8s-monitoring-values.yaml", _ksm_monitored
    ),
    "node-exporter": Exporter(
        K8S / "monitoring" / "k8s-monitoring-values.yaml", _node_exporter_monitored
    ),
    "kubelet": Exporter(K8S / "monitoring" / "k8s-monitoring-values.yaml", _kubelet_monitored),
    "cadvisor": Exporter(K8S / "monitoring" / "k8s-monitoring-values.yaml", _cadvisor_monitored),
}
DASHBOARD_EXPORTERS = {
    "llm-stack.json": ("litellm", "dcgm-exporter", "qdrant"),
    "otel-collector.json": ("otel-collector",),
    "prometheus-server.json": ("prometheus-server",),
    "coredns.json": ("coredns",),
    "ingress-tunnel.json": ("traefik", "cloudflared", "cadvisor"),
    "k8s-views-global.json": ("kube-state-metrics", "node-exporter", "kubelet", "cadvisor"),
    "k8s-views-namespaces.json": ("kube-state-metrics", "node-exporter", "kubelet", "cadvisor"),
    "k8s-views-nodes.json": ("kube-state-metrics", "node-exporter", "kubelet", "cadvisor"),
}


def _family_series(
    name: str, family: dict[str, Any], scraped_labels: frozenset[str]
) -> dict[str, frozenset[str]]:
    """Every series a family puts in Prometheus, each with the labels it may carry there."""
    labels = frozenset(family.get("labels", [])) | scraped_labels
    return {
        name + suffix: labels | added
        for suffix, added in _TYPE_SERIES.get(family["type"], _OWN_SERIES).items()
    }


def _filter_by_cluster_metrics_allowlist(
    exporter: str,
    series: dict[str, frozenset[str]],
    monitoring_values: dict[str, Any] | None = None,
) -> dict[str, frozenset[str]]:
    """Filter a clusterMetrics exporter's series by its effective k8s-monitoring allow list (#1136)."""
    if exporter not in TUNED_CLUSTER_EXPORTERS:
        return series
    values = (
        monitoring_values
        if monitoring_values is not None
        else _yaml(K8S / "monitoring" / "k8s-monitoring-values.yaml")
    )
    tuning = values.get("clusterMetrics", {}).get(exporter, {}).get("metricsTuning", {})
    default_patterns: list[str] = (
        _yaml(CLUSTER_METRICS_ALLOWLISTS / f"{exporter}.yaml")["metrics"]
        if tuning.get("useDefaultAllowList", True)
        else []
    )
    patterns = [*default_patterns, *tuning.get("includeMetrics", [])]
    if not patterns:
        return {}
    allowed = re.compile("|".join(f"(?:{p})" for p in patterns))
    return {name: labels for name, labels in series.items() if allowed.fullmatch(name)}


def _capture(
    exporter: str, monitoring_values: dict[str, Any] | None = None
) -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    """An exporter's series with their labels, and the labels its scrape adds."""
    record = _yaml(CAPTURES / f"{exporter}.yaml")
    target_labels = frozenset(record["target_labels"])
    families = {**record["families"], **record.get("from_source", {})}
    series = {
        series_name: labels
        for name, family in families.items()
        for series_name, labels in _family_series(name, family, target_labels).items()
    }
    return _filter_by_cluster_metrics_allowlist(exporter, series, monitoring_values), target_labels


def relabelled_by_source(record: dict[str, Any]) -> list[str]:
    """The `from_source` families that override a family the capture printed a sample of.

    `from_source` may only fill in a family that printed no sample: one missing from the
    capture, or captured with its type and no labels.
    """
    families = record["families"]
    return [
        name
        for name, family in record.get("from_source", {}).items()
        if families.get(name, {"type": family["type"]}) != {"type": family["type"]}
    ]


def known_series(
    exporters: tuple[str, ...], monitoring_values: dict[str, Any] | None = None
) -> dict[str, frozenset[str]]:
    """The series a dashboard's exporters serve, and the scrape's own, with their labels."""
    captures = [_capture(exporter, monitoring_values) for exporter in exporters]
    target_labels = frozenset().union(*(labels for _, labels in captures))
    known = dict.fromkeys(SYNTHETIC_SERIES, target_labels)
    for series, _ in captures:
        known |= {name: known.get(name, frozenset()) | labels for name, labels in series.items()}
    return known


def expression_violations(expression: str, known: dict[str, frozenset[str]]) -> list[str]:
    """Describe every series, label and fallback in a query that no exporter backs."""
    found = selectors(expression)
    carried = frozenset().union(
        *(known.get(selector.metric or "", frozenset()) for selector in found)
    )
    return [
        *(f"{expression}: {s.metric} is in no capture" for s in found if s.metric not in known),
        *(
            f"{expression}: {s.metric} does not carry {label}"
            for s in found
            for label in sorted(s.labels - known.get(s.metric or "", s.labels))
        ),
        *(
            f"{expression}: groups by {label}, which no series it selects carries"
            for label in sorted(grouping_labels(expression) - carried)
        ),
        *(
            [f"{expression}: falls back to a constant"]
            if falls_back_to_constant(expression)
            else []
        ),
    ]


def _panels(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Every panel in a dashboard, including those inside collapsed rows."""
    return [
        *dashboard["panels"],
        *(p for row in dashboard["panels"] for p in row.get("panels", [])),
    ]


def _expressions(dashboard: dict[str, Any]) -> list[str]:
    """Every query in a dashboard."""
    return [target["expr"] for panel in _panels(dashboard) for target in panel.get("targets", [])]


def _threshold_line_off_axis(panel: dict[str, Any]) -> bool:
    """Whether a panel draws a threshold line above the least its y-axis is sure to reach.

    A timeseries panel scales its axis to the data, not to its thresholds, so a limit drawn
    above the data stays off-scale unless `axisSoftMax` reaches it.
    """
    defaults = panel.get("fieldConfig", {}).get("defaults", {})
    custom = defaults.get("custom", {})
    if custom.get("thresholdsStyle", {}).get("mode", "off") == "off":
        return False
    highest = max(step["value"] or 0 for step in defaults["thresholds"]["steps"])
    return bool(highest > custom.get("axisSoftMax", float("-inf")))


def threshold_lines_off_axis(dashboard: dict[str, Any]) -> list[str]:
    """The titles of the panels whose limit line the y-axis may never reach."""
    return [panel["title"] for panel in _panels(dashboard) if _threshold_line_off_axis(panel)]


def dashboard_violations(
    dashboard: dict[str, Any],
    exporters: tuple[str, ...],
    monitoring_values: dict[str, Any] | None = None,
) -> list[str]:
    """Describe every query in a dashboard that its exporters do not back."""
    known = known_series(exporters, monitoring_values)
    return [
        violation
        for expr in _expressions(dashboard)
        for violation in expression_violations(expr, known)
    ]


def _dashboard(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((DASHBOARDS / name).read_text(encoding="utf-8"))
    return loaded


def _violations_after_adding(name: str, expression: str) -> list[str]:
    """The violations of a dashboard with one more query on its first visualisation."""
    dashboard = _dashboard(name)
    panel = next(panel for panel in dashboard["panels"] if panel.get("targets"))
    panel["targets"].append({"expr": expression, "refId": "Z"})
    return dashboard_violations(dashboard, DASHBOARD_EXPORTERS[name])


@pytest.mark.parametrize(
    ("name", "exporters"), DASHBOARD_EXPORTERS.items(), ids=list(DASHBOARD_EXPORTERS)
)
def test_the_dashboard_queries_only_what_its_exporters_serve(
    name: str, exporters: tuple[str, ...]
) -> None:
    """Verify every series, matcher and grouping label is backed, and every exporter is scraped."""
    dashboard = _dashboard(name)
    unscraped = [e for e in exporters if not EXPORTERS[e].scraped(_yaml(EXPORTERS[e].values))]

    assert (
        bool(_expressions(dashboard)),
        dashboard_violations(dashboard, exporters),
        unscraped,
    ) == (
        True,
        [],
        [],
    )


def test_a_query_naming_a_series_missing_from_the_capture_fails() -> None:
    """Verify a series no exporter serves is named."""
    expression = "sum(rate(litellm_requests_served_total[5m]))"

    assert _violations_after_adding("llm-stack.json", expression) == [
        f"{expression}: litellm_requests_served_total is in no capture"
    ]


def test_grouping_by_a_label_no_selected_series_carries_fails() -> None:
    """Verify a `by` label that would collapse every series into one is named."""
    expression = "sum by (api_base) (rate(litellm_output_tokens_metric_total[5m]))"

    assert _violations_after_adding("llm-stack.json", expression) == [
        f"{expression}: groups by api_base, which no series it selects carries"
    ]


def test_a_matcher_on_a_label_the_series_lacks_fails() -> None:
    """Verify a matcher on a label the series does not carry is named."""
    expression = 'otelcol_exporter_queue_size{receiver="otlp"}'

    assert _violations_after_adding("otel-collector.json", expression) == [
        f"{expression}: otelcol_exporter_queue_size does not carry receiver"
    ]


@pytest.mark.parametrize(
    "fallback", ["or vector(0)", "OR vector(0)", "or on () vector(0)", "or 0 * up"]
)
def test_a_constant_fallback_fails_however_it_is_spelled(fallback: str) -> None:
    """Verify an empty panel is never turned into a false zero."""
    expression = f"sum(rate(prometheus_http_requests_total[5m])) {fallback}"

    assert _violations_after_adding("prometheus-server.json", expression) == [
        f"{expression}: falls back to a constant"
    ]


@pytest.mark.parametrize(
    ("name", "expression", "violations"),
    [
        (
            "llm-stack.json",
            "histogram_quantile(0.95, sum by (le) (rate(litellm_llm_api_latency_metric[5m])))",
            [
                "litellm_llm_api_latency_metric is in no capture",
                "groups by le, which no series it selects carries",
            ],
        ),
        (
            "llm-stack.json",
            "sum by (le) (rate(litellm_llm_api_latency_metric_count[5m]))",
            ["groups by le, which no series it selects carries"],
        ),
        (
            "prometheus-server.json",
            'prometheus_engine_query_duration_seconds_sum{quantile="0.9"}',
            ["prometheus_engine_query_duration_seconds_sum does not carry quantile"],
        ),
    ],
    ids=["histogram-bare-name", "le-on-count", "quantile-on-summary-sum"],
)
def test_a_series_or_label_a_classic_histogram_or_summary_never_serves_fails(
    name: str, expression: str, violations: list[str]
) -> None:
    """Verify only `_bucket` carries `le`, only a summary's own name carries `quantile`, and a
    histogram's bare name selects nothing."""
    assert _violations_after_adding(name, expression) == [
        f"{expression}: {violation}" for violation in violations
    ]


# The panels that draw a limit as a threshold line, by dashboard.
LIMIT_LINES = {
    "llm-stack.json": ["GPU Memory Utilization (%)"],
    "otel-collector.json": [
        "Exporter Queue Fill",
        "Process Memory against the memory_limiter Limit",
    ],
    "prometheus-server.json": ["TSDB Size", "Resident Memory"],
    "coredns.json": [],
    "ingress-tunnel.json": ["Cloudflare Tunnel Request Error Ratio (%)"],
    "k8s-views-global.json": [],
    "k8s-views-namespaces.json": [],
    "k8s-views-nodes.json": [],
}


@pytest.mark.parametrize("name", DASHBOARD_EXPORTERS)
def test_every_threshold_line_lies_within_the_axis(name: str) -> None:
    """Verify a panel drawn against a limit extends its axis to that limit, and only then."""
    dashboard = _dashboard(name)
    unbounded = copy.deepcopy(dashboard)
    for panel in _panels(unbounded):
        panel.get("fieldConfig", {}).get("defaults", {}).get("custom", {}).pop("axisSoftMax", None)

    assert (threshold_lines_off_axis(dashboard), threshold_lines_off_axis(unbounded)) == (
        [],
        LIMIT_LINES[name],
    )


def test_collector_values_without_the_scrape_annotations_fail() -> None:
    """Verify the collector is scraped only while its pods carry both annotations."""
    collector = EXPORTERS["otel-collector"]
    values = _yaml(collector.values)
    unannotated = copy.deepcopy(values)
    unannotated.pop("podAnnotations", None)
    portless = copy.deepcopy(values)
    portless["podAnnotations"].pop("prometheus.io/port")

    assert (
        collector.scraped(values),
        collector.scraped(unannotated),
        collector.scraped(portless),
    ) == (
        True,
        False,
        False,
    )


def test_prometheus_values_without_the_self_scrape_fail() -> None:
    """Verify the server's self-scrape must be enabled explicitly."""
    server = EXPORTERS["prometheus-server"]
    values = _yaml(server.values)
    unset = copy.deepcopy(values)
    del unset["scrapeConfigs"]["prometheus"]["enabled"]

    assert (server.scraped(values), server.scraped(unset)) == (True, False)


def test_qdrant_values_without_an_authenticated_service_monitor_fail() -> None:
    """Verify Qdrant's ServiceMonitor must be enabled and authenticate with `qdrant-api-key`."""
    qdrant = EXPORTERS["qdrant"]
    values = _yaml(qdrant.values)
    disabled = copy.deepcopy(values)
    disabled.setdefault("metrics", {}).setdefault("serviceMonitor", {})["enabled"] = False
    unauthenticated = copy.deepcopy(values)
    unauthenticated.setdefault("metrics", {}).setdefault("serviceMonitor", {}).pop(
        "authorization", None
    )

    assert (
        qdrant.scraped(values),
        qdrant.scraped(disabled),
        qdrant.scraped(unauthenticated),
    ) == (
        True,
        False,
        False,
    )


def test_llm_stack_dashboard_includes_qdrant_row_over_captured_metrics() -> None:
    """Verify `llm-stack.json` restores the Qdrant row with request rate/errors, latency, and
    collections/vectors panels over captured Qdrant metrics (#823)."""
    dashboard = _dashboard("llm-stack.json")
    qdrant_series, _ = _capture("qdrant")
    panels = _panels(dashboard)
    row_titles = [p["title"] for p in panels if p.get("type") == "row"]
    qdrant_panels = [
        p["title"]
        for p in panels
        if any(
            s.metric in qdrant_series
            for target in p.get("targets", [])
            for s in selectors(target["expr"])
        )
    ]

    assert (
        "qdrant" in dashboard.get("tags", []),
        "Qdrant" in row_titles,
        qdrant_panels,
    ) == (
        True,
        True,
        [
            "Qdrant Request Rate and Errors",
            "Qdrant Request Latency p95",
            "Qdrant Collections and Vectors",
        ],
    )


def test_llm_stack_dashboard_shows_latency_per_output_token_beside_time_to_first_token() -> None:
    """Verify `llm-stack.json` charts the p50 and p95 of the gateway's latency per output token for
    each deployment and model, beside the time-to-first-token panel, and says what it measures (#598)."""
    panels = _panels(_dashboard("llm-stack.json"))
    first_token = next(p for p in panels if p.get("title") == "Time to First Token p95 per Model")
    per_token = [
        p
        for p in panels
        if any(
            s.metric == "litellm_deployment_latency_per_output_token_bucket"
            for target in p.get("targets", [])
            for s in selectors(target["expr"])
        )
    ]
    panel = per_token[0] if per_token else {"targets": [], "gridPos": {}}
    position = panel["gridPos"]

    assert (
        [p["title"] for p in per_token],
        [re.findall(r"histogram_quantile\(([0-9.]+),", t["expr"]) for t in panel["targets"]],
        [grouping_labels(t["expr"]) for t in panel["targets"]],
        panel.get("fieldConfig", {}).get("defaults", {}).get("unit"),
        (position.get("y"), position.get("x")),
        bool(panel.get("description")),
    ) == (
        ["Latency per Output Token (p50 / p95) per Deployment"],
        [["0.5"], ["0.95"]],
        [frozenset({"le", "api_base", "litellm_model_name"})] * 2,
        "s",
        (first_token["gridPos"]["y"], first_token["gridPos"]["x"] + first_token["gridPos"]["w"]),
        True,
    )


def test_coredns_dashboard_covers_requests_responses_latency_cache_and_forward() -> None:
    """Verify `coredns.json` charts requests by type/proto, responses by rcode, request duration
    p50/p95/p99, cache hits/misses, and forward request duration over captured `coredns_*` series (#822)."""
    dashboard = _dashboard("coredns.json")
    panels = [p for p in _panels(dashboard) if p.get("type") != "row"]
    titles = [p["title"] for p in panels]
    coredns_exporter = EXPORTERS["coredns"]
    values = _yaml(coredns_exporter.values)
    disabled = copy.deepcopy(values)
    disabled["clusterMetrics"]["kubeDNS"]["enabled"] = False

    assert (
        dashboard["uid"],
        titles,
        coredns_exporter.scraped(values),
        coredns_exporter.scraped(disabled),
    ) == (
        "devops-coredns",
        [
            "Requests by Type and Protocol",
            "Responses by Rcode",
            "Request Duration (p50 / p95 / p99)",
            "Forward Request Duration (p50 / p95 / p99)",
            "Cache Hits and Misses",
        ],
        True,
        False,
    )


@pytest.mark.parametrize("exporter", EXPORTERS)
def test_captures_hold_names_types_and_label_names_only(exporter: str) -> None:
    """Verify a capture records no label value, cites the source of every family it read there,
    and reads there only families that printed no sample."""
    record = _yaml(CAPTURES / f"{exporter}.yaml")
    family_keys = {key for family in record["families"].values() for key in family}
    sourced = record.get("from_source", {}).values()

    assert (
        family_keys <= {"type", "labels"},
        all(set(family) == {"type", "labels", "source"} for family in sourced),
        all(family["source"].startswith("https://github.com/") for family in sourced),
        relabelled_by_source(record),
    ) == (True, True, True, [])


def test_a_source_entry_overriding_a_sampled_family_fails() -> None:
    """Verify `from_source` cannot replace the labels a family printed, nor change its type."""
    record = _yaml(CAPTURES / "litellm.yaml")
    sampled = "litellm_proxy_total_requests_metric_total"
    cited = {"source": "https://github.com/BerriAI/litellm"}
    record["from_source"] |= {
        sampled: {**record["families"][sampled], "labels": ["api_base"], **cited},
        "litellm_deployment_cooled_down_total": {"type": "gauge", "labels": [], **cited},
    }

    assert relabelled_by_source(record) == ["litellm_deployment_cooled_down_total", sampled]


def test_cluster_metrics_allowlist_fixtures_match_pinned_k8s_monitoring_version() -> None:
    """Verify cluster_metrics allow-list fixtures record the pinned k8s-monitoring chart version (#1136)."""
    k8s_mon_release = next(
        r for r in _HELM_RELEASES_BY_STACK["infra"] if r["name"] == "k8s-monitoring"
    )
    expected_header = f"# chart: {k8s_mon_release['chart']} {k8s_mon_release['version']}"
    headers = {
        exporter: next(
            (
                line.strip()
                for line in (CLUSTER_METRICS_ALLOWLISTS / f"{exporter}.yaml")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.startswith("# chart:")
            ),
            "",
        )
        for exporter in sorted(TUNED_CLUSTER_EXPORTERS)
    }
    lists = {
        exporter: bool(_yaml(CLUSTER_METRICS_ALLOWLISTS / f"{exporter}.yaml").get("metrics"))
        for exporter in sorted(TUNED_CLUSTER_EXPORTERS)
    }

    assert (headers, lists) == (
        dict.fromkeys(sorted(TUNED_CLUSTER_EXPORTERS), expected_header),
        dict.fromkeys(sorted(TUNED_CLUSTER_EXPORTERS), True),
    )


def test_readding_kube_hpa_labels_or_removing_allowlist_entries_fails() -> None:
    """Verify re-adding `kube_hpa_labels`, removing a required `includeMetrics` entry, or disabling
    `useDefaultAllowList` fails dashboard verification (#1136)."""
    hpa_expr = 'sum(kube_hpa_labels{cluster=~"$cluster"})'
    global_dash = _dashboard("k8s-views-global.json")
    exporters = DASHBOARD_EXPORTERS["k8s-views-global.json"]
    base_values = _yaml(K8S / "monitoring" / "k8s-monitoring-values.yaml")

    missing_include = copy.deepcopy(base_values)
    tuning = missing_include["clusterMetrics"]["kube-state-metrics"]["metricsTuning"]
    tuning["includeMetrics"] = [
        m for m in tuning["includeMetrics"] if m != "kube_horizontalpodautoscaler_labels"
    ]

    default_off = copy.deepcopy(base_values)
    default_off["clusterMetrics"]["kube-state-metrics"]["metricsTuning"]["useDefaultAllowList"] = (
        False
    )

    assert (
        _violations_after_adding("k8s-views-global.json", hpa_expr),
        any(
            "kube_horizontalpodautoscaler_labels is in no capture" in v
            for v in dashboard_violations(global_dash, exporters, missing_include)
        ),
        bool(dashboard_violations(global_dash, exporters, default_off)),
    ) == (
        [f"{hpa_expr}: kube_hpa_labels is in no capture"],
        True,
        True,
    )


def test_otel_failed_spans_no_value_and_k8s_views_storage_omission() -> None:
    """Verify `otel-collector.json` sets `noValue: "none recorded"` on its failed-spans panel and
    the Kubernetes views omit `kubelet_volume_stats_*` panels with an explanatory note (#1136)."""
    otel = _dashboard("otel-collector.json")
    spans_panel = next(
        p for p in _panels(otel) if p.get("title") == "Spans Sent and Failed per Exporter"
    )
    namespaces = _dashboard("k8s-views-namespaces.json")
    nodes = _dashboard("k8s-views-nodes.json")
    ingress = _dashboard("ingress-tunnel.json")
    ingress_titles = [p.get("title") for p in _panels(ingress)]

    assert (
        spans_panel["fieldConfig"]["defaults"].get("noValue"),
        any("kubelet_volume_stats_" in expr for expr in _expressions(namespaces)),
        any("kubelet_volume_stats_" in expr for expr in _expressions(nodes)),
        "LogOrMetricVolumeDiskLow" in namespaces.get("description", ""),
        "LogOrMetricVolumeDiskLow" in nodes.get("description", ""),
        "Cloudflare Service Status" in ingress_titles,
        "Per-Service Request Rate" in ingress_titles,
    ) == (
        "none recorded",
        False,
        False,
        True,
        True,
        False,
        True,
    )
