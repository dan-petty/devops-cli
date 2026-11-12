"""The Grafana sidecar provisions the shipped dashboards from generated ConfigMaps (#692).

Only the four Kubernetes views reached the sidecar, through hand-copied ConfigMaps that nothing
applied, and devops-cli's own dashboards reached Grafana only through `grafana dashboards sync`.
A `configMapGenerator` now builds the ConfigMaps from the dashboard files, and the root
kustomization that `devops k8s deploy-stack` applies includes it. These tests read the
kustomizations in Python; they never run kustomize or kubectl.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import genai_prices
import pytest
import yaml
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GenAiOperationNameValues,
)

from devops_cli.config.defaults import (
    DEFAULT_AI_REFERENCE_EMBEDDING_MODEL,
    DEFAULT_AI_REFERENCE_MODEL,
    DEFAULT_AI_REFERENCE_PROVIDER,
)
from devops_cli.prometheus.promql import falls_back_to_constant, grouping_labels, selectors
from tests.support.paths import FIXTURES, REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
MONITORING_DIR = K8S_DIR / "monitoring"
DASHBOARDS_DIR = MONITORING_DIR / "dashboards"

# Today's ConfigMap names and groupings, so a re-apply updates them in place.
PROVISIONED = {
    "grafana-k8s-global-dashboards": ["k8s-views-global.json", "k8s-views-pods.json"],
    "grafana-k8s-node-dashboards": ["k8s-views-nodes.json", "k8s-views-namespaces.json"],
    "grafana-devops-cli-dashboards": ["devops-cli.json", "ai-spend.json", "project-metrics.json"],
    "grafana-stack-dashboards": [
        "sre-service.json",
        "ingress-tunnel.json",
        "llm-stack.json",
        "otel-collector.json",
        "prometheus-server.json",
        "pyroscope.json",
        "nvidia-dcgm.json",
        "coredns.json",
    ],
    # The upstream CloudNativePG dashboard (#4994) fills most of one ConfigMap alone.
    "grafana-database-dashboards": ["cloudnative-pg.json"],
}
# All dashboards are now provisioned via sidecar ConfigMaps.
SYNC_ONLY: set[str] = set()
SIDECAR_LABELS = {
    "grafana_dashboard": "1",
    "app.kubernetes.io/name": "grafana",
    "app.kubernetes.io/part-of": "devops-cli-stack",
}
# kubectl's client-side apply stores the object in an annotation, and annotations are capped.
LAST_APPLIED_ANNOTATION_LIMIT_BYTES = 262_144
# The dashboard constant that holds the hosted price of a local token, as a PromQL vector by
# operation and token type, and the part of each savings query that multiplies local tokens by
# it (#2194). Grafana puts the value in unchanged (`:raw`), so its quotes are not escaped.
PRICE_VARIABLE = "reference_price_usd_per_token"
PRICED = f"* on (operation, type) group_left () (${{{PRICE_VARIABLE}:raw}})"
# One price of the vector, written as USD per million tokens of one operation and token type.
PRICE_TERM = re.compile(
    r'label_replace\(label_replace\(vector\(([0-9.]+) / 1e6\), "operation", "(\w+)", "", ""\), '
    r'"type", "(\w+)", "", ""\)'
)
# The local tokens: a series that says so, or a series from before the `local` label (#1672) that
# the gateway served, because the gateway serves only local models. Chat is every operation but
# embeddings, so a series from before the `operation` label (#1623) is chat.
LOCAL_TOKEN_SELECTORS = tuple(
    f"devops_cli_ai_tokens_total{{{local}, {operation}}}"
    for operation in ('operation!="embeddings"', 'operation="embeddings"')
    for local in ('local="true"', 'local="", provider="gateway", server!="cache"')
)
SAVINGS_RECORD = FIXTURES / "recorded_queries" / "ai_spend_local_savings.yaml"
SAVINGS_IN_RANGE = "Local Cloud Savings in Range"


def _kustomization(directory: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (directory / "kustomization.yaml").read_text(encoding="utf-8")
    )
    return loaded


def _generator_options(kustomization: dict[str, Any], generator: dict[str, Any]) -> dict[str, Any]:
    """A generator's options: the kustomization's `generatorOptions`, then its own."""
    shared = kustomization.get("generatorOptions", {})
    own = generator.get("options", {})
    return {
        **shared,
        **own,
        "labels": {**shared.get("labels", {}), **own.get("labels", {})},
    }


def _configmap(kustomization: dict[str, Any], generator: dict[str, Any]) -> dict[str, Any]:
    """The ConfigMap one generator produces, built as kustomize builds it."""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": generator["name"],
            "namespace": kustomization.get("namespace", generator.get("namespace")),
            "labels": _generator_options(kustomization, generator)["labels"],
        },
        "data": {
            name: (DASHBOARDS_DIR / name).read_text(encoding="utf-8") for name in generator["files"]
        },
    }


def _generated_configmaps() -> list[dict[str, Any]]:
    """The ConfigMaps the dashboards generator produces."""
    kustomization = _kustomization(DASHBOARDS_DIR)
    return [
        _configmap(kustomization, generator) for generator in kustomization["configMapGenerator"]
    ]


def _hashed_names() -> list[bool]:
    """Whether kustomize appends a content hash to each generated ConfigMap's name."""
    kustomization = _kustomization(DASHBOARDS_DIR)
    return [
        _generator_options(kustomization, generator).get("disableNameSuffixHash") is not True
        for generator in kustomization["configMapGenerator"]
    ]


