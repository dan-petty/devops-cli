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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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

    def test_threads_list_error_exit(self, runner: CliRunner) -> None:
        from devops_cli.exceptions.git import GitHubOperationError

        with (
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                side_effect=GitHubOperationError("API failure"),
            ),
        ):
            res = runner.invoke(app, ["threads", "list", "83"])
            assert res.exit_code == 1
            assert "Failed to retrieve PR #83 review threads: API failure" in res.output

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

    def test_threads_resolve_all_success(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ThreadResolutionResult

        mock_res = ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True, success=True)
        with (
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.github.pr_threads.resolve_all_pr_review_threads",
                return_value=[mock_res],
            ) as mock_resolve_all,
        ):
            res = runner.invoke(app, ["threads", "resolve-all", "83"])
            assert res.exit_code == 0
            assert "Resolved 1/1 review thread(s) on PR #83" in res.output
            mock_resolve_all.assert_called_once_with("owner", "repo", 83, only_replied=True)

    def test_threads_resolve_all_empty(self, runner: CliRunner) -> None:
        with (
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.github.pr_threads.resolve_all_pr_review_threads",
                return_value=[],
            ),
        ):
            res = runner.invoke(app, ["threads", "resolve-all", "83"])
            assert res.exit_code == 0
            assert "No unresolved candidate review threads found on PR #83" in res.output

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

    def test_pr_monitor_blocked_by_protection(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=182,
            title="fix: blocked pr",
            is_draft=False,
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable_state="blocked",
        )
        mock_result = PRMonitorResult(
            success=False,
            exit_code=2,
            message="PR #182 is blocked from merging by GitHub: awaiting required review approval.",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "182"])
            assert res.exit_code == 2
            assert "blocked from merging" in res.output
            assert "100% READY FOR MERGING" not in res.output

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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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

    def test_pr_ready_blocks_on_failing_checks(self, runner: CliRunner) -> None:
        """devops pr ready blocks conversion when check runs are failing."""
        mock_preflight = json.dumps({"number": 179, "draft": True, "head": {"sha": "sha123"}})
        mock_check_runs = json.dumps(
            {"check_runs": [{"name": "CI Quality Gate", "conclusion": "failure"}]}
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                side_effect=[
                    MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
                    MagicMock(returncode=0, stdout=mock_check_runs, stderr=""),
                ],
            ),
        ):
            result = runner.invoke(app, ["ready", "179"])
            assert result.exit_code == 1
            assert "Cannot mark PR #179 as ready for review: 1 check(s) failed" in result.output
            assert "CI Quality Gate (failure)" in result.output
            assert "Pass --force to override" in result.output

    def test_pr_ready_force_overrides_failing_checks(self, runner: CliRunner) -> None:
        """devops pr ready --force bypasses failing checks verification."""
        mock_preflight = json.dumps({"number": 179, "draft": True, "head": {"sha": "sha123"}})
        mock_post_verify = json.dumps({"number": 179, "draft": False})
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                side_effect=[
                    MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
                    MagicMock(returncode=0, stdout="", stderr=""),
                    MagicMock(returncode=0, stdout=mock_post_verify, stderr=""),
                ],
            ),
        ):
            result = runner.invoke(app, ["ready", "179", "--force"])
            assert result.exit_code == 0
            assert "ready for review" in result.output.lower()

    def test_pr_diff_success(self, runner: CliRunner) -> None:
        """devops pr diff outputs unified diff."""
        mock_diff = "diff --git a/file.py b/file.py\n+new line"
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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
                "devops_cli.commands.pr.run_gh",
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

    def test_pr_edit_with_milestone(self, runner: CliRunner) -> None:
        """devops pr edit passes --milestone to gh pr edit and succeeds."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh", return_value=MagicMock(returncode=0)
            ) as mock_run,
        ):
            res = runner.invoke(app, ["edit", "184", "--milestone", "v0.2.19"])
            assert res.exit_code == 0
            assert "Successfully updated PR #184" in res.output
            assert "--milestone" in mock_run.call_args[0][0]
            assert "v0.2.19" in mock_run.call_args[0][0]

    def test_list_prs_rest_fallback(self, runner: CliRunner) -> None:
        """devops pr list falls back to REST when GraphQL fails."""
        mock_rest_prs = json.dumps(
            [
                {
                    "number": 187,
                    "title": "feat: test pr",
                    "head": {"ref": "feat/test"},
                    "base": {"ref": "main"},
                    "user": {"login": "test-user"},
                    "updated_at": "2026-09-13T12:00:00Z",
                    "html_url": "https://example.com/pr/187",
                }
            ]
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                side_effect=[
                    MagicMock(returncode=1, stdout="", stderr="GraphQL: rate limit exceeded"),
                    MagicMock(returncode=0, stdout=mock_rest_prs, stderr=""),
                ],
            ),
        ):
            res = runner.invoke(app, ["list"])
            assert res.exit_code == 0
            assert "#187" in res.output
            assert "feat: test pr" in res.output

    def test_check_readiness_clean(self, runner: CliRunner) -> None:
        """devops pr check-readiness passes when 0 blockers."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert (res.exit_code, "satisfies merge readiness" in res.output) == (0, True)

    def test_check_readiness_already_merged(self, runner: CliRunner) -> None:
        """devops pr check-readiness passes when PR is already merged."""
        mock_pr = json.dumps(
            {
                "state": "closed",
                "merged": True,
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert (res.exit_code, "already merged into base branch" in res.output) == (0, True)

    def test_check_readiness_closed_unmerged(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails when PR is closed without being merged."""
        mock_pr = json.dumps(
            {
                "state": "closed",
                "merged": False,
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert (res.exit_code, "closed without being merged" in res.output) == (1, True)

    def test_check_readiness_conflicts(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails on merge conflicts."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": False,
                "mergeable_state": "dirty",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert res.exit_code == 1
            assert "merge conflicts" in res.output

    def test_check_readiness_unresolved_threads(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails when unresolved review threads exist."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        mock_thread = MagicMock(
            id="T1",
            is_resolved=False,
            path="src/main.py",
            line=10,
            comments=[MagicMock(author="copilot", body="Fix this bug")],
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=[mock_thread],
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert res.exit_code == 1
            assert "unresolved review discussion thread" in res.output
            assert "PR Review Discussion Threads" in res.output

    def test_check_readiness_auto_resolve_success(self, runner: CliRunner) -> None:
        """devops pr check-readiness auto-resolves replied review threads when --auto-resolve is set."""
        from devops_cli.github.pr_threads import ThreadResolutionResult

        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        mock_res = ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True, success=True)
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch(
                "devops_cli.github.pr_threads.resolve_all_pr_review_threads",
                return_value=[mock_res],
            ) as mock_auto_resolve,
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=[],
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--auto-resolve"])
            assert res.exit_code == 0
            assert "Auto-resolved 1 replied review discussion thread(s)" in res.output
            assert "satisfies merge readiness" in res.output
            mock_auto_resolve.assert_called_once_with("owner", "repo", 187, only_replied=True)

    def test_check_readiness_allow_replied_threads_all_replied(self, runner: CliRunner) -> None:
        """devops pr check-readiness passes when unresolved threads have replies and --allow-replied-threads is set."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        mock_thread = MagicMock(
            id="T1",
            is_resolved=False,
            path="src/main.py",
            line=10,
            comments=[
                MagicMock(author="copilot", body="Fix this bug"),
                MagicMock(author="developer", body="Fixed in commit abc"),
            ],
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=[mock_thread],
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--allow-replied-threads"])
            assert res.exit_code == 0
            assert "satisfies merge readiness" in res.output
            assert "awaiting reviewer resolution" in res.output

    def test_check_readiness_allow_replied_threads_unreplied_fails(self, runner: CliRunner) -> None:
        """devops pr check-readiness still fails with --allow-replied-threads if an unreplied thread exists."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        mock_replied = MagicMock(
            id="T1",
            is_resolved=False,
            path="src/main.py",
            line=10,
            comments=[
                MagicMock(author="copilot", body="Fix"),
                MagicMock(author="dev", body="Fixed"),
            ],
        )
        mock_unreplied = MagicMock(
            id="T2",
            is_resolved=False,
            path="src/other.py",
            line=20,
            comments=[MagicMock(author="copilot", body="Unaddressed")],
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=[mock_replied, mock_unreplied],
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--allow-replied-threads"])
            assert res.exit_code == 1
            assert "unreplied review discussion thread" in res.output

    def test_check_readiness_fails_on_a_draft_without_any_flag(self, runner: CliRunner) -> None:
        """A draft cannot be merged, so it blocks by default rather than on request.

        `--require-ready` made the safe answer opt-in, and GitHub reports
        `mergeable_state: clean` for a draft, so the command called one ready.
        """
        mock_pr = json.dumps(
            {
                "draft": True,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
                "head": {"sha": "a" * 40},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
            patch("devops_cli.commands.pr._failing_check_runs", return_value=([], [])),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert res.exit_code == 1
            assert "draft status" in res.output

    def test_check_readiness_mergeable_null(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails when mergeability is null/unresolved."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": None,
                "mergeable_state": "unknown",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert res.exit_code == 1
            assert "mergeability is unresolved" in res.output

    def test_check_readiness_mergeable_state_blocked(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails when mergeable_state is blocked."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "blocked",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert res.exit_code == 1
            assert "merge state is blocked" in res.output

    def test_check_readiness_allow_blocked_state(self, runner: CliRunner) -> None:
        """devops pr check-readiness passes when mergeable_state is blocked and --allow-blocked-state is set."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "blocked",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_pr, stderr=""),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--allow-blocked-state"])
            assert res.exit_code == 0
            assert "satisfies merge readiness" in res.output

    def test_pr_diff_mask_secrets(self, runner: CliRunner) -> None:
        """devops pr diff masks secret tokens in output."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(
                    returncode=0,
                    stdout="+ export GITHUB_TOKEN=ghp_secrettoken1234567890abcdefghijklmn\n",
                    stderr="",
                ),
            ),
        ):
            res = runner.invoke(app, ["diff", "187"])
            assert res.exit_code == 0
            assert "ghp_secrettoken" not in res.output

    def test_pr_diff_error_masked(self, runner: CliRunner) -> None:
        """devops pr diff masks secrets in error output."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="Failed diff token ghp_secrettoken1234567890abcdefghijklmn",
                ),
            ),
        ):
            res = runner.invoke(app, ["diff", "187"])
            assert res.exit_code == 1
            assert "ghp_secrettoken" not in res.output

    def test_pr_close_error_masked(self, runner: CliRunner) -> None:
        """devops pr close masks secrets in error output."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="Failed close token ghp_secrettoken1234567890abcdefghijklmn",
                ),
            ),
        ):
            res = runner.invoke(app, ["close", "187"])
            assert res.exit_code == 1
            assert "ghp_secrettoken" not in res.output

    def test_fallback_create_pr_existing(self, runner: CliRunner) -> None:
        """_fallback_create_pr discovers existing PR and avoids duplicate POST."""
        from devops_cli.commands.pr import _fallback_create_pr

        mock_existing = json.dumps(
            [
                {
                    "number": 187,
                    "html_url": "https://github.com/dan-petty/devops-cli/pull/187",
                    "base": {"ref": "release/v0.2.17"},
                }
            ]
        )
        with (
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.commands.pr._detect_current_branch", return_value="feat/test"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_existing, stderr=""),
            ) as mock_sub,
        ):
            result = _fallback_create_pr(
                title="test",
                body="test",
                base="release/v0.2.17",
                draft=False,
            )
            assert result is True
            # Verified that only the query was called, not a POST
            assert len(mock_sub.call_args_list) == 1
            assert "pulls?head=owner:feat/test" in mock_sub.call_args[0][0][2]

    def test_pr_list_fallback_merged_filter(self) -> None:
        """_render_pr_list_fallback filters merged_at when state is merged."""
        from devops_cli.commands.pr import _render_pr_list_fallback

        mock_prs = json.dumps(
            [
                {
                    "number": 1,
                    "title": "PR 1",
                    "merged_at": "2026-09-12T10:00:00Z",
                    "user": {"login": "user1"},
                    "base": {"ref": "main"},
                    "head": {"ref": "feat/1"},
                },
                {
                    "number": 2,
                    "title": "PR 2",
                    "merged_at": None,
                    "user": {"login": "user2"},
                    "base": {"ref": "main"},
                    "head": {"ref": "feat/2"},
                },
            ]
        )
        with (
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_prs, stderr=""),
            ),
            patch("devops_cli.commands.pr._render_pr_table") as mock_table,
        ):
            result = _render_pr_list_fallback(state="merged", limit=10)
            assert result is True
            # Only PR 1 should be passed to _render_pr_table
            rendered = mock_table.call_args[0][0]
            assert len(rendered) == 1
            assert rendered[0]["number"] == 1

    def test_create_pr_fallback_on_nonzero(self, runner: CliRunner) -> None:
        """devops pr create falls back to _fallback_create_pr when gh pr create fails."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._detect_active_release_branch",
                return_value="release/v0.2.17",
            ),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=1, stdout="", stderr="GraphQL error"),
            ),
            patch("devops_cli.commands.pr._fallback_create_pr", return_value=True) as mock_fallback,
        ):
            result = runner.invoke(app, ["create", "--title", "test title", "--body", "test body"])
            assert result.exit_code == 0
            assert mock_fallback.called

    def test_create_pr_draft(self, runner: CliRunner) -> None:
        """devops pr create --draft passes --draft to gh CLI."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._detect_active_release_branch",
                return_value="release/v0.2.17",
            ),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ) as mock_sub,
        ):
            result = runner.invoke(
                app, ["create", "--title", "draft pr", "--draft", "--base", "main"]
            )
            assert result.exit_code == 0
            cmd = mock_sub.call_args[0][0]
            assert "--draft" in cmd

    def test_ready_pr_already_ready(self, runner: CliRunner) -> None:
        """devops pr ready detects when PR is already non-draft."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._fetch_pr_details",
                return_value={"draft": False, "number": 184},
            ),
        ):
            result = runner.invoke(app, ["ready", "184"])
            assert result.exit_code == 0
            assert "already marked ready for review" in result.output

    def test_ready_pr_rate_limit(self, runner: CliRunner) -> None:
        """devops pr ready handles GraphQL rate limits gracefully."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._fetch_pr_details",
                return_value={"draft": True, "number": 184},
            ),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="GraphQL error: API rate limit exceeded",
                ),
            ),
        ):
            result = runner.invoke(app, ["ready", "184"])
            assert result.exit_code == 1
            assert "GitHub GraphQL rate limit exceeded" in result.output

    def test_ready_pr_success(self, runner: CliRunner) -> None:
        """devops pr ready marks draft PR as ready."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._fetch_pr_details",
                side_effect=[{"draft": True, "number": 184}, {"draft": False, "number": 184}],
            ),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ),
        ):
            result = runner.invoke(app, ["ready", "184"])
            assert result.exit_code == 0
            assert "marked as ready for review" in result.output

    def test_check_readiness_no_repo(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails when repo cannot be resolved."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value=None),
        ):
            result = runner.invoke(app, ["check-readiness"])
            assert result.exit_code == 1
            assert "Target repository must be in OWNER/REPO format" in result.output

    def test_check_readiness_not_found(self, runner: CliRunner) -> None:
        """devops pr check-readiness fails when PR details cannot be retrieved."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.commands.pr._fetch_pr_details", return_value=None),
        ):
            result = runner.invoke(app, ["check-readiness", "999"])
            assert result.exit_code == 1
            assert "Unable to retrieve details" in result.output

    def test_render_threads_table_masks_secrets(self) -> None:
        """_render_threads_table masks secret tokens in comment bodies."""
        from devops_cli.commands.pr import _render_threads_table

        mock_thread = MagicMock(
            id="THREAD_SEC_1",
            is_resolved=False,
            path="src/config.py",
            line=42,
            comments=[
                MagicMock(
                    author="bot",
                    body="Leak token: ghp_supersecrettoken1234567890abcdefghijklmn here",
                )
            ],
        )
        with patch("devops_cli.commands.pr.print_table") as mock_print_table:
            _render_threads_table([mock_thread])
            mock_print_table.assert_called_once()
            rows = mock_print_table.call_args.kwargs.get("rows") or mock_print_table.call_args[
                1
            ].get("rows", mock_print_table.call_args[0][2])
            rendered_comment = rows[0][4]
            assert "ghp_supersecrettoken" not in rendered_comment
            assert "<masked-github-token>" in rendered_comment

    def test_pr_checks_fallback_empty_checks(self) -> None:
        """_render_pr_checks_fallback prints message when check_runs is empty."""
        from devops_cli.commands.pr import _render_pr_checks_fallback

        mock_pr_details = {"head": {"sha": "sha12345"}}
        mock_api_empty = json.dumps({"check_runs": []})

        with (
            patch("devops_cli.commands.pr._fetch_pr_details", return_value=mock_pr_details),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_api_empty, stderr=""),
            ),
            patch("devops_cli.commands.pr.print_info") as mock_print_info,
        ):
            res = _render_pr_checks_fallback(184)
            assert res is True
            mock_print_info.assert_called_once_with("No check runs found for PR #184.")

    def test_pr_diff_failure_exit_code(self, runner: CliRunner) -> None:
        """devops pr diff exits with returncode when gh pr diff fails."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=2, stdout="", stderr="Error fetching diff"),
            ),
        ):
            res = runner.invoke(app, ["diff", "184"])
            assert res.exit_code == 2


