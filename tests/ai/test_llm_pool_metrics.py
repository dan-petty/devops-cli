"""LLM serving and GPU metrics in Prometheus (#546).

Prometheus scraped no gateway or GPU metric, so #545's imbalance was found by exec-ing
`nvidia-smi` in each pod, and `llm-stack.json` queried `http_requests_total`, which nothing in
the stack exposes. That dashboard's queries are checked against captures of the exporters in
`tests/test_stack_dashboards.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml

from devops_cli.ai import pool_load as pool_load_module
from devops_cli.ai.pool_load import pool_load, window_seconds
from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK, HELM_REPOS_BY_STACK
from devops_cli.http.egress import EgressLevel
from tests.web_fakes import StubWeb

K8S = Path("k8s")


def _yaml_docs(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def test_monitoring_scrapes_the_gateway() -> None:
    """Verify k8s-monitoring has prometheusOperatorObjects enabled and k8s/llm/gateway/servicemonitor.yaml selects the gateway."""
    values = yaml.safe_load((K8S / "monitoring/k8s-monitoring-values.yaml").read_text("utf-8"))
    poo = values["prometheusOperatorObjects"]
    monitors = {
        m["metadata"]["name"]: m["spec"]
        for m in _yaml_docs(K8S / "llm/gateway/servicemonitor.yaml")
        if m.get("kind") == "ServiceMonitor"
    }
    all_services = list(_yaml_docs(K8S / "llm/gateway/service.yaml"))

    def scraped(monitor: dict[str, Any]) -> list[tuple[str, str]]:
        selector = monitor["selector"]
        match_labels = selector.get("matchLabels", {})
        matched_services = [
            svc
            for svc in all_services
            if all(svc["metadata"].get("labels", {}).get(k) == v for k, v in match_labels.items())
        ]
        endpoint = monitor["endpoints"][0]
        return [
            (svc["metadata"]["name"], endpoint["path"])
            for svc in matched_services
            if endpoint["port"] in {p["name"] for p in svc["spec"]["ports"]}
        ]

    gateway_scraped = scraped(monitors["llm-gateway"])

    assert (
        poo["enabled"],
        "extraObjects" in values,
        gateway_scraped,
    ) == (
        True,
        False,
        [("llm-gateway", "/metrics/")],
    )


def test_network_policies_let_prometheus_reach_the_metrics_ports() -> None:
    """Verify Prometheus may leave for the gateway metrics port."""
    (monitoring,) = _yaml_docs(K8S / "monitoring/networkpolicy.yaml")
    to_llm = {
        port["port"]
        for rule in monitoring["spec"]["egress"]
        for dest in rule.get("to", [])
        if dest.get("namespaceSelector", {})
        .get("matchLabels", {})
        .get("kubernetes.io/metadata.name")
        == "llm"
        for port in rule.get("ports", [])
    }

    assert 4000 in to_llm


def test_the_gateway_serves_its_prometheus_metrics() -> None:
    """Verify LiteLLM's Prometheus callback is on."""
    config = yaml.safe_load((K8S / "llm/gateway/config.yaml").read_text(encoding="utf-8"))

    assert "prometheus" in config["litellm_settings"]["callbacks"]


def test_the_dcgm_exporter_runs_on_every_gpu_node_without_extra_privileges() -> None:
    """Verify the exporter is installed with the monitoring stack, scheduled onto GPU nodes with
    the NVIDIA runtime, and holds SYS_ADMIN capability required for datacenter GPUs. Its own
    ServiceMonitor stays off: k8s-monitoring's dcgm-exporter integration scrapes it (#1130)."""
    values = yaml.safe_load((K8S / "monitoring/dcgm-exporter-values.yaml").read_text("utf-8"))
    release = next(r for r in HELM_RELEASES_BY_STACK["infra"] if r["name"] == "dcgm-exporter")
    repo = release["chart"].split("/")[0]

    assert (
        (values["runtimeClassName"], values["nodeSelector"]),
        {t["key"] for t in values["tolerations"]} >= {"nvidia.com/gpu"},
        values["securityContext"]["capabilities"].get("add", []),
        values["rollingUpdate"]["maxUnavailable"],
        values["serviceMonitor"]["enabled"],
        (release["namespace"], Path(release["values"]).name, repo in HELM_REPOS_BY_STACK["infra"]),
    ) == (
        ("nvidia", {"nvidia.com/gpu.present": "true"}),
        True,
        ["SYS_ADMIN"],
        "50%",
        False,
        ("monitoring", "dcgm-exporter-values.yaml", True),
    )


