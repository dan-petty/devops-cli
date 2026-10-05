"""Review, findings and AI spend metrics reach Prometheus (#564).

The dashboards queried review and findings metrics nothing emitted, and AI spend metrics that
only `devops server` exposed, which nothing scraped. Every metric was also sent as a gauge from a
short-lived process, so counters and histograms could not accumulate. Counters and histograms are
now deltas that the collector adds up.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.ai.personas import PersonaDefinition
from devops_cli.ai.review.runner import _record_review_metrics
from devops_cli.ai.review_schema import Finding, ReviewResult
from devops_cli.ai.spend.ledger import SpendLedger, track_request_spend
from devops_cli.telemetry import tracer as tracer_module
from devops_cli.telemetry.instruments import INSTRUMENTS, InstrumentKind, backend_name
from devops_cli.telemetry.tracer import OTelTelemetryClient

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS = REPO_ROOT / "k8s" / "monitoring" / "dashboards"
SERIES_NAME = re.compile(r"devops_cli_[a-z0-9_]+")
SENT_SERIES = {series for instrument in INSTRUMENTS for series in instrument.series}
# A quantile past a histogram's top bucket comes out as that bucket's bound.
QUANTILE_CAPS = {
    f"{instrument.name}_bucket": f"{instrument.bounds[-1]:g} {instrument.unit}"
    for instrument in INSTRUMENTS
    if instrument.kind is InstrumentKind.HISTOGRAM
}
# `by (labels) (rate(selector[window]))` or `increase(...)`: the labels one series is summed by.
GROUPED_SERIES = re.compile(r"\bby\s*\(([^)]*)\)\s*\(\s*(?:rate|increase)\(\s*([^\s\[]+)\s*\[")
QUANTILE_OF = re.compile(
    r"histogram_quantile\(\s*([0-9.]+)\s*,\s*sum\s+by\s*\([^)]*\)\s*\(\s*(?:(?:rate|increase)\(\s*)?([a-z0-9_]+)"
)
INNERMOST_PARENTHESES = re.compile(r"\([^()]*\)")


def _queries(dashboard: Path) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "expr" in node:
                found.append(node["expr"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(dashboard.read_text(encoding="utf-8")))
    return found


_PURE_DEVOPS_CLI_DASHBOARDS: frozenset[str] = frozenset(
    {"ai-spend.json", "devops-cli.json", "project-metrics.json"}
)


def _devops_cli_dashboards() -> list[Path]:
    """The shipped dashboards dedicated to devops-cli metrics."""
    return [
        dashboard
        for dashboard in sorted(DASHBOARDS.glob("*.json"))
        if dashboard.name in _PURE_DEVOPS_CLI_DASHBOARDS
    ]


def _panels(dashboard: Path) -> list[dict[str, Any]]:
    """A dashboard's visualisation panels, without its rows."""
    panels = json.loads(dashboard.read_text(encoding="utf-8"))["panels"]
    return [panel for panel in panels if panel.get("type") != "row"]


def _panel_queries(panel: dict[str, Any]) -> str:
    return " ".join(target.get("expr", "") for target in panel.get("targets", []))


def _all_queries() -> list[str]:
    """Every query in the devops-cli dashboards."""
    return [query for dashboard in _devops_cli_dashboards() for query in _queries(dashboard)]


def _outermost(query: str) -> str:
    """A query with each parenthesised part collapsed, leaving its outermost operators."""
    collapsed = INNERMOST_PARENTHESES.sub("<>", query)
    return query if collapsed == query else _outermost(collapsed)


