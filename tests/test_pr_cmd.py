"""Unit tests for devops pr command group."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from tests.support.fakes.github import GitHubApiFake


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
            '"state": "OPEN", "headRefName": "feat/security", "baseRefName": "main", '
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
            assert "main" in result.output

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
        mock_checks = json.dumps(
            [
                {
                    "name": "CI Quality Gate",
                    "state": "SUCCESS",
                    "bucket": "pass",
                    "workflow": "CI",
                    "link": "https://example.com/runs/1",
                }
            ]
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_checks, stderr=""),
            ) as mock_run,
        ):
            result = runner.invoke(app, ["checks", "13"])
            args = mock_run.call_args[0][0]
            assert (
                result.exit_code,
                mock_run.call_count,
                "checks" in args,
                "13" in args,
            ) == (0, 1, True, True)

    def test_edit_pr(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ) as mock_run,
        ):
            result = runner.invoke(app, ["edit", "13", "--base", "main", "--title", "New Title"])
            assert result.exit_code == 0
            assert "Successfully updated PR #13" in result.output
            args = mock_run.call_args[0][0]
            assert "--base" in args
            assert "main" in args

    def test_create_opens_a_draft_into_the_default_branch(self, runner: CliRunner) -> None:
        """Without --base gh picks the repository's default branch, and the PR is a draft."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(
                    returncode=0,
                    stdout="https://example.com/org/repo/pull/14\n",
                    stderr="",
                ),
            ) as mock_run,
        ):
            result = runner.invoke(
                app,
                ["create", "--title", "feat: new feature", "--body", "PR description"],
            )
        args = mock_run.call_args[0][0]
        assert (
            result.exit_code,
            "Opened a draft pull request: https://example.com/org/repo/pull/14." in result.output,
            "--draft" in args,
            "--base" in args,
        ) == (0, True, True, False)

    def test_create_passes_the_base_it_is_given(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ) as mock_run,
        ):
            result = runner.invoke(app, ["create", "--title", "t", "--base", "feat/base"])
        args = mock_run.call_args[0][0]
        assert (
            result.exit_code,
            args[args.index("--base") + 1],
            "--draft" in args,
            "Opened a draft pull request into feat/base." in result.output,
        ) == (0, "feat/base", True, True)

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
        from devops_cli.github.pr_threads import ReviewComment, ReviewThread, ThreadResolutionResult

        mock_thread = ReviewThread(
            id="PRRT_1",
            comments=[
                ReviewComment(id="c1", author="reviewer", body="Fix this"),
                ReviewComment(id="c2", author="developer", body="Addressed in commit abc"),
            ],
        )
        with (
            patch(
                "devops_cli.github.pr_threads.get_pr_review_thread",
                return_value=mock_thread,
            ),
            patch(
                "devops_cli.github.pr_threads.resolve_pr_review_thread",
                return_value=ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True),
            ),
        ):
            res = runner.invoke(app, ["threads", "resolve", "PRRT_1"])
            assert (res.exit_code, "Thread PRRT_1 marked as resolved" in res.output) == (0, True)

    def test_threads_resolve_refuses_without_reply(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ReviewComment, ReviewThread

        # Probe case: follow-up by the same author does not count as a valid reply
        probe_thread = ReviewThread(
            id="PRRT_PROBE",
            comments=[
                ReviewComment(id="c1", author="reviewer", body="Fix this"),
                ReviewComment(id="c2", author="reviewer", body="Still not fixed."),
            ],
        )
        with patch(
            "devops_cli.github.pr_threads.get_pr_review_thread",
            return_value=probe_thread,
        ):
            res = runner.invoke(app, ["threads", "resolve", "PRRT_PROBE"])
            assert (
                res.exit_code,
                "has no reply from someone other than the thread opener" in res.output,
                "--without-reply" in res.output,
            ) == (1, True, True)

    def test_threads_resolve_override_without_reply(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ThreadResolutionResult

        with patch(
            "devops_cli.github.pr_threads.resolve_pr_review_thread",
            return_value=ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True),
        ):
            res = runner.invoke(app, ["threads", "resolve", "PRRT_1", "--without-reply"])
            assert (res.exit_code, "Thread PRRT_1 marked as resolved" in res.output) == (0, True)

    def test_threads_resolve_override_short_flag(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_threads import ThreadResolutionResult

        with patch(
            "devops_cli.github.pr_threads.resolve_pr_review_thread",
            return_value=ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True),
        ):
            res = runner.invoke(app, ["threads", "resolve", "PRRT_1", "-w"])
            assert (res.exit_code, "Thread PRRT_1 marked as resolved" in res.output) == (0, True)

    def test_threads_resolve_fetch_error(self, runner: CliRunner) -> None:
        from devops_cli.exceptions.git import GitHubOperationError

        with patch(
            "devops_cli.github.pr_threads.get_pr_review_thread",
            side_effect=GitHubOperationError("GraphQL query failed"),
        ):
            res = runner.invoke(app, ["threads", "resolve", "PRRT_FAIL"])
            assert (
                res.exit_code,
                "Failed to fetch review thread PRRT_FAIL" in res.output,
            ) == (1, True)

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

    def test_pr_monitor_json_format_copilot_unread(self, runner: CliRunner) -> None:
        from devops_cli.github.pr_monitor import (
            CopilotReviewStatus,
            PRCheckRun,
            PRMonitorResult,
            PRMonitorStatus,
        )

        mock_status = PRMonitorStatus(
            number=168,
            title="fix: unread",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(
                is_active=False,
                state="unread",
                unread_reason="HTTP 403: rate limit",
                message="Copilot review state could not be read: HTTP 403: rate limit",
            ),
            unresolved_threads=[],
        )
        mock_result = PRMonitorResult(
            success=False,
            exit_code=3,
            message="PR #168 monitoring timed out after 300s: 0 check(s) pending (Copilot review state could not be read: HTTP 403: rate limit).",
            status=mock_status,
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.github.pr_monitor.monitor_pr", return_value=mock_result),
        ):
            res = runner.invoke(app, ["monitor", "168", "--format", "json"])
            assert res.exit_code == 3
            parsed = json.loads(res.output.strip())
            assert (
                parsed["status"]["copilot_status"]["state"],
                parsed["status"]["copilot_status"]["unread_reason"],
            ) == ("unread", "HTTP 403: rate limit")

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

    def test_pr_ready_check_fetch_failure_handles_gracefully(self, runner: CliRunner) -> None:
        """devops pr ready exits 1 with diagnostic message if check verdicts fetch raises error."""
        mock_preflight = json.dumps({"number": 179, "draft": True, "head": {"sha": "sha123"}})
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=0, stdout=mock_preflight, stderr=""),
            ),
            patch(
                "devops_cli.github.check_verdict.fetch_pr_check_verdicts",
                side_effect=RuntimeError("API endpoint unavailable"),
            ),
        ):
            result = runner.invoke(app, ["ready", "179"])
            assert (
                result.exit_code,
                "Failed fetching PR #179 check verdicts: API endpoint unavailable" in result.output,
                "Pass --force to override" in result.output,
            ) == (1, True, True)

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

    def test_pr_checks_fallback_on_gh_failure(
        self, runner: CliRunner, github_api: GitHubApiFake
    ) -> None:
        """devops pr checks falls back to the REST check-runs listing, read through the GitHub
        session, when gh pr checks fails."""
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
        github_api.route(
            "GET",
            "/repos/owner/repo/commits/abcdef123456/check-runs?per_page=100",
            httpx2.Response(
                200, headers={"content-type": "application/json"}, content=mock_checks_json.encode()
            ),
        )
        mock_statuses_json = json.dumps(
            {
                "state": "success",
                "total_count": 1,
                "statuses": [
                    {
                        "context": "ci/status",
                        "state": "success",
                        "target_url": "https://example.com/status/1",
                    }
                ],
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
                    MagicMock(returncode=0, stdout=mock_statuses_json, stderr=""),
                ],
            ),
        ):
            res = runner.invoke(app, ["checks", "184"])
            assert (
                res.exit_code,
                "Validation" in res.output,
                "Analyze" in res.output,
                "ci/status" in res.output,
            ) == (1, True, True, True)

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
            res = runner.invoke(app, ["edit", "184", "--milestone", "2026-11"])
            assert res.exit_code == 0
            assert "Successfully updated PR #184" in res.output
            assert "--milestone" in mock_run.call_args[0][0]
            assert "2026-11" in mock_run.call_args[0][0]

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
                    "base": {"ref": "main"},
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
            result = _fallback_create_pr(title="test", body="test", base="main")
            assert result is True
            # Verified that only the query was called, not a POST
            assert len(mock_sub.call_args_list) == 1
            assert "pulls?head=owner:feat/test" in mock_sub.call_args[0][0][2]

    def test_fallback_create_pr_paces_its_post_as_a_write(self) -> None:
        """Through the real `run_gh` with gh's process stubbed (#1125): the existing-PR lookup
        acquires as a read and the implicit-POST `gh api .../pulls -f ...` as a write."""
        from devops_cli.commands.pr import _fallback_create_pr
        from devops_cli.github.rate_limiter import GitHubRateLimiter

        def gh(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            lookup = any("pulls?head=" in arg for arg in cmd)
            created = {"number": 9, "html_url": "https://github.com/o/r/pull/9"}
            return subprocess.CompletedProcess(cmd, 0, "[]" if lookup else json.dumps(created), "")

        with (
            patch("devops_cli.commands.pr._detect_current_branch", return_value="feat/x"),
            patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=gh),
            patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as acquire,
        ):
            created = _fallback_create_pr(title="t", body="b", base="main", repo="o/r")
        assert (created, [call.kwargs["is_mutation"] for call in acquire.call_args_list]) == (
            True,
            [False, True],
        )

    @pytest.mark.parametrize(
        ("stdout", "said"),
        [
            (
                json.dumps({"html_url": "https://example.com/o/r/pull/9"}),
                "Opened a draft pull request: https://example.com/o/r/pull/9.",
            ),
            ("not json", "Opened a draft pull request into main."),
            ("[]", "Opened a draft pull request into main."),
        ],
        ids=["url", "not-json", "no-url"],
    )
    def test_the_fallback_names_the_draft_by_its_url_or_else_its_base(
        self, stdout: str, said: str
    ) -> None:
        from devops_cli.commands.pr import _print_created_pr_message

        with patch("devops_cli.commands.pr.print_success") as success:
            _print_created_pr_message(stdout, "main")
        assert success.call_args.args[0].startswith(said)

    def test_the_fallback_reports_a_failed_post(self) -> None:
        from devops_cli.commands.pr import _fallback_create_pr

        def gh(args: list[str], **_: object) -> MagicMock:
            if any("pulls?head=" in arg for arg in args):
                return MagicMock(returncode=0, stdout="[]", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="HTTP 422")

        with (
            patch("devops_cli.commands.pr._detect_current_branch", return_value="feat/x"),
            patch("devops_cli.commands.pr.run_gh", side_effect=gh),
        ):
            assert _fallback_create_pr(title="t", body="b", base="main", repo="o/r") is False

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
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=1, stdout="", stderr="GraphQL error"),
            ),
            patch("devops_cli.commands.pr._fallback_create_pr", return_value=True) as mock_fallback,
        ):
            result = runner.invoke(app, ["create", "--title", "test title", "--body", "test body"])
            assert result.exit_code == 0
            assert mock_fallback.called

    def test_create_has_no_option_to_skip_the_draft(self, runner: CliRunner) -> None:
        """devops pr ready is the only way to ready, so create takes no --draft flag at all."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.commands.pr.run_gh") as mock_sub,
        ):
            result = runner.invoke(app, ["create", "--title", "t", "--draft"])
        assert (result.exit_code, mock_sub.call_count) == (2, 0)

    def test_the_fallback_opens_a_draft_into_the_default_branch_it_reads(self) -> None:
        """Without --base the REST fallback reads the default branch, then posts a draft."""
        from devops_cli.commands.pr import _fallback_create_pr

        replies = {
            "repos/o/r/pulls?head=": MagicMock(returncode=0, stdout="[]", stderr=""),
            "repos/o/r/pulls -f": MagicMock(
                returncode=0, stdout=json.dumps({"html_url": "https://example.com/o/r/pull/9"})
            ),
            "repos/o/r": MagicMock(returncode=0, stdout=json.dumps({"default_branch": "trunk"})),
        }

        def gh(args: list[str], **_: object) -> MagicMock:
            sent = " ".join(args)
            return replies[max((key for key in replies if key in sent), key=len)]

        with (
            patch("devops_cli.commands.pr._detect_current_branch", return_value="feat/x"),
            patch("devops_cli.commands.pr.run_gh", side_effect=gh) as mock_sub,
            patch("devops_cli.commands.pr.print_success") as said,
        ):
            created = _fallback_create_pr(title="t", body="b", base=None, repo="o/r")
        post = mock_sub.call_args_list[-1].args[0]
        assert (
            created,
            "base=trunk" in post,
            post[-2:],
            "https://example.com/o/r/pull/9" in str(said.call_args),
        ) == (True, True, ["-F", "draft=true"], True)

    @pytest.mark.parametrize(
        "repository",
        [
            MagicMock(returncode=1, stdout="", stderr="gh: Server Error (HTTP 500)"),
            MagicMock(returncode=0, stdout="not json", stderr=""),
            MagicMock(returncode=0, stdout="[]", stderr=""),
        ],
        ids=["unread", "not-json", "no-object"],
    )
    def test_the_fallback_creates_nothing_when_the_default_branch_is_unread(
        self, repository: MagicMock
    ) -> None:
        from devops_cli.commands.pr import _fallback_create_pr

        def gh(args: list[str], **_: object) -> MagicMock:
            if any("pulls?head=" in arg for arg in args):
                return MagicMock(returncode=0, stdout="[]", stderr="")
            return repository

        with (
            patch("devops_cli.commands.pr._detect_current_branch", return_value="feat/x"),
            patch("devops_cli.commands.pr.run_gh", side_effect=gh) as mock_sub,
        ):
            created = _fallback_create_pr(title="t", body="b", base=None, repo="o/r")
        assert (created, mock_sub.call_count) == (False, 2)

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

    @pytest.mark.parametrize(
        ("said", "details"),
        [
            pytest.param(
                "gh: Too Many Requests (HTTP 429)", "gh: Too Many Requests (HTTP 429)", id="429"
            ),
            pytest.param(
                "gh: Please retry your request again later. (HTTP 403)",
                "gh: Please retry your request again later. (HTTP 403)",
                id="secondary",
            ),
            pytest.param(
                "GraphQL: API rate limit already exceeded for user ID 1.",
                "GraphQL: API rate limit already exceeded for user ID 1",
                id="ends-with-a-period",
            ),
        ],
    )
    def test_ready_names_a_rate_limit_only_the_gh_table_names(
        self, runner: CliRunner, said: str, details: str
    ) -> None:
        """A rate limit gh writes without the words "rate limit" is still named one (#983). The
        message is one paragraph: `print_error` wraps softly at the 250 columns the tests set, so
        a line break would come from the message itself, and gh's own closing period is not
        doubled."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "devops_cli.commands.pr._fetch_pr_details",
                return_value={"draft": True, "number": 184},
            ),
            patch(
                "devops_cli.commands.pr.run_gh",
                return_value=MagicMock(returncode=1, stdout="", stderr=said),
            ),
        ):
            result = runner.invoke(app, ["ready", "184"])
        assert (
            result.exit_code,
            f"GitHub GraphQL rate limit exceeded. Details: {details}. Note:" in result.output,
            result.output.count("\n"),
        ) == (1, True, 1)

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

    def test_check_readiness_no_open_pr(self, runner: CliRunner) -> None:
        """devops pr check-readiness on a branch with no open PR exits 1 with a one-line error."""
        mock_proc = MagicMock(returncode=1, stdout="", stderr="no pull requests found")
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.github.pr_monitor._resolve_current_git_branch",
                return_value="feat/untracked",
            ),
            patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc),
        ):
            result = runner.invoke(app, ["check-readiness"], catch_exceptions=False)
            assert result.exit_code == 1
            assert "No open pull request found for branch 'feat/untracked'" in result.output
            assert "Traceback" not in result.output

    def test_pr_monitor_no_open_pr(self, runner: CliRunner) -> None:
        """devops pr monitor on a branch with no open PR exits 1 with a one-line error."""
        mock_proc = MagicMock(returncode=1, stdout="", stderr="no pull requests found")
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.github.pr_monitor._resolve_current_git_branch",
                return_value="feat/untracked",
            ),
            patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc),
        ):
            result = runner.invoke(app, ["monitor"], catch_exceptions=False)
            assert result.exit_code == 1
            assert "No open pull request found for branch 'feat/untracked'" in result.output
            assert "Traceback" not in result.output

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
        """_render_pr_checks_fallback renders table with 'no checks reported' pending when empty."""
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
            patch("devops_cli.commands.pr.print_table") as mock_print_table,
        ):
            res = _render_pr_checks_fallback(184)
            assert res is True
            mock_print_table.assert_called_once()
            call_kwargs = mock_print_table.call_args[1]
            rows = call_kwargs.get("rows", [])
            assert (len(rows), rows[0][0], "pending" in rows[0][1]) == (
                1,
                "no checks reported",
                True,
            )

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
# The pull request template asks only for what no check decides
# =============================================================================

