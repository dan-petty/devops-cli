"""Unit and integration tests for GitHub Pull Request branch update integrations."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import pr_update_branch
from devops_cli.commands.pr import (
    _build_update_branch_cmd,
    _execute_update_branch,
    _parse_update_error,
    _process_candidate_pr_row,
    app,
)


def test_build_update_branch_cmd() -> None:
    """Test construction of GitHub CLI update-branch API command."""
    cmd_plain = _build_update_branch_cmd("owner/repo", 101)
    cmd_sha = _build_update_branch_cmd("owner/repo", 101, expected_head_sha="sha999")

    assert (
        cmd_plain,
        cmd_sha[-2:],
    ) == (
        ["gh", "api", "-X", "PUT", "repos/owner/repo/pulls/101/update-branch"],
        ["-f", "expected_head_sha=sha999"],
    )


def test_parse_update_error() -> None:
    """Test parsing structured error responses from GitHub API."""
    err_simple = json.dumps({"message": "Branch update failed"})
    err_detailed = json.dumps(
        {"message": "Validation Failed", "errors": ["merge commit cannot be clean"]}
    )
    err_plain = "HTTP 500 Server Error"

    assert (
        _parse_update_error(err_simple),
        _parse_update_error(err_detailed),
        _parse_update_error(err_plain),
        _parse_update_error(""),
    ) == (
        "Branch update failed",
        "Validation Failed: merge commit cannot be clean",
        "HTTP 500 Server Error",
        "Unknown API error",
    )


def test_execute_update_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test execution of update branch command on success and failure."""
    mock_success = MagicMock(returncode=0, stdout='{"message": "Updating branch"}', stderr="")
    monkeypatch.setattr("devops_cli.commands.pr.run_gh", lambda *args, **kwargs: mock_success)
    success, msg = _execute_update_branch(["gh", "api"])

    mock_fail = MagicMock(
        returncode=1,
        stdout="",
        stderr=json.dumps({"message": "Merge conflict between base and head"}),
    )
    monkeypatch.setattr("devops_cli.commands.pr.run_gh", lambda *args, **kwargs: mock_fail)
    failed, fail_msg = _execute_update_branch(["gh", "api"])

    assert (success, failed, "Merge conflict" in fail_msg) == (
        True,
        False,
        True,
    )


def test_process_candidate_pr_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test processing draft and active pull request table rows."""
    draft_pr = {
        "number": 10,
        "headRefName": "feat/draft",
        "baseRefName": "main",
        "isDraft": True,
    }
    active_pr = {
        "number": 11,
        "headRefName": "feat/active",
        "baseRefName": "main",
        "isDraft": False,
    }

    monkeypatch.setattr(
        "devops_cli.commands.pr._update_single_pr",
        lambda *args, **kwargs: (True, "Updated"),
    )

    draft_row = _process_candidate_pr_row(draft_pr, repo=None, dry_run=False)
    active_row = _process_candidate_pr_row(active_pr, repo=None, dry_run=False)

    assert (
        draft_row,
        active_row,
    ) == (
        ["#10", "feat/draft", "main", "[dim]draft (skipped)[/dim]"],
        ["#11", "feat/active", "main", "[green]✓ updated[/green]"],
    )


def test_update_single_pr_cli_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update for a single PR succeeding."""
    runner = CliRunner()
    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: {
            "head": {"ref": "feat/my-branch"},
            "base": {"ref": "release/v0.2.20"},
        },
    )
    monkeypatch.setattr(
        "devops_cli.commands.pr._execute_update_branch",
        lambda *args, **kwargs: (True, "Updated"),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        "Successfully updated branch for PR #42" in result.stdout,
    ) == (0, True)


def test_update_single_pr_cli_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update with --dry-run bypassing remote API call."""
    runner = CliRunner()
    execute_called: list[bool] = []
    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: {
            "head": {"ref": "feat/my-branch"},
            "base": {"ref": "release/v0.2.20"},
        },
    )

    def _mock_execute(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        execute_called.append(True)
        return True, "Updated"

    monkeypatch.setattr("devops_cli.commands.pr._execute_update_branch", _mock_execute)

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo", "--dry-run"])
    assert (
        result.exit_code,
        len(execute_called),
        "[dry-run]" in result.output,
    ) == (0, 0, True)


def test_update_single_pr_cli_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update failure exiting with status 1."""
    runner = CliRunner()
    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: {
            "head": {"ref": "feat/my-branch"},
            "base": {"ref": "release/v0.2.20"},
        },
    )
    monkeypatch.setattr(
        "devops_cli.commands.pr._execute_update_branch",
        lambda *args, **kwargs: (False, "merge conflict"),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        "Failed to update PR #42" in result.output,
    ) == (1, True)


def test_update_all_prs_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update --all batch processing."""
    runner = CliRunner()
    candidate_prs = [
        {"number": 201, "headRefName": "feat/a", "baseRefName": "main", "isDraft": False},
        {"number": 202, "headRefName": "feat/b", "baseRefName": "main", "isDraft": True},
    ]
    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_open_prs",
        lambda *args, **kwargs: candidate_prs,
    )
    monkeypatch.setattr(
        "devops_cli.commands.pr._update_single_pr",
        lambda num, **kwargs: (True, "Updated"),
    )

    result = runner.invoke(app, ["update", "--all", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        "Pull Request Branch Update Summary" in result.stdout,
        "#201" in result.stdout,
        "#202" in result.stdout,
    ) == (0, True, True, True)


def test_update_missing_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update without PR number or --all exits with error."""
    runner = CliRunner()
    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    result = runner.invoke(app, ["update"])
    assert (
        result.exit_code,
        "Please specify a PR number or use --all" in result.output,
    ) == (1, True)


def test_mcp_pr_update_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test FastMCP pr_update_branch tool command assembly."""
    captured_cmds: list[list[str]] = []

    def mock_run_mcp_cmd(cmd: list[str], **kwargs: Any) -> str:
        captured_cmds.append(cmd)
        return "OK"

    monkeypatch.setattr("devops_cli.ai.mcp.server._run_mcp_cmd", mock_run_mcp_cmd)

    res = pr_update_branch(
        pr_number=55,
        repo="owner/repo",
        expected_head_sha="sha123",
        dry_run=True,
    )

    expected_cmd = [
        "uv",
        "run",
        "devops",
        "pr",
        "update",
        "55",
        "--repo",
        "owner/repo",
        "--expected-head-sha",
        "sha123",
        "--dry-run",
    ]
    assert (res, captured_cmds) == ("OK", [expected_cmd])
