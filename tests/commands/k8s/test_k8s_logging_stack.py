"""Unit tests for Kubernetes logging stack lifecycle, manifests, and CLI integration."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.networking import VALID_STACKS
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_REPOS_BY_STACK,
    HELM_RELEASES_BY_STACK,
    MANIFESTS_BY_STACK,
)
from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.http import WebFake
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.k8s_commands import answer_helm_version
from tests.support.paths import REPO_ROOT

runner = CliRunner()


def test_logging_stack_definitions_and_single_shipper() -> None:
    """Verify logging stack registers Loki alone and Alloy ships pod logs to Loki (#548)."""
    mon_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "monitoring" / "k8s-monitoring-values.yaml").read_text(
            encoding="utf-8"
        )
    )
    release_names = tuple(r["name"] for r in HELM_RELEASES_BY_STACK["logging"])
    repo_names = tuple(_HELM_REPOS_BY_STACK["logging"].keys())
    pod_logs_enabled = mon_values["podLogsViaLoki"]["enabled"]
    local_loki_url = mon_values["destinations"]["localLoki"]["url"]

    assert (
        release_names,
        repo_names,
        pod_logs_enabled,
        local_loki_url,
    ) == (
        ("loki",),
        ("grafana-community",),
        True,
        "http://loki.logging.svc.cluster.local:3100/loki/api/v1/push",
    )

    manifest_paths = [str(p) for p in MANIFESTS_BY_STACK["logging"]]
    assert ("logging" in VALID_STACKS, any("networkpolicy.yaml" in p for p in manifest_paths)) == (
        True,
        True,
    )


def test_deploy_stack_installs_loki_from_the_grafana_community_chart() -> None:
    """The logging stack of deploy-stack installs the chart that the Argo CD Application pins,
    `grafana-community/loki` 20.0.2, which runs Loki 3.7.9 and so is out of reach of
    CVE-2026-21729 (#1632). It adds only the grafana-community repository, and gives the chart
    only the values file. The invariant test of the Application and the values is in
    tests/invariants/test_k8s_manifests.py."""
    (release,) = HELM_RELEASES_BY_STACK["logging"]

    assert (release, _HELM_REPOS_BY_STACK["logging"]) == (
        {
            "name": "loki",
            "chart": "grafana-community/loki",
            "namespace": "logging",
            "values": str(DEFAULT_K8S_DIR / "logging" / "loki-values.yaml"),
            "version": "20.0.2",
        },
        {"grafana-community": "https://grafana-community.github.io/helm-charts"},
    )


def test_monitoring_network_policy_alloy_egress_rules() -> None:
    """Verify monitoring NetworkPolicy retains Alloy API discovery and Loki log shipping egress (#548)."""
    np_path = REPO_ROOT / "k8s" / "monitoring" / "networkpolicy.yaml"
    np_doc = yaml.safe_load(np_path.read_text(encoding="utf-8"))
    egress_rules = np_doc.get("spec", {}).get("egress", [])

    api_rule = next(
        (
            rule
            for rule in egress_rules
            if any(
                p.get("port") == 6443 and p.get("protocol") == "TCP" for p in rule.get("ports", [])
            )
            and any(
                t.get("ipBlock", {}).get("cidr") == "0.0.0.0/0"
                and t.get("ipBlock", {}).get("except") == ["169.254.169.254/32"]
                for t in rule.get("to", [])
            )
        ),
        None,
    )
    loki_rule = next(
        (
            rule
            for rule in egress_rules
            if any(
                p.get("port") == 3100 and p.get("protocol") == "TCP" for p in rule.get("ports", [])
            )
            and any(
                t.get("namespaceSelector", {})
                .get("matchLabels", {})
                .get("kubernetes.io/metadata.name")
                == "logging"
                for t in rule.get("to", [])
            )
        ),
        None,
    )
    assert isinstance(api_rule, dict)
    assert isinstance(loki_rule, dict)
    assert {"port": 6443, "protocol": "TCP"} in api_rule.get("ports", [])
    assert {"port": 3100, "protocol": "TCP"} in loki_rule.get("ports", [])


def test_deploy_logging_stack_dry_run() -> None:
    """Verify deploy-stack --stack logging with dry run."""
    set_dry_run(True)
    result = runner.invoke(app, ["deploy-stack", "--stack", "logging", "--no-push-secrets"])
    assert result.exit_code == 0
    assert "deploy-stack" in result.output
    assert "logging" in result.output


