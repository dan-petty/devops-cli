"""Unit tests for Kubernetes logging stack lifecycle, manifests, and CLI integration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _HELM_REPOS_BY_STACK,
    _MANIFESTS_BY_STACK,
    VALID_STACKS,
)

runner = CliRunner()


def test_logging_stack_definitions_and_single_shipper() -> None:
    """Verify logging stack registers Loki alone and Alloy ships pod logs to Loki (#548)."""
    repo_root = Path(__file__).resolve().parent.parent
    mon_values = yaml.safe_load(
        (repo_root / "k8s" / "monitoring" / "k8s-monitoring-values.yaml").read_text(
            encoding="utf-8"
        )
    )
    release_names = tuple(r["name"] for r in _HELM_RELEASES_BY_STACK["logging"])
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
        ("grafana",),
        True,
        "http://loki.logging.svc.cluster.local:3100/loki/api/v1/push",
    )

    manifest_paths = [str(p) for p in _MANIFESTS_BY_STACK["logging"]]
    assert ("logging" in VALID_STACKS, any("networkpolicy.yaml" in p for p in manifest_paths)) == (
        True,
        True,
    )


def test_monitoring_network_policy_alloy_egress_rules() -> None:
    """Verify monitoring NetworkPolicy retains Alloy API discovery and Loki log shipping egress (#548)."""
    repo_root = Path(__file__).resolve().parent.parent
    np_path = repo_root / "k8s" / "monitoring" / "networkpolicy.yaml"
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
    assert (api_rule is not None, loki_rule is not None) == (True, True)


def test_deploy_logging_stack_dry_run() -> None:
    """Verify deploy-stack --stack logging with dry run."""
    with patch("devops_cli.commands.k8s.stack_lifecycle.is_dry_run", return_value=True):
        result = runner.invoke(app, ["deploy-stack", "--stack", "logging", "--no-push-secrets"])
        assert result.exit_code == 0
        assert "deploy-stack" in result.output
        assert "logging" in result.output


def test_teardown_logging_stack_dry_run() -> None:
    """Verify teardown-stack --stack logging with dry run."""
    with patch("devops_cli.commands.k8s.stack_lifecycle.is_dry_run", return_value=True):
        result = runner.invoke(app, ["teardown-stack", "--stack", "logging"])
        assert result.exit_code == 0
        assert "teardown-stack" in result.output
        assert "logging" in result.output


def test_deploy_logging_stack_live() -> None:
    """Verify deploy-stack --stack logging execution."""
    mock_proc = MagicMock(returncode=0, stdout="success", stderr="")
    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch("devops_cli.commands.k8s.run_subprocess", return_value=mock_proc),
        patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc),
    ):
        result = runner.invoke(app, ["deploy-stack", "--stack", "logging", "--no-push-secrets"])
        assert result.exit_code == 0


def test_teardown_logging_stack_live() -> None:
    """Verify teardown-stack --stack logging execution."""
    mock_proc = MagicMock(returncode=0, stdout="success", stderr="")
    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch("devops_cli.commands.k8s.run_subprocess", return_value=mock_proc),
        patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc),
    ):
        result = runner.invoke(app, ["teardown-stack", "--stack", "logging"])
        assert result.exit_code == 0


