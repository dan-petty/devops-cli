"""Tests for dry-run request plans and classifications across gh project, views, and pages.

Issue #2236: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

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
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

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


@pytest.fixture
def no_external_calls(process_fake: ProcessFake) -> None:
    """Fail the test immediately if any external subprocess, gh, or socket is touched."""
    process_fake.answer(
        ["git", "remote", "get-url", "origin"],
        ProcessAnswer(returncode=0, stdout="git@github.com:dan-petty/devops-cli.git\n"),
    )


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
    cli: Callable[..., Any],
    no_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 2: devops <command> --dry-run and devops --dry-run <command> make no external calls."""
    res1 = cli(*argv, "--dry-run")
    assert res1.exit_code == 0, f"{name} with --dry-run failed: {res1.output}"
    assert "1." in res1.output, f"{name} output missing numbered request plan: {res1.output}"

    res2 = cli("--dry-run", *argv)
    assert res2.exit_code == 0, f"{name} with root --dry-run failed: {res2.output}"
    assert "1." in res2.output, f"{name} output missing numbered request plan: {res2.output}"


@pytest.mark.parametrize("name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_run_normally(
    cli: Callable[..., Any],
    no_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 5: devops --dry-run <command> executes normally for mark-only commands."""
    res = cli("--dry-run", *argv)
    assert res.exit_code == 0, f"{name} failed under devops --dry-run: {res.output}"
    assert "Would run delegated command" not in res.output


def test_project_workflows_list_dry_run_json_output(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 3: --format json or --json produces dry_run: true and requests."""
    monkeypatch.setattr(
        "devops_cli.core.repo.get_repo_origin_name", lambda *args, **kwargs: "dan-petty/devops-cli"
    )
    res = cli("gh", "project", "workflows", "list", "--project-number", "5", "--dry-run", "--json")
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


def test_dry_run_plans_match_dispatched_calls(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """Criteria 4 & 6: planned requests match dispatched calls using a recording fake transport."""
    from devops_cli.github import pages, projects
    from devops_cli.github.projects import reset_project_caches

    reset_project_caches()

    process_fake.answer(
        ["git", "remote", "get-url", "origin"],
        ProcessAnswer(returncode=0, stdout="git@github.com:dan-petty/devops-cli.git\n"),
    )
    fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(
            stdout=json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
        ),
    )

    def _side_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        args = list(call.argv)
        if "rate_limit" in args:
            out = json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
        elif any("pages/builds" in a for a in args):
            out = "[]"
        elif any("pages" in a for a in args):
            out = json.dumps(
                {"status": "built", "html_url": "https://dan-petty.github.io/devops-cli"}
            )
        elif "project" in args and "list" in args:
            out = "[]"
        else:
            out = "{}"
        return subprocess.CompletedProcess(args, 0, out, "")

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh"),
        ProcessAnswer(side_effect=_side_effect),
    )

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
        gh_calls_before = [
            c
            for c in process_fake.calls
            if c.argv
            and c.argv[0] == "gh"
            and list(c.argv[1:3]) != ["api", "rate_limit"]
            and list(c.argv[1:]) != ["api", "user", "--jq", ".login"]
        ]
        res = cli(*argv)
        assert res.exit_code == 0, f"Running {argv} failed: {res.output}"
        gh_calls = [
            c
            for c in process_fake.calls
            if c.argv
            and c.argv[0] == "gh"
            and list(c.argv[1:3]) != ["api", "rate_limit"]
            and list(c.argv[1:]) != ["api", "user", "--jq", ".login"]
        ][len(gh_calls_before) :]
        assert len(gh_calls) == len(planned), (
            f"Expected {len(planned)} calls for {argv}, got {len(gh_calls)}"
        )
        for actual_call, planned_req in zip(gh_calls, planned, strict=False):
            _assert_args_match(list(actual_call.argv), planned_req.argv, argv)
