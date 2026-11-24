"""Review, findings and AI spend metrics reach Prometheus (#564).

The dashboards queried review and findings metrics nothing emitted, and AI spend metrics that
only `devops server` exposed, which nothing scraped. Every metric was also sent as a gauge from a
short-lived process, so counters and histograms could not accumulate. Counters and histograms are
now deltas that the collector adds up.
"""

from __future__ import annotations

import ast
import contextlib
import functools
import json
import re
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from devops_cli.ai.client import LLMClient, LLMResponse
from devops_cli.ai.response_cache import get_llm_response_cache
from devops_cli.ai.review.runner import record_review_metrics
from devops_cli.ai.review_schema import Finding, ReviewResult
from devops_cli.ai.spend.ledger import SpendLedger, track_request_spend
from devops_cli.ai.spend.pricing import get_pricing_registry
from devops_cli.config.constants import (
    CONST_SERVICE_METRIC_BUDGET_HOLDS,
    CONST_SERVICE_METRIC_BUDGET_LIMIT,
    CONST_SERVICE_METRIC_BUDGET_SPENT,
    CONST_SERVICE_METRIC_CHAT_COMMANDS,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED,
    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
    CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
    CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
    CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
    CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS,
    CONST_SERVICE_METRIC_JOB_SECONDS,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_QUEUE_DEPTH,
    CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED,
    CONST_SERVICE_METRIC_STAGE_JOBS,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
)
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import instruments as instruments_module
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
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.otlp import FakeCollector, plain_attributes
from tests.support.paths import REPO_ROOT
from tests.support.trees import ParsedTreeMap, tree_guard
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

# The product dashboards of devops-cli (#5292), and the dashboards of the environment.
DASHBOARDS = REPO_ROOT / "k8s" / "devops" / "dashboards"
ENVIRONMENT_DASHBOARDS = REPO_ROOT / "k8s" / "monitoring" / "dashboards"
SERIES_NAME = re.compile(r"devops_cli_[a-z0-9_]+")
REGISTRY_COUNTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("table", "INSTRUMENTS", "src/devops_cli/telemetry/instruments.py"),
    ("prefix", "devops_cli_", "src/devops_cli/telemetry/instruments.py"),
)
# The series of the Service, which Prometheus scrapes from its /metrics route (#2479). The label set
# of the identity counter starts with the first refusal, so increase() loses that count. Its panel
# reads the value, as its alert does, so the test takes it as a gauge.
SERVICE_SERIES: dict[str, InstrumentKind] = {
    CONST_SERVICE_METRIC_BUDGET_HOLDS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_BUDGET_LIMIT: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_BUDGET_SPENT: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_CHAT_COMMANDS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_IDENTITY_REFUSED: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_IMPLEMENT_JOBS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_IMPLEMENT_TOKENS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_JOB_SECONDS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_JOB_START_TIMESTAMP: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_JOB_SUSPENDED: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_JOBS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_QUEUE_DEPTH: InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_STAGE_JOBS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS: InstrumentKind.COUNTER,
    "devops_cli_service_state_unkept": InstrumentKind.GAUGE,
    CONST_SERVICE_METRIC_TRIGGERS: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES: InstrumentKind.COUNTER,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES: InstrumentKind.GAUGE,
}
SENT_SERIES = {instrument.name for instrument in INSTRUMENTS} | set(SERVICE_SERIES)


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
    {
        "ai-spend.json",
        "devops-ai-rag.json",
        "devops-cli.json",
        "project-metrics.json",
        "roadmap-service-telemetry.json",
    }
)


def _devops_cli_dashboards() -> list[Path]:
    """The shipped dashboards dedicated to devops-cli metrics: each one of the product folder."""
    return [
        dashboard
        for dashboard in sorted(DASHBOARDS.glob("*.json"))
        if dashboard.name in _PURE_DEVOPS_CLI_DASHBOARDS
    ]


def _all_queries() -> list[str]:
    """Every query in the devops-cli dashboards."""
    return [query for dashboard in _devops_cli_dashboards() for query in _queries(dashboard)]


