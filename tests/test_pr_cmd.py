"""Unit tests for devops pr command group."""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import ChangedFile, app
from devops_cli.github.issue_closure import extract_linked_issues
from devops_cli.github.rate_limiter import get_github_rate_limiter, reset_github_rate_limiter


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _gh_reply(stdout: object = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    """A `run_gh` result; a stdout that is not a string is sent as JSON."""
    text = stdout if isinstance(stdout, str) else json.dumps(stdout)
    return MagicMock(returncode=returncode, stdout=text, stderr=stderr)


_NOT_FOUND = _gh_reply('{"message": "Not Found", "status": "404"}', 1, "gh: Not Found (HTTP 404)")
_SERVER_ERROR = _gh_reply("", 1, "gh: Server Error (HTTP 500)")


def _readiness_gh(
    pr_payload: str = "{}", routes: dict[str, MagicMock] | None = None
) -> Callable[..., MagicMock]:
    """Answer `run_gh` by the endpoint it is given, its last argument.

    Unless `routes` says otherwise the repository keeps no task files and the PR changes no
    files; anything unrouted gets the PR payload.
    """
    replies = {"/contents/": _NOT_FOUND, "/files?": _gh_reply([]), **(routes or {})}

    def answer(args: list[str], **_: object) -> MagicMock:
        return next(
            (reply for key, reply in replies.items() if key in args[-1]), _gh_reply(pr_payload)
        )

    return answer


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
            assert (
                res.exit_code,
                "Validation" in res.output,
                "Analyze" in res.output,
            ) == (1, True, True)

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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=[mock_replied, mock_unreplied],
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--allow-replied-threads"])
            assert res.exit_code == 1
            assert "unreplied review discussion thread" in res.output

    def test_check_readiness_allow_replied_threads_probe_case_fails(
        self, runner: CliRunner
    ) -> None:
        """devops pr check-readiness treats threads with only opener follow-ups as unreplied blockers."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "release/v0.2.17"},
            }
        )
        mock_probe_thread = MagicMock(
            id="T_PROBE",
            is_resolved=False,
            path="src/main.py",
            line=10,
            comments=[
                MagicMock(author="copilot", body="Fix this issue"),
                MagicMock(author="copilot", body="Still not fixed."),
            ],
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                return_value=[mock_probe_thread],
            ),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--allow-replied-threads"])
            assert (
                res.exit_code,
                "unreplied review discussion thread" in res.output,
            ) == (1, True)

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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
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
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187", "--allow-blocked-state"])
            assert res.exit_code == 0
            assert "satisfies merge readiness" in res.output

    def test_check_readiness_fails_closed_under_unstable_when_check_runs_fails(
        self, runner: CliRunner
    ) -> None:
        """devops pr check-readiness fails closed under unstable mergeable_state when check-runs fails."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "unstable",
                "base": {"ref": "release/v0.2.17"},
                "head": {"sha": "abcdef1234567890abcdef1234567890abcdef12"},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch(
                "devops_cli.commands.pr.run_gh",
                side_effect=_readiness_gh(
                    mock_pr,
                    {
                        "/check-runs": MagicMock(
                            returncode=1, stdout="", stderr="HTTP 500: Server Error"
                        )
                    },
                ),
            ),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert (
                res.exit_code,
                "check verification failed closed" in res.output,
                "satisfies merge readiness" not in res.output,
            ) == (1, True, True)

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


def _file(filename: str, status: str = "modified") -> dict[str, str]:
    """One `pulls/{n}/files` entry."""
    return {"filename": filename, "status": status}


def _issue(milestone: str | None = "v0.2.25") -> MagicMock:
    """The `issues/{n}` reply for the issue a PR closes, in `milestone` or the backlog."""
    return _gh_reply({"number": 704, "milestone": {"title": milestone} if milestone else None})


_REPO = {"full_name": "dan-petty/devops-cli", "default_branch": "main"}
_TASK_704 = _file("docs/agent/tasks/task-704-x.md")
# The base keeps task files, the PR changes #704's, and #704 is in v0.2.25.
_GROUNDED = {"/contents/": _gh_reply(), "/files?": _gh_reply([_TASK_704]), "/issues/": _issue()}


def _ready_pr(**overrides: object) -> dict:
    """Shape a grounded pull request into a release branch, mergeable unless overridden."""
    payload = {
        "merged": False,
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "body": "Closes #704",
        "base": {"ref": "release/v0.2.25", "sha": "b" * 40, "repo": _REPO},
        "head": {"ref": "feat/x", "sha": "a" * 40, "repo": _REPO},
    }
    payload.update(overrides)
    return payload


def _blockers(
    pr_data: dict,
    *,
    checks: tuple[list[str], list[str]] = ([], []),
    gh: Callable[..., MagicMock] | None = None,
    **kwargs: object,
) -> list[str]:
    """Evaluate blockers with no review threads, the given check runs, and `run_gh` stubbed.

    Unless `gh` answers instead, the base keeps task files and the PR changes #704's.
    """
    from devops_cli.commands import pr as pr_module

    with (
        patch.object(pr_module, "list_pr_review_threads", return_value=[], create=True),
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        patch.object(pr_module, "_failing_check_runs", return_value=checks),
        patch.object(pr_module, "run_gh", side_effect=gh or _readiness_gh(routes=_GROUNDED)),
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
    blockers = _blockers(_ready_pr(), checks=(["CodeQL"], []))
    assert any("CodeQL" in blocker for blocker in blockers)


def test_checks_still_running_block_by_default() -> None:
    """An unfinished check is not a passing one; calling it ready would be a guess."""
    assert _blockers(_ready_pr(), checks=([], ["Tests & Coverage"])) != []


def test_running_checks_can_be_excused_for_in_flight_verification() -> None:
    """A CI job checking its own pull request cannot wait for itself to finish."""
    blockers = _blockers(_ready_pr(), checks=([], ["Tests & Coverage"]), allow_pending_checks=True)
    assert blockers == []


def test_a_clean_pull_request_reports_ready() -> None:
    """Adding gates must not make every pull request unmergeable."""
    assert _blockers(_ready_pr()) == []


# =============================================================================
# Grounding: one closed issue and its task file
# =============================================================================


def _grounding_gh(
    files: object, task_dir: MagicMock | None = None, issue: MagicMock | None = None
) -> MagicMock:
    """A recording `run_gh` stub for a base with task files, this list of changed files, and
    the issue the PR closes, in v0.2.25 unless `issue` says otherwise."""
    files_reply = files if isinstance(files, MagicMock) else _gh_reply(files)
    routes = {
        "/contents/": task_dir or _gh_reply(),
        "/files?": files_reply,
        "/issues/": issue or _issue(),
    }
    return MagicMock(side_effect=_readiness_gh(routes=routes))


@pytest.mark.parametrize(
    ("body", "files"),
    [
        ("Closes #704", [_TASK_704]),
        ("Closes #704", [_file("docs/agent/tasks/task-704-x.md", "added")]),
        ("Closes #704", [_file("docs/agent/tasks/task-704-x.md", "renamed")]),
        ("Fixes #89", [_file("src/x.py"), _file("docs/agent/tasks/task-089-x.md")]),
    ],
    ids=["modified", "added", "renamed", "zero-padded-089"],
)
def test_grounding_passes_a_pr_closing_one_issue_with_its_task_file(
    body: str, files: list[dict[str, str]]
) -> None:
    """A PR into `release/v0.2.25` closing one issue and writing its task file is grounded."""
    assert _blockers(_ready_pr(body=body), gh=_grounding_gh(files)) == []


@pytest.mark.parametrize(
    ("body", "files", "cause"),
    [
        ("Adds the readiness blocker.", [_TASK_704], "closes no issue in dan-petty/devops-cli"),
        ("Closes #1\nCloses #2", [_TASK_704], "closes 2 issues (#1, #2)"),
        ("Part 1 of #704", [_TASK_704], "closes no issue"),
        ("Closes other/repo#704", [_TASK_704], "closes no issue"),
        (
            "Closes #704",
            [_file("docs/agent/tasks/task-705-x.md")],
            "renames no docs/agent/tasks/task-704-*.md for #704",
        ),
        (
            "Closes #704",
            [_file("docs/agent/tasks/task-704-x.md", "removed")],
            "renames no docs/agent/tasks/task-704-*.md for #704",
        ),
        ("Closes #704", _SERVER_ERROR, "could not be read (gh: Server Error (HTTP 500))"),
    ],
    ids=[
        "no-closing-reference",
        "two-issues",
        "part-of-an-item",
        "other-repository",
        "another-issues-task-file",
        "task-file-removed",
        "files-unreadable",
    ],
)
def test_grounding_blocks_once_and_names_the_cause(body: str, files: object, cause: str) -> None:
    """Each way a PR can be ungrounded is exactly one blocker that says what is missing.

    Of the 41 PRs merged into release/v0.2.24, 8 closed no issue, 2 closed several and 3
    closed one without changing its task file. Nothing blocked any of them.
    """
    blockers = _blockers(_ready_pr(body=body), gh=_grounding_gh(files))
    assert [cause in blocker for blocker in blockers] == [True], blockers


_RELEASE_HEAD = {"ref": "chore/cut-v0.2.25", "sha": "a" * 40, "repo": _REPO}
_MAIN_BASE = {"ref": "main", "sha": "b" * 40, "repo": _REPO}


@pytest.mark.parametrize("files", [[], _SERVER_ERROR], ids=["files-read", "files-unreadable"])
def test_grounding_exempts_only_the_release_pr(files: object) -> None:
    """`chore/cut-vX.Y.Z` from this repository into the default branch delivers a release.

    It is exempt before any lookup, so even a task directory that can't be read doesn't
    block it, and an unread file list is one warning.
    """
    release_pr = _ready_pr(body="", head=_RELEASE_HEAD, base=_MAIN_BASE)
    with patch("devops_cli.commands.pr.print_warning") as warn:
        blockers = _blockers(release_pr, gh=_grounding_gh(files, task_dir=_SERVER_ERROR))
    assert (blockers, warn.call_count) == ([], 0 if files == [] else 1)


@pytest.mark.parametrize(
    "head",
    [
        {"ref": "feat/x", "sha": "a" * 40, "repo": _REPO},
        {"ref": "release/foo", "sha": "a" * 40, "repo": _REPO},
        {"ref": "release/v0.2.25", "sha": "a" * 40, "repo": _REPO},
        {"ref": "chore/cut-v0.2.25", "sha": "a" * 40, "repo": {"full_name": "fork/devops-cli"}},
    ],
    ids=["topic-branch", "not-a-release-version", "release-branch-into-main", "cut-from-a-fork"],
)
def test_grounding_holds_other_prs_into_the_default_branch(head: dict) -> None:
    """Only the release PR is exempt; a topic, malformed release, release branch or forked cut is not."""
    blockers = _blockers(_ready_pr(body="", head=head, base=_MAIN_BASE), gh=_grounding_gh([]))
    assert ["closes no issue" in blocker for blocker in blockers] == [True], blockers


def test_grounding_skips_a_base_without_task_files() -> None:
    """A 404 for `docs/agent/tasks` means the repository keeps none, so nothing is required.

    None of the other repositories devops-cli manages has the directory, and a file list that
    can't be read there is a warning, not a blocker.
    """
    gh = _grounding_gh(_SERVER_ERROR, task_dir=_NOT_FOUND)
    with patch("devops_cli.commands.pr.print_warning") as warn:
        blockers = _blockers(_ready_pr(body=""), gh=gh)
    assert (blockers, warn.call_count, "Could not read the files" in str(warn.call_args)) == (
        [],
        1,
        True,
    )


def test_grounding_blocks_when_the_task_directory_lookup_fails() -> None:
    """Only a 404 rules grounding out; any other failure is a blocker that names it."""
    blockers = _blockers(_ready_pr(), gh=_grounding_gh([_TASK_704], task_dir=_SERVER_ERROR))
    assert blockers == [
        "PR #335 is not grounded: docs/agent/tasks/ could not be read at its base "
        "(gh: Server Error (HTTP 500))."
    ]


def test_grounding_reads_the_files_the_base_and_the_closed_issue_once_each() -> None:
    """The reader's argv is pinned: without `per_page=100`, `run_gh` stops after 30 files."""
    gh = _grounding_gh([_TASK_704])
    _blockers(_ready_pr(), gh=gh)
    assert [call.args[0] for call in gh.call_args_list] == [
        ["gh", "api", "--paginate", "repos/dan-petty/devops-cli/pulls/335/files?per_page=100"],
        [
            "gh",
            "api",
            "--silent",
            f"repos/dan-petty/devops-cli/contents/docs/agent/tasks?ref={'b' * 40}",
        ],
        ["gh", "api", "repos/dan-petty/devops-cli/issues/704"],
    ]


@pytest.fixture
def full_core_quota() -> Iterator[None]:
    """A fresh `run_gh` limiter whose core quota is known and large.

    No request then reads `rate_limit`, and the pacing between requests (time to reset over
    requests remaining) is microseconds.
    """
    reset_github_rate_limiter()
    limiter = get_github_rate_limiter()
    quota = 1_000_000
    limiter.update_quota("core", remaining=quota, limit=quota, reset_epoch=time.time() + 60.0)
    yield
    reset_github_rate_limiter()


@pytest.mark.usefixtures("full_core_quota")
def test_grounding_reads_every_page_of_changed_files_through_the_pager() -> None:
    """`run_gh` pages the files itself, so the 101st file, on page 2, is read.

    PR #738 changed 51 files; without `per_page=100` the pager stopped after GitHub's
    default page of 30.
    """
    from devops_cli.commands import pr as pr_module

    pages = {"1": [_file(f"src/m{n}.py") for n in range(100)], "2": [_TASK_704]}
    issue = {"number": 704, "milestone": {"title": "v0.2.25"}}

    def subprocess_reply(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        endpoint = urlsplit(cmd[-1])
        page = parse_qs(endpoint.query).get("page", [""])[0] if "/files" in endpoint.path else ""
        stdout = json.dumps(pages[page]) if page in pages else ""
        stdout = json.dumps(issue) if endpoint.path.endswith("/issues/704") else stdout
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=subprocess_reply),
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        patch.object(pr_module, "_failing_check_runs", return_value=([], [])),
    ):
        files = pr_module._fetch_pr_files(335, "dan-petty", "devops-cli")
        blockers = pr_module._evaluate_pr_blockers(_ready_pr(), 335, "dan-petty", "devops-cli")
    assert (len(files), files[-1], blockers) == (
        101,
        ChangedFile("docs/agent/tasks/task-704-x.md", "modified"),
        [],
    )


# =============================================================================
# Grounding: a PR into a release branch leaves CHANGELOG.md and docs/ROADMAP.md to the cut
# =============================================================================

_FRAGMENT_704 = _file("changelog.d/704.md", "added")


@pytest.mark.parametrize(
    ("files", "named"),
    [
        ([_file("CHANGELOG.md")], "changes CHANGELOG.md:"),
        ([_file("docs/ROADMAP.md")], "changes docs/ROADMAP.md:"),
        ([_file("CHANGELOG.md", "added")], "changes CHANGELOG.md:"),
        ([_file("CHANGELOG.md", "removed")], "changes CHANGELOG.md:"),
        (
            [
                {
                    "filename": "docs/HISTORY.md",
                    "status": "renamed",
                    "previous_filename": "CHANGELOG.md",
                }
            ],
            "changes CHANGELOG.md:",
        ),
        (
            [_file("docs/ROADMAP.md"), _file("CHANGELOG.md"), _FRAGMENT_704],
            "changes CHANGELOG.md and docs/ROADMAP.md:",
        ),
    ],
    ids=["changelog", "roadmap", "added", "removed", "renamed-away", "both-and-a-fragment"],
)
def test_a_pr_into_a_release_branch_that_changes_a_release_file_is_blocked_once(
    files: list[dict[str, str]], named: str
) -> None:
    """Each open PR into release/v0.2.25 edited the same CHANGELOG.md lines.

    #928 and #932 each conflicted twice in one hour, and every conflict cost a rebase and a
    full CI run. The cut writes both files, so a PR that changes either is one blocker that
    names them and the fragment to add instead.
    """
    blockers = _blockers(_ready_pr(), gh=_grounding_gh([_TASK_704, *files]))
    assert (
        [named in blocker for blocker in blockers],
        all("Add its changelog entry as changelog.d/704.md instead." in b for b in blockers),
    ) == ([True], True), blockers


def test_the_same_pr_with_a_fragment_instead_is_ready() -> None:
    """The rule blocks the shared files only; a fragment and the task file pass."""
    assert _blockers(_ready_pr(), gh=_grounding_gh([_TASK_704, _FRAGMENT_704])) == []


def test_the_release_file_blocker_reads_in_full() -> None:
    """The blocker names the PR, the files, the base and the fragment path."""
    blockers = _blockers(_ready_pr(), gh=_grounding_gh([_TASK_704, _file("CHANGELOG.md")]))
    assert blockers == [
        "PR #335 changes CHANGELOG.md: a PR into release/v0.2.25 leaves them to the cut, so "
        "open PRs never conflict on them. Add its changelog entry as changelog.d/704.md instead."
    ]


_RELEASE_FILES = [_file("CHANGELOG.md"), _file("docs/ROADMAP.md")]


@pytest.mark.parametrize(
    ("head", "base"),
    [
        ({"ref": "chore/open-v0.2.25", "repo": _REPO}, {"ref": "release/v0.2.25", "repo": _REPO}),
        (
            {"ref": "chore/open-v0.2.25-cycle", "repo": _REPO},
            {"ref": "release/v0.2.25", "repo": _REPO},
        ),
    ],
    ids=["bootstrap", "bootstrap-with-slug"],
)
def test_release_process_prs_are_exempt_from_grounding(head: dict, base: dict) -> None:
    """The bootstrap delivers the release process, not one item.

    It closes no issue, keeps no task file and writes CHANGELOG.md and docs/ROADMAP.md, and is
    exempt before any lookup, as the release PR is.
    """
    gh = _grounding_gh(_RELEASE_FILES, task_dir=_SERVER_ERROR)
    blockers = _blockers(_ready_pr(body="", head=head, base=base), gh=gh)
    endpoints = [call.args[0][-1] for call in gh.call_args_list]
    assert (blockers, ["/contents/" in endpoint for endpoint in endpoints]) == ([], [False])


@pytest.mark.parametrize(
    ("head", "base", "release_file_blockers"),
    [
        ("chore/cut-v0.2.25", "release/v0.2.25", 1),
        ("chore/cut-v0.2.26", "release/v0.2.25", 1),
        ("chore/open-cycle-v0.2.25", "release/v0.2.25", 1),
        ("feat/open-v0.2.25", "release/v0.2.25", 1),
        ("chore/open-v0.2.25", "main", 0),
    ],
    ids=[
        "cut-into-release",
        "other-version",
        "slug-before-version",
        "not-chore",
        "into-the-default-branch",
    ],
)
def test_other_branches_are_held_to_grounding(
    head: str, base: str, release_file_blockers: int
) -> None:
    """Only `chore/open-vX.Y.Z[-slug]` into `release/vX.Y.Z` of that version is exempt.

    The release-file rule applies only into a `release/*` branch.
    """
    pr = _ready_pr(body="", head={"ref": head, "repo": _REPO}, base={"ref": base, "repo": _REPO})
    blockers = _blockers(pr, gh=_grounding_gh(_RELEASE_FILES))
    assert (
        sum("closes no issue" in blocker for blocker in blockers),
        sum("leaves them to the cut" in blocker for blocker in blockers),
    ) == (1, release_file_blockers), blockers


def test_a_release_process_branch_from_a_fork_is_not_exempt() -> None:
    """A fork can name its branch anything, so the exemption needs the same repository."""
    fork = {"ref": "chore/open-v0.2.25", "repo": {"full_name": "fork/devops-cli"}}
    blockers = _blockers(_ready_pr(body="", head=fork), gh=_grounding_gh(_RELEASE_FILES))
    assert ["closes no issue" in blocker for blocker in blockers] == [True, False], blockers


# =============================================================================
# Grounding: a PR into release/vX.Y.Z closes an item of release vX.Y.Z (#740)
# =============================================================================

_INTO_V0226 = {"ref": "release/v0.2.26", "sha": "b" * 40, "repo": _REPO}


@pytest.mark.parametrize(
    ("milestone", "blocker"),
    [
        (
            "v0.2.27",
            "PR #335 closes #704, which is in v0.2.27, not in v0.2.26: a PR into "
            "release/v0.2.26 delivers an item of v0.2.26, whose scope was fixed when it started.",
        ),
        (
            None,
            "PR #335 closes #704, which is in the backlog, not in v0.2.26: a PR into "
            "release/v0.2.26 delivers an item of v0.2.26, whose scope was fixed when it started.",
        ),
        ("v0.2.26", None),
    ],
    ids=["another-release", "the-backlog", "its-release"],
)
def test_a_pr_into_a_release_branch_is_blocked_unless_it_closes_an_item_of_that_release(
    milestone: str | None, blocker: str | None
) -> None:
    """A release's scope is fixed when it starts, so its branch takes only its own items.

    The blocker names the item and the release it is in, or says it is in the backlog.
    """
    gh = _grounding_gh([_TASK_704], issue=_issue(milestone))
    assert _blockers(_ready_pr(base=_INTO_V0226), gh=gh) == ([blocker] if blocker else [])


def test_a_part_of_an_item_line_names_no_item_so_only_the_one_issue_rule_blocks_it() -> None:
    """#704 dropped `Part N of #M`: a PR closes exactly one issue, and that issue is judged.

    A body that only names a backlog item with `Part 1 of #704` closes nothing, so it gets
    #704's one blocker, and no issue is read for the release check.
    """
    gh = _grounding_gh([_TASK_704], issue=_issue(None))
    blockers = _blockers(_ready_pr(body="Part 1 of #704", base=_INTO_V0226), gh=gh)
    endpoints = [call.args[0][-1] for call in gh.call_args_list]
    assert (
        ["closes no issue" in blocker for blocker in blockers],
        any("/issues/" in endpoint for endpoint in endpoints),
    ) == ([True], False)


def test_an_issue_that_cannot_be_read_is_one_blocker_naming_it() -> None:
    gh = _grounding_gh([_TASK_704], issue=_SERVER_ERROR)
    assert _blockers(_ready_pr(base=_INTO_V0226), gh=gh) == [
        "PR #335 is not grounded: the Release of #704 could not be read (gh: Server Error "
        "(HTTP 500))."
    ]


@pytest.mark.parametrize(
    "head",
    [
        {"ref": "release/v0.2.25", "sha": "a" * 40, "repo": _REPO},
        {"ref": "feat/x", "sha": "a" * 40, "repo": _REPO},
    ],
    ids=["the-release-pr", "a-topic-pr"],
)
def test_prs_into_the_default_branch_are_not_judged_by_release(head: dict) -> None:
    """The release PR is exempt from grounding, and a PR into `main` delivers no release's item.

    Neither reads the issue it closes, whichever release that issue is in.
    """
    gh = _grounding_gh([_TASK_704], issue=_issue("v0.2.27"))
    blockers = _blockers(_ready_pr(head=head, base=_MAIN_BASE), gh=gh)
    endpoints = [call.args[0][-1] for call in gh.call_args_list]
    assert (blockers, any("/issues/" in endpoint for endpoint in endpoints)) == ([], False)


# =============================================================================
# The pull request template asks only for what no check decides
# =============================================================================

_PR_TEMPLATE = Path(".github/pull_request_template.md")
_CHECKBOX_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]")