def test_the_generator_provisions_all_dashboards_under_todays_configmap_names() -> None:
    """Verify unhashed ConfigMaps in `monitoring` carry all dashboard files and sidecar labels."""
    configmaps = _generated_configmaps()

    assert (
        {cm["metadata"]["name"]: sorted(cm["data"]) for cm in configmaps},
        [cm["metadata"]["namespace"] for cm in configmaps],
        [cm["metadata"]["labels"] for cm in configmaps],
        _hashed_names(),
    ) == (
        {name: sorted(files) for name, files in PROVISIONED.items()},
        ["monitoring"] * len(PROVISIONED),
        [SIDECAR_LABELS] * len(PROVISIONED),
        [False] * len(PROVISIONED),
    )


def test_every_other_dashboard_is_left_to_sync_by_name() -> None:
    """Verify a dashboard added to the directory cannot be left out of the generator unnoticed."""
    generated = {name for cm in _generated_configmaps() for name in cm["data"]}
    shipped = {path.name for path in DASHBOARDS_DIR.glob("*.json")}

    assert sorted(shipped - generated - SYNC_ONLY) == []


def test_each_configmap_fits_kubectls_last_applied_annotation() -> None:
    """Verify each ConfigMap, as compact JSON, stays under the 262,144-byte annotation limit.

    `kubectl apply` stores the whole object in its last-applied annotation, and an object past
    the limit fails to apply; the Kubernetes views were split into two ConfigMaps for it.
    """
    sizes = {
        cm["metadata"]["name"]: len(json.dumps(cm, separators=(",", ":")).encode("utf-8"))
        for cm in _generated_configmaps()
    }
    assert [
        name for name, size in sizes.items() if size >= LAST_APPLIED_ANNOTATION_LIMIT_BYTES
    ] == []


def test_the_monitoring_kustomization_takes_its_dashboards_from_the_generator() -> None:
    """Verify `k8s/monitoring` lists the generator and every resource it lists exists."""
    resources = _kustomization(MONITORING_DIR)["resources"]

    assert (
        "dashboards" in resources,
        [resource for resource in resources if not (MONITORING_DIR / resource).exists()],
    ) == (True, [])


def test_root_kustomization_leaves_dashboards_to_monitoring_stack() -> None:
    """Verify `k8s/kustomization.yaml` avoids duplicate dashboard ownership with `k8s/monitoring`.

    Argo CD's `monitoring` application owns `dashboards` in namespace `monitoring`. Listing
    dashboards in the root kustomization causes a SharedResourceWarning conflict loop with `base`.
    """
    resources = _kustomization(K8S_DIR)["resources"]

    assert "monitoring/dashboards" not in resources


def _multi_value_variables(dashboard: dict[str, Any]) -> set[str]:
    """The names of a dashboard's template variables that can hold more than one value."""
    return {
        variable["name"]
        for variable in dashboard.get("templating", {}).get("list", [])
        if variable.get("multi") or variable.get("includeAll")
    }


def _expressions(node: Any) -> list[str]:
    """Every query expression in a dashboard: `expr` for Prometheus and Loki targets."""
    if isinstance(node, dict):
        own = [node["expr"]] if isinstance(node.get("expr"), str) else []
        return own + [expr for value in node.values() for expr in _expressions(value)]
    if isinstance(node, list):
        return [expr for value in node for expr in _expressions(value)]
    return []


def test_no_query_matches_a_multi_value_variable_exactly() -> None:
    """A variable that holds All or several values expands to a regular expression, so an exact
    `label="$var"` matcher finds nothing. The Pods view matched `pod="$pod"` against such a
    variable, and nine of its panels were empty (#1955)."""
    exact = {
        (path.name, variable)
        for path in sorted(DASHBOARDS_DIR.glob("*.json"))
        for dashboard in [json.loads(path.read_text(encoding="utf-8"))]
        for variable in _multi_value_variables(dashboard)
        for expr in _expressions(dashboard)
        if f'="${variable}"' in expr or f'="${{{variable}}}"' in expr
    }
    assert exact == set()