def _fake_prometheus(expr: str) -> list[tuple[dict[str, str], float]]:
    """Answers shaped like Prometheus's for a pool of two Ollama nodes."""
    ollama_0 = "http://ollama-0.ollama-nodes.llm.svc.cluster.local:11434/v1"
    ollama_1 = "http://ollama-1.ollama-nodes.llm.svc.cluster.local:11434/v1"
    if "litellm_deployment_total_requests_total[" in expr:
        return [({"api_base": ollama_1}, 120.0), ({"api_base": ollama_0}, 30.0)]
    if "litellm_deployment_failure_responses_total" in expr:
        return [({"api_base": ollama_0}, 2.0)]
    if "litellm_llm_api_latency_metric_sum" in expr:
        return [({"api_base": ollama_1}, 1.8), ({"api_base": ollama_0}, 0.4)]
    gpu = {"Hostname": "gpu-node", "gpu": "0", "modelName": "RTX 3090"}
    if "DCGM_FI_DEV_GPU_UTIL" in expr:
        return [(gpu, 71.0)]
    if "DCGM_FI_DEV_FB_USED" in expr:
        return [(gpu, 20480.0)]
    return []


def test_pool_load_reports_views_of_each_backend() -> None:
    """Verify each backend's gateway figures land on their respective rows."""
    load = pool_load(_fake_prometheus, "1h")

    assert (
        [(b.backend, b.requests, b.failures, b.mean_in_flight) for b in load.backends],
        [(g.host, g.mean_utilisation, g.peak_memory_mib) for g in load.gpus],
    ) == (
        [("ollama-0", 30.0, 2.0, 0.4), ("ollama-1", 120.0, 0.0, 1.8)],
        [("gpu-node", 71.0, 20480.0)],
    )


@pytest.mark.parametrize(("window", "seconds"), [("30m", 1800), ("2h", 7200), ("1d", 86400)])
def test_windows_are_promql_durations(window: str, seconds: int) -> None:
    """Verify the window is read as PromQL reads it."""
    assert window_seconds(window) == seconds


@pytest.mark.parametrize("window", ["", "1w", "0h", "1h30m", "1h;drop"])
def test_other_windows_are_refused(window: str) -> None:
    """Verify only a plain duration reaches a query."""
    with pytest.raises(ValueError, match="not a duration"):
        window_seconds(window)


def _fake_prometheus_http(request: httpx2.Request) -> httpx2.Response | None:
    if "/api/v1/query" not in str(request.url):
        return None
    expr = request.url.params.get("query", "")
    ollama_0 = "http://ollama-0.ollama-nodes.llm.svc.cluster.local:11434/v1"
    ollama_1 = "http://ollama-1.ollama-nodes.llm.svc.cluster.local:11434/v1"
    results: list[dict[str, Any]] = []
    if "litellm_deployment_total_requests_total[" in expr:
        results = [
            {"metric": {"api_base": ollama_1}, "value": [1000, "120.0"]},
            {"metric": {"api_base": ollama_0}, "value": [1000, "30.0"]},
        ]
    elif "litellm_deployment_failure_responses_total" in expr:
        results = [{"metric": {"api_base": ollama_0}, "value": [1000, "2.0"]}]
    elif "litellm_llm_api_latency_metric_sum" in expr:
        results = [
            {"metric": {"api_base": ollama_1}, "value": [1000, "1.8"]},
            {"metric": {"api_base": ollama_0}, "value": [1000, "0.4"]},
        ]
    elif "DCGM_FI_DEV_GPU_UTIL" in expr:
        results = [
            {
                "metric": {"Hostname": "gpu-node", "gpu": "0", "modelName": "RTX 3090"},
                "value": [1000, "71.0"],
            }
        ]
    elif "DCGM_FI_DEV_FB_USED" in expr:
        results = [
            {
                "metric": {"Hostname": "gpu-node", "gpu": "0", "modelName": "RTX 3090"},
                "value": [1000, "20480.0"],
            }
        ]
    return httpx2.Response(
        200,
        json={"status": "success", "data": {"resultType": "vector", "result": results}},
    )


