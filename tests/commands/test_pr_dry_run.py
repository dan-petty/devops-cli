"""Tests for dry-run request plans and classifications across all 17 pr commands.

Issue #2234: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from collections.abc import Callable
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import (
    check_readiness,
    close_pr,
    create_pr,
    diff_pr,
    edit_pr,
    hardening_report_cmd,
    list_prs,
    list_threads,
    monitor_pr_command,
    pr_checks,
    ready_pr,
    reply_thread,
    resolve_all_threads_cmd,
    resolve_threads,
    unresolve_thread,
    view_pr,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app
from tests.support.paths import FIXTURES

runner = CliRunner()

PR_COMMAND_CALLBACKS = [
    ("pr check-readiness", check_readiness, ["pr", "check-readiness", "42", "-R", "owner/repo"]),
    ("pr checks", pr_checks, ["pr", "checks", "42", "-R", "owner/repo"]),
    ("pr close", close_pr, ["pr", "close", "42", "-R", "owner/repo"]),
    ("pr create", create_pr, ["pr", "create", "-t", "feat: new feature", "-R", "owner/repo"]),
    ("pr diff", diff_pr, ["pr", "diff", "42", "-R", "owner/repo"]),
    ("pr edit", edit_pr, ["pr", "edit", "42", "-t", "new title", "-R", "owner/repo"]),
    (
        "pr hardening-report",
        hardening_report_cmd,
        ["pr", "hardening-report", "--pr", "42", "-R", "owner/repo"],
    ),
    ("pr list", list_prs, ["pr", "list", "-R", "owner/repo"]),
    ("pr monitor", monitor_pr_command, ["pr", "monitor", "42", "-R", "owner/repo"]),
    ("pr ready", ready_pr, ["pr", "ready", "42", "-R", "owner/repo"]),
    ("pr threads list", list_threads, ["pr", "threads", "list", "42", "-R", "owner/repo"]),
    ("pr threads reply", reply_thread, ["pr", "threads", "reply", "PRRT_kwDOAbc", "LGTM"]),
    (
        "pr threads resolve",
        resolve_threads,
        ["pr", "threads", "resolve", "PRRT_kwDOAbc", "--without-reply"],
    ),
    (
        "pr threads resolve-all",
        resolve_all_threads_cmd,
        ["pr", "threads", "resolve-all", "42", "-R", "owner/repo"],
    ),
    ("pr threads unresolve", unresolve_thread, ["pr", "threads", "unresolve", "PRRT_kwDOAbc"]),
    ("pr view", view_pr, ["pr", "view", "42", "-R", "owner/repo"]),
    ("pr wait", monitor_pr_command, ["pr", "wait", "42", "-R", "owner/repo"]),
]


@pytest.mark.parametrize("name,callback,_argv", PR_COMMAND_CALLBACKS)
def test_commands_declare_request_plan_class(
    name: str,
    callback: Callable[..., Any],
    _argv: list[str],
) -> None:
    """Every command in scope declares @dry_run_class('request-plan')."""
    assert get_dry_run_class(callback) == "request-plan", (
        f"Command callback {name} must declare @dry_run_class('request-plan')"
    )


def test_pr_commands_removed_from_gaps_fixture() -> None:
    """All 17 pr commands are removed from dry_run_gaps.json."""
    gaps_path = FIXTURES / "dry_run_gaps.json"
    with gaps_path.open(encoding="utf-8") as f:
        gaps = json.load(f)

    for name, _, _ in PR_COMMAND_CALLBACKS:
        assert name not in gaps, f"Command '{name}' must be removed from dry_run_gaps.json"


@pytest.mark.parametrize("name,_callback,argv", PR_COMMAND_CALLBACKS)
def test_commands_execute_zero_external_requests_under_dry_run(
    name: str,
    _callback: Callable[..., Any],
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under --dry-run and devops --dry-run <cmd>, commands make zero external calls and print planned requests."""
    monkeypatch.setattr("devops_cli.commands.pr._require_gh_cli", lambda: None)

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(f"A dry run of '{name}' attempted an external request")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr("devops_cli.github.rate_limiter.run_gh", refuse)
    monkeypatch.setattr("devops_cli.commands.pr.run_gh", refuse)
    monkeypatch.setattr("devops_cli.core.process.run_subprocess", refuse)

    # 1. devops <command> --dry-run
    res1 = runner.invoke(app, [*argv, "--dry-run"])
    assert res1.exit_code == 0, (
        f"devops {' '.join(argv)} --dry-run failed with {res1.exit_code}: {res1.output}"
    )
    assert "Planned" in res1.output or "1." in res1.output or "Plan for" in res1.output, (
        f"Output of '{name} --dry-run' missing planned requests: {res1.output}"
    )

    # 2. devops --dry-run <command>
    res2 = runner.invoke(app, ["--dry-run", *argv])
    assert res2.exit_code == 0, (
        f"devops --dry-run {' '.join(argv)} failed with {res2.exit_code}: {res2.output}"
    )
    assert "Planned" in res2.output or "1." in res2.output or "Plan for" in res2.output, (
        f"Output of '--dry-run {name}' missing planned requests: {res2.output}"
    )


