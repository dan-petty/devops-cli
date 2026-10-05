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
    success, _msg = _execute_update_branch(["gh", "api"])

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
    dispatch_calls: list[list[str]] = []
    sleep_calls: list[float] = []

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
    monkeypatch.setattr("devops_cli.commands.pr.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(
        "devops_cli.commands.pr.run_gh",
        lambda cmd, *args, **kwargs: dispatch_calls.append(cmd) or MagicMock(returncode=0),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        len(dispatch_calls),
        len(sleep_calls),
        "Successfully updated branch for PR #42" in result.stdout,
    ) == (0, 0, 0, True)


def test_update_single_pr_cli_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update with --dry-run bypassing remote API call."""
    runner = CliRunner()
    execute_called: list[bool] = []
    fetch_called: list[bool] = []
    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: (
            fetch_called.append(True)
            or {
                "head": {"ref": "feat/my-branch"},
                "base": {"ref": "release/v0.2.20"},
            }
        ),
    )

    def _mock_execute(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        execute_called.append(True)
        return True, "Updated"

    monkeypatch.setattr("devops_cli.commands.pr._execute_update_branch", _mock_execute)

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo", "--dry-run"])
    assert (
        result.exit_code,
        len(execute_called),
        len(fetch_called),
        "[dry-run]" in result.output,
    ) == (0, 0, 0, True)


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


def test_sort_prs_oldest_first() -> None:
    """Verify sort_prs_oldest_first orders PRs in ascending order by number (FIFO)."""
    from devops_cli.github.pr_monitor import sort_prs_oldest_first

    newest_first = [
        {"number": 577, "title": "PR 577"},
        {"number": 576, "title": "PR 576"},
        {"number": 573, "title": "PR 573"},
        {"number": 575, "title": "PR 575"},
        {"number": 574, "title": "PR 574"},
    ]
    sorted_prs = sort_prs_oldest_first(newest_first)
    numbers = [p["number"] for p in sorted_prs]
    assert numbers == [573, 574, 575, 576, 577]


def test_update_all_prs_runs_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops pr update --all processes candidates in oldest-first order."""
    runner = CliRunner()
    # Provide descending PR numbers matching gh pr list default order
    descending_prs = [
        {"number": 577, "headRefName": "feat/c", "baseRefName": "main", "isDraft": False},
        {"number": 576, "headRefName": "feat/b", "baseRefName": "main", "isDraft": False},
        {"number": 573, "headRefName": "feat/a", "baseRefName": "main", "isDraft": False},
    ]
    updated_order: list[int] = []

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_open_prs",
        lambda *args, **kwargs: descending_prs,
    )

    def mock_update(num: int, **kwargs: Any) -> tuple[bool, str]:
        updated_order.append(num)
        return True, "Updated"

    monkeypatch.setattr("devops_cli.commands.pr._update_single_pr", mock_update)

    res = runner.invoke(app, ["update", "--all", "--repo", "owner/repo"])
    assert (res.exit_code, updated_order) == (0, [573, 576, 577])


def test_fetch_open_prs_sorts_oldest_first() -> None:
    """Verify _fetch_open_prs sorts gh pr list output in oldest-first order."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.pr import _fetch_open_prs

    raw_output = json.dumps(
        [
            {"number": 300, "headRefName": "feat/3", "baseRefName": "main", "isDraft": False},
            {"number": 100, "headRefName": "feat/1", "baseRefName": "main", "isDraft": False},
            {"number": 200, "headRefName": "feat/2", "baseRefName": "main", "isDraft": False},
        ]
    )
    mock_proc = MagicMock(returncode=0, stdout=raw_output)
    with patch("devops_cli.commands.pr.run_gh", return_value=mock_proc):
        prs = _fetch_open_prs("owner/repo", "main")
        numbers = [p["number"] for p in prs]
        assert numbers == [100, 200, 300]


def test_build_dispatch_ci_cmd() -> None:
    """_build_dispatch_ci_cmd returns proper GitHub CLI API dispatch invocation."""
    from devops_cli.commands.pr import _build_dispatch_ci_cmd

    cmd = _build_dispatch_ci_cmd("owner/repo", "feat/x")
    assert cmd == [
        "gh",
        "api",
        "-X",
        "POST",
        "repos/owner/repo/actions/workflows/ci.yml/dispatches",
        "-f",
        "ref=feat/x",
    ]


def test_update_single_pr_cli_dispatch_ci_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI devops pr update --dispatch-ci dispatches CI on head SHA change."""
    runner = CliRunner()
    calls: list[dict[str, Any]] = []
    fetch_count = [0]
    sleep_calls: list[float] = []

    def mock_fetch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        fetch_count[0] += 1
        sha = "old" if fetch_count[0] == 1 else "new"
        return {
            "head": {"ref": "feat/my-branch", "sha": sha, "repo": {"full_name": "owner/repo"}},
            "base": {"ref": "release/v0.2.20"},
        }

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr("devops_cli.commands.pr._fetch_pr_details", mock_fetch)
    monkeypatch.setattr(
        "devops_cli.commands.pr._execute_update_branch",
        lambda *args, **kwargs: (True, "Updated"),
    )
    monkeypatch.setattr("devops_cli.commands.pr.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(
        "devops_cli.commands.pr.run_gh",
        lambda cmd, *args, **kwargs: calls.append({"cmd": cmd}) or MagicMock(returncode=0),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(calls),
        calls[0]["cmd"],
        "Dispatched ci.yml" in result.stdout or "dispatched" in result.stdout.lower(),
    ) == (
        0,
        1,
        [
            "gh",
            "api",
            "-X",
            "POST",
            "repos/owner/repo/actions/workflows/ci.yml/dispatches",
            "-f",
            "ref=feat/my-branch",
        ],
        True,
    )


