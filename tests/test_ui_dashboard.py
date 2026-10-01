"""Test suite for interactive terminal UI dashboard, subsystem data providers, and CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import TabbedContent
from typer.testing import CliRunner

import devops_cli.commands.dashboard as dashboard_command
import devops_cli.ui.data_providers as data_providers
from devops_cli.commands.dashboard import app as dashboard_app
from devops_cli.config.defaults import DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS
from devops_cli.main import app as main_app
from devops_cli.models.k8s import PodInfo
from devops_cli.ui.dashboard import DashboardApp, HelpScreen
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    ReviewSummary,
    TelemetrySummary,
    ValkeySummary,
    fetch_docker_status,
    fetch_k8s_status,
    fetch_review_status,
    fetch_telemetry_status,
    fetch_valkey_status,
)
from devops_cli.ui.projections import k8s_banner
from tests.k8s_fakes import FakeCoreV1, crashlooping_pod, healthy_pod, node

runner = CliRunner()


# =============================================================================
# Subsystem Data Provider Tests
# =============================================================================


@pytest.fixture
def lab_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Name the context the provider reports, whatever the workstation has configured."""
    monkeypatch.setattr(data_providers, "_k8s_context_name", lambda: "lab")


def _serve(monkeypatch: pytest.MonkeyPatch, core: FakeCoreV1) -> FakeCoreV1:
    monkeypatch.setattr(data_providers, "_get_k8s_client", lambda: core)
    return core


@pytest.mark.usefixtures("lab_context")
def test_fetch_k8s_status_reads_pods_and_nodes_on_one_bounded_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pods become typed records, nodes are counted Ready, and neither call can hang."""
    core = _serve(
        monkeypatch,
        FakeCoreV1(
            pods=[healthy_pod("api-0", "shop"), crashlooping_pod("exporter-0", "monitoring")],
            nodes=[node("worker-1"), node("worker-2"), node("worker-3"), node("worker-4", "False")],
        ),
    )
    summary = fetch_k8s_status()
    assert (
        summary.connected,
        summary.context,
        [(pod.name, pod.status, pod.ready_containers) for pod in summary.pods],
        (summary.nodes_ready, summary.nodes_total),
        [(method, kwargs.get("_request_timeout")) for method, kwargs in core.calls],
        "3/4 nodes Ready" in k8s_banner(summary),
    ) == (
        True,
        "lab",
        [("api-0", "Running", "1/1"), ("exporter-0", "CrashLoopBackOff", "0/1")],
        (3, 4),
        [
            ("list_pod_for_all_namespaces", DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS),
            ("list_node", DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS),
        ],
        True,
    )


@pytest.mark.usefixtures("lab_context")
def test_pods_still_render_when_the_node_list_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Listing nodes needs a cluster-scoped permission listing pods does not."""
    from kubernetes.client.exceptions import ApiException  # type: ignore[import-untyped]

    _serve(
        monkeypatch,
        FakeCoreV1(pods=[healthy_pod("api-0")], nodes=ApiException(status=403, reason="Forbidden")),
    )
    summary = fetch_k8s_status()
    assert (summary.connected, len(summary.pods), summary.nodes_error) == (
        True,
        1,
        "403 Forbidden",
    )
    assert "nodes: unavailable (403 Forbidden)" in k8s_banner(summary)


