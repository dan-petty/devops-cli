"""LLM serving and GPU metrics in Prometheus (#546).

Prometheus scraped no vLLM, gateway or GPU metric, so #545's imbalance was found by exec-ing
`nvidia-smi` in each pod, and `llm-stack.json` queried `http_requests_total`, which nothing in
the stack exposes. That dashboard's queries are checked against captures of the exporters in
`tests/test_stack_dashboards.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.ai import pool_load as pool_load_module
from devops_cli.ai.pool_load import pool_load, window_seconds
from devops_cli.commands import ai_gateway
from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK, _HELM_REPOS_BY_STACK
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})

K8S = Path("k8s")


def _yaml_docs(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def test_monitoring_scrapes_the_gateway() -> None:
    """Verify k8s-monitoring has prometheusOperatorObjects enabled and defines gateway ServiceMonitor."""
    values = yaml.safe_load((K8S / "monitoring/k8s-monitoring-values.yaml").read_text("utf-8"))
    poo = values["prometheusOperatorObjects"]
    extra_objects = values.get("extraObjects", [])
    monitors = {
        m["metadata"]["name"]: m["spec"] for m in extra_objects if m.get("kind") == "ServiceMonitor"
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
        gateway_scraped,
    ) == (
        True,
        [("llm-gateway", "/metrics/")],
    )


def test_network_policies_let_prometheus_reach_the_metrics_ports() -> None:
    """Verify the vLLM servers admit the monitoring namespace, and Prometheus may leave for the
    vLLM and gateway ports."""

    def admits_monitoring(path: Path) -> bool:
        (policy,) = _yaml_docs(path)
        return any(
            any(
                src.get("namespaceSelector", {})
                .get("matchLabels", {})
                .get("kubernetes.io/metadata.name")
                == "monitoring"
                for src in rule.get("from", [])
            )
            and 8000 in {p["port"] for p in rule.get("ports", [])}
            for rule in policy["spec"]["ingress"]
        )

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

    assert (
        admits_monitoring(K8S / "llm/profiles/networkpolicy.yaml"),
        {8000, 4000} <= to_llm,
    ) == (True, True)


def test_the_gateway_serves_its_prometheus_metrics() -> None:
    """Verify LiteLLM's Prometheus callback is on."""
    (configmap,) = _yaml_docs(K8S / "llm/gateway/configmap.yaml")
    config = yaml.safe_load(configmap["data"]["config.yaml"])

    assert "prometheus" in config["litellm_settings"]["callbacks"]


def test_the_dcgm_exporter_runs_on_every_gpu_node_without_extra_privileges() -> None:
    """Verify the exporter is installed with the monitoring stack, scheduled onto GPU nodes with
    the NVIDIA runtime, and holds SYS_ADMIN capability required for datacenter GPUs."""
    values = yaml.safe_load((K8S / "monitoring/dcgm-exporter-values.yaml").read_text("utf-8"))
    release = next(r for r in _HELM_RELEASES_BY_STACK["infra"] if r["name"] == "dcgm-exporter")
    repo = release["chart"].split("/")[0]

    assert (
        (values["runtimeClassName"], values["nodeSelector"]),
        {t["key"] for t in values["tolerations"]} >= {"nvidia.com/gpu"},
        values["securityContext"]["capabilities"].get("add", []),
        values["rollingUpdate"]["maxUnavailable"],
        values["serviceMonitor"]["enabled"],
        (release["namespace"], Path(release["values"]).name, repo in _HELM_REPOS_BY_STACK["infra"]),
    ) == (
        ("nvidia", {"nvidia.com/gpu.present": "true"}),
        True,
        ["SYS_ADMIN"],
        "50%",
        True,
        ("monitoring", "dcgm-exporter-values.yaml", True),
    )


