"""Tests for dry-run request plans and classifications across 14 Kubernetes cluster commands.

Issue #2238: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import socket
import subprocess
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s.cluster_context import (
    contexts,
    logs,
    status,
    switch_context,
)
from devops_cli.commands.k8s.diagnostics import (
    pods_cmd,
    security_stream_cmd,
    stream_logs_cmd,
)
from devops_cli.commands.k8s.gpu_matrix import gpu_matrix_cmd
from devops_cli.commands.k8s.networking import (
    port_forward,
    port_forward_status,
    port_forward_stop,
    service_url,
)
from devops_cli.commands.k8s.security_audit import (
    k8s_audit,
    rbac_audit,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("k8s audit", k8s_audit, ["k8s", "audit", "--dry-run"]),
    ("k8s contexts", contexts, ["k8s", "contexts", "--dry-run"]),
    ("k8s logs", logs, ["k8s", "logs", "my-pod", "--dry-run"]),
    ("k8s pods", pods_cmd, ["k8s", "pods", "--dry-run"]),
    ("k8s port-forward", port_forward, ["k8s", "port-forward", "--dry-run"]),
    ("k8s rbac-audit", rbac_audit, ["k8s", "rbac-audit", "--dry-run"]),
    ("k8s security-stream", security_stream_cmd, ["k8s", "security-stream", "--dry-run"]),
    ("k8s service-url", service_url, ["k8s", "service-url", "my-svc", "--fetch", "--dry-run"]),
    ("k8s status", status, ["k8s", "status", "--dry-run"]),
    ("k8s stream-logs", stream_logs_cmd, ["k8s", "stream-logs", "my-app", "--dry-run"]),
    (
        "k8s switch-context",
        switch_context,
        ["k8s", "switch-context", "docker-desktop", "--dry-run"],
    ),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("k8s gpu-matrix", gpu_matrix_cmd, ["--dry-run", "k8s", "gpu-matrix"]),
    ("k8s port-forward-status", port_forward_status, ["--dry-run", "k8s", "port-forward-status"]),
    ("k8s port-forward-stop", port_forward_stop, ["k8s", "port-forward-stop", "--dry-run"]),
]


@pytest.fixture
def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real subprocess, socket, or process executions occur during dry-run."""

    def _fail_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected process invocation: {args}, {kwargs}")

    def _fail_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected socket call: {args}, {kwargs}")

    monkeypatch.setattr(subprocess, "run", _fail_process)
    monkeypatch.setattr(subprocess, "Popen", _fail_process)
    monkeypatch.setattr("devops_cli.core.process.run_subprocess", _fail_process)
    monkeypatch.setattr(socket, "socket", _fail_socket)
    monkeypatch.setattr(socket, "create_connection", _fail_socket)