def test_update_single_pr_cli_head_sha_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """When head.sha never changes, sleep is called at most attempts times, no dispatch, exits 1."""
    from devops_cli.config.defaults import (
        DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
        DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS,
    )

    runner = CliRunner()
    calls: list[list[str]] = []
    sleep_calls: list[float] = []

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: {
            "head": {
                "ref": "feat/my-branch",
                "sha": "unchanged_sha",
                "repo": {"full_name": "owner/repo"},
            },
            "base": {"ref": "release/v0.2.20"},
        },
    )
    monkeypatch.setattr(
        "devops_cli.commands.pr._execute_update_branch",
        lambda *args, **kwargs: (True, "Updated"),
    )
    monkeypatch.setattr("devops_cli.commands.pr.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(
        "devops_cli.commands.pr.run_gh",
        lambda cmd, *args, **kwargs: calls.append(cmd) or MagicMock(returncode=0),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(calls),
        len(sleep_calls) <= DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
        all(s == DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS for s in sleep_calls),
        "did not change" in result.output,
    ) == (1, 0, True, True, True)


def test_update_single_pr_cli_fork_head(monkeypatch: pytest.MonkeyPatch) -> None:
    """When head.repo is a fork, no poll, no dispatch, output names fork, exits 0."""
    runner = CliRunner()
    calls: list[list[str]] = []
    sleep_calls: list[float] = []

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: {
            "head": {
                "ref": "feat/my-branch",
                "sha": "fork_sha",
                "repo": {"full_name": "other/repo"},
            },
            "base": {"ref": "release/v0.2.20"},
        },
    )
    monkeypatch.setattr(
        "devops_cli.commands.pr._execute_update_branch",
        lambda *args, **kwargs: (True, "Updated"),
    )
    monkeypatch.setattr("devops_cli.commands.pr.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(
        "devops_cli.commands.pr.run_gh",
        lambda cmd, *args, **kwargs: calls.append(cmd) or MagicMock(returncode=0),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(calls),
        len(sleep_calls),
        "other/repo" in result.output,
    ) == (0, 0, 0, True)


def test_update_single_pr_cli_dispatch_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """When dispatch run_gh returns non-zero, output carries parsed API error and exits 1."""
    runner = CliRunner()
    fetch_count = [0]

    def mock_fetch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        fetch_count[0] += 1
        sha = "old" if fetch_count[0] == 1 else "new"
        return {
            "head": {"ref": "feat/my-branch", "sha": sha, "repo": {"full_name": "owner/repo"}},
            "base": {"ref": "release/v0.2.20"},
        }

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr("devops_cli.commands.pr._fetch_pr_details", mock_fetch)
    monkeypatch.setattr(
        "devops_cli.commands.pr._execute_update_branch",
        lambda *args, **kwargs: (True, "Updated"),
    )
    monkeypatch.setattr("devops_cli.commands.pr.time.sleep", lambda s: None)
    monkeypatch.setattr(
        "devops_cli.commands.pr.run_gh",
        lambda *args, **kwargs: MagicMock(
            returncode=1,
            stdout="",
            stderr=json.dumps({"message": "Workflow not found"}),
        ),
    )

    result = runner.invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        "Workflow not found" in result.output,
    ) == (1, True)


def test_update_single_pr_cli_dispatch_ci_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """update 42 --repo owner/repo --dispatch-ci --dry-run: no poll, no sleep, no dispatch."""
    runner = CliRunner()
    calls: list[list[str]] = []
    sleep_calls: list[float] = []
    fetch_calls: list[bool] = []

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_pr_details",
        lambda *args, **kwargs: fetch_calls.append(True) or {},
    )
    monkeypatch.setattr("devops_cli.commands.pr.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(
        "devops_cli.commands.pr.run_gh",
        lambda cmd, *args, **kwargs: calls.append(cmd) or MagicMock(returncode=0),
    )

    result = runner.invoke(
        app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci", "--dry-run"]
    )
    assert (
        result.exit_code,
        len(calls),
        len(sleep_calls),
        len(fetch_calls),
        "[dry-run]" in result.output,
    ) == (0, 0, 0, 0, True)


def test_update_all_prs_cli_dispatch_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """update --all --repo owner/repo --dispatch-ci calls _update_single_pr with dispatch_ci=True."""
    runner = CliRunner()
    candidate_prs = [
        {"number": 201, "headRefName": "feat/a", "baseRefName": "main", "isDraft": False},
        {"number": 202, "headRefName": "feat/b", "baseRefName": "main", "isDraft": True},
    ]
    dispatched_args: list[dict[str, Any]] = []

    monkeypatch.setattr("devops_cli.commands.pr.check_binary", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "devops_cli.commands.pr._fetch_open_prs",
        lambda *args, **kwargs: candidate_prs,
    )

    def mock_update(num: int, **kwargs: Any) -> tuple[bool, str]:
        dispatched_args.append({"num": num, "kwargs": kwargs})
        return True, "dispatched"

    monkeypatch.setattr("devops_cli.commands.pr._update_single_pr", mock_update)

    result = runner.invoke(app, ["update", "--all", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(dispatched_args),
        dispatched_args[0]["kwargs"].get("dispatch_ci"),
        "dispatched" in result.stdout,
        "draft (skipped)" in result.stdout,
    ) == (0, 1, True, True, True)
