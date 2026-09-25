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
from devops_cli.telemetry.instruments import INSTRUMENTS, backend_name
from devops_cli.telemetry.tracer import OTelTelemetryClient

DASHBOARDS = Path("k8s/monitoring/dashboards")


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


@pytest.mark.parametrize("dashboard", ["devops-cli.json", "ai-spend.json"])
def test_every_dashboard_query_names_a_metric_devops_cli_sends(dashboard: str) -> None:
    """Verify each query reads a counter or histogram series devops-cli sends over OTLP."""
    sent = {series for instrument in INSTRUMENTS for series in instrument.series}
    queries = _queries(DASHBOARDS / dashboard)

    unsent = {
        name for query in queries for name in re.findall(r"devops_cli_[a-z0-9_]+", query)
    } - sent
    unnamed = [q for q in queries if not re.search(r"devops_cli_[a-z0-9_]+", q)]

    assert (len(queries) > 0, sorted(unsent), unnamed) == (True, [], [])


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
    values = yaml.safe_load(Path("k8s/otel/values.yaml").read_text(encoding="utf-8"))
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
