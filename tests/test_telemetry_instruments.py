"""Review, findings and AI spend metrics reach Prometheus (#564).

The dashboards queried review and findings metrics nothing emitted, and AI spend metrics that
only `devops server` exposed, which nothing scraped. Every metric was also sent as a gauge from a
short-lived process, so counters and histograms could not accumulate. Counters and histograms are
now deltas that the collector adds up.
"""

from __future__ import annotations

import ast
import contextlib
import json
import re
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.ai.client import LLMClient, LLMResponse
from devops_cli.ai.personas import PersonaDefinition
from devops_cli.ai.response_cache import get_llm_response_cache
from devops_cli.ai.review.runner import _record_review_metrics
from devops_cli.ai.review_schema import Finding, ReviewResult
from devops_cli.ai.spend.ledger import SpendLedger, track_request_spend
from devops_cli.ai.spend.pricing import get_pricing_registry
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import tracer as tracer_module
from devops_cli.telemetry.exporter import OtlpSignal
from devops_cli.telemetry.instruments import (
    INSTRUMENTS,
    PROJECT_ITEM_LABELS,
    PROJECT_ITEMS,
    REVIEW_DURATION,
    UPSTREAM_SERVICE_STATUS,
    InstrumentKind,
    backend_name,
    emit,
)
from devops_cli.telemetry.tracer import OTelTelemetryClient
from tests.support.fakes.otlp import FakeCollector
from tests.support.paths import REPO_ROOT
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

DASHBOARDS = REPO_ROOT / "k8s" / "monitoring" / "dashboards"
SERIES_NAME = re.compile(r"devops_cli_[a-z0-9_]+")
SENT_SERIES = {instrument.name for instrument in INSTRUMENTS}
# `by (labels) (rate(selector[window]))` or `increase(...)`: the labels one series is summed by.
GROUPED_SERIES = re.compile(r"\bby\s*\(([^)]*)\)\s*\(\s*(?:rate|increase)\(\s*([^\s\[]+)\s*\[")
QUANTILE_OF = re.compile(
    r"histogram_quantile\(\s*([0-9.]+)\s*,\s*sum\s*(?:by\s*\([^)]*\)\s*)?\(\s*"
    r"(?:(?:rate|increase|last_over_time)\(\s*)?([a-z0-9_]+)"
)
INNERMOST_PARENTHESES = re.compile(r"\([^()]*\)")


def _queries(dashboard: Path) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ds = node.get("datasource")
            if isinstance(ds, dict) and ds.get("type") == "loki":
                return
            if node.get("type") == "logs":
                return
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


# The AI spend dashboard also reads the gateway's request and token series, which count every
# caller's calls (#1668). tests/test_stack_dashboards.py checks them against the LiteLLM capture.
_GATEWAY_SERIES_DASHBOARDS: frozenset[str] = frozenset({"ai-spend.json"})
GATEWAY_SERIES_NAME = re.compile(r"\blitellm_[a-z0-9_]+")


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_dashboard_query_names_a_metric_devops_cli_sends(dashboard: Path) -> None:
    """Verify each query reads a counter or histogram series devops-cli sends over OTLP, or, on
    the AI spend dashboard, a series of the gateway."""
    queries = _queries(dashboard)
    reads_gateway = dashboard.name in _GATEWAY_SERIES_DASHBOARDS

    unsent = {name for query in queries for name in SERIES_NAME.findall(query)} - SENT_SERIES
    unnamed = [
        q
        for q in queries
        if not SERIES_NAME.search(q) and not (reads_gateway and GATEWAY_SERIES_NAME.search(q))
    ]

    assert (len(queries) > 0, sorted(unsent), unnamed) == (True, [], [])


# The functions that read each kind of series over time. A counter's raw sum is the count since
# the collector last reset the series, which it does when the series sits idle for an hour. A
# gauge holds a snapshot, which Prometheus finds only within five minutes of its sample (#974).
_READ_THROUGH: dict[InstrumentKind, frozenset[str]] = {
    InstrumentKind.COUNTER: frozenset({"rate", "increase"}),
    InstrumentKind.GAUGE: frozenset({"last_over_time"}),
    InstrumentKind.HISTOGRAM: frozenset({"rate", "increase", "last_over_time"}),
}
_KIND_OF: dict[str, InstrumentKind] = {
    instrument.name: instrument.kind for instrument in INSTRUMENTS
}


def _reading_function(before: str) -> str:
    """The function whose first argument starts where `before` ends, or "" for none."""
    found = re.search(r"\b([a-z_]+)\(\s*$", before)
    return found.group(1) if found else ""


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_series_is_read_through_the_function_of_its_kind(dashboard: Path) -> None:
    """Verify each series is the first argument of a function that reads its kind over time: a
    counter's `rate(` or `increase(`, a gauge's `last_over_time(`, a histogram's either."""
    misread = [
        (query, match.group(0))
        for query in _queries(dashboard)
        for match in SERIES_NAME.finditer(query)
        if _reading_function(query[: match.start()])
        not in _READ_THROUGH.get(_KIND_OF.get(match.group(0)), frozenset())
    ]
    assert misread == []


