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
from devops_cli.prometheus.promql import selectors
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
