"""Tests for CLI dashboard commands, arguments, and non-interactive summary output."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.commands import dashboard as dashboard_command
from devops_cli.config.constants import CONST_DASHBOARD_DOMAINS
from devops_cli.models.k8s import PodInfo
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    ReviewSummary,
    TelemetrySummary,
    ValkeySummary,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.usefixtures("empty_docker_engine")
def test_cli_dashboard_summary_option(cli: Any) -> None:
    """devops dashboard --summary prints all subsystem summaries non-interactively."""
    res = cli(["dashboard", "--summary"])
    assert res.exit_code == 0
    assert "Kubernetes" in res.output
    assert "Docker" in res.output
    assert "Telemetry" in res.output
    assert "AI Review" in res.output
    assert "Valkey" in res.output


def test_the_summary_lists_unhealthy_pods_first_and_counts_the_rest(
    monkeypatch: pytest.MonkeyPatch,
    cli: Any,
    snapshot: SnapshotAssertion,
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
    res = cli(["dashboard", "--summary"])
    order = [res.output.index(name) for name in ("crash-a", "crash-b", "web-00", "web-07")]
    assert (
        res.exit_code,
        order == sorted(order),
        "web-08" in res.output,
        "5 more pods not shown" in res.output,
        "context lab" in res.output,
    ) == (0, True, False, True, True)
    assert res.output == snapshot


@pytest.mark.usefixtures("empty_docker_engine")
def test_cli_main_dashboard_command(cli: Any) -> None:
    """devops dashboard --summary through main entry point."""
    res = cli(["dashboard", "--summary"])
    assert res.exit_code == 0
    assert "Workstation Dashboard Summary" in res.output


@pytest.mark.usefixtures("empty_docker_engine")
def test_cli_tui_alias_command(cli: Any) -> None:
    """devops tui --summary invokes dashboard logic."""
    res = cli(["tui", "--summary"])
    assert res.exit_code == 0
    assert "Workstation Dashboard Summary" in res.output


@pytest.mark.usefixtures("empty_docker_engine")
def test_cli_dashboard_non_tty_auto_summary(cli: Any) -> None:
    """When stdout is not a TTY, devops dashboard falls back to summary mode."""
    with patch("sys.stdout.isatty", return_value=False):
        res = cli(["dashboard"])
        assert res.exit_code == 0
        assert "Workstation Dashboard Summary" in res.output


@pytest.mark.usefixtures("empty_docker_engine")
@pytest.mark.parametrize("invalid_tab", ["nope", "ai", "5", "tab-nope", "tab-ai", "tab-5"])
def test_dashboard_cli_rejects_unknown_tab(cli: Any, invalid_tab: str) -> None:
    """CLI rejects tabs other than k8s, docker, telemetry, valkey and logs (#1883)."""
    res = cli(["dashboard", "--tab", invalid_tab])
    assert res.exit_code == 1
    assert "Unknown tab" in res.output
    for domain in CONST_DASHBOARD_DOMAINS:
        assert domain in res.output