def test_no_query_selects_the_container_series_the_chart_drops() -> None:
    """k8s-monitoring drops every cAdvisor CPU, memory, filesystem, network and pressure series
    with an empty `image` label (`clusterMetrics.cadvisor.metricsTuning.dropEmptyImageLabels`,
    on by default), so a panel that selects `image=""` is always empty. Two Nodes panels did
    (#1955)."""
    values = yaml.safe_load((MONITORING_DIR / "k8s-monitoring-values.yaml").read_text("utf-8"))
    tuning = values["clusterMetrics"]["cadvisor"].get("metricsTuning", {})
    selecting = sorted(
        path.name
        for path in DASHBOARDS_DIR.glob("*.json")
        if any('image=""' in expr for expr in _expressions(json.loads(path.read_text("utf-8"))))
    )
    assert (tuning.get("dropEmptyImageLabels", True), selecting) == (True, [])


def _ai_spend_dashboard() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (DASHBOARDS_DIR / "ai-spend.json").read_text(encoding="utf-8")
    )
    return loaded


def _price_variable(dashboard: dict[str, Any]) -> dict[str, Any]:
    """The dashboard constant that holds the reference prices, or an empty dict."""
    variables: list[dict[str, Any]] = dashboard.get("templating", {}).get("list", [])
    return next((variable for variable in variables if variable["name"] == PRICE_VARIABLE), {})


def _dashboard_prices(variable: dict[str, Any]) -> dict[tuple[str, str], Decimal]:
    """The USD price per million tokens of each (operation, token type) that the price vector
    holds. A term of the vector that is not a price is put in as ("not a price", <term>)."""
    prices: dict[tuple[str, str], Decimal] = {}
    for term in variable.get("query", "").split(" or "):
        price = PRICE_TERM.fullmatch(term)
        if price:
            prices[(price.group(2), price.group(3))] = Decimal(price.group(1))
        else:
            prices[("not a price", term)] = Decimal(-1)
    return prices


def _genai_prices_per_million(model: str) -> dict[str, Decimal]:
    """genai-prices' bundled USD price per million prompt and completion tokens of a model."""
    usage = genai_prices.Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    price = genai_prices.calc_price(usage, model, provider_id=DEFAULT_AI_REFERENCE_PROVIDER)
    return {"prompt": price.input_price, "completion": price.output_price}


def _reference_prices() -> dict[tuple[str, str], Decimal]:
    """genai-prices' price of the default reference model of each operation, by token type."""
    references = {
        GenAiOperationNameValues.CHAT.value: DEFAULT_AI_REFERENCE_MODEL,
        GenAiOperationNameValues.EMBEDDINGS.value: DEFAULT_AI_REFERENCE_EMBEDDING_MODEL,
    }
    return {
        (operation, token_type): price
        for operation, model in references.items()
        for token_type, price in _genai_prices_per_million(model).items()
    }


def _price_rules() -> list[str]:
    """The recording rules of the Prometheus values that record a price."""
    values = yaml.safe_load((MONITORING_DIR / "prometheus-values.yaml").read_text("utf-8"))
    groups = values["serverFiles"].get("recording_rules.yml", {}).get("groups", [])
    return [
        rule["record"]
        for group in groups
        for rule in group["rules"]
        if "price" in rule.get("record", "")
    ]


def test_the_dashboard_holds_the_genai_prices_price_of_each_default_reference() -> None:
    """The AI spend dashboard holds, in one hidden constant, the price that genai-prices gives
    the default reference model of each operation and token type that devops-cli sends. The chat
    reference is gpt-4o, the `ai.reference_model` of the owner, so the dashboard and
    `devops ai cost` price at one model. No recording rule holds a second copy of a price
    (#2194)."""
    variable = _price_variable(_ai_spend_dashboard())
    description = variable.get("description", "")
    references = (DEFAULT_AI_REFERENCE_MODEL, DEFAULT_AI_REFERENCE_EMBEDDING_MODEL)

    assert (
        DEFAULT_AI_REFERENCE_MODEL,
        (variable.get("type"), variable.get("hide")),
        _dashboard_prices(variable),
        [model for model in references if f"`{model}`" not in description],
        _price_rules(),
    ) == ("gpt-4o", ("constant", 2), _reference_prices(), [], [])


