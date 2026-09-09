"""Test suite for interactive terminal UI dashboard, subsystem data providers, and CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import TabbedContent
from typer.testing import CliRunner

from devops_cli.commands.dashboard import app as dashboard_app
from devops_cli.main import app as main_app
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

runner = CliRunner()


# =============================================================================
# Subsystem Data Provider Tests
# =============================================================================


def test_fetch_k8s_status_success() -> None:
    """fetch_k8s_status returns structured pod records when Kubernetes client succeeds."""
    mock_pod = MagicMock()
    mock_pod.metadata.name = "devops-api-7b8f9c-xyz"
    mock_pod.metadata.namespace = "devops-system"
    mock_pod.status.phase = "Running"
    mock_container_status = MagicMock()
    mock_container_status.ready = True
    mock_container_status.restart_count = 0
    mock_pod.status.container_statuses = [mock_container_status]

    mock_v1 = MagicMock()
    mock_v1.list_pod_for_all_namespaces.return_value.items = [mock_pod]

    with (
        patch("devops_cli.ui.data_providers._get_k8s_client", return_value=mock_v1),
        patch("devops_cli.ui.data_providers.is_minikube_running", return_value=True),
    ):
        summary = fetch_k8s_status()
        assert isinstance(summary, K8sSummary)
        assert summary.connected is True
        assert summary.minikube_active is True
        assert len(summary.pods) == 1
        assert summary.pods[0]["name"] == "devops-api-7b8f9c-xyz"
        assert summary.pods[0]["status"] == "Running"
        assert summary.pods[0]["ready"] == "1/1"


def test_fetch_k8s_status_failure() -> None:
    """fetch_k8s_status gracefully returns disconnected summary on client failure."""
    with patch("devops_cli.ui.data_providers._get_k8s_client", side_effect=Exception("No cluster")):
        summary = fetch_k8s_status()
        assert isinstance(summary, K8sSummary)
        assert summary.connected is False
        assert summary.pods == []
        assert "No cluster" in summary.error_message


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
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        # Dismiss help screen via 'escape'
        await pilot.press("escape")
        await pilot.pause()
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