@pytest.mark.usefixtures("lab_context")
def test_a_failed_pod_list_reports_the_context_and_the_masked_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The banner names the cluster it tried, and a token in the error is not echoed."""
    _serve(monkeypatch, FakeCoreV1(pods=ConnectionError("refused, token=ghp_" + "a" * 36)))
    summary = fetch_k8s_status()
    banner = k8s_banner(summary)
    assert (
        summary.connected,
        "Disconnected | context lab — ConnectionError: refused" in banner,
        "ghp_" + "a" * 36 in banner,
    ) == (False, True, False)


def test_fetch_k8s_status_failure() -> None:
    """fetch_k8s_status gracefully returns disconnected summary on client failure."""
    with patch("devops_cli.ui.data_providers._get_k8s_client", side_effect=Exception("No cluster")):
        summary = fetch_k8s_status()
        assert isinstance(summary, K8sSummary)
        assert summary.connected is False
        assert summary.pods == []
        assert "No cluster" in summary.error_message


@pytest.mark.usefixtures("lab_context")
def test_the_kubernetes_snapshot_runs_no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """A banner badge ran a CLI on every refresh, with a timeout of half an hour."""
    import subprocess

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the Kubernetes provider started a subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr("devops_cli.core.process.run_subprocess", forbidden)
    _serve(monkeypatch, FakeCoreV1(pods=[healthy_pod("api-0")], nodes=[node("worker-1")]))
    assert fetch_k8s_status().connected is True


def _in_a_pod(monkeypatch: pytest.MonkeyPatch, in_pod: bool) -> None:
    """Set or clear the variables the kubelet gives every pod, whatever this shell has."""
    if in_pod:
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "example.com")
        monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "443")
    else:
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.delenv("KUBERNETES_SERVICE_PORT", raising=False)


@pytest.mark.parametrize(
    ("configured", "kubeconfig", "in_pod", "expected"),
    [
        ("lab", ("ambient",), False, "lab"),
        (None, ("ambient",), False, "ambient"),
        (None, (), False, ""),
        (None, ("ambient",), True, "ambient"),
        (None, (), True, "in-cluster"),
        ("lab", (), True, "lab"),
    ],
)
def test_the_context_named_is_the_configured_one_or_kubectls_current_one(
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
    kubeconfig: tuple[str, ...],
    in_pod: bool,
    expected: str,
) -> None:
    """The banner names the cluster the dashboard actually connects to.

    Only a pod with no kubeconfig context to name connects with its service account.
    """

    def contexts() -> tuple[list[dict[str, str]], dict[str, str]]:
        if not kubeconfig:
            raise ValueError("no kubeconfig")
        return [{"name": kubeconfig[0]}], {"name": kubeconfig[0]}

    _in_a_pod(monkeypatch, in_pod)
    monkeypatch.setattr("devops_cli.k8s.context.resolve_context", lambda: configured)
    monkeypatch.setattr("kubernetes.config.list_kube_config_contexts", contexts)
    assert data_providers._k8s_context_name() == expected


@pytest.mark.parametrize("in_pod", [False, True])
def test_a_context_missing_from_the_kubeconfig_is_reported_as_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, in_pod: bool
) -> None:
    """The banner gave the in-cluster fallback's error, `Service host/port is not set`.

    Inside a pod the fallback connected instead, to a cluster other than the one named.
    """
    from kubernetes.config import kube_config  # type: ignore[import-untyped]

    kubeconfig = tmp_path / "config"
    kubeconfig.write_text(
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [{"name": "other", "cluster": {"server": "https://example.com"}}],
                "users": [{"name": "other", "user": {"token": "dummy"}}],
                "contexts": [{"name": "other", "context": {"cluster": "other", "user": "other"}}],
                "current-context": "other",
            }
        )
    )
    _in_a_pod(monkeypatch, in_pod)
    monkeypatch.setattr(kube_config, "KUBE_CONFIG_DEFAULT_LOCATION", str(kubeconfig))
    monkeypatch.setattr("devops_cli.k8s.context.resolve_context", lambda: "lab")
    banner = k8s_banner(fetch_k8s_status())
    assert (
        "Disconnected | context lab — ConfigException" in banner,
        "Expected object with name lab" in banner,
        "Service" in banner,
    ) == (True, True, False)


def test_fetch_docker_status_success() -> None:
    """fetch_docker_status returns container records when Docker daemon is available."""
    mock_container = MagicMock()
    mock_container.id = "c1a2b3c4d5e6f7a8"
    mock_container.name = "valkey-cache"
    mock_container.image.tags = ["valkey/valkey:8.0-alpine"]
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.list.return_value = [mock_container]

    with patch("devops_cli.ui.data_providers._get_docker_client", return_value=mock_client):
        summary = fetch_docker_status()
        assert isinstance(summary, DockerSummary)
        assert summary.connected is True
        assert len(summary.containers) == 1
        assert summary.containers[0]["name"] == "valkey-cache"
        assert summary.containers[0]["status"] == "running"


def test_fetch_docker_status_failure() -> None:
    """fetch_docker_status gracefully returns disconnected summary on daemon error."""
    with patch(
        "devops_cli.ui.data_providers._get_docker_client", side_effect=Exception("Daemon down")
    ):
        summary = fetch_docker_status()
        assert isinstance(summary, DockerSummary)
        assert summary.connected is False
        assert summary.containers == []


def test_fetch_telemetry_status() -> None:
    """fetch_telemetry_status inspects in-memory metric counters and gauges."""
    from devops_cli.telemetry.metrics import GLOBAL_METRICS

    GLOBAL_METRICS.reset()
    GLOBAL_METRICS.increment_counter("cli.commands.invoked", 3.0)
    GLOBAL_METRICS.set_gauge("memory.rss.bytes", 1024.0)
    GLOBAL_METRICS.record_histogram("request.duration.seconds", 0.042)

    summary = fetch_telemetry_status()
    assert isinstance(summary, TelemetrySummary)
    assert summary.counter_count >= 1
    assert summary.gauge_count >= 1
    assert summary.histogram_count >= 1
    assert "cli.commands.invoked" in summary.counters


def test_fetch_review_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_review_status parses latest session findings and severity counts."""
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260908-120000-sample-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-09-08T12:00:00",
        "personas": ["devsecops"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "status": "UNVERIFIED",
                "verified": False,
            },
            {
                "persona": "qa",
                "severity": "LOW",
                "location": "test.py:10",
                "title": "Missing docstring",
                "status": "VERIFIED",
                "verified": True,
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    summary = fetch_review_status()
    assert isinstance(summary, ReviewSummary)
    assert summary.has_session is True
    assert summary.total_findings == 2
    assert summary.verified_count == 1
    assert summary.unverified_count == 1
    assert summary.severity_distribution["HIGH"] == 1
    assert summary.severity_distribution["LOW"] == 1


def test_fetch_review_status_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_review_status handles missing review directories without error."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    summary = fetch_review_status()
    assert isinstance(summary, ReviewSummary)
    assert summary.has_session is False
    assert summary.total_findings == 0


def test_fetch_valkey_status_success() -> None:
    """fetch_valkey_status returns parsed info and hit ratios."""
    mock_client = MagicMock()
    mock_client.info.return_value = {
        "server": {"valkey_version": "8.0.1", "uptime_in_seconds": "3600"},
        "clients": {"connected_clients": "4"},
        "memory": {"used_memory_human": "2.4M", "used_memory_peak_human": "4.1M"},
        "stats": {
            "keyspace_hits": "800",
            "keyspace_misses": "200",
            "total_commands_processed": "5000",
        },
    }
    mock_client.dbsize.return_value = 150

    with patch("devops_cli.ui.data_providers.ValkeyClient", return_value=mock_client):
        summary = fetch_valkey_status()
        assert isinstance(summary, ValkeySummary)
        assert summary.connected is True
        assert summary.version == "8.0.1"
        assert summary.used_memory == "2.4M"
        assert summary.hit_ratio == 80.0
        assert summary.key_count == 150


def test_fetch_valkey_status_failure() -> None:
    """fetch_valkey_status returns offline summary when connection fails."""
    with patch(
        "devops_cli.ui.data_providers.ValkeyClient", side_effect=Exception("Connection refused")
    ):
        summary = fetch_valkey_status()
        assert isinstance(summary, ValkeySummary)
        assert summary.connected is False
        assert summary.version == "Offline"


# =============================================================================
# Textual DashboardApp Headless Execution Tests
# =============================================================================


@pytest.mark.asyncio
async def test_textual_dashboard_app_lifecycle() -> None:
    """DashboardApp initializes, mounts header, tabs, and footer, and handles tab switching."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        # Initial mount
        assert app.title == "DevOps CLI — Workstation Dashboard"
        assert app.is_running

        # Verify TabbedContent exists
        tabs = app.query_one(TabbedContent)
        assert tabs is not None
        assert app.is_mounted(tabs)

        # Switch to Docker tab via key '2'
        await pilot.press("2")
        await pilot.pause()
        assert tabs.active == "tab-docker"

        # Switch to Telemetry tab via key '3'
        await pilot.press("3")
        await pilot.pause()
        assert tabs.active == "tab-telemetry"

        # Switch to AI Review tab via key '4'
        await pilot.press("4")
        await pilot.pause()
        assert tabs.active == "tab-ai"

        # Switch to Valkey tab via key '5'
        await pilot.press("5")
        await pilot.pause()
        assert tabs.active == "tab-valkey"

        # Switch back to K8s tab via key '1'
        await pilot.press("1")
        await pilot.pause()
        assert tabs.active == "tab-k8s"

        # Refresh action via key 'r'
        await pilot.press("r")
        await pilot.pause()

        # Open help screen via '?'
        await pilot.press("question_mark")
        await pilot.pause(0.05)
        assert isinstance(app.screen, HelpScreen)

        # Dismiss help screen via 'escape'
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert not isinstance(app.screen, HelpScreen)


# =============================================================================
# CLI Command Tests
# =============================================================================


def test_dashboard_app_disable_auto_refresh() -> None:
    """DashboardApp handles refresh_interval=0 without scheduling timer."""
    tui = DashboardApp(refresh_interval=0)
    assert tui._refresh_interval == 0


def test_cli_dashboard_summary_option() -> None:
    """devops dashboard --summary outputs formatted multi-panel overview without starting TUI."""
    res = runner.invoke(dashboard_app, ["--summary"])
    assert res.exit_code == 0
    assert "Workstation Dashboard Summary" in res.output
    assert "Kubernetes Status" in res.output
    assert "Docker Containers" in res.output
    assert "Telemetry Metrics" in res.output
    assert "AI Review Findings" in res.output
    assert "Valkey Caching" in res.output


def test_the_summary_lists_unhealthy_pods_first_and_counts_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first ten pods by API order hid whichever pod was actually failing."""
    pods = [
        PodInfo(name=f"web-{index:02d}", status="Running", ready_containers="1/1")
        for index in range(13)
    ]
    pods[7:7] = [PodInfo(name="crash-a", status="CrashLoopBackOff", unhealthy=True)]
    pods.append(PodInfo(name="crash-b", status="Error", unhealthy=True))
    summary = K8sSummary(connected=True, context="lab", pods=pods)
    monkeypatch.setattr(dashboard_command, "fetch_k8s_status", lambda: summary)
    monkeypatch.setattr(dashboard_command, "fetch_docker_status", DockerSummary)
    monkeypatch.setattr(dashboard_command, "fetch_telemetry_status", TelemetrySummary)
    monkeypatch.setattr(dashboard_command, "fetch_review_status", ReviewSummary)
    monkeypatch.setattr(dashboard_command, "fetch_valkey_status", ValkeySummary)
    res = runner.invoke(dashboard_app, ["--summary"])
    order = [res.output.index(name) for name in ("crash-a", "crash-b", "web-00", "web-07")]
    assert (
        res.exit_code,
        order == sorted(order),
        "web-08" in res.output,
        "5 more pods not shown" in res.output,
        "context lab" in res.output,
    ) == (0, True, False, True, True)


def test_cli_main_dashboard_command() -> None:
    """devops dashboard --summary through main entry point."""
    res = runner.invoke(main_app, ["dashboard", "--summary"])
    assert res.exit_code == 0
    assert "Workstation Dashboard Summary" in res.output


def test_cli_tui_alias_command() -> None:
    """devops tui alias command behaves identically to devops dashboard."""
    res = runner.invoke(main_app, ["tui", "--summary"])
    assert res.exit_code == 0
    assert "Workstation Dashboard Summary" in res.output


def test_cli_dashboard_non_tty_auto_summary() -> None:
    """devops dashboard detects non-TTY stdout and falls back to static summary."""
    with patch("sys.stdout.isatty", return_value=False):
        res = runner.invoke(dashboard_app, [])
        assert res.exit_code == 0
        assert "Workstation Dashboard Summary" in res.output


def test_get_latest_review_session_dir_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _get_latest_review_session_dir rejects directory traversal sequences."""
    from devops_cli.ui.data_providers import _get_latest_review_session_dir

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "../../../outside")
    assert _get_latest_review_session_dir() is None


def test_get_latest_review_session_dir_rejects_forbidden_system_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _get_latest_review_session_dir rejects forbidden system directories."""
    from devops_cli.ui.data_providers import _get_latest_review_session_dir

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "/etc")
    assert _get_latest_review_session_dir() is None
