"""Tests for dry-run request plans and classifications across gh api, status, branch-protection, secrets, metrics, and root status.

Issue #2237: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.commands.gh import (
    api_cmd,
    audit_branch_protection_cmd,
    gh_status_cmd,
    list_secrets_cmd,
    project_metrics_cmd,
    rate_limit_cmd,
    sync_branch_protection_cmd,
    sync_secrets_cmd,
)
from devops_cli.commands.status_cmd import status_main
from devops_cli.dry_run import get_dry_run_class
from tests.support.paths import FIXTURES

REQUEST_PLAN_COMMANDS = [
    ("api", api_cmd, ["gh", "api", "repos/owner/repo/issues"]),
    (
        "branch_protection_audit",
        audit_branch_protection_cmd,
        ["gh", "branch-protection", "audit", "-R", "owner/repo"],
    ),
    (
        "branch_protection_sync",
        sync_branch_protection_cmd,
        ["gh", "branch-protection", "sync", "-R", "owner/repo"],
    ),
    ("metrics", project_metrics_cmd, ["gh", "metrics", "-R", "owner/repo"]),
    ("rate_limit", rate_limit_cmd, ["gh", "rate-limit"]),
    ("secrets_list", list_secrets_cmd, ["gh", "secrets", "list", "-R", "owner/repo"]),
    (
        "secrets_sync",
        sync_secrets_cmd,
        ["gh", "secrets", "sync", "-n", "MY_TOKEN", "-R", "owner/repo"],
    ),
    ("gh_status", gh_status_cmd, ["gh", "status"]),
    ("status", status_main, ["status"]),
]


@pytest.mark.parametrize("name,callback,_argv", REQUEST_PLAN_COMMANDS)
def test_commands_declare_request_plan_dry_run_class(
    name: str,
    callback: Callable[..., Any],
    _argv: list[str],
) -> None:
    """Every command in scope declares @dry_run_class('request-plan')."""
    assert get_dry_run_class(callback) == "request-plan", (
        f"Command callback {name} must declare @dry_run_class('request-plan')"
    )


def test_commands_removed_from_gaps_fixture() -> None:
    """All 9 commands are removed from dry_run_gaps.json."""
    gaps_path = FIXTURES / "dry_run_gaps.json"
    with gaps_path.open() as f:
        gaps = json.load(f)

    target_keys = [
        "gh api",
        "gh branch-protection audit",
        "gh branch-protection sync",
        "gh metrics",
        "gh rate-limit",
        "gh rate_limit",
        "gh secrets list",
        "gh secrets sync",
        "gh status",
        "status",
    ]
    for key in target_keys:
        assert key not in gaps, f"Command {key} must be removed from dry_run_gaps.json"


@pytest.mark.parametrize("name,_callback,argv", REQUEST_PLAN_COMMANDS)
def test_commands_execute_zero_external_requests_under_dry_run(
    cli: Callable[..., Any],
    name: str,
    _callback: Callable[..., Any],
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A dry run makes no external network, subprocess, or socket calls."""

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("A dry run attempted an external call")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr("httpx2.HTTPTransport.handle_request", refuse)

    # 1. devops <command> --dry-run
    cmd_args = [*argv]
    if "branch-protection" in argv:
        policy_file = tmp_path / "branch-protection.yml"
        if not policy_file.exists():
            policy_file.write_text("- branch: main\n", encoding="utf-8")
        cmd_args.extend(["-f", str(policy_file)])

    res1 = cli(*cmd_args, "--dry-run")
    assert res1.exit_code == 0, f"Command {name} --dry-run failed: {res1.output}"
    assert (
        "Plan for" in res1.output or "Planned Requests" in res1.output or "Dry run" in res1.output
    )

    # 2. devops --dry-run <command>
    res2 = cli("--dry-run", *cmd_args)
    assert res2.exit_code == 0, f"devops --dry-run {name} failed: {res2.output}"
    assert (
        "Plan for" in res2.output or "Planned Requests" in res2.output or "Dry run" in res2.output
    )