def test_a_counter_name_ends_in_total_and_no_other_name_does() -> None:
    """Prometheus keeps the `_total` suffix for counters, so a gauge that carries it reads as a
    counter to each consumer (#974)."""
    misnamed = [
        instrument.name
        for instrument in INSTRUMENTS
        if (instrument.kind is InstrumentKind.COUNTER) != instrument.name.endswith("_total")
    ]
    assert misnamed == []


def test_all_dashboards_referencing_devops_cli_metrics_name_sent_series() -> None:
    """Verify any dashboard in the repo that queries a devops_cli_* metric names a valid sent series."""
    for dashboard in sorted(DASHBOARDS.glob("*.json")):
        queries = _queries(dashboard)
        unsent = {name for query in queries for name in SERIES_NAME.findall(query)} - SENT_SERIES
        assert unsent == set(), f"{dashboard.name} queries unsent devops-cli metrics: {unsent}"


def _resolve_gauge_call_arg(
    arg: ast.AST, const_dict: dict[str, str], inst_dict: dict[str, Any]
) -> str | None:
    """Resolve the gauge name from an AST argument node."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Name) and arg.id in const_dict:
        return const_dict[arg.id]
    if isinstance(arg, ast.Attribute) and arg.attr == "name":
        if isinstance(arg.value, ast.Name) and arg.value.id in inst_dict:
            obj = inst_dict[arg.value.id]
            if hasattr(obj, "name"):
                return str(obj.name)
    return None


def _scraped_gauge_names_in_tree(tree: ast.AST) -> set[str]:
    """Return gauge names that an AST records into an in-memory registry or exposes via Prometheus."""
    import devops_cli.telemetry.instruments as inst_mod
    from devops_cli.config import constants

    const_dict = {
        name: getattr(constants, name)
        for name in dir(constants)
        if isinstance(getattr(constants, name), str)
    }
    inst_dict = {name: getattr(inst_mod, name) for name in dir(inst_mod)}

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if isinstance(node.func, ast.Attribute) and node.func.attr == "set_gauge":
            name = _resolve_gauge_call_arg(first, const_dict, inst_dict)
            if name:
                names.add(name)
        elif isinstance(node.func, ast.Name) and node.func.id == "GaugeMetricFamily":
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.add(first.value)
    return names


def _all_scraped_gauge_names() -> set[str]:
    """All gauge names recorded into in-memory registries or exposed via Prometheus in src/devops_cli."""
    gauges: set[str] = set()
    src_dir = REPO_ROOT / "src" / "devops_cli"
    for path in src_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        gauges |= _scraped_gauge_names_in_tree(tree)
    return gauges


def test_no_gauge_reaches_prometheus_through_two_paths() -> None:
    """Each gauge reaches Prometheus through one path (#2288). A check fails when two paths send the same gauge name."""
    otlp_gauges = {
        instrument.name for instrument in INSTRUMENTS if instrument.kind is InstrumentKind.GAUGE
    }
    scraped_gauges = _all_scraped_gauge_names()
    shared = otlp_gauges & scraped_gauges
    assert shared == set(), f"Gauges sent through both OTLP and scrape paths: {sorted(shared)}"


def test_a_check_fails_when_two_paths_send_the_same_gauge_name(tmp_path: Path) -> None:
    """A check fails when two paths send the same gauge name (#2288)."""
    bad_code = "reg.set_gauge(PROJECT_ITEMS.name, 1.0)\n"
    tree = ast.parse(bad_code, filename=str(tmp_path / "bad.py"))
    scraped = _scraped_gauge_names_in_tree(tree)
    otlp_gauges = {
        instrument.name for instrument in INSTRUMENTS if instrument.kind is InstrumentKind.GAUGE
    }
    shared = otlp_gauges & scraped
    assert PROJECT_ITEMS.name in shared


_METRIC_METHODS = frozenset(
    {"increment_counter", "record_gauge", "record_histogram", "record_metric"}
)
"""The telemetry client's methods that write a metric by its name."""
_SERVICE_REGISTRY = "GLOBAL_METRICS"
"""The Prometheus registry that the Service serves on `/metrics`: no OTLP metric."""
SRC = REPO_ROOT / "src" / "devops_cli"


def _declared_instrument_imports(tree: ast.AST) -> tuple[set[str], set[str]]:
    """The local names of `emit`, and of the declared instruments, that a module imports from
    the instruments module."""
    import devops_cli.telemetry.instruments as instruments

    emit_names: set[str] = set()
    declared: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != instruments.__name__:
            continue
        for alias in node.names:
            local = alias.asname or alias.name
            if alias.name == "emit":
                emit_names.add(local)
            elif getattr(instruments, alias.name, None) in INSTRUMENTS:
                declared.add(local)
    return emit_names, declared


def _writes_outside_emit(call: ast.Call, emit_names: set[str], declared: set[str]) -> bool:
    """Whether a call writes a metric by its name, or emits an instrument that `INSTRUMENTS`
    does not hold."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in _METRIC_METHODS:
        return not (isinstance(func.value, ast.Name) and func.value.id == _SERVICE_REGISTRY)
    if isinstance(func, ast.Name) and func.id in _METRIC_METHODS:
        return True
    if isinstance(func, ast.Name) and func.id in emit_names:
        first = call.args[0] if call.args else None
        return not (isinstance(first, ast.Name) and first.id in declared)
    return False


def _metric_writes_outside_emit(tree: ast.AST, label: str) -> list[str]:
    """Each call of a module, as `<label>:<line>`, that writes a metric by its name or emits an
    instrument that `INSTRUMENTS` does not hold."""
    emit_names, declared = _declared_instrument_imports(tree)
    lines = sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _writes_outside_emit(node, emit_names, declared)
    )
    return [f"{label}:{line}" for line in lines]


def test_every_metric_is_a_declared_instrument_sent_through_emit() -> None:
    """Verify no module but the instruments module writes a metric by its name, and every
    `emit()` sends a declared instrument (#817).

    A metric sent by name skips the kind that `INSTRUMENTS` gives it: a count sent as a gauge
    keeps only the last process's value.
    """
    instruments_module = SRC / "telemetry" / "instruments.py"
    found = [
        call
        for path in sorted(SRC.rglob("*.py"))
        if path != instruments_module
        for call in _metric_writes_outside_emit(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
            str(path.relative_to(SRC)),
        )
    ]
    assert found == []


def test_the_instrument_check_names_a_metric_sent_by_name_and_an_undeclared_instrument() -> None:
    """Verify the check names a metric written by its name and an `emit()` of an instrument that
    `INSTRUMENTS` does not hold, and lets the Service's registry and a declared instrument by
    (#817)."""
    module = (
        "from devops_cli.telemetry import get_tracer\n"
        "from devops_cli.telemetry.instruments import COMMAND_TOTAL, Instrument, InstrumentKind, emit\n"
        "from devops_cli.telemetry.metrics import GLOBAL_METRICS\n"
        'get_tracer().record_gauge("devops_cli_example", 1.0)\n'
        'emit(Instrument("devops_cli_example_total", InstrumentKind.COUNTER, "1", "x"), 1.0)\n'
        'GLOBAL_METRICS.increment_counter("service_rounds_total")\n'
        "emit(COMMAND_TOTAL, 1.0)\n"
    )

    assert _metric_writes_outside_emit(ast.parse(module), "example.py") == [
        "example.py:4",
        "example.py:5",
    ]


def test_the_items_panels_group_only_by_labels_the_gauge_sends() -> None:
    """A panel that groups `devops_cli_project_items` by a label that the gauge does not send
    shows one series for all items (#2263)."""
    queries = [query for query in _all_queries() if PROJECT_ITEMS.name in query]
    grouped = {
        label.strip()
        for query in queries
        for labels in re.findall(r"\bby\s*\(([^)]*)\)", query)
        for label in labels.split(",")
        if label.strip()
    }

    assert len(queries) == 2
    assert grouped - set(PROJECT_ITEM_LABELS) == set()


def test_the_release_panel_shows_an_item_in_no_release_as_unreleased() -> None:
    """An item that no release closed has an empty `release`, which a legend shows as a blank
    (#2702)."""
    queries = {
        panel["title"]: _panel_queries(panel)
        for panel in _panels(DASHBOARDS / "project-metrics.json")
    }

    assert queries["Items by Release"] == (
        "label_replace(sum by (release, state) "
        '(last_over_time(devops_cli_project_items[$__range])), "release", "unreleased", '
        '"release", "^$")'
    )
    assert queries["Active Items by State"] == (
        "sum by (state) (last_over_time(devops_cli_project_items[$__range]))"
    )


def test_the_dashboards_chart_latency_errors_reviews_and_findings_devops_cli_sends() -> None:
    """Verify each series sent but never charted is summed by the label asked for.

    The grouping must apply to that series, not to another in the same query, and the latency
    panels chart command p50, p95 and p99, review p50 and p95, RAG p50 and p95 of whole queries
    and RAG p95 of each stage (#975). Qdrant retries are charted by operation and error type.
    AI requests and tokens are charted by operation, so chat and embeddings are told apart (#1623).
    The Ollama slot wait is charted at p95 by priority (#815).
    """
    wanted = {
        ("devops_cli_command_duration_seconds", "command"),
        (
            'devops_cli_subcommand_duration_seconds{command=~"$command",sub_command=~"$sub_command"}',
            "sub_command",
        ),
        ('devops_cli_command_total{status="error"}', "command"),
        ("devops_cli_review_duration_seconds", "target_type"),
        ("devops_cli_findings_total", "severity"),
        ('devops_cli_rag_query_duration_ms{stage=~"embedding|search|ranking"}', "stage"),
        ("devops_cli_qdrant_retries_total", "operation"),
        ("devops_cli_qdrant_retries_total", "error_type"),
        ("devops_cli_ai_requests_total", "operation"),
        ("devops_cli_ai_tokens_total", "operation"),
        ("devops_cli_ai_ollama_slot_wait_seconds", "priority"),
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
            "devops_cli_command_duration_seconds": {0.5, 0.95, 0.99},
            "devops_cli_subcommand_duration_seconds": {0.5, 0.95, 0.99},
            "devops_cli_review_duration_seconds": {0.5, 0.95},
            "devops_cli_rag_query_duration_ms": {0.5, 0.95},
            "devops_cli_project_release_interval_days": {0.5, 0.95},
            "devops_cli_ai_ollama_slot_wait_seconds": {0.95},
        },
    )


def _row_panels(dashboard: Path, row_title: str) -> list[dict[str, Any]]:
    """The panels between the row `row_title` and the next row, in the order the file holds."""
    panels = json.loads(dashboard.read_text(encoding="utf-8"))["panels"]
    titles = [panel.get("title") if panel.get("type") == "row" else None for panel in panels]
    start = titles.index(row_title) + 1
    end = next((i for i in range(start, len(panels)) if titles[i] is not None), len(panels))
    return panels[start:end]


def test_the_github_api_row_charts_requests_throttles_and_graphql_points() -> None:
    """The GitHub API row shows the requests and the throttles by resource, the seconds spent
    waiting before a retry, and the GraphQL points (#814)."""
    panels = _row_panels(DASHBOARDS / "devops-cli.json", "GitHub API")

    assert {panel["title"]: _panel_queries(panel) for panel in panels} == {
        "GitHub Requests by Resource": (
            "sum by (resource) (increase(devops_cli_github_requests_total[1h]))"
        ),
        "GitHub Throttles by Resource": (
            "histogram_count(sum by (resource) "
            "(increase(devops_cli_github_throttle_wait_seconds[1h])))"
        ),
        "GitHub Throttle Wait by Resource": (
            "histogram_sum(sum by (resource) "
            "(increase(devops_cli_github_throttle_wait_seconds[1h])))"
        ),
        "GitHub GraphQL Points": (
            "sum(increase(devops_cli_github_graphql_points_total[1h])) or vector(0)"
        ),
    }


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


def test_the_hit_share_panel_divides_cached_requests_by_all_requests_over_an_hour() -> None:
    """Verify the response-cache hit share is cached requests over every chat request, each
    counted over the last hour, and shows 0 for an hour with requests and no hits (#816).

    The response cache answers no embedding request, so embedding requests stay out of the
    share; a series sent before requests carried an operation still counts as chat (#1623).
    Active backends still count only uncached requests: the cache is no backend.
    """
    panels = {panel["title"]: panel for panel in _panels(DASHBOARDS / "ai-spend.json")}
    numerator, _, requests = _panel_queries(panels["Response Cache Hit Share"]).rpartition(" / ")

    assert (
        numerator,
        requests,
        'cached="false"' in _panel_queries(panels["Active AI Backends"]),
    ) == (
        f'(sum(increase(devops_cli_ai_requests_total{{cached="true"}}[1h])) or {requests} * 0)',
        'sum(increase(devops_cli_ai_requests_total{operation!="embeddings"}[1h]))',
        True,
    )


def test_the_embedding_hit_share_panel_divides_hits_by_lookups_over_an_hour() -> None:
    """Verify the embedding cache hit share is the hits of the last hour over its lookups, and
    shows 0 for an hour with lookups and no hits (#817)."""
    panels = {panel["title"]: panel for panel in _panels(DASHBOARDS / "devops-cli.json")}

    assert _panel_queries(panels["Embedding Cache Hit Share"]) == (
        '(sum(increase(devops_cli_embedding_cache_lookups_total{result="hit"}[1h])) '
        "or sum(increase(devops_cli_embedding_cache_lookups_total[1h])) * 0) "
        "/ sum(increase(devops_cli_embedding_cache_lookups_total[1h]))"
    )


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


def _zero_fallback(query: str) -> str:
    """A spend query as it reads with its fallback to 0.

    An ungrouped result falls back to `vector(0)`. A grouped one falls back to the requests a
    model answered, grouped the same and times 0, so each backend that served requests shows
    $0 with its labels.
    """
    spend, _, _ = query.partition(" or ")
    if not re.search(r"\bby\b", _outermost(spend)):
        return f"{spend} or vector(0)"
    requests = re.sub(r"\s*\*\s*\d+$", "", spend).replace(
        "devops_cli_ai_spend_usd_total", 'devops_cli_ai_requests_total{cached="false"}'
    )
    return f"{spend} or {requests} * 0"


def test_every_spend_query_shows_zero_when_no_spend_series_matches() -> None:
    """Verify each query of the spend counter falls back to 0, so a dashboard shows $0, not
    "No data", which a broken pipeline also shows (#1631)."""
    spend_queries = [q for q in _all_queries() if "devops_cli_ai_spend_usd_total" in q]

    assert (
        len(spend_queries) > 0,
        [q for q in spend_queries if q != _zero_fallback(q)],
    ) == (True, [])


def _skew(queries: str) -> str:
    """How the samples `increase()` drops skew a panel's values.

    A count only loses them, while a share or a quantile can move either way.
    """
    either_way = "histogram_quantile(" in queries or " / " in queries
    return "come out high or low" if either_way else "come out low"


def _missing_limits(panel: dict[str, Any]) -> list[str]:
    """The limits a panel's description should state and does not.

    The limits are those of devops-cli's delta series. A panel that reads only the gateway's
    series reads counters that Prometheus scrapes whole, so it has none of them (#1668).
    """
    queries = _panel_queries(panel)
    counts_deltas = "increase(" in queries and SERIES_NAME.search(queries) is not None
    required = ["approximate", "two samples", "#792", _skew(queries)] if counts_deltas else []
    if "devops_cli_findings_total" in queries:
        required.append("#791")
    description = panel.get("description", "").lower()
    return [phrase for phrase in required if phrase.lower() not in description]


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_panel_counting_with_increase_states_its_limits(dashboard: Path) -> None:
    """Verify each panel built on `increase()` says how far its values can be off.

    `increase()` needs two samples of a series inside its window and deltas can arrive out of
    order (#792), so a count comes out low and a share or quantile high or low; and finding panels
    miss `--no-reporting` runs (#791). Exponential histograms have no fixed top-bucket cap.
    """
    panels = _panels(dashboard)
    capped = [
        panel["title"]
        for panel in panels
        if "past the top bucket" in panel.get("description", "").lower()
    ]
    assert ({panel["title"]: _missing_limits(panel) for panel in panels}, capped) == (
        {panel["title"]: [] for panel in panels},
        [],
    )


def test_duration_panels_chart_mean_and_sample_count_alongside_quantiles() -> None:
    """Verify every duration panel in devops-cli.json charts the mean and the sample count of its
    native histogram beside the quantiles."""
    duration_panels = [
        panel
        for panel in _panels(DASHBOARDS / "devops-cli.json")
        if "histogram_quantile(" in _panel_queries(panel)
    ]
    missing = [
        panel["title"]
        for panel in duration_panels
        if "histogram_avg(" not in _panel_queries(panel)
        or "histogram_count(" not in _panel_queries(panel)
    ]
    assert (len(duration_panels), missing) == (5, [])


def test_counters_are_monotonic_deltas_from_the_host_not_the_process(otlp: FakeCollector) -> None:
    """Verify a counter is a delta sum whose resource names the host and no process, so the
    collector adds up every command's deltas into one series per host."""
    tracer_module.get_tracer().increment_counter("devops_cli_command_total", 1, attributes={})

    (metric,) = otlp.metrics
    resource = {
        a["key"]: a["value"]["stringValue"]
        for a in otlp.payloads(OtlpSignal.METRICS)[0]["resourceMetrics"][0]["resource"][
            "attributes"
        ]
    }
    point = metric["sum"]["dataPoints"][0]

    assert (
        (metric["sum"]["aggregationTemporality"], metric["sum"]["isMonotonic"]),
        "process.pid" in resource or "service.version" in resource,
        resource["service.instance.id"] == resource["host.name"],
        int(point["startTimeUnixNano"]) < int(point["timeUnixNano"]),
    ) == ((1, True), False, True, True)


def test_flushes_from_two_threads_send_their_deltas_in_the_order_they_collected_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The collector's `deltatocumulative` drops a delta that is not later than the last delta it
    added to the series. The Service's lane workers flush at the same time, so a flush collects
    only when the export of the flush before it is done (#1629)."""
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    sent_payloads: list[dict[str, Any]] = []
    first_in_export, release_first = threading.Event(), threading.Event()

    def send(path: str, payload: dict[str, Any]) -> None:
        if not first_in_export.is_set():
            first_in_export.set()
            release_first.wait(THREAD_HANDOFF_BOUND_SECONDS)
        sent_payloads.append(payload)

    monkeypatch.setattr(client, "_send_payload", send)
    client.increment_counter("devops_cli_ai_requests_total", 1, attributes={})
    first = threading.Thread(target=client.flush)
    first.start()
    assert first_in_export.wait(THREAD_HANDOFF_BOUND_SECONDS)
    client.increment_counter("devops_cli_ai_requests_total", 2, attributes={})
    second_ready = threading.Event()

    def second_flush() -> None:
        second_ready.set()
        client.flush()

    second = threading.Thread(target=second_flush)
    second.start()
    assert second_ready.wait(THREAD_HANDOFF_BOUND_SECONDS)
    # This short window checks that the second flush sends nothing while the first export is
    # held. It opens only once the second thread is at its flush, so it times the flush's lock,
    # not a thread start-up.
    sent_during_first = wait_until(lambda: bool(sent_payloads), bound=0.2)
    release_first.set()
    first.join(THREAD_HANDOFF_BOUND_SECONDS)
    second.join(THREAD_HANDOFF_BOUND_SECONDS)

    sent = [
        float(point["asDouble"])
        for payload in sent_payloads
        for resource in payload["resourceMetrics"]
        for scope in resource["scopeMetrics"]
        for metric in scope["metrics"]
        for point in metric["sum"]["dataPoints"]
    ]
    assert (sent_during_first, sent, first.is_alive(), second.is_alive()) == (
        False,
        [1.0, 2.0],
        False,
        False,
    )


def test_a_histogram_observation_lands_in_its_bucket(otlp: FakeCollector) -> None:
    """Verify an exponential histogram buckets a 992 s review within 10% relative width (#792)."""
    emit(REVIEW_DURATION, 992.0, {"target_type": "pr"})

    (metric,) = otlp.metrics
    exp_hist = metric["exponentialHistogram"]
    point = exp_hist["dataPoints"][0]
    scale = int(point["scale"])
    offset = int(point["positive"]["offset"])
    counts = [int(c) for c in point["positive"]["bucketCounts"]]
    nonzero_idx = next(i for i, c in enumerate(counts) if c > 0)
    base = 2.0 ** (2.0**-scale)
    low = base ** (offset + nonzero_idx)
    high = base ** (offset + nonzero_idx + 1)

    assert (
        exp_hist["aggregationTemporality"],
        int(point["count"]),
        point["sum"],
        low < 992.0 <= high,
        (high - low) / 992.0 < 0.10,
    ) == (1, 1, 992.0, True, True)


def test_ai_calls_count_requests_tokens_and_spend_by_backend(
    otlp: FakeCollector, tmp_path: Path
) -> None:
    """Verify each call counts a request, its prompt and completion tokens, and its spend, by
    serving backend; a cached reply counts as cached and costs nothing. The gateway names
    OpenAI's API base `https://api.openai.com` as the backend of an OpenAI route (#1631)."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    for cached in (False, True):
        track_request_spend(
            provider="gateway",
            model="gpt-4o",
            server="example.com:4000",
            served_by="https://api.openai.com",
            prompt_tokens=1000,
            completion_tokens=200,
            cached=cached,
            ledger=ledger,
        )

    requests = otlp.points("devops_cli_ai_requests_total")
    tokens = otlp.points("devops_cli_ai_tokens_total")
    spend = otlp.points("devops_cli_ai_spend_usd_total")

    assert (
        [(a["backend"], a["cached"], v) for a, v in requests],
        sorted((a["type"], a["local"], v) for a, v in tokens),
        (len(spend), spend[0][1] > 0, spend[0][0]["backend"]),
    ) == (
        [("api", "false", 1.0), ("api", "true", 1.0)],
        [("completion", "false", 400.0), ("prompt", "false", 2000.0)],
        (1, True, "api"),
    )


@pytest.mark.parametrize(
    ("server", "served_by", "spent", "saved"),
    [
        ("example.com:4000", "http://ollama-16gib.llm.svc.cluster.local:11434", False, True),
        ("localhost:4000", "https://api.openai.com", True, False),
        ("localhost:4000", None, False, True),
        ("example.com:4000", None, True, False),
    ],
    ids=["local-backend", "hosted-backend", "local-host", "hosted-host"],
)
def test_a_gateway_call_is_spend_or_savings_by_the_backend_that_served_it(
    otlp: FakeCollector,
    spend_ledger: SpendLedger,
    server: str,
    served_by: str | None,
    spent: bool,
    saved: bool,
) -> None:
    """Verify the backend a gateway reply names decides whether a call is spend or local
    savings, whatever host the gateway has; with no backend named, the host decides. Each
    call adds one spend point, 0 when the call ran locally (#1631), and its tokens say whether a
    local model ran them (#1672)."""
    track_request_spend(
        provider="gateway",
        model="gpt-4o",
        server=server,
        served_by=served_by,
        prompt_tokens=1000,
        completion_tokens=200,
    )

    assert (
        [v > 0 for _, v in otlp.points("devops_cli_ai_spend_usd_total")],
        {a["local"] for a, _ in otlp.points("devops_cli_ai_tokens_total")},
    ) == ([spent], {str(saved).lower()})


def test_a_call_priced_at_its_deployment_model_keeps_the_route_name_as_its_model_label(
    otlp: FakeCollector, spend_ledger: SpendLedger
) -> None:
    """Verify a hosted gateway call is priced at the deployment model that the gateway names,
    and its points keep the model that the client asked for, so the dashboards still group by
    the route name (#2031)."""
    track_request_spend(
        provider="gateway",
        model="devops-chat",
        server="example.com:4000",
        served_by="https://api.openai.com",
        served_model="openai/gpt-4o",
        prompt_tokens=1_000_000,
        completion_tokens=0,
    )

    assert (
        [(a["model"], v) for a, v in otlp.points("devops_cli_ai_spend_usd_total")],
        {a["model"] for a, _ in otlp.points("devops_cli_ai_tokens_total")},
        [a["model"] for a, _ in otlp.points("devops_cli_ai_requests_total")],
    ) == ([("devops-chat", 2.5)], {"devops-chat"}, ["devops-chat"])


def test_a_price_override_leaves_a_local_call_in_local_savings(
    otlp: FakeCollector, spend_ledger: SpendLedger
) -> None:
    """Verify a custom price for a local model or server books no spend: the call adds a spend
    point of 0, and its tokens count as local, so the dashboard prices them as savings (#1631)."""
    registry = get_pricing_registry()
    registry.set_custom_pricing("qwen3:8b", prompt_rate=1.0, completion_rate=2.0)
    registry.set_custom_pricing("localhost:11434", prompt_rate=1.0, completion_rate=2.0)

    track_request_spend(
        provider="ollama",
        model="qwen3:8b",
        server="localhost:11434",
        prompt_tokens=1000,
        completion_tokens=200,
    )

    assert (
        [v for _, v in otlp.points("devops_cli_ai_spend_usd_total")],
        sorted((a["type"], a["local"]) for a, _ in otlp.points("devops_cli_ai_tokens_total")),
    ) == ([0.0], [("completion", "true"), ("prompt", "true")])


def test_a_response_cache_hit_counts_one_cached_request_with_no_tokens_or_spend(
    otlp: FakeCollector, spend_ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a second identical chat, which the cache answers, counts as one cached request
    that adds no tokens and no spend, and writes a cached ledger row costing nothing (#816)."""
    sent: list[str] = []

    def hosted_reply(
        _self: LLMClient, system: str, _messages: list[ChatMessage], **_: Any
    ) -> LLMResponse:
        sent.append(system)
        return LLMResponse("ok", prompt_tokens=1000, completion_tokens=200, total_tokens=1200)

    monkeypatch.setattr(LLMClient, "_openai_compat_messages", hosted_reply)
    config = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1")
    client = LLMClient(config, api_key="sk-test")

    replies = [client.chat("system", "user", use_cache=True).cached for _ in range(2)]

    hit_tokens = [v for a, v in otlp.points("devops_cli_ai_tokens_total") if a["server"] == "cache"]
    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT server, cached, prompt_tokens, completion_tokens, cost_usd"
            " FROM ai_spend_records ORDER BY id"
        ).fetchall()
    assert (
        (replies, len(sent)),
        [(a["server"], a["cached"], v) for a, v in otlp.points("devops_cli_ai_requests_total")],
        sum(hit_tokens),
        [a["server"] for a, _ in otlp.points("devops_cli_ai_spend_usd_total")],
        rows[1],
    ) == (
        ([False, True], 1),
        [("example.com", "false", 1.0), ("cache", "true", 1.0)],
        0,
        ["example.com"],
        ("cache", 1, 0, 0, 0.0),
    )


def test_response_cache_lookups_and_writes_send_no_metric_of_their_own(
    otlp: FakeCollector,
) -> None:
    """Verify a cache write, hit and miss send nothing: the requests counter's `cached` label
    carries the hits, and a gauge of 1 from a short-lived process counted nothing (#816)."""
    valid_key = "llm_" + "a" * 64
    missing_key = "llm_" + "b" * 64
    cache = get_llm_response_cache()
    cache.set(valid_key, "openai", "gpt-4o", "system", "user", "reply")
    lookups = (cache.get(valid_key) is not None, cache.get(missing_key) is None)

    assert (lookups, otlp.metrics) == ((True, True), [])


def test_a_local_call_sends_its_tokens_as_local_and_no_price_of_its_own(
    otlp: FakeCollector, tmp_path: Path
) -> None:
    """Verify a local AI call sends its tokens with `local="true"` and one spend point of 0, so the
    spend series exists before the first hosted call (#1631). It sends no savings in USD: the
    dashboard prices local tokens at the reference prices of the cluster (#1672)."""
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

    tokens = otlp.points("devops_cli_ai_tokens_total")
    spend = otlp.points("devops_cli_ai_spend_usd_total")

    assert (
        sorted((a["backend"], a["provider"], a["type"], a["local"], v) for a, v in tokens),
        [(a["backend"], a["provider"], v) for a, v in spend],
        sorted({metric["name"] for metric in otlp.metrics}),
    ) == (
        [
            ("ollama-0", "ollama", "completion", "true", 200.0),
            ("ollama-0", "ollama", "prompt", "true", 1000.0),
        ],
        [("ollama-0", "ollama", 0.0)],
        [
            "devops_cli_ai_requests_total",
            "devops_cli_ai_spend_usd_total",
            "devops_cli_ai_tokens_total",
        ],
    )


def test_ai_calls_count_requests_and_tokens_by_operation(
    otlp: FakeCollector, spend_ledger: SpendLedger
) -> None:
    """Verify a chat call counts as the `chat` operation and an embedding request as the
    `embeddings` operation, with its input tokens as prompt tokens (#1623)."""
    for model, request_type, completion in (
        ("qwen3:8b", "chat_dispatch", 200),
        ("bge-m3:latest", "embedding", 0),
    ):
        track_request_spend(
            provider="gateway",
            model=model,
            server="example.com:4000",
            prompt_tokens=1000,
            completion_tokens=completion,
            request_type=request_type,
        )

    assert (
        [(a["model"], a["operation"], v) for a, v in otlp.points("devops_cli_ai_requests_total")],
        sorted(
            (a["operation"], a["type"], v) for a, v in otlp.points("devops_cli_ai_tokens_total")
        ),
    ) == (
        [("qwen3:8b", "chat", 1.0), ("bge-m3:latest", "embeddings", 1.0)],
        [
            ("chat", "completion", 200.0),
            ("chat", "prompt", 1000.0),
            ("embeddings", "completion", 0.0),
            ("embeddings", "prompt", 1000.0),
        ],
    )


def _local_call_points(otlp: FakeCollector) -> list[tuple[str, list[tuple[str, Any]], float]]:
    """The points that one local chat call and one local embedding request send."""
    for model, request_type in (("qwen3:8b", "chat"), ("bge-m3:latest", "embedding")):
        track_request_spend(
            provider="ollama",
            model=model,
            server="localhost:11434",
            prompt_tokens=1_000_000,
            completion_tokens=0 if request_type == "embedding" else 1_000,
            request_type=request_type,
        )
    points = [
        (name, sorted(attributes.items()), value)
        for name in sorted({metric["name"] for metric in otlp.metrics})
        for attributes, value in otlp.points(name)
    ]
    otlp.clear()
    return points


def test_two_processes_with_different_references_send_the_same_local_series(
    otlp: FakeCollector, spend_ledger: SpendLedger, config: Callable[..., Path]
) -> None:
    """Verify the points of a local call do not depend on `ai.reference_model` or
    `ai.reference_embedding_model`. The workstation priced its savings at gpt-4o and the Service
    at gpt-4o-mini, and the dashboard added the two; now each process sends the same tokens and
    no price, and the prices of the dashboard price them (#1672, #2194)."""
    config(ai={"reference_model": "gpt-4o", "reference_embedding_model": "text-embedding-3-large"})
    workstation = _local_call_points(otlp)
    config(
        ai={"reference_model": "gpt-4o-mini", "reference_embedding_model": "text-embedding-3-small"}
    )
    service = _local_call_points(otlp)

    assert (len(workstation) > 0, workstation) == (True, service)


def test_a_review_sends_its_duration_and_findings_by_persona_severity_and_status(
    otlp: FakeCollector,
) -> None:
    """Verify findings are counted once per persona, severity and status, and failed personas
    contribute none."""
    persona = PersonaDefinition(
        name="devsecops", title="DevSecOps", system_prompt="", chat_prompt=""
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
        otlp.points("devops_cli_review_duration_seconds"),
        sorted(
            (a["severity"], a["status"], v) for a, v in otlp.points("devops_cli_findings_total")
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
        ("http://ollama-16gib.llm.svc.cluster.local:11434", "ollama-16gib"),
        ("ollama-0.ollama:11434", "ollama-0"),
        (None, ""),
    ],
)
def test_backends_are_named_by_their_hosts_first_label(served_by: str | None, name: str) -> None:
    """Verify a backend URL, or a bare host and port, is shortened to its host's first label."""
    assert backend_name(served_by) == name


def test_gauges_are_recorded_as_instantaneous_values(otlp: FakeCollector) -> None:
    """Verify gauge metrics emit instantaneous point-in-time values rather than accumulating deltas."""
    emit(PROJECT_ITEMS, 120.0, attributes={"milestone": "2026-11", "state": "closed"})
    tracer_module.get_tracer().flush()
    emit(PROJECT_ITEMS, 115.0, attributes={"milestone": "2026-11", "state": "closed"})
    emit(PROJECT_ITEMS, 125.0, attributes={"milestone": "2026-11", "state": "closed"})

    points = otlp.points("devops_cli_project_items")
    metric_entry = otlp.metrics[0]

    assert (
        "gauge" in metric_entry,
        PROJECT_ITEMS.kind is InstrumentKind.GAUGE,
        UPSTREAM_SERVICE_STATUS.kind is InstrumentKind.GAUGE,
        [(p[0]["milestone"], p[0]["state"], p[1]) for p in points],
    ) == (
        True,
        True,
        True,
        [("2026-11", "closed", 120.0), ("2026-11", "closed", 125.0)],
    )


def test_cluster_jobs_export_created_timestamps_and_prometheus_ingests_zeroes() -> None:
    """The collector transmits created timestamps via remote write 2.0 and Prometheus ingests zero samples at start time (#2039, #2506)."""
    otel_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "otel" / "values.yaml").read_text(encoding="utf-8")
    )
    prom_remote_write = otel_values["config"]["exporters"]["prometheus_remote_write"]

    prom_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "monitoring" / "prometheus-values.yaml").read_text(encoding="utf-8")
    )
    extra_args = prom_values["server"]["extraArgs"]

    assert "export_created_metric" not in prom_remote_write
    assert prom_remote_write.get("remote_write_version") == 2
    assert extra_args.get("enable-feature") == "created-timestamp-zero-ingestion"


def test_two_job_runs_add_up_in_the_increase_query_the_dashboards_use() -> None:
    """Two cluster Job runs that each export once add up in PromQL increase() when start times are ingested (#2039)."""

    def evaluate_promql_increase(series_points: dict[str, list[tuple[float, float]]]) -> float:
        total = 0.0
        for points in series_points.values():
            if len(points) < 2:
                continue
            total += points[-1][1] - points[0][1]
        return total

    job_1_start, job_1_end, job_1_requests = 100.0, 120.0, 2.0
    job_2_start, job_2_end, job_2_requests = 130.0, 150.0, 3.0

    series_without_created = {
        "job-1": [(job_1_end, job_1_requests)],
        "job-2": [(job_2_end, job_2_requests)],
    }
    assert evaluate_promql_increase(series_without_created) == 0.0

    series_with_created = {
        "job-1": [(job_1_start, 0.0), (job_1_end, job_1_requests)],
        "job-2": [(job_2_start, 0.0), (job_2_end, job_2_requests)],
    }
    assert evaluate_promql_increase(series_with_created) == job_1_requests + job_2_requests
