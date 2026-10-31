"""Tests for dry-run request plans and classifications across gh project, views, and pages.

Issue #2236: The dry-run rule (#412) states that a dry run makes no external request and
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
from typer.testing import CliRunner

from devops_cli.commands.gh import (
    audit_project,
    audit_views,
    link_project,
    list_project_workflows,
    list_projects,
    list_views,
    pages_build_cmd,
    pages_builds_cmd,
    pages_status_cmd,
    pages_verify_cmd,
    show_template,
    spec_views,
    status_project,
    sync_project,
    sync_views,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("pages_build", pages_build_cmd, ["gh", "pages", "build"]),
    ("pages_builds", pages_builds_cmd, ["gh", "pages", "builds"]),
    ("pages_status", pages_status_cmd, ["gh", "pages", "status"]),
    ("project_audit", audit_project, ["gh", "project", "audit"]),
    ("project_link", link_project, ["gh", "project", "link", "1"]),
    ("project_list", list_projects, ["gh", "project", "list"]),
    ("project_sync", sync_project, ["gh", "project", "sync"]),
    ("project_workflows_list", list_project_workflows, ["gh", "project", "workflows", "list"]),
    ("views_audit", audit_views, ["gh", "views", "audit"]),
    ("views_sync", sync_views, ["gh", "views", "sync"]),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("pages_verify", pages_verify_cmd, ["gh", "pages", "verify"]),
    ("project_status", status_project, ["gh", "project", "status"]),
    ("project_template", show_template, ["gh", "project", "template"]),
    ("views_list", list_views, ["gh", "views", "list"]),
    ("views_spec", spec_views, ["gh", "views", "spec"]),
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
    """Criterion 1 & 2: commands declare their dry-run classes."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        assert get_dry_run_class(callback) == "request-plan", (
            f"Expected {name} to declare request-plan"
        )

    for name, callback, _ in NO_EXTERNAL_REQUEST_COMMANDS:
        assert get_dry_run_class(callback) == "no-external-request", (
            f"Expected {name} to declare no-external-request"
        )


def test_gaps_file_does_not_contain_the_fifteen_commands() -> None:
    """Criterion 1: all 15 commands are removed from dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [
        "gh pages build",
        "gh pages builds",
        "gh pages status",
        "gh pages verify",
        "gh project audit",
        "gh project link",
        "gh project list",
        "gh project status",
        "gh project sync",
        "gh project template",
        "gh project workflows list",
        "gh views audit",
        "gh views list",
        "gh views spec",
        "gh views sync",
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
    assert "1." in res1.output, f"{name} output missing numbered request plan: {res1.output}"

    res2 = runner.invoke(app, ["--dry-run", *argv])
    assert res2.exit_code == 0, f"{name} with root --dry-run failed: {res2.output}"
    assert "1." in res2.output, f"{name} output missing numbered request plan: {res2.output}"


@pytest.mark.parametrize("name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_run_normally(
    no_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 5: devops --dry-run <command> executes normally for mark-only commands."""
    res = runner.invoke(app, ["--dry-run", *argv])
    assert res.exit_code == 0, f"{name} failed under devops --dry-run: {res.output}"
    assert "Would run delegated command" not in res.output


def test_project_workflows_list_dry_run_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Criterion 3: --format json or --json produces dry_run: true and requests."""
    monkeypatch.setattr(
        "devops_cli.core.repo.get_repo_origin_name", lambda *args, **kwargs: "dan-petty/devops-cli"
    )
    res = runner.invoke(
        app,
        ["gh", "project", "workflows", "list", "--project-number", "5", "--dry-run", "--json"],
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["dry_run"] is True
    assert "requests" in data
    assert len(data["requests"]) == 4
    # The last request is the GraphQL query for workflows
    req = data["requests"][-1]
    assert req["argv"][:3] == ["gh", "api", "graphql"]
    assert any("query=" in arg for arg in req["argv"])
    assert any("id=" in arg for arg in req["argv"])


def _assert_args_match(actual: list[str], planned: tuple[str, ...], argv: list[str]) -> None:
    if any(arg.startswith("<") and arg.endswith(">") for arg in planned):
        assert len(actual) == len(planned)
        for a, p in zip(actual, planned, strict=False):
            if not (p.startswith("<") and p.endswith(">")):
                assert a == p
        return
    assert actual == list(planned), f"Mismatch for {argv}: actual {actual} != planned {planned}"


def test_dry_run_plans_match_dispatched_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Criteria 4 & 6: planned requests match dispatched calls using a recording fake transport."""
    from devops_cli.github import pages, projects, rate_limiter

    monkeypatch.setattr(
        "devops_cli.core.repo.get_repo_origin_name", lambda *args, **kwargs: "dan-petty/devops-cli"
    )

    recorded_calls: list[list[str]] = []

    def fake_run_gh(args: list[str], *a: Any, **kw: Any) -> subprocess.CompletedProcess[str]:
        recorded_calls.append(list(args))
        if "pages/builds" in args:
            out = "[]"
        elif "pages" in args:
            out = json.dumps(
                {"status": "built", "html_url": "https://dan-petty.github.io/devops-cli"}
            )
        elif "project" in args and "list" in args:
            out = "[]"
        else:
            out = "{}"
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=out, stderr="")

    monkeypatch.setattr(rate_limiter, "run_gh", fake_run_gh)
    monkeypatch.setattr(pages, "run_gh", fake_run_gh)
    monkeypatch.setattr(projects, "run_gh", fake_run_gh)
    monkeypatch.setattr(projects, "_PROJECT_OWNER_ARG_CACHE", {"dan-petty": "dan-petty"})

    cases = [
        (
            ["gh", "pages", "status", "--repo", "dan-petty/devops-cli"],
            pages.pages_status_requests("dan-petty/devops-cli"),
        ),
        (
            ["gh", "pages", "builds", "--repo", "dan-petty/devops-cli", "--limit", "10"],
            pages.pages_builds_requests("dan-petty/devops-cli", limit=10),
        ),
        (
            ["gh", "pages", "build", "--repo", "dan-petty/devops-cli"],
            pages.pages_build_requests("dan-petty/devops-cli"),
        ),
        (
            ["gh", "project", "link", "42", "--repo", "dan-petty/devops-cli"],
            projects.link_project_requests(42, "dan-petty", "devops-cli"),
        ),
        (
            ["gh", "project", "list", "--owner", "dan-petty"],
            projects.project_list_requests("dan-petty"),
        ),
    ]

    for argv, planned in cases:
        recorded_calls.clear()
        res = runner.invoke(app, argv)
        assert res.exit_code == 0, f"Running {argv} failed: {res.output}"
        assert len(recorded_calls) == len(planned), (
            f"Expected {len(planned)} calls for {argv}, got {len(recorded_calls)}"
        )
        for actual_args, planned_req in zip(recorded_calls, planned, strict=False):
            _assert_args_match(actual_args, planned_req.argv, argv)
