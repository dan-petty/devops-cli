"""Unit tests for devops pr command group."""

from __future__ import annotations

import json
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
            '"url": "https://example.com/org/repo/pull/13"}]'
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
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
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
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
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
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
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
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "168"])
            assert res.exit_code == 2
            assert "unresolved review discussion thread" in res.output

    def test_pr_monitor_draft_pr_warning(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=173,
            title="fix: draft pr",
            is_draft=True,
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        mock_result = PRMonitorResult(
            success=False,
            exit_code=2,
            message="Pull request #173 is currently a draft.",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "173"])
            assert res.exit_code == 2
            assert "Pull request #173 is currently a draft" in res.output
            assert "unresolved review discussion thread" not in res.output

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
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.resolve_branch_pr_number", return_value=168),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor"])
            assert res.exit_code == 0
            assert "PR #168" in res.output

    def test_pr_monitor_yaml_and_markdown_formats_with_secret_masking(
        self, runner: CliRunner
    ) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )
        from devops_cli.github.pr_threads import ReviewComment, ReviewThread

        thread = ReviewThread(
            id="PRRT_kw1",
            is_resolved=False,
            path="config.py",
            comments=[
                ReviewComment(
                    id="C1",
                    body="Token leaked: ghp_1234567890abcdefghij in config",
                    author="copilot",
                )
            ],
        )
        mock_status = PRMonitorStatus(
            number=168,
            title="fix: secrets",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[thread],
        )
        mock_result = PRMonitorResult(
            success=False,
            exit_code=2,
            message="Action required",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            # YAML format
            res_yaml = runner.invoke(app, ["monitor", "168", "--format", "yaml"])
            assert res_yaml.exit_code == 2
            assert "<masked-github-token>" in res_yaml.output
            assert "ghp_1234567890abcdefghij" not in res_yaml.output

            # Markdown format
            res_md = runner.invoke(app, ["monitor", "168", "--format", "markdown"])
            assert res_md.exit_code == 2
            assert "# PR #168 Monitoring Status" in res_md.output
            assert "<masked-github-token>" in res_md.output
            assert "ghp_1234567890abcdefghij" not in res_md.output

    def test_pr_monitor_json_format_is_pure_json(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=168,
            title="fix: clean json",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        mock_result = PRMonitorResult(
            success=True,
            exit_code=0,
            message="Clean JSON",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "168", "--format", "json"])
            assert res.exit_code == 0
            # Must parse as clean JSON with no text preceding it
            parsed = json.loads(res.output.strip())
            assert parsed["success"] is True
            assert parsed["exit_code"] == 0

    def test_pr_monitor_invalid_bounds_and_format(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        ):
            res_int = runner.invoke(app, ["monitor", "168", "--interval", "0"])
            assert res_int.exit_code != 0

            res_timeout = runner.invoke(app, ["monitor", "168", "--timeout", "0"])
            assert res_timeout.exit_code != 0

            res_fmt = runner.invoke(app, ["monitor", "168", "--format", "invalid_fmt"])
            assert res_fmt.exit_code != 0
            assert "Unsupported format" in res_fmt.output

    def test_pr_ready_success(self, runner: CliRunner) -> None:
        """devops pr ready converts draft PR to ready and verifies draft: false."""
        mock_preflight = json.dumps({"number": 179, "draft": True})
        mock_post_verify = json.dumps({"number": 179, "draft": False})
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                side_effect=[
                    MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
                    MagicMock(returncode=0, stdout="", stderr=""),
                    MagicMock(returncode=0, stdout=mock_post_verify, stderr=""),
                ],
            ),
        ):
            result = runner.invoke(app, ["ready", "179"])
            assert result.exit_code == 0
            assert "ready for review" in result.output.lower()

    def test_pr_ready_already_ready(self, runner: CliRunner) -> None:
        """devops pr ready exits cleanly if PR is already ready for review."""
        mock_preflight = json.dumps({"number": 179, "draft": False})
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
            ) as mock_subprocess,
        ):
            result = runner.invoke(app, ["ready", "179"])
            assert result.exit_code == 0
            assert "already marked ready for review" in result.output
            assert mock_subprocess.call_count == 1

    def test_pr_ready_graphql_rate_limited(self, runner: CliRunner) -> None:
        """devops pr ready fails closed and informs user when GraphQL rate limit is exceeded."""
        mock_preflight = json.dumps({"number": 179, "draft": True})
        rate_limit_err = "GraphQL: API rate limit already exceeded for user ID 7726889."
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                side_effect=[
                    MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
                    MagicMock(returncode=1, stdout="", stderr=rate_limit_err),
                ],
            ),
        ):
            result = runner.invoke(app, ["ready", "179"])
            assert result.exit_code == 1
            assert "rate limit" in result.output.lower()

    def test_pr_ready_verification_failed_closed(self, runner: CliRunner) -> None:
        """devops pr ready fails closed if PR draft status remains true after command execution."""
        mock_preflight = json.dumps({"number": 179, "draft": True})
        mock_still_draft = json.dumps({"number": 179, "draft": True})
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                side_effect=[
                    MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
                    MagicMock(returncode=0, stdout="", stderr=""),
                    MagicMock(returncode=0, stdout=mock_still_draft, stderr=""),
                ],
            ),
        ):
            result = runner.invoke(app, ["ready", "179"])
            assert result.exit_code == 1
            assert "still in draft state" in result.output

    def test_pr_diff_success(self, runner: CliRunner) -> None:
        """devops pr diff outputs unified diff."""
        mock_diff = "diff --git a/file.py b/file.py\n+new line"
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout=mock_diff, stderr=""),
            ) as mock_subprocess,
        ):
            result = runner.invoke(app, ["diff", "179"])
            assert result.exit_code == 0
            assert "+new line" in result.output
            args = mock_subprocess.call_args[0][0]
            assert "diff" in args
            assert "179" in args

    def test_pr_close_success(self, runner: CliRunner) -> None:
        """devops pr close closes a pull request with optional comment."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ) as mock_subprocess,
        ):
            result = runner.invoke(
                app, ["close", "179", "--comment", "Superseded by new design", "--delete-branch"]
            )
            assert result.exit_code == 0
            assert "closed successfully" in result.output
            args = mock_subprocess.call_args[0][0]
            assert "close" in args
            assert "179" in args
            assert "--comment" in args
            assert "--delete-branch" in args

    def test_pr_view_fallback_on_gh_failure(self, runner: CliRunner) -> None:
        """devops pr view falls back to REST API when gh pr view fails."""
        mock_pr_json = json.dumps(
            {
                "title": "fix: resolve issue",
                "state": "open",
                "draft": True,
                "html_url": "https://example.com/pulls/184",
                "head": {"ref": "feature-branch"},
                "base": {"ref": "main"},
                "user": {"login": "testuser"},
                "body": "Detailed description text",
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                side_effect=[
                    MagicMock(returncode=1, stdout="", stderr="GraphQL: rate limit exceeded"),
                    MagicMock(returncode=0, stdout=mock_pr_json, stderr=""),
                ],
            ),
        ):
            res = runner.invoke(app, ["view", "184"])
            assert res.exit_code == 0
            assert "fix: resolve issue" in res.output
            assert "Detailed description text" in res.output

    def test_pr_checks_fallback_on_gh_failure(self, runner: CliRunner) -> None:
        """devops pr checks falls back to REST check-runs when gh pr checks fails."""
        mock_pr_json = json.dumps(
            {
                "head": {"sha": "abcdef123456"},
            }
        )
        mock_checks_json = json.dumps(
            {
                "check_runs": [
                    {
                        "name": "Validation",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://example.com/runs/1",
                    },
                    {
                        "name": "Analyze",
                        "status": "completed",
                        "conclusion": "failure",
                        "html_url": "https://example.com/runs/2",
                    },
                ]
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                side_effect=[
                    MagicMock(returncode=1, stdout="", stderr="GraphQL: rate limit exceeded"),
                    MagicMock(returncode=0, stdout=mock_pr_json, stderr=""),
                    MagicMock(returncode=0, stdout=mock_checks_json, stderr=""),
                ],
            ),
        ):
            res = runner.invoke(app, ["checks", "184"])
            assert res.exit_code == 0
            assert "Validation" in res.output
            assert "Analyze" in res.output

    def test_pr_edit_fallback(self, runner: CliRunner) -> None:
        """devops pr edit falls back to REST PATCH when gh pr edit fails."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_subprocess",
                side_effect=[
                    MagicMock(returncode=1, stdout="", stderr="GraphQL: rate limit exceeded"),
                    MagicMock(returncode=0, stdout="", stderr=""),
                ],
            ) as mock_sub,
        ):
            res = runner.invoke(
                app, ["edit", "184", "--title", "New Title", "--body", "New Body", "--base", "main"]
            )
            assert res.exit_code == 0
            assert "Successfully updated PR #184" in res.output
            assert mock_sub.call_count == 2
            patch_cmd = mock_sub.call_args_list[1][0][0]
            assert "PATCH" in patch_cmd
            assert "title=New Title" in patch_cmd

    def test_pr_edit_no_changes(self, runner: CliRunner) -> None:
        """devops pr edit warns when no options are provided."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        ):
            res = runner.invoke(app, ["edit", "184"])
            assert res.exit_code == 0
            assert "No changes specified" in res.output