def test_the_devops_cli_dashboards_are_found_by_their_queries() -> None:
    """Verify the glob the query checks run over finds both devops-cli dashboards."""
    names = {dashboard.name for dashboard in _devops_cli_dashboards()}
    assert {"devops-cli.json", "ai-spend.json", "project-metrics.json"} <= names


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_dashboard_query_names_a_metric_devops_cli_sends(dashboard: Path) -> None:
    """Verify each query reads a counter or histogram series devops-cli sends over OTLP."""
    queries = _queries(dashboard)

    unsent = {name for query in queries for name in SERIES_NAME.findall(query)} - SENT_SERIES
    unnamed = [q for q in queries if not SERIES_NAME.search(q)]

    assert (len(queries) > 0, sorted(unsent), unnamed) == (True, [], [])


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_series_is_read_through_rate_or_increase(dashboard: Path) -> None:
    """Verify each series is the first argument of `rate(` or `increase(`.

    A raw counter shows the count since the collector last reset the series, which happens
    whenever it sits idle for an hour, so a raw sum is neither a lifetime total nor a rate.
    `project-metrics.json` is exempt: its series report snapshot states of releases, commits,
    PRs, and milestones emitted on demand, rather than continuous runtime event streams.
    """
    if dashboard.name == "project-metrics.json":
        pytest.skip("project-metrics.json reports snapshot state, not event stream rates")
    raw = [
        (query, match.group(0))
        for query in _queries(dashboard)
        for match in SERIES_NAME.finditer(query)
        if not re.search(r"\b(?:rate|increase)\(\s*$", query[: match.start()])
    ]
    assert raw == []


def test_all_dashboards_referencing_devops_cli_metrics_name_sent_series() -> None:
    """Verify any dashboard in the repo that queries a devops_cli_* metric names a valid sent series."""
    for dashboard in sorted(DASHBOARDS.glob("*.json")):
        queries = _queries(dashboard)
        unsent = {name for query in queries for name in SERIES_NAME.findall(query)} - SENT_SERIES
        assert unsent == set(), f"{dashboard.name} queries unsent devops-cli metrics: {unsent}"


def test_the_dashboards_chart_latency_errors_reviews_and_findings_devops_cli_sends() -> None:
    """Verify each series sent but never charted is summed by the label asked for.

    The grouping must apply to that series, not to another in the same query, and the latency
    panels chart command p50, p95 and p99, review p50 and p95, RAG p50 and p95 of whole queries
    and RAG p95 of each stage (#975). Qdrant retries are charted by operation and error type.
    """
    wanted = {
        ("devops_cli_command_duration_seconds_bucket", "command"),
        ('devops_cli_command_total{status="error"}', "command"),
        ("devops_cli_review_duration_seconds_count", "target_type"),
        ("devops_cli_review_duration_seconds_bucket", "target_type"),
        ("devops_cli_findings_total", "severity"),
        ('devops_cli_rag_query_duration_ms_bucket{stage="total"}', "le"),
        ('devops_cli_rag_query_duration_ms_bucket{stage=~"embedding|search|ranking"}', "stage"),
        ("devops_cli_qdrant_retries_total", "operation"),
        ("devops_cli_qdrant_retries_total", "error_type"),
    }
    queries = _all_queries()
    grouped = {
        (series, label.strip())
        for query in queries
        for labels, series in GROUPED_SERIES.findall(query)
        for label in labels.split(",")
    }
    found = [match for query in queries for match in QUANTILE_OF.findall(query)]
    quantiles = {series: {float(q) for q, other in found if other == series} for _, series in found}

    assert (sorted(wanted - grouped), quantiles) == (
        [],
        {
            "devops_cli_command_duration_seconds_bucket": {0.5, 0.95, 0.99},
            "devops_cli_review_duration_seconds_bucket": {0.5, 0.95},
            "devops_cli_rag_query_duration_ms_bucket": {0.5, 0.95},
            "devops_cli_project_release_interval_days_bucket": {0.5, 0.95},
        },
    )


def test_a_command_group_without_errors_charts_a_zero_error_share() -> None:
    """Verify a command group with runs and no error series shows 0, not a missing line.

    Dividing two grouped sums keeps only the groups present on both sides, so a group that
    sent no error series dropped out; the numerator falls back to its runs times zero.
    """
    (query,) = [
        _panel_queries(panel)
        for panel in _panels(DASHBOARDS / "devops-cli.json")
        if panel["title"] == "Command Error Share"
    ]
    numerator, _, runs = query.rpartition(" / ")

    assert (
        numerator.startswith("("),
        numerator.endswith(f" or {runs} * 0)"),
        'status="error"' in numerator,
    ) == (True, True, True)


def test_a_grouped_query_adds_no_unlabelled_zero_series() -> None:
    """Verify `or vector(0)` follows only an ungrouped result.

    `vector(0)` has no labels, so it matches no labelled series and `or` always adds it: a
    grouped panel drew a constant zero with an empty legend beside its real series.
    """
    assert [
        query
        for query in _all_queries()
        if "or vector(0)" in query and re.search(r"\bby\b", _outermost(query))
    ] == []


