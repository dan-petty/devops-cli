"""Tests for devops k8s bootstrap-mattermost command."""

from __future__ import annotations

import json
import socket
import subprocess
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s.mattermost_bootstrap import bootstrap_mattermost
from devops_cli.dry_run import get_dry_run_class
from devops_cli.k8s.manifest_plans import plan_k8s_bootstrap_mattermost
from devops_cli.main import app
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

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


def test_bootstrap_mattermost_no_pod(process_fake: ProcessFake) -> None:
    """Verify failure when no Mattermost pod is found."""
    process_fake.answer("kubectl", ProcessAnswer(returncode=0, stdout=""))

    res = runner.invoke(app, ["k8s", "bootstrap-mattermost"])
    assert res.exit_code == 1
    assert "No Mattermost pod found" in res.output


_FULL_FLOW_TABLE = [
    ("get pods", "mattermost-pod-123"),
    ("user list", "admin_user_id: admin (admin@example.com)\n"),
    ("team list", json.dumps([{"id": "team123", "name": "homelab"}])),
    (
        "channel list",
        json.dumps(
            [
                {"id": "chan_alerts", "name": "alerts"},
                {"id": "chan_deploys", "name": "deploys"},
            ]
        ),
    ),
    ("webhook list", "[]"),
    ("webhook create-incoming", json.dumps({"id": "hook_token_abc"})),
    ("command list", "[]"),
    ("command create", json.dumps({"token": "cmd_token_xyz"})),
    ("apply", "secret/configured"),
]


def _handle_full_flow_cmd(call: ProcessCall) -> ProcessAnswer:
    cmd_str = " ".join(call.argv)
    if "get" in call.argv and "secret" in call.argv:
        return ProcessAnswer(returncode=1, stderr="NotFound")
    for key, val in _FULL_FLOW_TABLE:
        if key in cmd_str:
            return ProcessAnswer(returncode=0, stdout=val)
    return ProcessAnswer(returncode=0, stdout="{}")


def test_bootstrap_mattermost_full_flow(
    process_fake: ProcessFake, keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify full onboarding execution: team, channels, webhooks, command, keyring, push."""
    monkeypatch.setenv("DEVOPS_CLI_ARGOCD_GITHUB_APP_ID", "123456")
    monkeypatch.setenv("DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID", "7890123")
    keyring_store.values.update(
        {
            "service_github_app_private_key": "app-key",
            "llm_gateway_master_key": "sk-test-master-key",
            "argocd_github_app_private_key": "argocd-key",
        }
    )

    process_fake.answer("kubectl", _handle_full_flow_cmd)

    res = runner.invoke(app, ["k8s", "bootstrap-mattermost"])
    assert res.exit_code == 0, f"Failed: {res.output}"
    assert "Mattermost bootstrap complete" in res.output

    # Check keyring values
    assert keyring_store.values.get("mattermost_alerts_hook") == "hook_token_abc"
    assert keyring_store.values.get("mattermost_deploys_hook") == "hook_token_abc"
    assert keyring_store.values.get("mattermost_command_token") == "cmd_token_xyz"

    # Check secret push applied secrets
    assert any(c.argv[:2] == ("kubectl", "apply") for c in process_fake.calls)


def test_extract_json_payload_edges() -> None:
    """Verify JSON extraction handles empty string, decode errors, and lists."""
    from devops_cli.commands.k8s.mattermost_bootstrap import _extract_json_payload

    assert _extract_json_payload("") is None
    assert _extract_json_payload("not json {invalid") is None
    assert _extract_json_payload("[1, 2, 3]") == [1, 2, 3]


def test_find_admin_user_id_branches() -> None:
    """Verify user selection handles preferred user, bot filtering, and malformed lines."""
    from devops_cli.commands.k8s.mattermost_bootstrap import _find_admin_user_id

    out = "invalid line\nuser_id_1: specific_user (user@example.com)\nbot_id: calls (calls@example.com)\n"
    assert _find_admin_user_id(out, preferred_user="specific_user") == "user_id_1"
    assert _find_admin_user_id("bot_id: calls (calls@example.com)\n") == "bot_id"
    assert _find_admin_user_id("invalid line") == "admin"


def _handle_missing_resources_cmd(cmd: list[str]) -> str:
    cmd_str = " ".join(cmd)
    table = [
        ("get pods", "mattermost-pod-123"),
        ("user list", "admin_user_id: admin (admin@example.com)\n"),
        ("team create", json.dumps({"id": "team_created_123", "name": "homelab"})),
        ("channel create", json.dumps({"id": "channel_created_456"})),
        ("webhook create-incoming", json.dumps({"id": "hook_token_abc"})),
        ("command create", json.dumps({"token": "cmd_token_xyz"})),
        ("team list", "[]"),
        ("channel list", "[]"),
        ("webhook list", "[]"),
        ("command list", "[]"),
    ]
    for key, val in table:
        if key in cmd_str:
            return val
    return "{}"


def _handle_existing_resources_cmd(cmd: list[str]) -> str:
    cmd_str = " ".join(cmd)
    table = [
        ("get pods", "mattermost-pod-123"),
        ("user list", "admin_user_id: admin (admin@example.com)\n"),
        ("team list", json.dumps([{"id": "team123", "name": "homelab"}])),
        (
            "channel list",
            json.dumps(
                [
                    {"id": "chan_alerts", "name": "alerts"},
                    {"id": "chan_deploys", "name": "deploys"},
                ]
            ),
        ),
        (
            "webhook list",
            json.dumps(
                [
                    {
                        "id": "existing_alert_token",
                        "channel_id": "chan_alerts",
                        "channel_locked": True,
                    },
                    {
                        "id": "existing_deploy_token",
                        "channel_id": "chan_deploys",
                        "channel_locked": True,
                    },
                ]
            ),
        ),
        ("command list", json.dumps([{"trigger": "roadmap", "token": "existing_cmd_token"}])),
    ]
    for key, val in table:
        if key in cmd_str:
            return val
    return "{}"


def test_bootstrap_mattermost_creates_missing_team_and_channels(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Verify team and channel creation when they do not already exist."""

    def _handler(call: ProcessCall) -> ProcessAnswer:
        return ProcessAnswer(returncode=0, stdout=_handle_missing_resources_cmd(list(call.argv)))

    process_fake.answer("kubectl", _handler)
    res = runner.invoke(app, ["k8s", "bootstrap-mattermost", "--no-push-secrets"])
    assert res.exit_code == 0
    assert "Creating Mattermost team 'homelab'..." in res.output
    assert "Creating channel 'alerts'..." in res.output
    assert "Creating channel 'deploys'..." in res.output


def test_bootstrap_mattermost_reuses_existing_resources(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Verify idempotency when webhooks and slash commands already exist."""

    def _handler(call: ProcessCall) -> ProcessAnswer:
        return ProcessAnswer(returncode=0, stdout=_handle_existing_resources_cmd(list(call.argv)))

    process_fake.answer("kubectl", _handler)
    res = runner.invoke(app, ["k8s", "bootstrap-mattermost", "--no-push-secrets"])
    assert res.exit_code == 0
    assert keyring_store.values.get("mattermost_alerts_hook") == "existing_alert_token"
    assert keyring_store.values.get("mattermost_deploys_hook") == "existing_deploy_token"
    assert keyring_store.values.get("mattermost_command_token") == "existing_cmd_token"