# The AI spend dashboard also reads the gateway's request and token series, which count every
# caller's calls (#1668).
_GATEWAY_SERIES_DASHBOARDS: frozenset[str] = frozenset({"ai-spend.json"})
GATEWAY_SERIES_NAME = re.compile(r"\blitellm_[a-z0-9_]+")
# A reference line, such as a limit, is a constant query (docs/DESIGN.md C14).
REFERENCE_LINE = re.compile(r"vector\(\s*[0-9.]+\s*\)")


@pytest.mark.parametrize("dashboard", _devops_cli_dashboards(), ids=lambda path: path.name)
def test_every_dashboard_query_names_a_metric_devops_cli_sends(dashboard: Path) -> None:
    """Verify each query reads a counter or histogram series devops-cli sends over OTLP, a series
    that the Service gives on its /metrics route, or, on the AI spend dashboard, a series of the
    gateway. A constant reference line, such as a limit, reads no series."""
    queries = _queries(dashboard)
    reads_gateway = dashboard.name in _GATEWAY_SERIES_DASHBOARDS

    unsent = {name for query in queries for name in SERIES_NAME.findall(query)} - SENT_SERIES
    unnamed = [
        q
        for q in queries
        if not SERIES_NAME.search(q)
        and not REFERENCE_LINE.fullmatch(q.strip())
        and not (reads_gateway and GATEWAY_SERIES_NAME.search(q))
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
} | SERVICE_SERIES


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
    for dashboard in sorted([*DASHBOARDS.glob("*.json"), *ENVIRONMENT_DASHBOARDS.glob("*.json")]):
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


@functools.cache
def _gauge_name_tables() -> tuple[dict[str, str], dict[str, Any]]:
    """The string constants of `config/constants.py` and the names of the instruments module,
    which a gauge call can name its gauge by. Each module of `src/` reads the same tables."""
    import devops_cli.telemetry.instruments as inst_mod
    from devops_cli.config import constants

    const_dict = {
        name: getattr(constants, name)
        for name in dir(constants)
        if isinstance(getattr(constants, name), str)
    }
    return const_dict, {name: getattr(inst_mod, name) for name in dir(inst_mod)}


def _scraped_gauge_names_in_tree(tree: ast.AST) -> set[str]:
    """Return gauge names that an AST records into an in-memory registry or exposes via Prometheus."""
    const_dict, inst_dict = _gauge_name_tables()
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


def _all_scraped_gauge_names(trees: ParsedTreeMap) -> set[str]:
    """All gauge names recorded into in-memory registries or exposed via Prometheus in src/devops_cli."""
    gauges: set[str] = set()
    for tree in trees.values():
        gauges |= _scraped_gauge_names_in_tree(tree)
    return gauges