def test_load_reports_the_pool_as_json(
    config: Callable[..., Path], stub_web: StubWeb, cli: Callable[..., Any]
) -> None:
    """Verify `devops ai gateway load` reports the window's backends and GPUs."""
    config(
        prometheus={"url": "http://prometheus.example:9090"},
        ai={"allow_private_network": True},
    )
    stub_web.serve(_fake_prometheus_http)

    result = cli("ai", "gateway", "load", "--window", "2h", "-f", "json")
    report = json.loads(result.stdout)

    assert (
        result.exit_code,
        report["window"],
        [b["backend"] for b in report["backends"]],
        len(report["gpus"]),
    ) == (0, "2h", ["ollama-0", "ollama-1"], 1)


def test_load_table_and_an_empty_pool(
    config: Callable[..., Path], stub_web: StubWeb, cli: Callable[..., Any]
) -> None:
    """Verify the table shows GPU and backend figures, and a Prometheus without the pool's
    metrics is named rather than shown as idle."""
    config(
        prometheus={"url": "http://prometheus.example:9090"},
        ai={"allow_private_network": True},
    )
    stub_web.serve(_fake_prometheus_http)
    table = cli("ai", "gateway", "load")

    stub_web.servers.clear()
    stub_web.serve(
        lambda r: httpx2.Response(
            200,
            json={"status": "success", "data": {"resultType": "vector", "result": []}},
        )
    )
    empty = cli("ai", "gateway", "load")

    assert (
        (table.exit_code, "71%" in table.stdout, "gpu-node" in table.stdout),
        (empty.exit_code, "No LLM pool or GPU metrics" in empty.stdout),
    ) == ((0, True, True), (0, True))


def test_load_needs_prometheus_and_a_valid_window(
    config: Callable[..., Path], stub_web: StubWeb, cli: Callable[..., Any]
) -> None:
    """Verify a missing Prometheus URL or a malformed window exits non-zero without querying."""
    config(prometheus={"url": ""})
    unconfigured = cli("ai", "gateway", "load")

    config(
        prometheus={"url": "http://prometheus.example:9090"},
        ai={"allow_private_network": True},
    )
    stub_web.serve(_fake_prometheus_http)
    bad_window = cli("ai", "gateway", "load", "--window", "forever")

    assert (
        unconfigured.exit_code,
        bad_window.exit_code,
        "not a duration" in (bad_window.stdout + bad_window.stderr),
    ) == (
        1,
        1,
        True,
    )


def test_prometheus_errors_are_reported(refusing_port: int) -> None:
    """Verify an unreachable Prometheus is reported, not raised."""
    query = pool_load_module.prometheus_query(
        f"http://127.0.0.1:{refusing_port}", timeout=1, level=EgressLevel.LOOPBACK
    )

    with pytest.raises(pool_load_module.PoolLoadError, match="did not answer"):
        query("up")


def test_window_seconds_bounds_and_prometheus_query_validation() -> None:
    """Verify window_seconds enforces 30-day limit and a query refuses a scheme other than http."""
    with pytest.raises(ValueError, match="exceeds maximum permitted limit"):
        window_seconds("31d")

    query = pool_load_module.prometheus_query(
        "ftp://example.com", timeout=1, level=EgressLevel.LOOPBACK
    )
    with pytest.raises(pool_load_module.PoolLoadError, match="unsupported protocol"):
        query("up")

    assert (window_seconds("30d"), window_seconds("1h")) == (30 * 86400, 3600)