def test_k8s_logs_backward_compatibility() -> None:
    """Verify devops k8s logs <pod> continues to work as expected."""
    mock_proc = MagicMock(returncode=0, stdout="pod logs output", stderr="")
    with patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc) as mock_run:
        result = runner.invoke(app, ["logs", "my-legacy-pod", "-n", "default", "--tail", "25"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_logs_logql_query_dispatch() -> None:
    """Verify devops k8s logs '{app=\"foo\"}' routes to LogQL query engine."""
    with patch("devops_cli.k8s.logql.execute_logql_query") as mock_query:
        mock_query.return_value = MagicMock(
            source="mock",
            entries=[],
            duration_ms=5.0,
        )
        result = runner.invoke(
            app,
            ["logs", '{app="frontend"} |= "error"', "--since", "30m", "--limit", "20"],
        )
        assert result.exit_code == 0
        mock_query.assert_called_once()


def test_k8s_logs_subcommand_query_dispatch() -> None:
    """Verify devops k8s logs query '{app=\"foo\"}' routes to LogQL query engine."""
    with patch("devops_cli.k8s.logql.execute_logql_query") as mock_query:
        mock_query.return_value = MagicMock(
            source="mock",
            entries=[],
            duration_ms=5.0,
        )
        result = runner.invoke(
            app,
            ["logs", "query", '{app="backend"}', "--limit", "10"],
        )
        assert result.exit_code == 0
        mock_query.assert_called_once()


def test_k8s_logs_pod_named_tail_legacy() -> None:
    """Verify devops k8s logs tail without query argument treats tail as a pod name."""
    mock_proc = MagicMock(returncode=0, stdout="logs from pod tail", stderr="")
    with patch("devops_cli.commands.k8s._run_cmd", return_value=mock_proc) as mock_run:
        result = runner.invoke(app, ["logs", "tail", "-n", "default"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "tail" in cmd


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


def test_k8s_logs_escapes_rich_markup() -> None:
    """Verify log entries with Rich markup brackets are safely escaped in output."""
    from devops_cli.k8s.logql import LogEntry, LogQueryResult, parse_logql_query

    mock_result = LogQueryResult(
        query=parse_logql_query('{app="web"}'),
        entries=[
            LogEntry(
                timestamp="2026-09-10T12:00:00Z",
                line="[bold red]critical payload syntax error[/bold red] <xml>",
                stream_labels={"pod": "web-pod-1"},
            )
        ],
        source="loki",
    )
    with patch("devops_cli.k8s.logql.execute_logql_query", return_value=mock_result):
        result = runner.invoke(app, ["logs", '{app="web"}'])
        assert result.exit_code == 0
        assert "[bold red]critical payload syntax error[/bold red]" in result.output


def test_k8s_teardown_stack_case_insensitive() -> None:
    """Verify teardown-stack normalizes case-insensitive stack names."""
    with patch("devops_cli.commands.k8s.stack_lifecycle.is_dry_run", return_value=True):
        result = runner.invoke(app, ["teardown-stack", "--stack", "LOGGING"])
        assert result.exit_code == 0
        assert "teardown_k8s_stack" in result.output


def test_logging_stack_security_and_scoping() -> None:
    """Verify DevSecOps perimeter hardening and bidirectional NetworkPolicy for logging stack (#548)."""
    repo_root = Path(__file__).resolve().parent.parent
    logging_dir = repo_root / "k8s" / "logging"
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
def test_k8s_logs_native_streaming_framing_and_literals(follow: bool) -> None:
    """Verify devops k8s logs writes each line via write_stdout without markup or wrapping."""
    from devops_cli.k8s.service import KubernetesService

    svc = KubernetesService.get_instance()
    mock_resp = MagicMock()
    mock_resp.stream.return_value = [
        b"a\nb",
        b"c\n",
        b"literal [/bold] tags\n",
        b"w" * 200 + b"\n",
    ]
    mock_core = MagicMock()
    mock_core.read_namespaced_pod_log.return_value = mock_resp

    args = ["logs", "pod-1", "-n", "default"]
    if follow:
        args.append("--follow")

    with (
        patch.object(svc, "load_config", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd") as mock_cmd,
        patch("devops_cli.commands.k8s.run_subprocess") as mock_subproc,
    ):
        svc._core_v1 = mock_core
        res = runner.invoke(app, args)
        assert (
            res.exit_code,
            res.stdout,
            mock_cmd.called,
            mock_subproc.called,
        ) == (
            0,
            f"a\nbc\nliteral [/bold] tags\n{'w' * 200}\n",
            False,
            False,
        )


def test_k8s_logs_mid_body_error_raises_without_fallback() -> None:
    """Verify mid-body error in non-follow mode raises without fallback to kubectl."""
    from devops_cli.k8s.service import KubernetesService

    svc = KubernetesService.get_instance()

    def stream_with_error() -> Iterator[bytes]:
        yield b"head-line\n"
        raise RuntimeError("mid-stream failure")

    mock_resp = MagicMock()
    mock_resp.stream.return_value = stream_with_error()
    mock_core = MagicMock()
    mock_core.read_namespaced_pod_log.return_value = mock_resp

    with (
        patch.object(svc, "load_config", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd") as mock_cmd,
        patch("devops_cli.commands.k8s.run_subprocess") as mock_subproc,
    ):
        svc._core_v1 = mock_core
        res = runner.invoke(app, ["logs", "pod-1", "-n", "default"])
        assert (
            res.exit_code != 0,
            isinstance(res.exception, RuntimeError),
            "head-line\n" in res.stdout,
            mock_cmd.called,
            mock_subproc.called,
        ) == (True, True, True, False, False)
