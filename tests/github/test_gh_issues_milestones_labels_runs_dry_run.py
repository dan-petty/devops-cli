"""Tests for dry-run request plans and classifications across gh issues, labels, milestones, runs, roadmap run, and survey.

Issue #2235: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import (
    audit_labels,
    close_milestone,
    edit_issue_cmd,
    edit_milestone_cmd,
    issues_create_cmd,
    issues_list_cmd,
    issues_status_cmd,
    issues_triage_cmd,
    list_labels,
    list_milestones,
    runs_list_cmd,
    runs_view_cmd,
    status_milestone,
    sync_labels,
)
from devops_cli.commands.roadmap import run_cmd as roadmap_run_cmd
from devops_cli.commands.survey import survey_main
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("issues_create", issues_create_cmd, ["gh", "issues", "create", "--title", "test"]),
    ("issues_edit", edit_issue_cmd, ["gh", "issues", "edit", "1", "--title", "new-title"]),
    ("issues_list", issues_list_cmd, ["gh", "issues", "list"]),
    ("issues_status", issues_status_cmd, ["gh", "issues", "status"]),
    ("issues_triage", issues_triage_cmd, ["gh", "issues", "triage"]),
    ("labels_audit", audit_labels, ["gh", "labels", "audit"]),
    ("labels_list", list_labels, ["gh", "labels", "list"]),
    ("labels_sync", sync_labels, ["gh", "labels", "sync"]),
    ("milestones_close", close_milestone, ["gh", "milestones", "close", "v1.0"]),
    (
        "milestones_edit",
        edit_milestone_cmd,
        ["gh", "milestones", "edit", "v1.0", "--title", "v1.1"],
    ),
    ("milestones_list", list_milestones, ["gh", "milestones", "list"]),
    ("milestones_status", status_milestone, ["gh", "milestones", "status", "v1.0"]),
    ("runs_list", runs_list_cmd, ["gh", "runs", "list"]),
    ("runs_view", runs_view_cmd, ["gh", "runs", "view", "123"]),
    ("roadmap_run", roadmap_run_cmd, ["roadmap", "run"]),
    ("survey", survey_main, ["survey"]),
]


def _fail(what: str) -> Callable[..., Any]:
    def fail(*args: object, **_: object) -> Any:
        raise AssertionError(f"the dry run {what}: {str(args[:1])[:120]}")

    return fail


@pytest.fixture
def no_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test immediately if any external subprocess, gh, or socket is touched."""
    from devops_cli.github import rate_limiter

    monkeypatch.setattr(
        "devops_cli.core.repo.get_repo_origin_name", lambda *args, **kwargs: "dan-petty/devops-cli"
    )
    monkeypatch.setattr(rate_limiter, "run_gh", _fail("ran gh"))

    orig_run_subprocess = rate_limiter.run_subprocess

    def safe_run_subprocess(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if cmd and cmd[0] == "gh":
            raise AssertionError(f"the dry run started gh via run_subprocess: {cmd}")
        return orig_run_subprocess(cmd, *args, **kwargs)

    monkeypatch.setattr(rate_limiter, "run_subprocess", safe_run_subprocess)

    orig_popen = subprocess.Popen

    def safe_popen(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "gh":
            raise AssertionError(f"the dry run started gh Popen: {cmd}")
        return orig_popen(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", safe_popen)
    monkeypatch.setattr(socket.socket, "connect", _fail("connected socket"))
    monkeypatch.setattr(socket, "getaddrinfo", _fail("resolved DNS"))


def test_command_dry_run_class_declarations() -> None:
    """Criterion 1: all 16 commands declare request-plan."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        assert get_dry_run_class(callback) == "request-plan", (
            f"Expected {name} to declare request-plan"
        )


def test_gaps_file_does_not_contain_the_sixteen_commands() -> None:
    """Criterion 1: all 16 commands are removed from dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [
        "gh issues create",
        "gh issues edit",
        "gh issues list",
        "gh issues status",
        "gh issues triage",
        "gh labels audit",
        "gh labels list",
        "gh labels sync",
        "gh milestones close",
        "gh milestones edit",
        "gh milestones list",
        "gh milestones status",
        "gh runs list",
        "gh runs view",
        "roadmap run",
        "survey",
    ]
    remaining = [cmd for cmd in expected_removed if cmd in gaps]
    assert not remaining, f"Commands still present in dry_run_gaps.json: {remaining}"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_make_no_external_requests(
    no_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 2: devops <command> --dry-run and devops --dry-run <command> make no external calls."""
    res1 = runner.invoke(app, [*argv, "--dry-run"])
    assert res1.exit_code == 0, f"{name} with --dry-run failed: {res1.output}"
    assert "1." in res1.output or "Planned" in res1.output, (
        f"{name} output missing request plan: {res1.output}"
    )

    res2 = runner.invoke(app, ["--dry-run", *argv])
    assert res2.exit_code == 0, f"{name} with root --dry-run failed: {res2.output}"
    assert "1." in res2.output or "Planned" in res2.output, (
        f"{name} output missing request plan: {res2.output}"
    )


def test_runs_list_json_dry_run_output(
    no_external_calls: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterion 3: --format json produces dry_run: true and requests."""
    monkeypatch.setattr(
        "devops_cli.core.repo.get_repo_origin_name", lambda *args, **kwargs: "dan-petty/devops-cli"
    )
    res = runner.invoke(app, ["gh", "runs", "list", "--dry-run", "--format", "json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["dry_run"] is True
    assert "requests" in data
    assert len(data["requests"]) == 1
    req = data["requests"][0]
    assert req["argv"][:3] == ["gh", "run", "list"]


def test_survey_json_dry_run_output(
    no_external_calls: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterion 3: survey --json --dry-run produces dry_run: true and requests."""
    monkeypatch.setattr(
        "devops_cli.core.repo.get_repo_origin_name", lambda *args, **kwargs: "dan-petty/devops-cli"
    )
    res = runner.invoke(app, ["survey", "--dry-run", "--json", "--dependencies-only"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["dry_run"] is True
    assert "requests" in data
    assert len(data["requests"]) >= 1
    req = data["requests"][0]
    assert req["argv"][0] == "curl"


def test_dry_run_plans_match_dispatched_arguments() -> None:
    """Criterion 4: request plans match the argument builders that real runs dispatch."""
    from devops_cli.github.issues import (
        create_issue_args,
        create_issue_requests,
        issues_edit_args,
        issues_edit_requests,
        issues_list_args,
        issues_list_requests,
    )
    from devops_cli.github.run_view import (
        run_view_args,
        runs_list_args,
        runs_list_requests,
        runs_view_requests,
    )

    # 1. issues create
    c_args = create_issue_args("owner/repo", "Issue Title", "body text")
    c_plan = create_issue_requests("owner/repo", "Issue Title", "body text")
    assert list(c_plan[0].argv) == ["gh", *c_args]

    # 2. issues list
    l_args = issues_list_args("owner/repo", limit=15)
    l_plan = issues_list_requests("owner/repo", limit=15)
    assert list(l_plan[0].argv) == ["gh", *l_args]

    # 3. issues edit
    e_args = issues_edit_args("owner", "repo", 42)
    e_plan = issues_edit_requests("owner/repo", 42, {"title": "Updated"})
    assert list(e_plan[0].argv) == ["gh", *e_args]

    # 4. runs list
    rl_args = runs_list_args(limit=5, repo="owner/repo")
    rl_plan = runs_list_requests(limit=5, repo="owner/repo")
    assert list(rl_plan[0].argv) == ["gh", *rl_args]

    # 5. runs view
    rv_args = run_view_args(12345, log_failed=True, repo="owner/repo")
    rv_plan = runs_view_requests(12345, log_failed=True, repo="owner/repo")
    assert list(rv_plan[0].argv) == ["gh", *rv_args]


def test_additional_branch_coverage_for_dry_run_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from devops_cli.commands.survey import survey_requests
    from devops_cli.github.issues import get_repository_issues, issues_list_args
    from devops_cli.github.run_view import runs_list_args
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

    # 1. Survey with candidates
    res_survey = runner.invoke(
        app,
        ["survey", "--emit-candidates", "--dry-run", "-R", "owner/repo"],
    )
    assert res_survey.exit_code == 0
    assert "Plan for survey" in res_survey.output
    reqs = survey_requests("owner/repo", emit_candidates=True)
    assert len(reqs) > 0

    # 2. Milestones edit with description, state, due_date
    res_m = runner.invoke(
        app,
        [
            "gh",
            "milestones",
            "edit",
            "v1.0",
            "--title",
            "T",
            "--description",
            "D",
            "--state",
            "closed",
            "--due-date",
            "2026-12-01",
            "--dry-run",
            "-R",
            "owner/repo",
        ],
    )
    assert res_m.exit_code == 0
    assert "Plan for editing milestone" in res_m.output

    # 3. Issues edit with milestone, labels, and clear_milestone
    res_ie = runner.invoke(
        app,
        [
            "gh",
            "issues",
            "edit",
            "42",
            "--title",
            "T",
            "--milestone",
            "v1.0",
            "--add-label",
            "bug",
            "--dry-run",
            "-R",
            "owner/repo",
        ],
    )
    assert res_ie.exit_code == 0
    assert "Plan for editing issue" in res_ie.output

    res_ie_clear = runner.invoke(
        app,
        [
            "gh",
            "issues",
            "edit",
            "42",
            "--clear-milestone",
            "--dry-run",
            "-R",
            "owner/repo",
        ],
    )
    assert res_ie_clear.exit_code == 0
    assert "Plan for editing issue" in res_ie_clear.output

    # 4. Runs list with branch
    res_rl = runner.invoke(
        app,
        ["gh", "runs", "list", "--branch", "feature-x", "--dry-run", "-R", "owner/repo"],
    )
    assert res_rl.exit_code == 0
    assert "Plan for listing workflow runs" in res_rl.output

    # 5. Argument builders with options
    args_rl = runs_list_args(branch="main")
    assert "--branch" in args_rl
    assert "main" in args_rl

    args_il = issues_list_args("owner/repo", label="bug", labels=["feature"])
    assert "bug" in args_il
    assert "feature" in args_il

    mock_res = MagicMock(returncode=0, stdout="[]")
    monkeypatch.setattr("devops_cli.github.issues.run_gh", lambda *a, **k: mock_res)
    assert get_repository_issues("owner/repo", label="bug", labels=["feature"]) == []

    # 6. Roadmap run with in-memory store that has no jobs due
    store = InMemoryRoadmapStore()
    monkeypatch.setattr("devops_cli.commands.roadmap._open_store", lambda _r: ("owner/repo", store))
    monkeypatch.setattr("devops_cli.roadmap.run.run_due_jobs", lambda *a, **k: [])
    res_rm = runner.invoke(
        app,
        ["roadmap", "run", "--dry-run", "-R", "owner/repo"],
    )
    assert res_rm.exit_code == 0
    assert "Due: (none)\n" in res_rm.output
    assert "devops roadmap run for owner/repo" in res_rm.output

    # 7. Additional coverage for runs list format=json and _build_create_issue_cmd
    from devops_cli.github.issues import _build_create_issue_cmd

    built_cmd = _build_create_issue_cmd(
        "owner/repo", "Title", "Body", milestone="v1.0", labels=["bug"]
    )
    assert "issue" in built_cmd

    res_json = runner.invoke(
        app,
        ["gh", "runs", "list", "--format", "json", "--dry-run", "-R", "owner/repo"],
    )
    assert res_json.exit_code == 0
    assert '"dry_run": true' in res_json.output