@pytest.mark.parametrize("cmd_name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_classified(cmd_name: str, callback: Any, argv: list[str]) -> None:
    """Verify that external-request commands carry request-plan dry-run class."""
    cls = get_dry_run_class(callback)
    assert cls == "request-plan", (
        f"Command '{cmd_name}' has dry-run class {cls!r}, expected 'request-plan'"
    )


@pytest.mark.parametrize("cmd_name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_classified(
    cmd_name: str, callback: Any, argv: list[str]
) -> None:
    """Verify that local commands carry no-external-request dry-run class."""
    cls = get_dry_run_class(callback)
    assert cls == "no-external-request", (
        f"Command '{cmd_name}' has dry-run class {cls!r}, expected 'no-external-request'"
    )


@pytest.mark.parametrize("cmd_name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_zero_external_calls(
    cmd_name: str,
    callback: Any,
    argv: list[str],
    block_external_calls: None,
) -> None:
    """Executing request-plan command with --dry-run makes zero external calls."""
    res = runner.invoke(app, argv)
    assert res.exit_code == 0, f"Command {argv} failed with code {res.exit_code}: {res.output}"
    assert (
        "Planned requests" in res.output
        or "Planned" in res.output
        or "popeye" in res.output
        or "kubectl" in res.output
        or "kubernetes" in res.output
        or "GET" in res.output
    ), f"Command {argv} did not render expected request plan output:\n{res.output}"


def test_port_forward_stop_dry_run_local_preview(
    block_external_calls: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Executing k8s port-forward-stop --dry-run prints preview and terminates no daemon."""
    from devops_cli.k8s.port_forward_daemon import PortForwardDaemonManager

    def _fail_stop(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("stop_forwards called during dry-run")

    monkeypatch.setattr(PortForwardDaemonManager, "stop_forwards", _fail_stop)
    res = runner.invoke(app, ["k8s", "port-forward-stop", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Would terminate" in res.output or "dry-run" in res.output.lower()


def test_gpu_matrix_no_external_request_runs_under_root_proxy(block_external_calls: None) -> None:
    """Executing devops --dry-run k8s gpu-matrix runs normally without external calls."""
    res = runner.invoke(app, ["--dry-run", "k8s", "gpu-matrix"])
    assert res.exit_code == 0, res.output
    assert "Homelab GPU Inference Matrix" in res.output


def test_port_forward_status_no_external_request_runs_under_root_proxy(
    block_external_calls: None,
) -> None:
    """Executing devops --dry-run k8s port-forward-status runs normally without external calls."""
    res = runner.invoke(app, ["--dry-run", "k8s", "port-forward-status"])
    assert res.exit_code == 0, res.output


def test_plan_k8s_pods_variations() -> None:
    """plan_k8s_pods produces correct targets across namespace and label configurations."""
    from devops_cli.k8s.cluster_plans import plan_k8s_pods

    p1 = plan_k8s_pods(all_namespaces=True)
    assert p1[0].target == "list_pod_for_all_namespaces"

    p2 = plan_k8s_pods(all_namespaces=True, label="app=web")
    assert p2[0].target == "list_pod_for_all_namespaces [label=app=web]"

    p3 = plan_k8s_pods(namespace="staging", label="app=web")
    assert p3[0].target == "list_namespaced_pod(namespace=staging) [label=app=web]"


def test_plan_k8s_logs_variations() -> None:
    """plan_k8s_logs covers Loki query targets and kubectl flag builders."""
    from devops_cli.k8s.cluster_plans import plan_k8s_logs

    p_loki = plan_k8s_logs("api-pod", query='{app="api"}', loki_url="http://custom-loki:3100")
    assert p_loki[0].method == "GET"
    assert "custom-loki:3100" in p_loki[0].target

    p_kube = plan_k8s_logs("api-pod", container="app", namespace="prod", follow=True)
    assert p_kube[0].method == "kubectl"
    assert "-c" in p_kube[0].argv
    assert "-n" in p_kube[0].argv
    assert "-f" in p_kube[0].argv


def test_plan_k8s_stream_logs_variations(monkeypatch: pytest.MonkeyPatch) -> None:
    """plan_k8s_stream_logs covers Stern binary detection and kubectl fallback flags."""
    from devops_cli.k8s.cluster_plans import plan_k8s_stream_logs

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/stern")
    p_stern = plan_k8s_stream_logs(
        "web",
        namespace="prod",
        container="nginx",
        tail=50,
        follow=True,
    )
    assert p_stern[0].method == "stern"

    monkeypatch.setattr("shutil.which", lambda _: None)
    p_kubectl = plan_k8s_stream_logs(
        "web",
        namespace="prod",
        container="nginx",
        tail=50,
        follow=True,
    )
    assert p_kubectl[0].method == "kubectl"
    assert "-n" in p_kubectl[0].argv
    assert "-c" in p_kubectl[0].argv
    assert "-f" in p_kubectl[0].argv


def test_plan_k8s_security_stream_follow() -> None:
    """plan_k8s_security_stream includes -f flag when follow is requested."""
    from devops_cli.k8s.cluster_plans import plan_k8s_security_stream

    plan = plan_k8s_security_stream("falco", "app=falco", follow=True)
    assert "-f" in plan[0].argv


def test_plan_k8s_service_url_variations() -> None:
    """plan_k8s_service_url covers resolve and proxy GET methods."""
    from devops_cli.k8s.cluster_plans import plan_k8s_service_url

    p_resolve = plan_k8s_service_url("prometheus.monitoring:9090", fetch=False)
    assert p_resolve[0].method == "resolve"
    assert p_resolve[0].target == "prometheus.monitoring:9090"

    p_fetch = plan_k8s_service_url(
        "prometheus.monitoring:9090",
        proxy_url="http://127.0.0.1:9090",
        fetch=True,
    )
    assert p_fetch[0].method == "GET"
    assert p_fetch[0].target == "http://127.0.0.1:9090"


def test_k8s_port_forward_stop_with_service_filter(
    block_external_calls: None,
) -> None:
    """Executing k8s port-forward-stop with --service filter previews correctly."""
    res = runner.invoke(app, ["k8s", "port-forward-stop", "--service", "ollama", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Would terminate" in res.output


def test_k8s_service_url_fetch_dry_run(block_external_calls: None) -> None:
    """Executing k8s service-url with --fetch and --dry-run prints planned GET request."""
    res = runner.invoke(app, ["k8s", "service-url", "grafana", "--fetch", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Planned requests" in res.output or "GET" in res.output


def test_stream_logs_cmd_exit_code_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """stream-logs exits with non-zero code returned by underlying streaming helper."""
    import devops_cli.k8s.logs

    monkeypatch.setattr(
        devops_cli.k8s.logs,
        "stream_multi_pod_logs",
        lambda *args, **kwargs: 42,
    )
    res = runner.invoke(app, ["k8s", "stream-logs", "failing-app"])
    assert res.exit_code == 42