def _fake_prometheus(expr: str) -> list[tuple[dict[str, str], float]]:
    """Answers shaped like Prometheus's for a pool of one vLLM server and one Ollama node."""
    vllm = "http://vllm.llm.svc.cluster.local:8000/v1"
    ollama = "http://ollama-0.ollama-nodes.llm.svc.cluster.local:11434/v1"
    if "litellm_deployment_total_requests_total[" in expr:
        return [({"api_base": vllm}, 120.0), ({"api_base": ollama}, 30.0)]
    if "litellm_deployment_failure_responses_total" in expr:
        return [({"api_base": ollama}, 2.0)]
    if "litellm_llm_api_latency_metric_sum" in expr:
        return [({"api_base": vllm}, 1.8), ({"api_base": ollama}, 0.4)]
    if "> bool 0" in expr:
        return [({"job": "vllm"}, 0.9)]
    if "avg_over_time(sum by (job) (vllm:num_requests_waiting)" in expr:
        return [({"job": "vllm"}, 0.5)]
    if "max_over_time(sum by (job) (vllm:num_requests_waiting)" in expr:
        return [({"job": "vllm"}, 3.0)]
    gpu = {"Hostname": "gpu-node", "gpu": "0", "modelName": "RTX 3090"}
    if "DCGM_FI_DEV_GPU_UTIL" in expr:
        return [(gpu, 71.0)]
    if "DCGM_FI_DEV_FB_USED" in expr:
        return [(gpu, 20480.0)]
    return []


def test_pool_load_joins_gateway_and_vllm_views_of_each_backend() -> None:
    """Verify a vLLM server's gateway and engine figures land on one row, and an Ollama node,
    which exports nothing, has the gateway's figures only."""
    load = pool_load(_fake_prometheus, "1h")

    assert (
        [
            (b.backend, b.requests, b.failures, b.mean_in_flight, b.busy_share, b.max_waiting)
            for b in load.backends
        ],
        [(g.host, g.mean_utilisation, g.peak_memory_mib) for g in load.gpus],
    ) == (
        [("ollama-0", 30.0, 2.0, 0.4, None, None), ("vllm", 120.0, 0.0, 1.8, 0.9, 3.0)],
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


def _with_prometheus(monkeypatch: pytest.MonkeyPatch, answers: Any) -> None:
    settings = load_settings()
    settings.prometheus.url = "http://prometheus.example:9090"
    settings.ai.allow_private_network = True
    monkeypatch.setattr(ai_gateway, "load_settings", lambda: settings)
    monkeypatch.setattr(ai_gateway, "prometheus_query", lambda url, timeout: answers)


def test_load_reports_the_pool_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `devops ai gateway load` reports the window's backends and GPUs."""
    _with_prometheus(monkeypatch, _fake_prometheus)

    result = cli.invoke(app, ["ai", "gateway", "load", "--window", "2h", "-f", "json"])
    report = json.loads(result.stdout)

    assert (
        result.exit_code,
        report["window"],
        [b["backend"] for b in report["backends"]],
        len(report["gpus"]),
    ) == (0, "2h", ["ollama-0", "vllm"], 1)


def test_load_table_and_an_empty_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the table shows busy shares, and a Prometheus without the pool's metrics is named
    rather than shown as idle."""
    _with_prometheus(monkeypatch, _fake_prometheus)
    table = cli.invoke(app, ["ai", "gateway", "load"])
    monkeypatch.setattr(ai_gateway, "prometheus_query", lambda url, timeout: lambda expr: [])
    empty = cli.invoke(app, ["ai", "gateway", "load"])

    assert (
        (table.exit_code, "90%" in table.output, "gpu-node" in table.output),
        (empty.exit_code, "No LLM pool or GPU metrics" in empty.output),
    ) == ((0, True, True), (0, True))


def test_load_needs_prometheus_and_a_valid_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a missing Prometheus URL or a malformed window exits non-zero without querying."""
    unconfigured = cli.invoke(app, ["ai", "gateway", "load"])
    _with_prometheus(monkeypatch, _fake_prometheus)
    bad_window = cli.invoke(app, ["ai", "gateway", "load", "--window", "forever"])

    assert (
        unconfigured.exit_code,
        bad_window.exit_code,
        "not a duration" in bad_window.output,
    ) == (
        1,
        1,
        True,
    )


def test_prometheus_errors_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an unreachable Prometheus is reported, not raised."""
    query = pool_load_module.prometheus_query("http://127.0.0.1:9", timeout=1)

    with pytest.raises(pool_load_module.PoolLoadError, match="did not answer"):
        query("up")


def test_window_seconds_bounds_and_prometheus_query_validation() -> None:
    """Verify window_seconds enforces 30-day limit and prometheus_query validates egress."""
    with pytest.raises(ValueError, match="exceeds maximum permitted limit"):
        window_seconds("31d")

    with pytest.raises(SSRFBlockedError, match="Invalid Prometheus URL scheme"):
        pool_load_module.prometheus_query("ftp://example.com", timeout=1)

    assert (window_seconds("30d"), window_seconds("1h")) == (30 * 86400, 3600)
