"""Tests for dry-run request plans and classifications across the pr commands.

Issue #2234: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import (
    check_readiness,
    close_pr,
    create_pr,
    describe_pr,
    diff_pr,
    edit_pr,
    evidence_pr,
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

if TYPE_CHECKING:
    from tests.support.fakes.process import ProcessFake

runner = CliRunner()

CREATE_BODY = (
    "The command checks the form of the title and the body before it opens a draft.\n\n"
    "Closes #42\n\nChange: `openspec/changes/42-check-the-form/`"
)

PR_COMMAND_CALLBACKS = [
    ("pr check-readiness", check_readiness, ["pr", "check-readiness", "42", "-R", "owner/repo"]),
    ("pr checks", pr_checks, ["pr", "checks", "42", "-R", "owner/repo"]),
    ("pr close", close_pr, ["pr", "close", "42", "-R", "owner/repo"]),
    (
        "pr create",
        create_pr,
        ["pr", "create", "-t", "feat: new feature", "-b", CREATE_BODY, "-R", "owner/repo"],
    ),
    (
        "pr describe",
        describe_pr,
        ["pr", "describe", "42", "-s", "check the form", "-R", "owner/repo"],
    ),
    ("pr diff", diff_pr, ["pr", "diff", "42", "-R", "owner/repo"]),
    ("pr edit", edit_pr, ["pr", "edit", "42", "-t", "new title", "-R", "owner/repo"]),
    ("pr evidence", evidence_pr, ["pr", "evidence", "42", "-R", "owner/repo"]),
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


@pytest.mark.parametrize("name,_callback,argv", PR_COMMAND_CALLBACKS)
def test_commands_execute_zero_external_requests_under_dry_run(
    name: str,
    _callback: Callable[..., Any],
    argv: list[str],
    refuse_requests: list[str],
    process_fake: ProcessFake,
) -> None:
    """Under --dry-run, commands make zero external calls, start no program and print planned requests."""
    result = runner.invoke(app, [*argv, "--dry-run"])

    assert result.exit_code == 0, (
        f"{name} --dry-run failed with {result.exit_code}: {result.output}"
    )
    assert any(mark in result.output for mark in ("Planned", "1.", "Plan for")), result.output
    assert process_fake.calls == []


def test_pr_commands_dry_run_json_output(
    refuse_requests: list[str], process_fake: ProcessFake
) -> None:
    """Commands supporting json return structured output with dry_run: true and requests."""
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