def _savings_targets(dashboard: dict[str, Any]) -> list[str]:
    """The query of each target that charts local savings: in a panel about savings, or with a
    savings legend."""
    return [
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
        if "Savings" in panel.get("title", "") or "Savings" in target.get("legendFormat", "")
    ]


def _misses_a_local_token_or_the_price(expr: str) -> bool:
    """Whether a savings query leaves out a kind of local token or the dashboard prices, or
    reads a series other than the token counter."""
    return (
        any(selector not in expr for selector in LOCAL_TOKEN_SELECTORS)
        or '"operation", "chat", "", ""' not in expr
        or PRICED not in expr
        or {selector.metric for selector in selectors(expr)} != {"devops_cli_ai_tokens_total"}
    )


def test_each_savings_query_prices_all_local_tokens_at_the_dashboard_prices() -> None:
    """Each savings query multiplies the local tokens by the dashboard prices on operation and
    token type, and reads no series other than the token counter. The recording rule that priced
    the queries had samples only from its first evaluation, so every range that ended before
    it showed $0 (#2194). The local tokens include the series from before the `local` (#1672)
    and `operation` (#1623) labels, and no query reads a price that a process computed."""
    dashboard = _ai_spend_dashboard()
    targets = _savings_targets(dashboard)

    assert (
        len(targets),
        [expr for expr in targets if _misses_a_local_token_or_the_price(expr)],
        [expr for expr in _expressions(dashboard) if "cost_equivalent" in expr],
    ) == (8, [], [])


def _savings_record() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(SAVINGS_RECORD.read_text(encoding="utf-8"))
    return loaded


def _is_local(labels: dict[str, str]) -> bool:
    """Whether a local model ran the tokens of a series. A series from before the `local` label
    (#1672) is local when the gateway served it, because the gateway serves only local models.
    The response cache is no model (#816)."""
    if "local" in labels:
        return labels["local"] == "true"
    return labels.get("provider") == "gateway" and labels.get("server") != "cache"


def _priced_total(series: list[dict[str, Any]], prices: dict[tuple[str, str], Decimal]) -> Decimal:
    """The local savings of recorded series in USD: each local token at the price per million
    tokens of its operation and type. A series with no operation is chat (#1623), and a type
    with no price, such as reasoning, adds nothing."""
    return sum(
        (
            Decimal(point["value"])
            * prices.get(
                (point["labels"].get("operation", "chat"), point["labels"]["type"]), Decimal(0)
            )
            / 1_000_000
            for point in series
            if _is_local(point["labels"])
        ),
        Decimal(0),
    )


@pytest.mark.parametrize(
    "record",
    _savings_record()["records"],
    ids=lambda record: f"{record['range']}-to-{record['end']}",
)
def test_local_cloud_savings_in_range_gives_the_priced_total_of_the_recorded_series(
    record: dict[str, Any],
) -> None:
    """Prometheus' answer to the query of the panel is the total of the recorded token series
    at the dashboard prices, for series with and without the `local` and `operation` labels.
    From 2026-10-01 to 2026-10-22 it is $423 at gpt-4o, where the panel showed $0 (#2194). The
    record is of the query of the panel as it is now, so a changed query or price fails here
    until a person records it again."""
    dashboard = _ai_spend_dashboard()
    (panel,) = [panel for panel in dashboard["panels"] if panel.get("title") == SAVINGS_IN_RANGE]
    to_the_micro_dollar = Decimal("0.000001")
    total = _priced_total(record["series"], _dashboard_prices(_price_variable(dashboard)))

    assert (
        [target["expr"] for target in panel["targets"]],
        Decimal(record["result"]).quantize(to_the_micro_dollar),
    ) == ([_savings_record()["expr"]], total.quantize(to_the_micro_dollar))


def test_the_records_hold_each_kind_of_series_and_a_range_before_the_price_rule() -> None:
    """The records hold token series with both labels, without `local` (#1672), and without
    `local` and `operation` (#1623), and a range that ends before the first sample of the
    recording rule that priced the panel before #2194."""
    saved = _savings_record()
    kinds = {
        ("local" in point["labels"], "operation" in point["labels"])
        for record in saved["records"]
        for point in record["series"]
        if Decimal(point["value"]) > 0
    }
    first_price = datetime.fromisoformat(saved["deleted_price_rule_first_sample"])

    assert (
        kinds,
        any(datetime.fromisoformat(record["end"]) < first_price for record in saved["records"]),
    ) == ({(True, True), (False, True), (False, False)}, True)


