"""Tests for dry-run request plans and classifications across 22 Argo commands.

Issue #2240: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.argo import (
    argo_sync_cmd,
    cd_apps_bootstrap_gitops,
    cd_apps_list,
    cd_apps_status,
    cd_apps_sync,
    fleet_sync,
    gitops_drift,
    gitops_sync,
    gitops_watch,
    rollouts_abort,
    rollouts_analyze,
    rollouts_list,
    rollouts_promote,
    rollouts_restart,
    rollouts_status,
    workflows_list,
    workflows_logs,
    workflows_submit,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    (
        "argo cd apps bootstrap-gitops",
        cd_apps_bootstrap_gitops,
        ["argo", "cd", "apps", "bootstrap-gitops", "--dry-run"],
    ),
    ("argo cd apps list", cd_apps_list, ["argo", "cd", "apps", "list", "--dry-run"]),
    (
        "argo cd apps status",
        cd_apps_status,
        ["argo", "cd", "apps", "status", "test-app", "--dry-run"],
    ),
    ("argo cd apps sync", cd_apps_sync, ["argo", "cd", "apps", "sync", "test-app", "--dry-run"]),
    ("argo cd fleet sync", fleet_sync, ["argo", "cd", "fleet", "sync", "test-app", "--dry-run"]),
    (
        "argo cd gitops sync",
        gitops_sync,
        ["argo", "cd", "gitops", "sync", "--app-name", "test-app", "--dry-run"],
    ),
    (
        "argo cd gitops watch",
        gitops_watch,
        ["argo", "cd", "gitops", "watch", "--app-name", "test-app", "--once", "--dry-run"],
    ),
    ("argo fleet sync", fleet_sync, ["argo", "fleet", "sync", "test-app", "--dry-run"]),
    (
        "argo gitops sync",
        gitops_sync,
        ["argo", "gitops", "sync", "--app-name", "test-app", "--dry-run"],
    ),
    (
        "argo gitops watch",
        gitops_watch,
        ["argo", "gitops", "watch", "--app-name", "test-app", "--once", "--dry-run"],
    ),
    (
        "argo rollouts abort",
        rollouts_abort,
        ["argo", "rollouts", "abort", "test-rollout", "--dry-run"],
    ),
    (
        "argo rollouts analyze",
        rollouts_analyze,
        ["argo", "rollouts", "analyze", "test-rollout", "--dry-run"],
    ),
    ("argo rollouts list", rollouts_list, ["argo", "rollouts", "list", "--dry-run"]),
    (
        "argo rollouts promote",
        rollouts_promote,
        ["argo", "rollouts", "promote", "test-rollout", "--dry-run"],
    ),
    (
        "argo rollouts restart",
        rollouts_restart,
        ["argo", "rollouts", "restart", "test-rollout", "--dry-run"],
    ),
    (
        "argo rollouts status",
        rollouts_status,
        ["argo", "rollouts", "status", "test-rollout", "--dry-run"],
    ),
    ("argo sync", argo_sync_cmd, ["argo", "sync", "test-app", "--dry-run"]),
    ("argo workflows list", workflows_list, ["argo", "workflows", "list", "--dry-run"]),
    ("argo workflows logs", workflows_logs, ["argo", "workflows", "logs", "test-wf", "--dry-run"]),
    (
        "argo workflows submit",
        workflows_submit,
        ["argo", "workflows", "submit", "k8s/argocd/bootstrap/bootstrap.yaml", "--dry-run"],
    ),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("argo cd gitops drift", gitops_drift, ["--dry-run", "argo", "cd", "gitops", "drift"]),
    ("argo gitops drift", gitops_drift, ["--dry-run", "argo", "gitops", "drift"]),
]


@pytest.fixture
def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real subprocess, socket, HTTP client, or Kubernetes client execution occurs during dry run."""

    def _fail_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected process invocation: {args}, {kwargs}")

    def _fail_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected socket call: {args}, {kwargs}")

    def _fail_http(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected HTTP request: {args}, {kwargs}")

    def _fail_k8s(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected Kubernetes API call: {args}, {kwargs}")

    monkeypatch.setattr(subprocess, "run", _fail_process)
    monkeypatch.setattr(subprocess, "Popen", _fail_process)
    monkeypatch.setattr(socket.socket, "connect", _fail_socket)
    monkeypatch.setattr(socket, "getaddrinfo", _fail_socket)
    monkeypatch.setattr(httpx2.Client, "send", _fail_http)
    monkeypatch.setattr(httpx2.Client, "request", _fail_http)
    monkeypatch.setattr(
        "devops_cli.argo.crd.ArgoCRDService._api",
        _fail_k8s,
    )
    monkeypatch.setattr(
        "devops_cli.k8s.service.KubernetesService.read_pod_logs",
        _fail_k8s,
    )


def test_command_dry_run_class_declarations() -> None:
    """Criterion 1: all 20 request-plan commands declare request-plan, and 2 declare no-external-request."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        cls = get_dry_run_class(callback)
        assert cls == "request-plan", (
            f"Expected '{name}' callback to declare dry_run_class('request-plan'), got '{cls}'"
        )

    for name, callback, _ in NO_EXTERNAL_REQUEST_COMMANDS:
        cls = get_dry_run_class(callback)
        assert cls == "no-external-request", (
            f"Expected '{name}' callback to declare dry_run_class('no-external-request'), got '{cls}'"
        )


def test_gaps_file_does_not_contain_the_twenty_two_commands() -> None:
    """Criterion 1: all 22 argo commands are removed from dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [
        "argo cd apps bootstrap-gitops",
        "argo cd apps list",
        "argo cd apps status",
        "argo cd apps sync",
        "argo cd fleet sync",
        "argo cd gitops drift",
        "argo cd gitops sync",
        "argo cd gitops watch",
        "argo fleet sync",
        "argo gitops drift",
        "argo gitops sync",
        "argo gitops watch",
        "argo rollouts abort",
        "argo rollouts analyze",
        "argo rollouts list",
        "argo rollouts promote",
        "argo rollouts restart",
        "argo rollouts status",
        "argo sync",
        "argo workflows list",
        "argo workflows logs",
        "argo workflows submit",
    ]
    remaining = [cmd for cmd in expected_removed if cmd in gaps]
    assert not remaining, f"Commands still present in dry_run_gaps.json: {remaining}"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_make_no_external_requests(
    block_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 2 & 3: devops <command> --dry-run and devops --dry-run <command> make no external calls and print plan."""
    # Test 1: devops <command> --dry-run
    res1 = runner.invoke(app, argv)
    assert res1.exit_code == 0, (
        f"{name} with --dry-run failed with code {res1.exit_code}: {res1.output}"
    )
    assert "1." in res1.output or "Planned" in res1.output or "Plan for" in res1.output, (
        f"{name} output missing request plan: {res1.output}"
    )

    # Test 2: devops --dry-run <command>
    root_argv = ["--dry-run", *[arg for arg in argv if arg != "--dry-run"]]
    res2 = runner.invoke(app, root_argv)
    assert res2.exit_code == 0, (
        f"{name} with root --dry-run failed with code {res2.exit_code}: {res2.output}"
    )
    assert "1." in res2.output or "Planned" in res2.output or "Plan for" in res2.output, (
        f"{name} root dry-run output missing request plan: {res2.output}"
    )


@pytest.mark.parametrize("name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_execute_normally(
    block_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 6: devops --dry-run <cmd> executes normally for mark-only commands without external calls."""
    res = runner.invoke(app, argv)
    assert res.exit_code == 0, f"{name} failed with code {res.exit_code}: {res.output}"


def test_token_request_listed_before_argocd_request(
    block_external_calls: None,
) -> None:
    """Criterion 11: The plan for Argo CD commands lists the token request before the Argo CD request."""
    argocd_cmds = [
        ["argo", "cd", "apps", "list", "--dry-run"],
        ["argo", "cd", "apps", "status", "test-app", "--dry-run"],
        ["argo", "cd", "apps", "sync", "test-app", "--dry-run"],
        ["argo", "cd", "fleet", "sync", "test-app", "--dry-run"],
        ["argo", "cd", "gitops", "sync", "--app-name", "test-app", "--dry-run"],
        ["argo", "sync", "test-app", "--dry-run"],
    ]
    for cmd in argocd_cmds:
        res = runner.invoke(app, cmd)
        assert res.exit_code == 0, f"{cmd} failed: {res.output}"
        # Assert token session request is present in output before the subsequent request
        lines = [line.strip() for line in res.output.splitlines() if line.strip()]
        token_line_idx = -1
        api_line_idx = -1
        for idx, line in enumerate(lines):
            if "api/v1/session" in line or "mint_argocd_token" in line:
                token_line_idx = idx
            elif "api/v1/applications" in line:
                api_line_idx = idx
        assert token_line_idx != -1, f"Token request missing in plan for {cmd}: {res.output}"
        assert api_line_idx != -1, f"API endpoint request missing in plan for {cmd}: {res.output}"
        assert token_line_idx < api_line_idx, (
            f"Token request must appear before API request in plan for {cmd}: {res.output}"
        )


def test_json_dry_run_output_returns_real_result_type(
    block_external_calls: None,
) -> None:
    """Criterion 4: request-plan commands with --format json or --json return real result type marked dry_run: true."""
    # 1. fleet sync
    res_fleet = runner.invoke(
        app, ["argo", "fleet", "sync", "test-app", "--format", "json", "--dry-run"]
    )
    assert res_fleet.exit_code == 0, res_fleet.output
    data_fleet = json.loads(res_fleet.output)
    assert data_fleet.get("dry_run") is True
    assert "requests" in data_fleet
    assert "targets" in data_fleet

    # 2. gitops sync
    res_gitops = runner.invoke(
        app, ["argo", "gitops", "sync", "--app-name", "test-app", "--json", "--dry-run"]
    )
    assert res_gitops.exit_code == 0, res_gitops.output
    data_gitops = json.loads(res_gitops.output)
    assert data_gitops.get("dry_run") is True
    assert "requests" in data_gitops
    assert data_gitops.get("app_name") == "test-app"

    # 3. rollouts analyze
    res_analyze = runner.invoke(
        app, ["argo", "rollouts", "analyze", "test-rollout", "--format", "json", "--dry-run"]
    )
    assert res_analyze.exit_code == 0, res_analyze.output
    data_analyze = json.loads(res_analyze.output)
    assert data_analyze.get("dry_run") is True
    assert "requests" in data_analyze
    assert data_analyze.get("rollout_name") == "test-rollout"


def test_dry_run_plans_match_dispatched_arguments() -> None:
    """Criterion 5: request plans match the argument builders and calls that real runs dispatch."""
    from devops_cli.argo.argo_plans import (
        plan_argo_fleet_sync,
        plan_argo_gitops_sync,
        plan_argo_rollouts_abort,
        plan_argo_rollouts_promote,
        plan_argo_rollouts_restart,
        plan_argocd_apps_list,
        plan_argocd_apps_status,
        plan_argocd_apps_sync,
    )
    from devops_cli.argo.fleet import resolve_cluster_app_name
    from devops_cli.argo.sync import build_sync_request_body

    # 1. Apps list plan
    p_list = plan_argocd_apps_list(base_url="https://argo.example.com")
    assert len(p_list) == 2
    assert p_list[0].method == "POST"
    assert p_list[0].target == "https://argo.example.com/api/v1/session"
    assert p_list[1].method == "GET"
    assert p_list[1].target == "https://argo.example.com/api/v1/applications"

    # 2. Apps status plan
    p_status = plan_argocd_apps_status("test-app", base_url="https://argo.example.com")
    assert len(p_status) == 2
    assert p_status[1].target == "https://argo.example.com/api/v1/applications/test-app"

    # 3. Apps sync plan matches payload builder
    p_sync = plan_argocd_apps_sync(
        "test-app", prune=True, force=False, base_url="https://argo.example.com"
    )
    expected_body = json.dumps(build_sync_request_body(prune=True, force=False))
    assert p_sync[1].stdin == expected_body
    assert p_sync[1].target == "https://argo.example.com/api/v1/applications/test-app/sync"

    # 4. Fleet sync plan matches cluster targets and body
    clusters = ["dev", "prod"]
    p_fleet = plan_argo_fleet_sync(
        "test-app", clusters, prune=False, force=True, base_url="https://argo.example.com"
    )
    assert len(p_fleet) == 1 + len(clusters)
    fleet_body = json.dumps(
        build_sync_request_body(prune=False, force=True, app_namespace="argocd")
    )
    for idx, c in enumerate(clusters, start=1):
        target = resolve_cluster_app_name("test-app", c)
        assert (
            p_fleet[idx].target
            == f"https://argo.example.com/api/v1/applications/{target}/sync?appNamespace=argocd"
        )
        assert p_fleet[idx].stdin == fleet_body

    # 5. Gitops sync plan webhook vs api
    p_gw = plan_argo_gitops_sync("test-app", mode="webhook", base_url="https://argo.example.com")
    assert len(p_gw) == 1
    assert p_gw[0].target == "https://argo.example.com/api/webhook"

    p_ga = plan_argo_gitops_sync(
        "test-app", mode="api", prune=True, force=True, base_url="https://argo.example.com"
    )
    assert len(p_ga) == 2
    assert p_ga[1].target == "https://argo.example.com/api/v1/applications/test-app/sync"

    # 6. Rollouts control-plane patches
    p_abort = plan_argo_rollouts_abort("rollout1", namespace="prod")
    assert p_abort[0].target == "argoproj.io/v1alpha1/namespaces/prod/rollouts/rollout1"
    assert json.loads(p_abort[0].stdin or "{}") == {"spec": {"abort": True}}

    p_promote = plan_argo_rollouts_promote("rollout1", namespace="prod", full=True)
    assert json.loads(p_promote[0].stdin or "{}") == {"status": {"promoteFull": True}}

    p_restart = plan_argo_rollouts_restart("rollout1", namespace="prod")
    assert "restartAt" in json.loads(p_restart[0].stdin or "{}")["spec"]


def test_echo_only_previews_are_gone() -> None:
    """Criterion 7: Echo-only previews of these commands are gone, with no shim."""
    argo_cmd_file = Path("src/devops_cli/commands/argo.py")
    assert argo_cmd_file.exists()
    content = argo_cmd_file.read_text(encoding="utf-8")
    assert "@dry_run_command" not in content, (
        "@dry_run_command still found in src/devops_cli/commands/argo.py"
    )
    assert "render_dry_run_result" not in content, (
        "render_dry_run_result still found in src/devops_cli/commands/argo.py"
    )