def _skew(queries: str) -> str:
    """How the samples `increase()` drops skew a panel's values.

    A count only loses them, while a share or a quantile can move either way.
    """
    either_way = "histogram_quantile(" in queries or " / " in queries
    return "come out high or low" if either_way else "come out low"


def _missing_limits(panel: dict[str, Any]) -> list[str]:
    """The limits a panel's description should state and does not."""
    queries = _panel_queries(panel)
    required = [cap for bucket, cap in QUANTILE_CAPS.items() if bucket in queries]
    if "increase(" in queries:
        required += ["approximate", "two samples", "#792", _skew(queries)]
    if "devops_cli_findings_total" in queries:
        required.append("#791")
    description = panel.get("description", "").lower()
    return [phrase for phrase in required if phrase.lower() not in description]


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_panel_counting_with_increase_states_its_limits(dashboard: Path) -> None:
    """Verify each panel built on `increase()` says how far its values can be off.

    `increase()` needs two samples of a series inside its window and deltas can arrive out of
    order (#792), so a count comes out low and a share or quantile high or low; finding panels
    miss `--no-reporting` runs (#791); and a quantile past the top bucket comes out as that
    bucket's bound.
    """
    panels = _panels(dashboard)
    assert {panel["title"]: _missing_limits(panel) for panel in panels} == {
        panel["title"]: [] for panel in panels
    }


class Captured:
    """Metric data points an enabled client would send, with their resource."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, path: str, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)

    @property
    def metrics(self) -> list[dict[str, Any]]:
        return [
            metric
            for payload in self.payloads
            for resource in payload["resourceMetrics"]
            for scope in resource["scopeMetrics"]
            for metric in scope["metrics"]
        ]

    def points(self, name: str) -> list[tuple[dict[str, Any], float]]:
        """Each data point of a metric, as (attributes, value)."""
        found = []
        for metric in self.metrics:
            if metric["name"] != name:
                continue
            data = metric.get("sum") or metric.get("histogram") or metric["gauge"]
            for point in data["dataPoints"]:
                attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
                found.append((attrs, point.get("asDouble", point.get("sum"))))
        return found


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> Captured:
    """An enabled telemetry client whose payloads are captured instead of sent."""
    sink = Captured()
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    monkeypatch.setattr(client, "_send_payload", sink)
    monkeypatch.setattr(tracer_module, "get_tracer", lambda: client)
    return sink


def test_counters_are_monotonic_deltas_from_the_host_not_the_process(captured: Captured) -> None:
    """Verify a counter is a delta sum whose resource names the host and no process, so the
    collector adds up every command's deltas into one series per host."""
    tracer_module.get_tracer().increment_counter("devops_cli_command_total", 1, attributes={})

    (metric,) = captured.metrics
    resource = {
        a["key"]: a["value"]["stringValue"]
        for a in captured.payloads[0]["resourceMetrics"][0]["resource"]["attributes"]
    }
    point = metric["sum"]["dataPoints"][0]

    assert (
        (metric["sum"]["aggregationTemporality"], metric["sum"]["isMonotonic"]),
        "process.pid" in resource or "service.version" in resource,
        resource["service.instance.id"] == resource["host.name"],
        int(point["startTimeUnixNano"]) < int(point["timeUnixNano"]),
    ) == ((1, True), False, True, True)


def test_a_histogram_observation_lands_in_its_bucket(captured: Captured) -> None:
    """Verify a histogram point counts one observation in the first bucket that holds it."""
    client = tracer_module.get_tracer()
    client.record_histogram("h", 7.0, bounds=(1.0, 5.0, 10.0))
    client.record_histogram("h", 50.0, bounds=(1.0, 5.0, 10.0))

    points = [m["histogram"]["dataPoints"][0] for m in captured.metrics]

    assert [(p["bucketCounts"], p["count"], p["sum"]) for p in points] == [
        (["0", "0", "1", "0"], "1", 7.0),
        (["0", "0", "0", "1"], "1", 50.0),
    ]