def test_no_gauge_reaches_prometheus_through_two_paths(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """Each gauge reaches Prometheus through one path (#2288). A check fails when two paths send the same gauge name."""
    tree_guard(parsed_source_trees)
    otlp_gauges = {
        instrument.name for instrument in INSTRUMENTS if instrument.kind is InstrumentKind.GAUGE
    }
    scraped_gauges = _all_scraped_gauge_names(parsed_source_trees)
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


def test_every_metric_is_a_declared_instrument_sent_through_emit(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """Verify no module but the instruments module writes a metric by its name, and every
    `emit()` sends a declared instrument (#817).

    A metric sent by name skips the kind that `INSTRUMENTS` gives it: a count sent as a gauge
    keeps only the last process's value.
    """
    instruments_module = SRC / "telemetry" / "instruments.py"
    found = [
        call
        for path, tree in sorted(parsed_source_trees.items())
        if path != instruments_module
        for call in _metric_writes_outside_emit(tree, str(path.relative_to(SRC)))
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


_RESOURCE_LABELS = frozenset({"job", "instance"})
"""The labels that the resource of a process sets: the collector overwrites a data point
attribute with either name, with no log (#3240)."""


def _emit_attributes(call: ast.Call) -> ast.expr | None:
    """The attributes argument of a call, by position or by keyword, or None."""
    if len(call.args) > 2:
        return call.args[2]
    return next((keyword.value for keyword in call.keywords if keyword.arg == "attributes"), None)


def _attribute_keys(
    node: ast.expr | None,
    assigned: dict[str, list[ast.expr]],
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    """The constant keys of the attributes of an `emit()` call: a dict display, the dict displays
    that a name holds anywhere in the module, and each dict that `**` unpacks."""
    if isinstance(node, ast.Dict):
        keys: set[str] = set()
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                keys |= _attribute_keys(value, assigned, seen)
            elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
        return keys
    if isinstance(node, ast.Name) and node.id not in seen:
        return {
            key
            for value in assigned.get(node.id, [])
            for key in _attribute_keys(value, assigned, seen | {node.id})
        }
    return set()


def _emits_with_a_resource_label(tree: ast.AST, label: str) -> list[str]:
    """Each `emit()` call of a module, as `<label>:<line>`, whose attributes have the key `job` or
    `instance`: in a dict display, in a name that holds one, or in a dict that `**` unpacks."""
    emit_names, _ = _declared_instrument_imports(tree)
    if not emit_names:
        return []
    assigned: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name):
            assigned.setdefault(target.id, []).append(value)
    named = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in emit_names
        and _attribute_keys(_emit_attributes(node), assigned) & _RESOURCE_LABELS
    ]
    return [f"{label}:{line}" for line in sorted(named)]


def test_no_emit_sends_an_attribute_that_the_resource_sets(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """Verify no `emit()` call under `src/devops_cli/` sends the attribute `job` or `instance`
    (#3240). The collector sets both labels from the resource after it copies the attributes, so
    such an attribute never reaches Prometheus. The job row is the `row` label."""
    found = [
        call
        for path, tree in sorted(parsed_source_trees.items())
        for call in _emits_with_a_resource_label(tree, str(path.relative_to(SRC)))
    ]
    assert found == []


def test_the_resource_label_check_names_a_job_attribute_in_each_form_and_passes_a_row_attribute() -> (
    None
):
    module = (
        "from devops_cli.telemetry.instruments import COMMAND_TOTAL, emit\n"
        'emit(COMMAND_TOTAL, 1.0, {"job": "stage"})\n'
        'emit(COMMAND_TOTAL, 1.0, {"row": "stage"})\n'
        'emit(COMMAND_TOTAL, 1.0, attributes={"instance": "a", "row": "stage"})\n'
        "emit(COMMAND_TOTAL, 1.0)\n"
        'labels = {"job": "stage"}\n'
        "emit(COMMAND_TOTAL, 1.0, labels)\n"
        'emit(COMMAND_TOTAL, 1.0, {**labels, "x": 1})\n'
        'row = {"row": "stage"}\n'
        'emit(COMMAND_TOTAL, 1.0, {**row, "x": 1})\n'
        "emit(COMMAND_TOTAL, 1.0, row)\n"
    )

    assert _emits_with_a_resource_label(ast.parse(module), "example.py") == [
        "example.py:2",
        "example.py:4",
        "example.py:7",
        "example.py:8",
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


def test_each_project_instrument_names_the_repo_label() -> None:
    """Each project gauge carries the repository of its report as `repo`, so the description
    that the dashboards read names it, and the items gauge also names its own labels (#4690)."""
    project = [i for i in INSTRUMENTS if i.name.startswith("devops_cli_project_")]
    unnamed = [i.name for i in project if not re.search(r"\brepo\b", i.description)]
    items_labels = [
        label for label in PROJECT_ITEM_LABELS if label not in PROJECT_ITEMS.description
    ]

    assert (len(project), unnamed, items_labels) == (14, [], [])


ROADMAP_AGE_GAUGE_NAMES = (
    "devops_cli_roadmap_item_age_seconds",
    "devops_cli_roadmap_oldest_item_number",
    "devops_cli_roadmap_claim_age_seconds",
)


def test_the_roadmap_age_gauges_are_declared_gauges_with_their_units_and_labels() -> None:
    """The gauges of the age of the oldest roadmap item, of its number and of the oldest claim
    (#2919, #5495) are gauges in INSTRUMENTS. The item age and the claim age carry the unit `s`. The
    item gauges take the labels `repo` and `phase`, and their descriptions name them."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    assert [name for name in ROADMAP_AGE_GAUGE_NAMES if name not in declared] == []

    item_age, oldest_item, claim_age = (declared[name] for name in ROADMAP_AGE_GAUGE_NAMES)
    assert [item_age.kind, oldest_item.kind, claim_age.kind] == [InstrumentKind.GAUGE] * 3
    assert [item_age.unit, oldest_item.unit, claim_age.unit] == ["s", "1", "s"]
    labels = tuple(getattr(instruments_module, "ROADMAP_AGE_LABELS", ()))
    assert labels == ("repo", "phase")
    items_gauge = declared["devops_cli_roadmap_items"]
    stalled_gauge = declared["devops_cli_roadmap_stalled_items"]
    assert [items_gauge.kind, stalled_gauge.kind] == [InstrumentKind.GAUGE, InstrumentKind.GAUGE]
    assert [items_gauge.unit, stalled_gauge.unit] == ["1", "1"]
    assert all(
        label in gauge.description
        for gauge in (item_age, oldest_item, items_gauge, stalled_gauge)
        for label in labels
    )


INBOX_GAUGE_NAME = "devops_cli_roadmap_inbox_items"


def test_the_inbox_gauge_is_a_declared_instrument() -> None:
    """The count of the inbox lines of each kind is a gauge of unit `1` (#2968), labelled by the
    repository and the kind. One repository adds one series for each of its eight counted kinds,
    so seven repositories stay at 56 series."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    assert INBOX_GAUGE_NAME in declared

    inbox = declared[INBOX_GAUGE_NAME]
    assert (inbox.kind, inbox.unit) == (InstrumentKind.GAUGE, "1")
    assert all(label in inbox.description for label in ("repo", "kind"))
    assert "56 series" in inbox.description


PERSON_CAUSE_INSTRUMENT_NAMES = (
    "devops_cli_roadmap_person_cause_inflow_total",
    "devops_cli_roadmap_person_cause_outflow_total",
    "devops_cli_roadmap_person_cause_age_seconds",
)


def test_person_cause_instruments_are_declared() -> None:
    """Person cause telemetry (#2968): a counter of the items that a typed person cause added, a
    counter of the items it closed, and a gauge of the age of the oldest item it holds, each by
    repository and cause."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    assert [name for name in PERSON_CAUSE_INSTRUMENT_NAMES if name not in declared] == []

    inflow, outflow, age = (declared[name] for name in PERSON_CAUSE_INSTRUMENT_NAMES)
    assert [inflow.kind, outflow.kind, age.kind] == [
        InstrumentKind.COUNTER,
        InstrumentKind.COUNTER,
        InstrumentKind.GAUGE,
    ]
    assert [inflow.unit, outflow.unit, age.unit] == ["1", "1", "s"]
    assert all(
        label in instrument.description
        for instrument in (inflow, outflow, age)
        for label in ("repo", "cause")
    )


def test_the_alternatives_coverage_instruments_are_declared_with_their_kinds_and_units() -> None:
    """The check of open items for an open tool shows its coverage (#2950): two gauges, the open
    items with no check and the age of the oldest check, and a histogram of the searches of each
    written check."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    expected = {
        "devops_cli_roadmap_alternatives_unchecked_items": (InstrumentKind.GAUGE, "1"),
        "devops_cli_roadmap_alternatives_oldest_check_age_seconds": (InstrumentKind.GAUGE, "s"),
        "devops_cli_roadmap_alternatives_searches": (InstrumentKind.HISTOGRAM, "1"),
    }

    assert {
        name: (declared[name].kind, declared[name].unit) for name in expected if name in declared
    } == expected


def test_the_roadmap_tool_instruments_are_declared_with_their_kinds_and_units() -> None:
    """The five instruments of the tool calls of the stage planner (#3240, #3241): three counters,
    and two histograms that count characters and calls."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    expected = {
        "devops_cli_roadmap_tool_calls_total": (InstrumentKind.COUNTER, "1"),
        "devops_cli_roadmap_tool_limit_hits_total": (InstrumentKind.COUNTER, "1"),
        "devops_cli_roadmap_tool_cuts_total": (InstrumentKind.COUNTER, "1"),
        "devops_cli_roadmap_tool_answer_chars": (InstrumentKind.HISTOGRAM, "{char}"),
        "devops_cli_roadmap_tool_calls_per_run": (InstrumentKind.HISTOGRAM, "{call}"),
    }

    assert {
        name: (declared[name].kind, declared[name].unit) for name in expected if name in declared
    } == expected


def test_the_gate_slot_histogram_description_names_no_command() -> None:
    """The gate-slot histogram description names no command (#5451)."""
    from devops_cli.telemetry.instruments import CI_GATE_SLOT_WAIT

    assert (
        CI_GATE_SLOT_WAIT.description
        == "Time a gate run waited for a free gate slot before its checks started"
    )


def test_the_telemetry_document_lists_each_roadmap_tool_instrument_with_its_kind_and_unit() -> None:
    document = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    rows = [
        f"| `{instrument.name}` | {instrument.kind.value.title()} | `{instrument.unit}` |"
        for instrument in INSTRUMENTS
        if instrument.name.startswith("devops_cli_roadmap_tool_")
    ]
    assert (len(rows), [row for row in rows if row not in document]) == (5, [])


DECISION_POINT_INSTRUMENT_NAMES = (
    "devops_cli_decision_point_duration_seconds",
    "devops_cli_decision_point_failed_total",
)


def test_the_decision_point_duration_and_failed_instruments_are_declared() -> None:
    """The chain times each decision and counts each failed request (#5272): a histogram of the
    duration by point and resolver, and a counter of the failures by point and class. Both are
    declared, both are listed in the telemetry document, and each states the bound of its series."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    assert [name for name in DECISION_POINT_INSTRUMENT_NAMES if name not in declared] == []

    duration, failed = (declared[name] for name in DECISION_POINT_INSTRUMENT_NAMES)
    assert (duration.kind, duration.unit) == (InstrumentKind.HISTOGRAM, "s")
    assert (failed.kind, failed.unit) == (InstrumentKind.COUNTER, "1")
    assert all(label in duration.description for label in ("point", "resolver"))
    assert all(label in failed.description for label in ("point", "error"))
    assert "3 series" in duration.description
    assert "7 series" in failed.description

    document = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")
    rows = [
        f"| `{instrument.name}` | {instrument.kind.value.title()} | `{instrument.unit}` |"
        for instrument in (duration, failed)
    ]
    assert [row for row in rows if row not in document] == []


def test_the_brain_cache_counter_names_the_row_and_the_result() -> None:
    """The brain cache counter names the row and the result (#6013)."""
    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    assert "devops_cli_brain_cache_total" in declared
    counter = declared["devops_cli_brain_cache_total"]
    assert (counter.kind, counter.unit) == (InstrumentKind.COUNTER, "1")
    assert "row" in counter.description
    assert "result" in counter.description
    assert "hit" in counter.description
    assert "miss" in counter.description


def test_counters_are_monotonic_deltas_from_the_workload_not_the_process(
    otlp: FakeCollector, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a counter is a delta sum whose resource names the workload and no process, so the
    collector adds up every command's deltas into one series per workload. The instance comes
    from the standard variable, and the metric Resource holds no `host.name`, which is the pod
    name and would split the stream (#4697)."""
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "service.instance.id=devops-cli-job")
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
        "host.name" in resource,
        resource["service.instance.id"],
        int(point["startTimeUnixNano"]) < int(point["timeUnixNano"]),
    ) == ((1, True), False, False, "devops-cli-job", True)


def test_flushes_from_two_threads_send_their_deltas_in_the_order_they_collected_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The collector's `delta_to_cumulative` drops a delta that is not later than the last delta it
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


def test_a_piped_command_still_emits_its_subcommand_duration(
    cli: Callable[..., Any], otlp: FakeCollector, keyring_store: FakeKeyring
) -> None:
    """Verify a command whose stderr is the runner's pipe still sends its sub-command duration
    (#5448). The terminal guard of the printed elapsed line removes no measurement."""
    result = cli("config", "show", "--format", "json")

    (metric,) = [
        metric
        for metric in otlp.metrics
        if metric["name"] == "devops_cli_subcommand_duration_seconds"
    ]
    (point,) = metric["exponentialHistogram"]["dataPoints"]
    assert (result.exit_code, plain_attributes(point["attributes"])) == (
        0,
        {"command": "config", "sub_command": "config show", "status": "ok"},
    )


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
        ("localhost:4000", "http://10.0.0.1:8000", True, False),
        ("localhost:4000", "http://cloud.internal:8000", True, False),
        ("localhost:4000", None, True, False),
        ("example.com:4000", None, True, False),
    ],
    ids=[
        "local-backend",
        "hosted-backend",
        "vpc-private-ip-backend",
        "internal-dns-backend",
        "local-host-unrouted",
        "hosted-host-unrouted",
    ],
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
    savings. All traffic routed to a *.local api_base counts as local savings. All requests
    not routed to a *.local api_base count as spend (#1631). Each call adds one spend point,
    0 when the call ran locally (#1631), and its tokens say whether a local model ran them (#1672)."""
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


def test_a_local_gateway_call_with_no_backend_named_is_local_savings(
    otlp: FakeCollector, spend_ledger: SpendLedger
) -> None:
    """Verify an unrouted gateway call for a local model counts as local savings (#1631)."""
    track_request_spend(
        provider="gateway",
        model="local/devops-chat",
        server="localhost:4000",
        served_by=None,
        prompt_tokens=1000,
        completion_tokens=200,
    )

    assert (
        [v > 0 for _, v in otlp.points("devops_cli_ai_spend_usd_total")],
        {a["local"] for a, _ in otlp.points("devops_cli_ai_tokens_total")},
    ) == ([False], {"true"})


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
        served_by="http://ollama-0.ollama.llm.svc.cluster.local:11434",
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


def test_a_review_sends_its_duration_and_findings_by_severity_and_status(
    otlp: FakeCollector,
) -> None:
    """Verify findings are counted once per severity and status, and a result that is not a
    ReviewResult adds none."""
    findings = [
        Finding(severity="high", title="a", location="x:1", status="VERIFIED"),
        Finding(severity="HIGH", title="b", location="x:2", status="VERIFIED"),
        Finding(severity="LOW", title="c", location="x:3", status="INVALIDATED"),
    ]
    results: list[ReviewResult | str] = [ReviewResult(findings=findings), "a raw reply"]

    record_review_metrics(results, 312.5, "path")

    assert (
        otlp.points("devops_cli_review_duration_seconds"),
        sorted(
            (a["severity"], a["status"], v) for a, v in otlp.points("devops_cli_findings_total")
        ),
    ) == (
        [({"target_type": "path"}, 312.5)],
        [("HIGH", "VERIFIED", 2.0), ("LOW", "INVALIDATED", 1.0)],
    )


def test_the_collector_deletes_the_host_name_of_devops_cli_metrics_before_it_adds_them_up(
    otlp: FakeCollector,
) -> None:
    """A devops-cli build from before #4697 sends `host.name` in its metric Resource, and a new
    build does not. `delta_to_cumulative` keys a stream by every resource attribute, while
    Prometheus keeps only `job` and `instance`, so the two builds of one workload write two
    running totals into one series (#5338). A transform processor before `delta_to_cumulative`
    deletes `host.name` where `telemetry.sdk.name` is the SDK name that the tracer sends, so
    every build sends one stream and the Resource of another SDK stays as it is."""
    tracer_module.get_tracer().increment_counter("devops_cli_command_total", 1, attributes={})
    resource = {
        a["key"]: a["value"]["stringValue"]
        for a in otlp.payloads(OtlpSignal.METRICS)[0]["resourceMetrics"][0]["resource"][
            "attributes"
        ]
    }
    config = yaml.safe_load(
        (REPO_ROOT / "k8s" / "otel" / "values.yaml").read_text(encoding="utf-8")
    )["config"]
    processors = config["service"]["pipelines"]["metrics"]["processors"]
    sdk_condition = (
        f'resource.attributes["telemetry.sdk.name"] == "{resource["telemetry.sdk.name"]}"'
    )

    assert (
        processors[: processors.index("delta_to_cumulative")],
        config["processors"].get("transform/metric_resource"),
    ) == (
        ["memory_limiter", "transform/metric_resource"],
        {
            "error_mode": "ignore",
            "metric_statements": [
                {
                    "context": "resource",
                    "statements": [
                        f'delete_key(resource.attributes, "host.name") where {sdk_condition}'
                    ],
                }
            ],
        },
    )


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