# =============================================================================
# Merge readiness gates
# =============================================================================


def _ready_pr(**overrides: object) -> dict:
    """Shape a pull request that is mergeable unless an override says otherwise."""
    payload = {
        "merged": False,
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "base": {"ref": "release/v0.2.22"},
        "head": {"sha": "a" * 40},
    }
    payload.update(overrides)
    return payload


def _blockers(pr_data: dict, **kwargs: object) -> list[str]:
    """Evaluate blockers with no review threads and no check runs unless stubbed."""
    from devops_cli.commands import pr as pr_module

    with (
        patch.object(pr_module, "list_pr_review_threads", return_value=[], create=True),
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        patch.object(pr_module, "_failing_check_runs", return_value=([], [])),
    ):
        return pr_module._evaluate_pr_blockers(pr_data, 335, "dan-petty", "devops-cli", **kwargs)


def test_a_draft_pull_request_is_not_merge_ready() -> None:
    """GitHub refuses to merge a draft, and still reports `mergeable_state: clean` for one.

    So a draft passed this check and was reported ready. PR #335 was reported ready while
    it was a draft, because draft status was a warning rather than a blocker.
    """
    assert _blockers(_ready_pr(draft=True)) != []


def test_a_draft_can_be_excused_explicitly() -> None:
    """Checking a draft you intend to keep draft is a legitimate use; it must be asked for."""
    assert _blockers(_ready_pr(draft=True), allow_draft=True) == []