# The gateway counts every caller's model calls and their status, and devops-cli counts only its
# own calls that ended with a reply, so the dashboard takes gateway traffic from the gateway (#1668).
GATEWAY_REQUESTS = "litellm_proxy_total_requests_metric_total"
GATEWAY_TOKENS = "litellm_total_tokens_metric_total"
GATEWAY_MODEL_CALLS = 'route=~"/v1/(chat/completions|embeddings)"'
GATEWAY_REPLIED = 'status_code=~"2.."'


def _ai_spend_panel(title: str) -> dict[str, Any]:
    (panel,) = [panel for panel in _ai_spend_dashboard()["panels"] if panel.get("title") == title]
    return panel


def _targets(panel: dict[str, Any]) -> list[str]:
    return [target["expr"] for target in panel["targets"]]


def test_requests_and_tokens_in_range_take_gateway_traffic_from_the_gateways_own_series() -> None:
    """A call through the gateway is counted once, from the gateway's series, whoever sent it: a
    reply's request with `status_code` 2xx, and its tokens. devops-cli's own series add only the
    calls that bypassed the gateway, and never a gateway call a second time (#1668)."""
    (requests,) = _targets(_ai_spend_panel("AI Requests in Range"))
    (tokens,) = _targets(_ai_spend_panel("Tokens Processed in Range"))

    assert (
        {s.metric for s in selectors(requests)},
        GATEWAY_MODEL_CALLS in requests and GATEWAY_REPLIED in requests,
        'devops_cli_ai_requests_total{provider!="gateway", cached="false"}' in requests,
        {s.metric for s in selectors(tokens)},
        'devops_cli_ai_tokens_total{provider!="gateway", server!="cache", type!="reasoning"}'
        in tokens,
        [expr for expr in (requests, tokens) if 'provider="gateway"' in expr],
    ) == (
        {GATEWAY_REQUESTS, "devops_cli_ai_requests_total"},
        True,
        True,
        {GATEWAY_TOKENS, "devops_cli_ai_tokens_total"},
        True,
        [],
    )


def test_the_gateway_row_shows_attempts_by_status_traffic_by_caller_and_devops_cli_coverage() -> (
    None
):
    """The gateway's model calls by status show the attempts that failed, such as its 408
    timeouts. Its replied requests and its tokens by `end_user` show each caller that names
    itself. The coverage stat is the share of the gateway's replied requests that devops-cli's
    own series count (#1668)."""
    attempts = _ai_spend_panel("Gateway Attempts by Status")
    callers = _ai_spend_panel("Gateway Requests and Tokens by Caller")
    coverage = _ai_spend_panel("devops-cli Coverage of Gateway Requests")
    (coverage_expr,) = _targets(coverage)
    numerator, _, denominator = coverage_expr.partition(" / ")

    assert (
        [
            (grouping_labels(e), GATEWAY_MODEL_CALLS in e, GATEWAY_REPLIED in e)
            for e in _targets(attempts)
        ],
        [
            ({s.metric for s in selectors(e)}, grouping_labels(e), GATEWAY_REPLIED in e)
            for e in _targets(callers)
        ],
        coverage["type"],
        coverage["fieldConfig"]["defaults"]["unit"],
        'devops_cli_ai_requests_total{provider="gateway", cached="false"}' in numerator,
        GATEWAY_REQUESTS in denominator and GATEWAY_REPLIED in denominator,
    ) == (
        [({"status_code"}, True, False)],
        [
            ({GATEWAY_REQUESTS}, {"end_user"}, True),
            ({GATEWAY_TOKENS}, {"end_user"}, False),
        ],
        "stat",
        "percentunit",
        True,
        True,
    )


TRAFFIC_PANELS = (
    "Views (14d Total & Uniques)",
    "Git Clones & Uniques (14d)",
    "Top Referral Sources (14 Days)",
    "Popular Content Paths (14 Days)",
)
TRAFFIC_SOURCES = (
    "The roadmap Service and `devops gh metrics --emit-telemetry` send traffic numbers.",
    "A repository whose traffic GitHub refused has no traffic series.",
)


def test_each_traffic_panel_names_the_senders_of_its_numbers() -> None:
    """The roadmap Service and a person's workstation send the traffic gauges (#2752, #4757). A
    repository whose traffic GitHub refused has no series. Each traffic panel says so."""
    dashboard = json.loads((DASHBOARDS_DIR / "project-metrics.json").read_text(encoding="utf-8"))
    descriptions = {
        panel["title"]: panel.get("description", "")
        for panel in dashboard["panels"]
        if panel["title"] in TRAFFIC_PANELS
    }

    assert {
        title: all(source in text for source in TRAFFIC_SOURCES) and "sends none" not in text
        for title, text in descriptions.items()
    } == dict.fromkeys(TRAFFIC_PANELS, True)