def test_teardown_logging_stack_dry_run() -> None:
    """Verify teardown-stack --stack logging with dry run."""
    set_dry_run(True)
    result = runner.invoke(app, ["teardown-stack", "--stack", "logging"])
    assert result.exit_code == 0
    assert "teardown-stack" in result.output
    assert "logging" in result.output


def test_deploy_logging_stack_live(cluster: FakeCluster, process_fake: ProcessFake) -> None:
    """Verify deploy-stack --stack logging execution."""
    answer_helm_version(process_fake)

    result = runner.invoke(app, ["deploy-stack", "--stack", "logging", "--no-push-secrets"])

    installed = [
        call.argv[4]
        for call in process_fake.calls
        if call.argv[:3] == ("helm", "upgrade", "--install")
    ]
    assert (result.exit_code, installed) == (
        0,
        [release["name"] for release in HELM_RELEASES_BY_STACK["logging"]],
    )


def test_teardown_logging_stack_live(cluster: FakeCluster, process_fake: ProcessFake) -> None:
    """Verify teardown-stack --stack logging execution."""
    result = runner.invoke(app, ["teardown-stack", "--stack", "logging"])

    removed = [
        call.argv[2] for call in process_fake.calls if call.argv[:2] == ("helm", "uninstall")
    ]
    assert (result.exit_code, removed) == (
        0,
        [release["name"] for release in reversed(HELM_RELEASES_BY_STACK["logging"])],
    )


def test_k8s_logs_backward_compatibility(process_fake: ProcessFake) -> None:
    """Verify devops k8s logs <pod> continues to work as expected."""
    process_fake.answer("kubectl logs", ProcessAnswer(stdout="pod logs output"))

    result = runner.invoke(app, ["logs", "my-legacy-pod", "-n", "default", "--tail", "25"])

    assert result.exit_code == 0
    assert [call.argv[:3] for call in process_fake.calls] == [("kubectl", "logs", "my-legacy-pod")]


def _serve_loki(web: WebFake, streams: list[dict[str, Any]] | None = None) -> None:
    """Answer each Loki range query with `streams`, or with no stream."""
    body = json.dumps({"data": {"result": streams or []}})
    web.serve(lambda _request: httpx2.Response(200, text=body))


def _loki_queries(web: WebFake) -> list[str]:
    """The LogQL expression of each range query that reached Loki."""
    return [
        parse_qs(urlsplit(request.url).query)["query"][0]
        for request in web.recorded
        if urlsplit(request.url).path == "/loki/api/v1/query_range"
    ]


def test_k8s_logs_logql_query_dispatch(
    config: Callable[..., Path], web: WebFake, process_fake: ProcessFake
) -> None:
    """Verify devops k8s logs '{app=\"foo\"}' routes to LogQL query engine."""
    config(loki={"url": "http://example.com:3100"})
    _serve_loki(web)

    result = runner.invoke(
        app,
        ["logs", '{app="frontend"} |= "error"', "--since", "30m", "--limit", "20"],
    )

    sent = parse_qs(urlsplit(web.recorded[0].url).query)
    assert (
        result.exit_code,
        _loki_queries(web),
        sent["since"],
        sent["limit"],
        process_fake.calls,
    ) == (0, ['{app="frontend"} |= "error"'], ["30m"], ["20"], [])


def test_k8s_logs_subcommand_query_dispatch(
    config: Callable[..., Path], web: WebFake, process_fake: ProcessFake
) -> None:
    """Verify devops k8s logs query '{app=\"foo\"}' routes to LogQL query engine."""
    config(loki={"url": "http://example.com:3100"})
    _serve_loki(web)

    result = runner.invoke(app, ["logs", "query", '{app="backend"}', "--limit", "10"])

    assert (result.exit_code, _loki_queries(web), process_fake.calls) == (
        0,
        ['{app="backend"}'],
        [],
    )


def test_k8s_logs_pod_named_tail_legacy(process_fake: ProcessFake) -> None:
    """Verify devops k8s logs tail without query argument treats tail as a pod name."""
    process_fake.answer("kubectl logs", ProcessAnswer(stdout="logs from pod tail"))

    result = runner.invoke(app, ["logs", "tail", "-n", "default"])

    assert result.exit_code == 0
    assert len(process_fake.calls) == 1
    assert "tail" in process_fake.calls[0].argv


def test_k8s_logs_logql_rejects_follow() -> None:
    """Verify devops k8s logs with LogQL query rejects --follow."""
    result = runner.invoke(app, ["logs", '{app="frontend"}', "--follow"])
    assert result.exit_code == 1
    assert "--follow" in result.output


