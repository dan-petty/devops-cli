"""Unit tests for devops pr command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestPrCommands:
    """Tests for devops pr subcommands."""

    def test_list_prs_requires_gh_cli(self, runner: CliRunner) -> None:
        with patch("shutil.which", return_value=None):
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 1
            assert "GitHub CLI ('gh') is required" in result.output

    def test_list_prs_success(self, runner: CliRunner) -> None:
        mock_output = (
            '[{"number": 13, "title": "fix(security): resolve review findings", '
            '"state": "OPEN", "headRefName": "feat/security", "baseRefName": "release/v0.1.12", '
            '"author": {"login": "devops-user"}, "updatedAt": "2026-08-18T15:00:00Z", '
            '"url": "https://github.com/org/repo/pull/13"}]'
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout=mock_output, stderr=""),
            ),
        ):
            result = runner.invoke(app, ["list", "--state", "open"])
            assert result.exit_code == 0
            assert "#13" in result.output
            assert "feat/security" in result.output
            assert "release/v0.1.12" in result.output

    def test_list_prs_empty(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout="[]", stderr=""),
            ),
        ):
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0
            assert "No pull requests found" in result.output

    def test_view_pr(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout="PR details", stderr=""),
            ) as mock_run,
        ):
            result = runner.invoke(app, ["view", "13", "--repo", "owner/repo"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "view" in args
            assert "13" in args
            assert "owner/repo" in args

    def test_pr_checks(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout="Checks passed", stderr=""),
            ) as mock_run,
        ):
            result = runner.invoke(app, ["checks", "13"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "checks" in args
            assert "13" in args

    def test_edit_pr(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ) as mock_run,
        ):
            result = runner.invoke(
                app, ["edit", "13", "--base", "release/v0.1.12", "--title", "New Title"]
            )
            assert result.exit_code == 0
            assert "Successfully updated PR #13" in result.output
            args = mock_run.call_args[0][0]
            assert "--base" in args
            assert "release/v0.1.12" in args

    def test_create_pr(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._detect_active_release_branch",
                return_value="release/v0.1.12",
            ),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(
                    returncode=0,
                    stdout="https://github.com/org/repo/pull/14",
                    stderr="",
                ),
            ) as mock_run,
        ):
            result = runner.invoke(
                app,
                ["create", "--title", "feat: new feature", "--body", "PR description"],
            )
            assert result.exit_code == 0
            assert "Pull request created successfully" in result.output
            args = mock_run.call_args[0][0]
            assert "--base" in args
            assert "release/v0.1.12" in args

    def test_threads_list_success(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ReviewComment, ReviewThread

        mock_threads = [
            ReviewThread(
                id="PRRT_1",
                is_resolved=False,
                path="src/main.py",
                line=20,
                comments=[ReviewComment(id="C1", body="Fix timeout", author="alice")],
            )
        ]
        with (
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="dan-petty/devops-cli"),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=mock_threads,
            ),
        ):
            res = runner.invoke(app, ["threads", "list", "83"])
            assert res.exit_code == 0
            assert "PRRT_1" in res.output
            assert "Open" in res.output

    def test_threads_reply_success(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ReviewComment

        mock_comment = ReviewComment(id="C_reply_1", body="Fixed", author="bob")
        with patch(
            "devops_cli.github.pr_threads.reply_pr_review_thread",
            return_value=mock_comment,
        ):
            res = runner.invoke(app, ["threads", "reply", "PRRT_1", "Addressed in commit 123"])
            assert res.exit_code == 0
            assert "In-thread reply posted successfully" in res.output
            assert "C_reply_1" in res.output

    def test_threads_resolve_success(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ThreadResolutionResult

        with patch(
            "devops_cli.github.pr_threads.resolve_pr_review_thread",
            return_value=ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True),
        ):
            res = runner.invoke(app, ["threads", "resolve", "PRRT_1"])
            assert res.exit_code == 0
            assert "Thread PRRT_1 marked as resolved" in res.output

    def test_threads_unresolve_success(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ThreadResolutionResult

        with patch(
            "devops_cli.github.pr_threads.unresolve_pr_review_thread",
            return_value=ThreadResolutionResult(thread_id="PRRT_1", is_resolved=False),
        ):
            res = runner.invoke(app, ["threads", "unresolve", "PRRT_1"])
            assert res.exit_code == 0
            assert "reopened (unresolved)" in res.output

    def test_pr_monitor_ready(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=168,
            title="fix: all green",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        mock_result = PRMonitorResult(
            success=True,
            exit_code=0,
            message="Ready",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="dan-petty/devops-cli"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "168"])
            assert res.exit_code == 0
            assert "100% READY FOR MERGING" in res.output

    def test_pr_monitor_failing_checks(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=168,
            title="fix: broken",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="FAILURE")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        mock_result = PRMonitorResult(
            success=False,
            exit_code=1,
            message="Failed",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="dan-petty/devops-cli"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "168"])
            assert res.exit_code == 1
            assert "Remote CI checks failed" in res.output

    def test_pr_monitor_unresolved_threads(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )
        from devops_cli.github.pr_threads import ReviewComment, ReviewThread

        thread = ReviewThread(
            id="PRRT_1",
            is_resolved=False,
            path="main.py",
            comments=[ReviewComment(id="C1", body="Fix this issue", author="copilot")],
        )
        mock_status = PRMonitorStatus(
            number=168,
            title="fix: comments",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[thread],
        )
        mock_result = PRMonitorResult(
            success=False,
            exit_code=2,
            message="Unresolved threads",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="dan-petty/devops-cli"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "168"])
            assert res.exit_code == 2
            assert "unresolved review discussion thread" in res.output

    def test_pr_monitor_auto_detect_branch(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=168,
            title="fix: branch pr",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        mock_result = PRMonitorResult(
            success=True,
            exit_code=0,
            message="Ready",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="dan-petty/devops-cli"),
            patch("devops_cli.github.pr_monitor.resolve_branch_pr_number", return_value=168),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor"])
            assert res.exit_code == 0
            assert "PR #168" in res.output
