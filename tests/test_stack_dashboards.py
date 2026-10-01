"""Stack dashboards query only the series their exporters serve (#693).

`llm-stack.json`, `otel-collector.json` and `prometheus-server.json` are checked against the
metric families captured from the exporters behind them (`tests/fixtures/metrics/`): every
series a query selects, every label it matches or groups by, and the scrape that brings
each exporter's series into Prometheus. A query naming a series nothing serves renders an
empty panel, and an `or vector(0)` fallback turns that empty panel into a false zero, so a
broken export reads as a quiet system. A panel drawn against a limit must also reach it on
its axis, or the limit line is never seen.

The checks read files only.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.prometheus.promql import falls_back_to_constant, grouping_labels, selectors

ROOT = Path(__file__).resolve().parents[1]
K8S = ROOT / "k8s"
DASHBOARDS = K8S / "monitoring" / "dashboards"
CAPTURES = ROOT / "tests" / "fixtures" / "metrics"

# Series Prometheus records about every scrape itself, whatever the target serves. Alloy
# forwards all of them for its ServiceMonitor targets (the gateway, DCGM); its cluster-metrics
# jobs keep only `up` and `scrape_samples_scraped`.
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
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _gateway_monitored(values: dict[str, Any]) -> bool:
    """Alloy reads ServiceMonitors, and one selects the gateway."""
    monitors = [
        obj for obj in values.get("extraObjects", []) if obj.get("kind") == "ServiceMonitor"
    ]
    return values["prometheusOperatorObjects"]["enabled"] is True and any(
        monitor["metadata"]["name"] == "llm-gateway" for monitor in monitors
    )


def _dcgm_monitored(values: dict[str, Any]) -> bool:
    """The DCGM chart creates its own ServiceMonitor."""
    return values.get("serviceMonitor", {}).get("enabled") is True


def _collector_annotated(values: dict[str, Any]) -> bool:
    """The server's kubernetes-pods job keeps pods annotated for scraping, on their port."""
    wanted = {"prometheus.io/scrape": "true", "prometheus.io/port": "8888"}
    annotations = values.get("podAnnotations") or {}
    return wanted.items() <= annotations.items() and values["ports"]["metrics"]["enabled"] is True


def _server_jobs_enabled(values: dict[str, Any]) -> bool:
    """The server scrapes itself and annotated pods, set explicitly rather than by chart default."""
    jobs = values.get("scrapeConfigs", {})
    return all(
        jobs.get(job, {}).get("enabled") is True for job in ("prometheus", "kubernetes-pods")
    )


@dataclass(frozen=True)
class Exporter:
    """Where an exporter's scrape is defined in `k8s/`, and the check that it is."""

    values: Path
    scraped: Callable[[dict[str, Any]], bool]


EXPORTERS = {
    "litellm": Exporter(K8S / "monitoring" / "k8s-monitoring-values.yaml", _gateway_monitored),
    "dcgm-exporter": Exporter(K8S / "monitoring" / "dcgm-exporter-values.yaml", _dcgm_monitored),
    "otel-collector": Exporter(K8S / "otel" / "values.yaml", _collector_annotated),
    "prometheus-server": Exporter(
        K8S / "monitoring" / "prometheus-values.yaml", _server_jobs_enabled
    ),
}
DASHBOARD_EXPORTERS = {
    "llm-stack.json": ("litellm", "dcgm-exporter"),
    "otel-collector.json": ("otel-collector",),
    "prometheus-server.json": ("prometheus-server",),
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


def _capture(exporter: str) -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    """An exporter's series with their labels, and the labels its scrape adds."""
    record = _yaml(CAPTURES / f"{exporter}.yaml")
    target_labels = frozenset(record["target_labels"])
    families = {**record["families"], **record.get("from_source", {})}
    series = {
        series_name: labels
        for name, family in families.items()
        for series_name, labels in _family_series(name, family, target_labels).items()
    }
    return series, target_labels


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


def known_series(exporters: tuple[str, ...]) -> dict[str, frozenset[str]]:
    """The series a dashboard's exporters serve, and the scrape's own, with their labels."""
    captures = [_capture(exporter) for exporter in exporters]
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


def dashboard_violations(dashboard: dict[str, Any], exporters: tuple[str, ...]) -> list[str]:
    """Describe every query in a dashboard that its exporters do not back."""
    known = known_series(exporters)
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
    "llm-stack.json": [],
    "otel-collector.json": [
        "Exporter Queue Fill",
        "Process Memory against the memory_limiter Limit",
    ],
    "prometheus-server.json": ["TSDB Size", "Resident Memory"],
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