def test_commands_dry_run_json_output(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Commands supporting json return structured output with dry_run: true."""

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("A dry run attempted an external call")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr("httpx2.HTTPTransport.handle_request", refuse)

    # 1. gh rate-limit --format json --dry-run
    res_rl = cli("gh", "rate-limit", "--format", "json", "--dry-run")
    assert res_rl.exit_code == 0
    data_rl = json.loads(res_rl.output)
    assert data_rl.get("dry_run") is True
    assert "requests" in data_rl

    # 2. gh status --json --dry-run
    res_st = cli("gh", "status", "--json", "--dry-run")
    assert res_st.exit_code == 0
    data_st = json.loads(res_st.output)
    assert data_st.get("dry_run") is True

    # 3. status --json --dry-run
    res_s = cli("status", "--json", "--dry-run")
    assert res_s.exit_code == 0
    data_s = json.loads(res_s.output)
    assert data_s.get("dry_run") is True

    # 4. gh branch-protection audit --json --dry-run
    policy_file = tmp_path / "branch-protection.yml"
    policy_file.write_text("- branch: main\n", encoding="utf-8")
    res_bpa = cli(
        "gh",
        "branch-protection",
        "audit",
        "--json",
        "--dry-run",
        "-R",
        "owner/repo",
        "-f",
        str(policy_file),
    )
    assert res_bpa.exit_code == 0
    data_bpa = json.loads(res_bpa.output)
    assert data_bpa.get("dry_run") is True

    # 5. gh metrics --json --dry-run
    res_m = cli("gh", "metrics", "--json", "--dry-run", "-R", "owner/repo")
    assert res_m.exit_code == 0
    data_m = json.loads(res_m.output)
    assert data_m.get("dry_run") is True


def test_dry_run_plans_match_dispatched_arguments() -> None:
    """Planned requests match the argument builders and endpoints exactly."""
    from devops_cli.github.branch_protection import (
        BranchProtectionPolicy,
        audit_branch_protection_args,
        audit_branch_protection_requests,
        sync_branch_protection_args,
        sync_branch_protection_requests,
    )
    from devops_cli.github.metrics import project_metrics_requests
    from devops_cli.github.secrets import (
        get_public_key_args,
        list_secrets_args,
        list_secrets_requests,
        sync_secrets_requests,
        upload_secret_args,
    )
    from devops_cli.telemetry.service_status import service_status_requests

    # 1. branch protection audit
    b_args = audit_branch_protection_args("owner/repo", "main")
    pol = BranchProtectionPolicy(branch="main")
    b_plan = audit_branch_protection_requests("owner/repo", [pol])
    assert list(b_plan[0].argv) == ["gh", *b_args]

    # 2. branch protection sync
    bs_args = sync_branch_protection_args("owner/repo", "main")
    bs_plan = sync_branch_protection_requests("owner/repo", [pol])
    assert list(bs_plan[0].argv) == ["gh", *bs_args]

    # 3. secrets list
    sl_args = list_secrets_args("owner/repo")
    sl_plan = list_secrets_requests("owner/repo")
    assert list(sl_plan[0].argv) == ["gh", *sl_args]

    # 4. secrets sync
    pk_args = get_public_key_args("owner/repo")
    up_args = upload_secret_args("owner/repo", "SEC1")
    ss_plan = sync_secrets_requests("owner/repo", ["SEC1"])
    assert list(ss_plan[0].argv) == ["gh", *pk_args]
    assert list(ss_plan[1].argv) == ["gh", *up_args]

    # 5. metrics
    m_plan = project_metrics_requests("owner/repo", ci_limit=25)
    assert len(m_plan) >= 5

    # 6. status
    st_plan = service_status_requests(("github", "cloudflare"))
    assert len(st_plan) == 2


def test_branch_coverage_for_dry_run_options(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exercise option variations under dry-run to ensure thorough branch coverage."""

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("A dry run attempted an external call")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr("httpx2.HTTPTransport.handle_request", refuse)

    # gh api with method, paginate, jq, template
    res_api = cli(
        "gh",
        "api",
        "repos/owner/repo/pulls",
        "-X",
        "POST",
        "--paginate",
        "-q",
        ".id",
        "-t",
        "{{.id}}",
        "--dry-run",
    )
    assert res_api.exit_code == 0
    assert "Plan for api" in res_api.output

    # gh branch-protection audit with specific branch
    policy_file = tmp_path / "branch-protection.yml"
    policy_file.write_text("- branch: develop\n", encoding="utf-8")
    res_bpa = cli(
        "gh",
        "branch-protection",
        "audit",
        "--branch",
        "develop",
        "--dry-run",
        "-R",
        "owner/repo",
        "-f",
        str(policy_file),
    )
    assert res_bpa.exit_code == 0
    assert "Plan for auditing branch protection" in res_bpa.output

    # status with cloudflare only
    res_cf = cli("status", "--service", "cloudflare", "--dry-run")
    assert res_cf.exit_code == 0
    assert "Plan for status" in res_cf.output

    # secrets sync with empty secret names
    res_empty = cli("gh", "secrets", "sync", "-n", "   ", "--dry-run", "-R", "owner/repo")
    assert res_empty.exit_code == 0