def test_k8s_logs_empty_query_rejected() -> None:
    """Verify devops k8s logs with empty query string exits with error."""
    result = runner.invoke(app, ["logs", "--query", "   "])
    assert result.exit_code == 1
    assert "LogQL query expression is required" in result.output


def test_k8s_logs_escapes_rich_markup(config: Callable[..., Path], web: WebFake) -> None:
    """Verify log entries with Rich markup brackets are safely escaped in output."""
    config(loki={"url": "http://example.com:3100"})
    _serve_loki(
        web,
        [
            {
                "stream": {"pod": "web-pod-1"},
                "values": [
                    [
                        "1788950400000000000",
                        "[bold red]critical payload syntax error[/bold red] <xml>",
                    ]
                ],
            }
        ],
    )

    result = runner.invoke(app, ["logs", '{app="web"}'])

    assert result.exit_code == 0
    assert "[bold red]critical payload syntax error[/bold red]" in result.output


def test_k8s_teardown_stack_case_insensitive() -> None:
    """Verify teardown-stack normalizes case-insensitive stack names."""
    set_dry_run(True)
    result = runner.invoke(app, ["teardown-stack", "--stack", "LOGGING"])
    assert result.exit_code == 0
    assert "teardown_k8s_stack" in result.output


def test_logging_stack_security_and_scoping() -> None:
    """Verify DevSecOps perimeter hardening and bidirectional NetworkPolicy for logging stack (#548)."""
    logging_dir = REPO_ROOT / "k8s" / "logging"
    np_path = logging_dir / "networkpolicy.yaml"
    assert np_path.is_file()
    np_doc = yaml.safe_load(np_path.read_text(encoding="utf-8"))
    assert np_doc.get("metadata", {}).get("namespace") == "logging"

    # 1. Egress: exactly intra-namespace and CoreDNS in kube-system
    egress_rules = np_doc.get("spec", {}).get("egress", [])
    assert (
        len(egress_rules),
        egress_rules[0].get("to"),
        egress_rules[1].get("to"),
        egress_rules[1].get("ports"),
    ) == (
        2,
        [{"podSelector": {}}],
        [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}],
        [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
    )

    # 2. Ingress: intra-namespace and telemetry (monitoring and otel on TCP 3100)
    ingress_rules = np_doc.get("spec", {}).get("ingress", [])
    assert len(ingress_rules) == 2

    # Ingress rule 1: intra-namespace
    assert ingress_rules[0].get("from") == [{"podSelector": {}}]

    # Ingress rule 2: monitoring and the otel collector on port 3100
    rule_telemetry = ingress_rules[1]
    from_telemetry = rule_telemetry.get("from", [])
    allowed_namespaces = {
        f.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        for f in from_telemetry
    }
    assert (
        allowed_namespaces,
        rule_telemetry.get("ports"),
    ) == (
        {"monitoring", "otel"},
        [{"protocol": "TCP", "port": 3100}],
    )

    # Ensure no ingress-nginx or unconstrained CIDR rules
    for rule in ingress_rules:
        for f in rule.get("from", []):
            ns_name = (
                f.get("namespaceSelector", {})
                .get("matchLabels", {})
                .get("kubernetes.io/metadata.name", "")
            )
            assert (ns_name != "ingress-nginx", "ipBlock" not in f) == (True, True)


@pytest.mark.parametrize("follow", [False, True])
def test_k8s_logs_native_streaming_framing_and_literals(
    follow: bool, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """Verify devops k8s logs writes each line via write_stdout without markup or wrapping."""
    cluster.core.answers["read_namespaced_pod_log"] = [
        b"a\nb",
        b"c\n",
        b"literal [/bold] tags\n",
        b"w" * 200 + b"\n",
    ]

    args = ["logs", "pod-1", "-n", "default"]
    if follow:
        args.append("--follow")

    res = runner.invoke(app, args)

    assert (res.exit_code, res.stdout, process_fake.calls) == (
        0,
        f"a\nbc\nliteral [/bold] tags\n{'w' * 200}\n",
        [],
    )


def test_k8s_logs_mid_body_error_raises_without_fallback(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """Verify mid-body error in non-follow mode raises without fallback to kubectl."""
    cluster.core.answers["read_namespaced_pod_log"] = [
        b"head-line\n",
        RuntimeError("mid-stream failure"),
    ]

    res = runner.invoke(app, ["logs", "pod-1", "-n", "default"])

    assert res.exit_code != 0
    assert isinstance(res.exception, RuntimeError)
    assert "head-line\n" in res.stdout
    assert process_fake.calls == []