_PR_TEMPLATE = Path(".github/pull_request_template.md")
_CHECKBOX_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]")


def test_pr_template_asks_for_the_issue_and_its_change_and_nothing_a_check_decides() -> None:
    """The template's quality-gate boxes asked authors to tick what they could not verify.

    All 5 of the last 40 merged PRs that used it ticked "complexity <= 10", which nothing
    enforced. The template asks for the one issue the PR closes and its change folder, and for
    nothing that a check decides.
    """
    text = _PR_TEMPLATE.read_text(encoding="utf-8")
    assert (
        [line for line in text.splitlines() if _CHECKBOX_LINE.match(line)],
        "Closes #<issue>" in text,
        "Change: `openspec/changes/archive/<date>-<issue>-<slug>/`" in text,
        re.search(r"Part of #|changelog\.d|release/v", text),
        re.search(r"complexity|coverage|quality gate|10/10", text, re.IGNORECASE),
    ) == ([], True, True, None, None)


_HEADING_OR_RULE_LINE = re.compile(r"^\s*(?:#{1,6}\s|(?:-\s*){3,}$|(?:\*\s*){3,}$|(?:_\s*){3,}$)")


def test_pr_template_reads_as_the_squash_commit_message() -> None:
    """The squash merge copies the body into `main` as the commit message (#2266).

    The repository squash-merges with `PR_TITLE` and `PR_BODY`. Of the last 60 merges, 49
    messages held the template's `## Summary` and `## Item` headings, and the `Change:` line
    named a folder that the archive had moved. The template has no heading and no rule, and
    names the archived change folder.
    """
    text = _PR_TEMPLATE.read_text(encoding="utf-8")
    assert [line for line in text.splitlines() if _HEADING_OR_RULE_LINE.match(line)] == []


