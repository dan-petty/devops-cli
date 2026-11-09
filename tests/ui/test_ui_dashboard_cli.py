"""Tests for CLI dashboard commands, arguments, and non-interactive summary output."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.config.constants import CONST_DASHBOARD_DOMAINS

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.usefixtures("empty_docker_engine")
def test_cli_dashboard_summary_option(cli: Any) -> None:
    """devops dashboard --summary prints all subsystem summaries non-interactively."""
    res = cli(["dashboard", "--summary"])
    assert res.exit_code == 0
    assert "Kubernetes" not in res.output
    assert "Docker" in res.output
    assert "Telemetry" in res.output
    assert "AI Review" in res.output
    assert "Valkey" in res.output


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
@pytest.mark.parametrize(
    "invalid_tab",
    ["nope", "k8s", "ai", "4", "tab-nope", "tab-k8s", "tab-ai", "tab-4", "logs", "tab-logs"],
)
def test_dashboard_cli_rejects_unknown_tab(cli: Any, invalid_tab: str) -> None:
    """CLI rejects tabs other than docker, telemetry, and valkey."""
    res = cli(["dashboard", "--tab", invalid_tab])
    assert res.exit_code == 1
    assert "Unknown tab" in res.output
    for domain in CONST_DASHBOARD_DOMAINS:
        assert domain in res.output