CLI_DASHBOARD = DASHBOARDS_DIR / "devops-cli.json"
# The rows of devops-cli.json that #4718 makes readable with the same chart rules. The rules
# check each other panel of the dashboard (#4707).
SERVICE_ROWS = frozenset(
    {
        "AI Spend & Economics",
        "Planner Tools",
        "Roadmap Service",
        "Alternatives Check",
        "Roadmap Job Success",
    }
)
GOLDEN_SIGNALS_ROW = "Golden signals: devops commands"
# The golden signals in the order of the SRE book, with the unit of each (docs/DESIGN.md C12 d).
GOLDEN_SIGNALS = (
    ("Latency", "s"),
    ("Traffic", "short"),
    ("Errors", "percentunit"),
    ("Saturation", "percentunit"),
)
# The range windows that follow the step of a time series, so its points do not overlap.
STEP_WINDOWS = frozenset({"$__interval", "$__rate_interval"})
RANGE_WINDOW = re.compile(r"\[([^\]]+)\]")
DURATION_UNITS = frozenset({"s", "ms"})
# The functions of a native histogram that give a duration: each histogram that a duration panel
# reads counts seconds or milliseconds.
DURATION_OF_HISTOGRAM = re.compile(r"\bhistogram_(?:quantile|avg|sum)\(")
# A reference line, such as a limit, is a constant query.
REFERENCE_LINE = re.compile(r"vector\(\s*[0-9.]+\s*\)")
# The override properties that give a field a y axis of its own.
SECOND_AXIS = frozenset({"unit", "custom.axisPlacement"})
INNERMOST_PARENTHESES = re.compile(r"\([^()]*\)")


def _outermost(query: str) -> str:
    """A query with each part in parentheses collapsed, which leaves its outermost operators."""
    collapsed = INNERMOST_PARENTHESES.sub("<>", query)
    return query if collapsed == query else _outermost(collapsed)


def measure(expr: str) -> str | None:
    """The quantity that a query gives: `share` for a ratio, `duration` for a quantile, a mean or
    a sum of a duration histogram, `count` for another query, and None for a reference line."""
    if REFERENCE_LINE.fullmatch(expr.strip()):
        return None
    if " / " in _outermost(expr):
        return "share"
    if DURATION_OF_HISTOGRAM.search(expr):
        return "duration"
    return "count"


def _second_axes(panel: dict[str, Any]) -> list[str]:
    """The override properties of a panel that give a field its own y axis."""
    return [
        prop["id"]
        for override in panel.get("fieldConfig", {}).get("overrides", [])
        for prop in override.get("properties", [])
        if prop.get("id") in SECOND_AXIS
    ]


def _time_series_problems(title: str, expr: str) -> list[str]:
    """The problems of one target of a time series: a window that does not follow the step, and
    a line for each command or sub-command."""
    problems = []
    windows = sorted(set(RANGE_WINDOW.findall(expr)) - STEP_WINDOWS)
    if windows or "$__range" in expr:
        problems.append(f"{title}: the window {windows} does not follow the step")
    if grouping_labels(expr) & {"command", "sub_command"}:
        problems.append(f"{title}: draws a line for each command")
    return problems


def readability_problems(panel: dict[str, Any]) -> list[str]:
    """One line for each chart rule of #4707 that a panel breaks: no repeat, a description, a
    title that names the signal and the measure, one unit and one y axis in a panel that is not
    a table, no count on a duration axis, `or vector(0)` only in a stat, and time series windows
    that follow the step and draw no line for each command."""
    title = panel.get("title", "")
    exprs = [target.get("expr", "") for target in panel.get("targets", [])]
    unit = panel.get("fieldConfig", {}).get("defaults", {}).get("unit")
    problems = []
    if "repeat" in panel:
        problems.append(f"{title}: repeats by {panel['repeat']}")
    if not panel.get("description"):
        problems.append(f"{title}: has no description")
    if ": " not in title:
        problems.append(f"{title}: the title does not name the signal and the measure")
    if panel.get("type") != "table":
        measures = sorted({measure(expr) for expr in exprs} - {None})
        if len(measures) > 1:
            problems.append(f"{title}: targets of two units: {measures}")
        if _second_axes(panel):
            problems.append(f"{title}: an override sets a second axis: {_second_axes(panel)}")
    if unit in DURATION_UNITS and any("histogram_count(" in expr for expr in exprs):
        problems.append(f"{title}: a count on a {unit} axis")
    if panel.get("type") != "stat" and any(falls_back_to_constant(expr) for expr in exprs):
        problems.append(f"{title}: or vector(0) outside a stat")
    if panel.get("type") == "timeseries":
        problems.extend(problem for expr in exprs for problem in _time_series_problems(title, expr))
    return problems