def test_pr_template_asks_for_the_issue_and_task_file_and_nothing_a_check_decides() -> None:
    """The template's quality-gate boxes asked authors to tick what they could not verify.

    All 5 of the last 40 merged PRs that used it ticked "complexity <= 10", which nothing
    enforced, and its "e.g. Closes #123" comment read as closing #123 in any body that kept it.
    """
    text = _PR_TEMPLATE.read_text(encoding="utf-8")
    assert (
        [line for line in text.splitlines() if _CHECKBOX_LINE.match(line)],
        "Closes #" in text,
        "docs/agent/tasks/task-" in text,
        "changelog.d/<issue>.md" in text,
        extract_linked_issues(text, "dan-petty/devops-cli"),
        re.search(r"complexity|coverage|quality gate|10/10", text, re.IGNORECASE),
    ) == (
        [
            "- [ ] `feat`: New feature or capability",
            "- [ ] `fix`: Bug fix or defect remediation",
            "- [ ] `refactor`: Code reorganization with zero functional behavior change",
            "- [ ] `docs`: Documentation updates or additions",
            "- [ ] `test`: New or updated tests",
            "- [ ] `chore`: Maintenance, dependencies, or tooling updates",
        ],
        True,
        True,
        True,
        [],
        None,
    )


def test_a_failed_create_explains_itself() -> None:
    """`run_gh` captures the CLI's output, so a failure printed nothing at all.

    Three invocations in one session produced no pull request and no message beyond the
    command's own elapsed time; the base branch had been deleted when its release merged
    and nothing said so.
    """
    from devops_cli.commands.pr import app as pr_app

    failure = MagicMock(returncode=1, stdout="", stderr="Base ref must be a branch")
    with (
        patch("devops_cli.commands.pr.run_gh", return_value=failure),
        patch("devops_cli.commands.pr._fallback_create_pr", return_value=False),
    ):
        result = CliRunner().invoke(
            pr_app, ["create", "--title", "t", "--body", "b", "--base", "release/v9.9.9"]
        )
    assert (result.exit_code, "release/v9.9.9" in result.output) == (1, True)


def test_a_failed_create_relays_the_underlying_reason() -> None:
    """The CLI's own message is the diagnostic; suppressing it hid the cause."""
    from devops_cli.commands.pr import app as pr_app

    failure = MagicMock(returncode=1, stdout="", stderr="Base ref must be a branch")
    with (
        patch("devops_cli.commands.pr.run_gh", return_value=failure),
        patch("devops_cli.commands.pr._fallback_create_pr", return_value=False),
    ):
        result = CliRunner().invoke(
            pr_app, ["create", "--title", "t", "--body", "b", "--base", "release/v9.9.9"]
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