def test_a_failing_check_blocks_readiness() -> None:
    """Branch protection refuses a red pull request, so readiness must account for checks.

    #335 passed this command while a CodeQL check had been failing on it for the whole
    release, because check status was never consulted.
    """
    from devops_cli.commands import pr as pr_module

    with (
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        patch.object(pr_module, "_failing_check_runs", return_value=(["CodeQL"], [])),
    ):
        blockers = pr_module._evaluate_pr_blockers(_ready_pr(), 335, "dan-petty", "devops-cli")
    assert any("CodeQL" in blocker for blocker in blockers)


def test_checks_still_running_block_by_default() -> None:
    """An unfinished check is not a passing one; calling it ready would be a guess."""
    from devops_cli.commands import pr as pr_module

    with (
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        patch.object(pr_module, "_failing_check_runs", return_value=([], ["Tests & Coverage"])),
    ):
        blockers = pr_module._evaluate_pr_blockers(_ready_pr(), 335, "dan-petty", "devops-cli")
    assert blockers != []


def test_running_checks_can_be_excused_for_in_flight_verification() -> None:
    """A CI job checking its own pull request cannot wait for itself to finish."""
    from devops_cli.commands import pr as pr_module

    with (
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        patch.object(pr_module, "_failing_check_runs", return_value=([], ["Tests & Coverage"])),
    ):
        blockers = pr_module._evaluate_pr_blockers(
            _ready_pr(), 335, "dan-petty", "devops-cli", allow_pending_checks=True
        )
    assert blockers == []


def test_a_clean_pull_request_reports_ready() -> None:
    """Adding gates must not make every pull request unmergeable."""
    assert _blockers(_ready_pr()) == []