def test_ai_calls_count_requests_tokens_and_spend_by_backend(
    captured: Captured, tmp_path: Path
) -> None:
    """Verify each call counts a request, its prompt and completion tokens, and its spend, by
    serving backend; a cached reply counts as cached and costs nothing."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    for cached in (False, True):
        track_request_spend(
            provider="gateway",
            model="gpt-4o",
            server="gateway.example:4000",
            served_by="http://vllm.llm.svc.cluster.local:8000/v1",
            prompt_tokens=1000,
            completion_tokens=200,
            cached=cached,
            ledger=ledger,
        )

    requests = captured.points("devops_cli_ai_requests_total")
    tokens = captured.points("devops_cli_ai_tokens_total")
    spend = captured.points("devops_cli_ai_spend_usd_total")

    assert (
        [(a["backend"], a["cached"], v) for a, v in requests],
        sorted({(a["type"], v) for a, v in tokens}),
        (len(spend), spend[0][1] > 0, spend[0][0]["backend"]),
    ) == (
        [("vllm", "false", 1.0), ("vllm", "true", 1.0)],
        [("completion", 200.0), ("prompt", 1000.0)],
        (1, True, "vllm"),
    )


def test_local_ai_calls_emit_equivalent_spend_instrument(
    captured: Captured, tmp_path: Path
) -> None:
    """Verify local AI calls emit devops_cli_ai_local_cost_equivalent_usd_total and zero direct spend."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    track_request_spend(
        provider="ollama",
        model="qwen2.5-coder:7b",
        server="http://localhost:11434",
        served_by="http://ollama-0.ollama:11434",
        prompt_tokens=1000,
        completion_tokens=200,
        cached=False,
        ledger=ledger,
    )

    equiv = captured.points("devops_cli_ai_local_cost_equivalent_usd_total")
    spend = captured.points("devops_cli_ai_spend_usd_total")

    assert (
        len(equiv),
        equiv[0][1] > 0,
        equiv[0][0]["backend"],
        equiv[0][0]["provider"],
        len(spend),
    ) == (
        1,
        True,
        "ollama-0",
        "ollama",
        0,
    )


def test_a_review_sends_its_duration_and_findings_by_persona_severity_and_status(
    captured: Captured,
) -> None:
    """Verify findings are counted once per persona, severity and status, and failed personas
    contribute none."""
    persona = PersonaDefinition(
        name="devsecops", title="DevSecOps", system_prompt="", chat_prompt="", compose_prompt=""
    )
    findings = [
        Finding(severity="high", title="a", location="x:1", status="VERIFIED"),
        Finding(severity="HIGH", title="b", location="x:2", status="VERIFIED"),
        Finding(severity="LOW", title="c", location="x:3", status="INVALIDATED"),
    ]
    results: list[tuple[PersonaDefinition, ReviewResult | str]] = [
        (persona, ReviewResult(findings=findings)),
        (persona, "the persona failed"),
    ]

    _record_review_metrics(results, 312.5, "path")

    assert (
        captured.points("devops_cli_review_duration_seconds"),
        sorted(
            (a["severity"], a["status"], v) for a, v in captured.points("devops_cli_findings_total")
        ),
    ) == (
        [({"target_type": "path"}, 312.5)],
        [("HIGH", "VERIFIED", 2.0), ("LOW", "INVALIDATED", 1.0)],
    )


def test_the_collector_adds_up_deltas_before_prometheus() -> None:
    """Verify the metrics pipeline turns deltas into running totals before remote write."""
    values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "otel" / "values.yaml").read_text(encoding="utf-8")
    )
    config = values["config"]
    processors = config["service"]["pipelines"]["metrics"]["processors"]

    assert (
        "deltatocumulative" in config["processors"],
        processors.index("deltatocumulative") < processors.index("batch"),
    ) == (True, True)


@pytest.mark.parametrize(
    ("served_by", "name"),
    [
        ("http://vllm.llm.svc.cluster.local:8000/v1", "vllm"),
        ("ollama-0.ollama:11434", "ollama-0"),
        (None, ""),
    ],
)
def test_backends_are_named_by_their_hosts_first_label(served_by: str | None, name: str) -> None:
    """Verify a backend URL, or a bare host and port, is shortened to its host's first label."""
    assert backend_name(served_by) == name