def test_pr_commands_dry_run_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Commands supporting json return structured output with dry_run: true and requests."""
    monkeypatch.setattr("devops_cli.commands.pr._require_gh_cli", lambda: None)

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("A dry run attempted an external request")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr("devops_cli.github.rate_limiter.run_gh", refuse)
    monkeypatch.setattr("devops_cli.commands.pr.run_gh", refuse)

    # 1. pr monitor --format json --dry-run
    res_mon = runner.invoke(
        app, ["pr", "monitor", "42", "-R", "owner/repo", "--format", "json", "--dry-run"]
    )
    assert res_mon.exit_code == 0, res_mon.output
    data_mon = json.loads(res_mon.output)
    assert data_mon.get("dry_run") is True
    assert "requests" in data_mon
    assert len(data_mon["requests"]) > 0

    # 2. pr wait --format json --dry-run
    res_wait = runner.invoke(
        app, ["pr", "wait", "42", "-R", "owner/repo", "--format", "json", "--dry-run"]
    )
    assert res_wait.exit_code == 0, res_wait.output
    data_wait = json.loads(res_wait.output)
    assert data_wait.get("dry_run") is True
    assert "requests" in data_wait

    # 3. pr hardening-report --format json --dry-run
    res_hr = runner.invoke(
        app,
        [
            "pr",
            "hardening-report",
            "--pr",
            "42",
            "-R",
            "owner/repo",
            "--format",
            "json",
            "--dry-run",
        ],
    )
    assert res_hr.exit_code == 0, res_hr.output
    data_hr = json.loads(res_hr.output)
    assert data_hr.get("dry_run") is True
    assert "requests" in data_hr

    # 4. pr threads list --format json --dry-run
    res_th = runner.invoke(
        app, ["pr", "threads", "list", "42", "-R", "owner/repo", "--format", "json", "--dry-run"]
    )
    assert res_th.exit_code == 0, res_th.output
    data_th = json.loads(res_th.output)
    assert data_th.get("dry_run") is True
    assert "requests" in data_th


def test_dry_run_plans_match_dispatched_arguments() -> None:
    """Planned requests match the argument builders and endpoints exactly."""
    from devops_cli.github.check_verdict import pr_checks_args
    from devops_cli.github.pr_plans import (
        plan_pr_checks,
        plan_pr_close,
        plan_pr_create,
        plan_pr_diff,
        plan_pr_edit,
        plan_pr_list,
        plan_pr_view,
        pr_close_args,
        pr_create_args,
        pr_diff_args,
        pr_edit_args,
        pr_list_args,
        pr_view_args,
    )

    # 1. pr list
    plan_list = plan_pr_list("open", 30, "owner/repo")
    assert plan_list[0].argv == tuple(pr_list_args("open", 30, "owner/repo"))

    # 2. pr view
    plan_view = plan_pr_view(42, "owner/repo")
    assert plan_view[0].argv == tuple(pr_view_args(42, "owner/repo"))

    # 3. pr checks
    plan_checks = plan_pr_checks(42, "owner/repo")
    assert plan_checks[0].argv == tuple(pr_checks_args(42, "owner/repo"))

    # 4. pr edit
    plan_edit = plan_pr_edit(42, "main", "title", "body", "owner/repo", "v1.0")
    assert plan_edit[0].argv == tuple(
        pr_edit_args(42, "main", "title", "body", "owner/repo", "v1.0")
    )

    # 5. pr create
    plan_create = plan_pr_create("feat: new", "body", "main", "owner/repo")
    assert plan_create[0].argv == tuple(pr_create_args("feat: new", "body", "main", "owner/repo"))

    # 6. pr diff
    plan_diff = plan_pr_diff(42, "auto", "owner/repo")
    assert plan_diff[0].argv == tuple(pr_diff_args(42, "auto", "owner/repo"))

    # 7. pr close
    plan_close = plan_pr_close(42, "closing", True, "owner/repo")
    assert plan_close[0].argv == tuple(pr_close_args(42, "closing", True, "owner/repo"))