def _cli_dashboard() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(CLI_DASHBOARD.read_text(encoding="utf-8"))
    return loaded


def _panels_by_row(panels: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Each panel that is not a row, with the title of the row above it."""
    row = ""
    for panel in panels:
        if panel.get("type") == "row":
            row = panel.get("title", "")
            yield from ((row, inner) for inner in panel.get("panels", []))
        else:
            yield row, panel


def _row(title: str) -> list[dict[str, Any]]:
    return [panel for row, panel in _panels_by_row(_cli_dashboard()["panels"]) if row == title]


def test_each_panel_outside_the_service_rows_follows_the_chart_rules() -> None:
    """Each panel of devops-cli.json outside the rows of #4718 has one unit and one y axis, no
    repeat, a description and a title that names the signal and the measure. A time series has
    no window of `$__range` or of a fixed length, and no line for each command (#4707)."""
    panels = [
        panel
        for row, panel in _panels_by_row(_cli_dashboard()["panels"])
        if row not in SERVICE_ROWS
    ]
    assert (
        len(panels) > 10,
        [line for panel in panels for line in readability_problems(panel)],
    ) == (
        True,
        [],
    )


_P95 = (
    "histogram_quantile(0.95, sum(rate("
    'devops_cli_subcommand_duration_seconds{job=~"$job"}[$__rate_interval])))'
)
_CALLS = 'histogram_count(sum(increase(devops_cli_subcommand_duration_seconds{job=~"$job"}[$__interval])))'


def _latency_panel(**changes: Any) -> dict[str, Any]:
    """A time series of the p95 of calls that follows each chart rule, with `changes` put in."""
    panel: dict[str, Any] = {
        "type": "timeseries",
        "title": "Latency: p95 of successful calls",
        "description": "The p95 of the calls of each step.",
        "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []},
        "targets": [{"refId": "A", "expr": _P95}],
    }
    return panel | changes


def _override(prop: str, value: object) -> dict[str, Any]:
    return {
        "defaults": {"unit": "s"},
        "overrides": [
            {
                "matcher": {"id": "byName", "options": "calls"},
                "properties": [{"id": prop, "value": value}],
            }
        ],
    }


@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        pytest.param({}, None, id="a panel that follows the rules"),
        pytest.param(
            {"fieldConfig": {"defaults": {}}, "targets": [{"expr": _P95}, {"expr": _CALLS}]},
            "targets of two units",
            id="two units",
        ),
        pytest.param(
            {"fieldConfig": _override("custom.axisPlacement", "right")},
            "second axis",
            id="an axis on the right",
        ),
        pytest.param(
            {"fieldConfig": _override("unit", "short")}, "second axis", id="a unit override"
        ),
        pytest.param(
            {"fieldConfig": {"defaults": {"unit": "s"}}, "targets": [{"expr": _CALLS}]},
            "a count on a s axis",
            id="a count on a duration axis",
        ),
        pytest.param({"repeat": "sub_command"}, "repeats", id="a repeat"),
        pytest.param({"description": ""}, "no description", id="no description"),
        pytest.param(
            {"title": "Command latency"}, "signal and the measure", id="a title with no signal"
        ),
        pytest.param(
            {"targets": [{"expr": _P95.replace("$__rate_interval", "1h")}]},
            "does not follow the step",
            id="a fixed window",
        ),
        pytest.param(
            {"targets": [{"expr": _P95.replace("$__rate_interval", "$__range")}]},
            "does not follow the step",
            id="the range as a window",
        ),
        pytest.param(
            {"targets": [{"expr": _P95.replace("sum(", "sum by (command) (")}]},
            "a line for each command",
            id="a line for each command",
        ),
        pytest.param(
            {"targets": [{"expr": f"{_P95} or vector(0)"}]},
            "or vector(0) outside a stat",
            id="a zero fallback in a time series",
        ),
    ],
)
def test_each_broken_chart_rule_is_reported_once(changes: dict[str, Any], rule: str | None) -> None:
    """A panel that breaks one chart rule gets one problem line, which names the rule, and a
    panel that breaks none gets no line."""
    problems = readability_problems(_latency_panel(**changes))
    assert [rule is not None and rule in line for line in problems] == ([True] if rule else [])


def test_a_reference_line_and_a_table_take_more_than_one_unit() -> None:
    """A constant reference line takes the unit of its panel, and the columns of a table each
    have their own unit."""
    limit = _latency_panel(targets=[{"expr": _P95}, {"expr": "vector(1)"}])
    table = _latency_panel(type="table", targets=[{"expr": _P95}, {"expr": _CALLS}])
    table["fieldConfig"]["defaults"]["unit"] = "short"
    assert (readability_problems(limit), readability_problems(table)) == ([], [])


