"""Tests for devops k8s bootstrap-mattermost command."""

from __future__ import annotations

import json
import socket
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s.mattermost_bootstrap import bootstrap_mattermost
from devops_cli.dry_run import get_dry_run_class
from devops_cli.k8s.manifest_plans import plan_k8s_bootstrap_mattermost
from devops_cli.main import app

runner = CliRunner()


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


def test_bootstrap_mattermost_classification() -> None:
    """Verify that bootstrap-mattermost carries request-plan dry-run class."""
    cls = get_dry_run_class(bootstrap_mattermost)
    assert cls == "request-plan"


def test_plan_k8s_bootstrap_mattermost() -> None:
    """Verify plan_k8s_bootstrap_mattermost returns planned requests."""
    plans = plan_k8s_bootstrap_mattermost(team="homelab", context="homelab-k3s", push_secrets=True)
    assert len(plans) == 3
    assert plans[0].target == "pods"
    assert plans[1].target == "exec"
    assert plans[2].target == "secrets"


def test_bootstrap_mattermost_dry_run(block_external_calls: None) -> None:
    """Executing --dry-run prints request plan and makes zero external requests."""
    res = runner.invoke(app, ["k8s", "bootstrap-mattermost", "--dry-run"])
    assert res.exit_code == 0, f"Command failed with output:\n{res.output}"
    assert "Planned requests" in res.output or "kubectl" in res.output


def test_bootstrap_mattermost_no_pod() -> None:
    """Verify failure when no Mattermost pod is found."""
    with patch("devops_cli.commands.k8s.cluster_runtime._run_cmd") as mock_run:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = ""
        mock_run.return_value = mock_res

        res = runner.invoke(app, ["k8s", "bootstrap-mattermost"])
        assert res.exit_code == 1
        assert "No Mattermost pod found" in res.output


def test_bootstrap_mattermost_full_flow() -> None:
    """Verify full onboarding execution: team, channels, webhooks, command, keyring, push."""
    with (
        patch("devops_cli.commands.k8s.cluster_runtime._run_cmd") as mock_run,
        patch("devops_cli.config.os_keyring.store_keyring_secret") as mock_keyring,
        patch("devops_cli.commands.k8s.cluster_secret_push.push_secrets") as mock_push,
    ):

        def _mock_cmd_handler(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            res = MagicMock()
            res.returncode = 0
            if "get" in cmd and "pods" in cmd:
                res.stdout = "mattermost-pod-123"
            elif "user" in cmd and "list" in cmd:
                res.stdout = "admin_user_id: admin (admin@example.com)\n"
            elif "team" in cmd and "list" in cmd:
                res.stdout = json.dumps([{"id": "team123", "name": "homelab"}])
            elif "channel" in cmd and "list" in cmd:
                res.stdout = json.dumps(
                    [
                        {"id": "chan_alerts", "name": "alerts"},
                        {"id": "chan_deploys", "name": "deploys"},
                    ]
                )
            elif "webhook" in cmd and "list" in cmd:
                res.stdout = json.dumps([])
            elif "webhook" in cmd and "create-incoming" in cmd:
                res.stdout = json.dumps({"id": "hook_token_abc"})
            elif "command" in cmd and "list" in cmd:
                res.stdout = json.dumps([])
            elif "command" in cmd and "create" in cmd:
                res.stdout = json.dumps({"token": "cmd_token_xyz"})
            else:
                res.stdout = "{}"
            return res

        mock_run.side_effect = _mock_cmd_handler

        res = runner.invoke(app, ["k8s", "bootstrap-mattermost"])
        assert res.exit_code == 0, f"Failed: {res.output}"
        assert "Mattermost bootstrap complete" in res.output

        # Check keyring calls
        saved_keys = {call.args[0]: call.args[1] for call in mock_keyring.call_args_list}
        assert "mattermost_alerts_hook" in saved_keys
        assert "mattermost_deploys_hook" in saved_keys
        assert "mattermost_command_token" in saved_keys

        # Check secret push was called
        mock_push.assert_called_once()