def test_a_failed_create_explains_itself() -> None:
    """`run_gh` captures the CLI's output, so a failure printed nothing at all.

    Three invocations in one session produced no pull request and no message beyond the
    command's own elapsed time; the base branch did not exist and nothing said so.
    """
    from devops_cli.commands.pr import app as pr_app

    failure = MagicMock(returncode=1, stdout="", stderr="Base ref must be a branch")
    with (
        patch("devops_cli.commands.pr.run_gh", return_value=failure),
        patch("devops_cli.commands.pr._fallback_create_pr", return_value=False),
    ):
        result = CliRunner().invoke(
            pr_app, ["create", "--title", "t", "--body", "b", "--base", "feat/gone"]
        )
    assert (result.exit_code, "feat/gone" in result.output) == (1, True)


def test_a_failed_create_without_a_base_names_the_default_branch() -> None:
    from devops_cli.commands.pr import app as pr_app

    failure = MagicMock(returncode=1, stdout="", stderr="GraphQL error")
    with (
        patch("devops_cli.commands.pr.run_gh", return_value=failure),
        patch("devops_cli.commands.pr._fallback_create_pr", return_value=False),
    ):
        result = CliRunner().invoke(pr_app, ["create", "--title", "t"])
    assert (result.exit_code, "against base 'the default branch'" in result.output) == (1, True)