def test_the_first_row_holds_the_golden_signals_in_the_order_of_the_book() -> None:
    """The first row of devops-cli.json is "Golden signals: devops commands" with latency,
    traffic, errors and saturation, `w12 h8` each and two to a line, each with its unit
    (docs/DESIGN.md, "Grafana layout" and C12 d)."""
    panels = _cli_dashboard()["panels"]
    golden = _row(GOLDEN_SIGNALS_ROW)

    assert (
        (panels[0]["type"], panels[0]["title"]),
        [
            (panel["title"].partition(": ")[0], panel["fieldConfig"]["defaults"]["unit"])
            for panel in golden
        ],
        [
            (
                panel["gridPos"]["x"],
                panel["gridPos"]["y"],
                panel["gridPos"]["w"],
                panel["gridPos"]["h"],
            )
            for panel in golden
        ],
    ) == (
        ("row", GOLDEN_SIGNALS_ROW),
        list(GOLDEN_SIGNALS),
        [(0, 1, 12, 8), (12, 1, 12, 8), (0, 9, 12, 8), (12, 9, 12, 8)],
    )


def test_the_golden_signals_read_the_sub_command_histogram_of_the_selection() -> None:
    """Latency, traffic and errors read `devops_cli_subcommand_duration_seconds`, the histogram
    with the label `status`, for the selected job, command and sub-command. Latency reads the ok
    calls only. Saturation divides the spend of the Service budget by its limit, with a reference
    line at 100 % (#4707)."""
    latency, traffic, errors, saturation = _row(GOLDEN_SIGNALS_ROW)
    selection = (
        'devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command",'
        'sub_command=~"$sub_command"'
    )

    assert (
        [
            all(selection in target["expr"] for target in panel["targets"])
            for panel in (latency, traffic, errors)
        ],
        [target["expr"].count('status="ok"') for target in latency["targets"]],
        (traffic["interval"], traffic["fieldConfig"]["defaults"]["custom"]["drawStyle"]),
        [target["expr"] for target in saturation["targets"]][1:],
        [panel["fieldConfig"]["defaults"].get("min") for panel in (traffic, errors, saturation)],
    ) == ([True, True, True], [1, 1, 1], ("1h", "bars"), ["vector(1)"], [0, 0, 0])


def _links(panel: dict[str, Any]) -> list[str]:
    return [
        link["url"]
        for override in panel["fieldConfig"].get("overrides", [])
        for prop in override["properties"]
        if prop["id"] == "links"
        for link in prop["value"]
    ]


def _sort(table: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The sort of a table: the fields of its last transformation, and the initial sort of the
    table, each as (field, descending)."""
    last = table["transformations"][-1]
    return (
        [(field["field"], field["desc"]) for field in last["options"]["sort"]]
        if last["id"] == "sortBy"
        else [],
        [(field["displayName"], field["desc"]) for field in table["options"]["sortBy"]],
    )


def test_each_breakdown_table_sorts_by_errors_and_opens_the_golden_signals_of_a_row() -> None:
    """The tables of the commands and of the sub-commands are sorted by errors, then by calls.
    A row links to this dashboard with `var-command`, and `var-sub_command` for a sub-command, set
    to the row, so the golden signals show that command over time (#4707)."""
    (_, commands, _) = _row("Breakdown by command")
    (sub_commands,) = _row("Sub-commands")
    keep = "/d/devops-cli-telemetry/devops-cli-telemetry?${__url_time_range}&${job:queryparam}"
    errors_then_calls = [("Errors", True), ("Calls", True)]

    assert (
        [(table["type"], _sort(table)) for table in (commands, sub_commands)],
        _links(commands),
        _links(sub_commands),
    ) == (
        [("table", (errors_then_calls, errors_then_calls))] * 2,
        [f"{keep}&var-command=${{__data.fields.command}}"],
        [
            f"{keep}&var-command=${{__data.fields.command}}"
            "&var-sub_command=${__data.fields.sub_command:percentencode}"
        ],
    )


def test_the_cli_dashboard_opens_on_a_day_and_refreshes_each_minute() -> None:
    """An OTLP series gets about 4 samples an hour, so the dashboard opens on the last 24 h and
    refreshes each minute (#4707)."""
    dashboard = _cli_dashboard()
    assert (dashboard["time"], dashboard["refresh"]) == ({"from": "now-24h", "to": "now"}, "1m")