def test_a_failed_create_relays_the_underlying_reason() -> None:
    """The CLI's own message is the diagnostic; suppressing it hid the cause."""
    from devops_cli.commands.pr import app as pr_app

    failure = MagicMock(returncode=1, stdout="", stderr="Base ref must be a branch")
    with (
        patch("devops_cli.commands.pr.run_gh", return_value=failure),
        patch("devops_cli.commands.pr._fallback_create_pr", return_value=False),
    ):
        result = CliRunner().invoke(
            pr_app, ["create", "--title", "t", "--body", "b", "--base", "feat/gone"]
        )
    assert "Base ref must be a branch" in result.output


def test_an_unpushed_branch_gets_the_remedy() -> None:
    """The most common cause has a one-line fix; naming it saves a round trip."""
    from devops_cli.commands.pr import app as pr_app

    failure = MagicMock(
        returncode=1, stdout="", stderr="aborted: you must first push the current branch"
    )
    with (
        patch("devops_cli.commands.pr.run_gh", return_value=failure),
        patch("devops_cli.commands.pr._fallback_create_pr", return_value=False),
    ):
        result = CliRunner().invoke(
            pr_app, ["create", "--title", "t", "--body", "b", "--base", "main"]
        )
    assert "git push -u origin HEAD" in result.output
