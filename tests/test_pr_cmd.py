"""Unit tests for devops pr command group."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import ChangedFile, app
from devops_cli.config.constants import CONST_ROADMAP_CONFIG_PATH
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.github import GitHubApiFake, github_json, next_page


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
    """Answer `run_gh` by the longest route its arguments name, so the roadmap config's
    `/contents/.github/roadmap.toml` is not the change directory's `/contents/`.

    Unless `routes` says otherwise the repository keeps no change folders and the PR changes no
    files; anything unrouted gets the PR payload.
    """
    replies = {"/contents/": _NOT_FOUND, "/files?": _gh_reply([]), **(routes or {})}

    def answer(args: list[str], **_: object) -> MagicMock:
        sent = " ".join(args)
        route = max((key for key in replies if key in sent), key=len, default=None)
        return replies[route] if route is not None else _gh_reply(pr_payload)

    return answer


class _RoutedSession:
    """The GitHub session readiness reads a pull request's changed files and check runs through,
    answered from the routes of the test's `run_gh` stub (#983).

    Each read is recorded in `reads`, and the stub is asked for its endpoint with an argv that
    is plainly no gh command (`<session> GET <endpoint>`), so a reader that went back to a
    one-page `gh api` read shows in a test as a different call. A reply holding a list is the
    whole listing; a failed reply raises the read's failure; anything else fails closed as the
    session does, through its own `listed_items`. A read with `run_gh` left unstubbed fails the
    test instead of reaching a real gh.
    """

    def __init__(self, gh: Callable[..., MagicMock]) -> None:
        self._gh = gh
        self.reads: list[str] = []

    def paginate(self, path: str, *, iterable_key: str | None = None) -> Iterator[object]:
        from devops_cli.commands import pr as pr_module
        from devops_cli.exceptions.git import GitHubOperationError
        from devops_cli.github import rate_limiter
        from devops_cli.github.error_classifier import classify_http_error
        from devops_cli.github.session_transport import listed_items

        if pr_module.run_gh is rate_limiter.run_gh:
            raise AssertionError("A session read under test_pr_cmd needs run_gh stubbed")
        self.reads.append(path)
        reply = self._gh([_SESSION_READ, "GET", path.lstrip("/")])
        if reply.returncode != 0:
            raise GitHubOperationError(reply.stderr.strip())
        try:
            answer = json.loads(reply.stdout or "null")
        except json.JSONDecodeError as exc:
            raise classify_http_error(exc, method="GET", path=path, page=1) from exc
        yield from listed_items(answer, path=path, page=1, iterable_key=iterable_key)


# What a session read looks like among the `run_gh` stub's calls: no gh command does.
_SESSION_READ = "<session>"


@pytest.fixture(autouse=True)
def routed_session(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> _RoutedSession | None:
    """Readiness reads a pull request's changed files and check runs through the GitHub
    session (#983). Here both are answered from the routes of whatever stands in for `run_gh`
    in `commands.pr`, as its gh reads are, and recorded on the session, which a test can ask
    for by name. A read with `run_gh` unstubbed fails, so no test reaches GitHub or a real gh.
    A test over the `github_api` fake keeps the real session."""
    if "github_api" in request.fixturenames:
        return None
    from devops_cli.commands import pr as pr_module

    session = _RoutedSession(lambda args, **kwargs: pr_module.run_gh(args, **kwargs))
    monkeypatch.setattr("devops_cli.github.session.get_github_session", lambda: session)
    monkeypatch.setattr("devops_cli.github.check_verdict.get_github_session", lambda: session)
    return session


def test_the_routed_session_refuses_an_unstubbed_run_gh() -> None:
    """A session read in a test that left `run_gh` alone fails at once and starts no gh."""
    from devops_cli.github import session as session_module

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess") as spawned,
        pytest.raises(AssertionError, match="needs run_gh stubbed"),
    ):
        list(session_module.get_github_session().paginate("/repos/o/r/pulls/1/files?per_page=100"))
    assert spawned.call_count == 0


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

    def test_check_readiness_clean(self, runner: CliRunner) -> None:
        """devops pr check-readiness passes when 0 blockers."""
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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

    def test_check_readiness_fails_closed_when_review_threads_cannot_be_read(
        self, runner: CliRunner
    ) -> None:
        """A failed review-thread read blocks readiness and names the error (#797)."""
        from devops_cli.exceptions.git import GitHubOperationError

        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "main"},
                "head": {"sha": "a" * 40},
            }
        )
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
            patch(
                "devops_cli.github.pr_threads.list_pr_review_threads",
                side_effect=GitHubOperationError("GraphQL 502 Bad Gateway"),
            ),
            patch("devops_cli.commands.pr._failing_check_runs", return_value=([], [])),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert (
                res.exit_code,
                "Could not retrieve review threads for PR #187: GraphQL 502 Bad Gateway"
                in res.output,
                "satisfies merge readiness" not in res.output,
            ) == (1, True, True)

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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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
                "base": {"ref": "main"},
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

    def test_check_readiness_fails_closed_when_second_page_check_runs_malformed(
        self, runner: CliRunner, github_api: GitHubApiFake
    ) -> None:
        """A check-run listing whose second page is malformed makes pr check-readiness fail
        closed, naming the page, rather than judge the first page's runs alone."""
        sha = "abcdef1234567890abcdef1234567890abcdef12"
        mock_pr = json.dumps(
            {
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "base": {"ref": "main"},
                "head": {"sha": sha},
            }
        )
        runs = [
            {"name": f"check-{i}", "status": "completed", "conclusion": "success"}
            for i in range(100)
        ]
        second = f"/repositories/1/commits/{sha}/check-runs?per_page=100&page=2"
        github_api.route(
            "GET",
            f"/repos/owner/repo/commits/{sha}/check-runs?per_page=100",
            github_json({"total_count": 200, "check_runs": runs}, headers=next_page(second)),
        )
        github_api.route(
            "GET",
            second,
            httpx2.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<html>upstream 502 Bad Gateway</html>",
            ),
        )
        github_api.route("GET", "/repos/owner/repo/pulls/187/files?per_page=100", github_json([]))
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
            patch("devops_cli.commands.pr.run_gh", side_effect=_readiness_gh(mock_pr)),
            patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]),
        ):
            res = runner.invoke(app, ["check-readiness", "187"])
            assert (
                res.exit_code,
                "check verification failed closed" in res.output,
                "page 2" in res.output,
                "satisfies merge readiness" not in res.output,
            ) == (1, True, True, True)

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
# Merge readiness gates
# =============================================================================


def _file(filename: str, status: str = "modified") -> dict[str, str]:
    """One `pulls/{n}/files` entry."""
    return {"filename": filename, "status": status}


_OWN_REPO = "dan-petty/devops-cli"
_REPO = {"full_name": _OWN_REPO, "default_branch": "main"}
_ARCHIVE_704 = _file("openspec/changes/archive/2026-10-23-704-x/proposal.md", "added")
_BOARD = 2


def _closing_issue(
    number: int = 704,
    *,
    state: str = "OPEN",
    repo: str = _OWN_REPO,
    boards: tuple[tuple[str, int], ...] = (("dan-petty", _BOARD),),
) -> dict[str, object]:
    """One `closingIssuesReferences` node, on the boards `(owner, number)` names."""
    cards = [{"project": {"number": board, "owner": {"login": owner}}} for owner, board in boards]
    return {
        "number": number,
        "state": state,
        "repository": {"nameWithOwner": repo},
        "projectItems": {"nodes": cards},
    }


def _closing(*issues: dict[str, object], total: int | None = None) -> MagicMock:
    """GitHub's GraphQL reply naming the issues a PR closes, `total` of them in all."""
    references = {"totalCount": len(issues) if total is None else total, "nodes": list(issues)}
    payload = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": references}}}}
    return _gh_reply(payload)


_CLOSING_ROUTE = "closingIssuesReferences"
# The base keeps change folders, the PR archives #704's, and #704 is open and on the board.
_GROUNDED = {
    "/contents/": _gh_reply(),
    "/files?": _gh_reply([_ARCHIVE_704]),
    _CLOSING_ROUTE: _closing(_closing_issue()),
}


@pytest.fixture(autouse=True)
def roadmap_board(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The roadmap whose `.github/roadmap.toml` names board 2, which readiness reads the board
    from through the roadmap store."""
    roadmap_store.seed_file(CONST_ROADMAP_CONFIG_PATH, f"board = {_BOARD}\n")
    return roadmap_store


def _ready_pr(**overrides: object) -> dict:
    """Shape a grounded pull request into the default branch, mergeable unless overridden."""
    payload = {
        "merged": False,
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "body": "Closes #704",
        "base": {"ref": "main", "sha": "b" * 40, "repo": _REPO},
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
    """Evaluate blockers with no review threads, the given check runs, and `run_gh` stubbed,
    which also answers the files read (`routed_session`).

    Unless `gh` answers instead, the PR is grounded as `_GROUNDED` says.
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

    #335 passed this command while a CodeQL check had been failing on it, because check status
    was never consulted.
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
# Grounding: one open issue on the board, closed into the default branch, and its archived change
# =============================================================================

_ARCHIVE = "openspec/changes/archive"


def _grounding_gh(
    files: object, *, changes_dir: MagicMock | None = None, closing: MagicMock | None = None
) -> MagicMock:
    """A recording `run_gh` stub for a base with change folders, this list of changed files, and
    the issues the PR closes, open #704 on the board unless `closing` says otherwise."""
    files_reply = files if isinstance(files, MagicMock) else _gh_reply(files)
    routes = {
        "/contents/": changes_dir or _gh_reply(),
        "/files?": files_reply,
        _CLOSING_ROUTE: closing or _closing(_closing_issue()),
    }
    return MagicMock(side_effect=_readiness_gh(routes=routes))


@pytest.mark.parametrize(
    ("issue", "files"),
    [
        (704, [_ARCHIVE_704]),
        (704, [_file(f"{_ARCHIVE}/2026-10-23-704-x/tasks.md", "renamed")]),
        (704, [_file(f"{_ARCHIVE}/2026-10-23-704-x/design.md", "copied")]),
        (89, [_file("src/x.py"), _file(f"{_ARCHIVE}/2026-10-23-089-x/proposal.md", "added")]),
        (
            704,
            [
                _file("openspec/changes/704-x/proposal.md", "removed"),
                _file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "added"),
                _file("openspec/specs/widget/spec.md", "added"),
                _file("openspec/specs/export/spec.md", "modified"),
            ],
        ),
    ],
    ids=["added", "renamed", "copied", "zero-padded-089", "with-the-living-specs-it-writes"],
)
def test_grounding_passes_a_pr_that_archives_the_change_of_its_issue(
    issue: int, files: list[dict[str, str]]
) -> None:
    """A PR into the default branch that closes one open issue on the board and adds that
    issue's archived change folder is grounded, with the living specs its archive wrote."""
    gh = _grounding_gh(files, closing=_closing(_closing_issue(issue)))
    assert _blockers(_ready_pr(), gh=gh) == []


def _not_archived(change: str = "704-<slug>") -> str:
    """The blocker of a PR that closes #704 and adds no archived folder for it."""
    return (
        f"PR #335 is not grounded: it adds no {_ARCHIVE}/<date>-{change}/ for #704. Archive "
        f"the change in the last commit of the PR with uv run devops openspec archive {change}."
    )


def _writes_a_record(paths: str, change: str = "704-<slug>") -> str:
    """The blocker of a PR that closes #704 and changes `paths`, which only its own archive may."""
    return (
        f"PR #335 is not grounded: it changes {paths}. Only the archive of the change of #704 "
        f"writes openspec/specs/ and {_ARCHIVE}/, and only in {_ARCHIVE}/<date>-{change}/."
    )


@pytest.mark.parametrize(
    ("files", "blockers"),
    [
        ([_file("src/x.py")], [_not_archived()]),
        ([_file("openspec/changes/704-x/proposal.md", "added")], [_not_archived("704-x")]),
        (
            [_file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "modified")],
            [_not_archived()],
        ),
        ([_file(f"{_ARCHIVE}/2026-10-23-704-x/proposal.md", "removed")], [_not_archived()]),
        (
            [_file(f"{_ARCHIVE}/2026-10-23-705-x/proposal.md", "added")],
            [_not_archived(), _writes_a_record(f"{_ARCHIVE}/2026-10-23-705-x/proposal.md")],
        ),
        (
            [_file("openspec/specs/widget/spec.md", "modified")],
            [_not_archived(), _writes_a_record("openspec/specs/widget/spec.md")],
        ),
        (
            [_ARCHIVE_704, _file(f"{_ARCHIVE}/2026-10-01-705-y/tasks.md", "modified")],
            [_writes_a_record(f"{_ARCHIVE}/2026-10-01-705-y/tasks.md", "704-x")],
        ),
        (
            [_ARCHIVE_704, _file(f"{_ARCHIVE}/.gitkeep", "removed")],
            [_writes_a_record(f"{_ARCHIVE}/.gitkeep", "704-x")],
        ),
        (
            [
                _file("openspec/changes/704-x/proposal.md", "added"),
                _file("openspec/changes/704-x/tasks.md", "added"),
            ],
            [_not_archived("704-x")],
        ),
    ],
    ids=[
        "no-change-folder",
        "an-active-change",
        "an-archived-folder-the-base-holds",
        "its-archived-folder-removed",
        "the-archived-folder-of-another-issue",
        "a-spec-without-the-archive",
        "another-issues-archive-changed",
        "a-file-of-the-archive-directory",
        "one-blocker-for-the-files-of-one-change",
    ],
)
def test_grounding_blocks_a_pr_that_does_not_archive_its_change_naming_the_folder(
    files: list[dict[str, str]], blockers: list[str]
) -> None:
    """A PR that closes #704 adds #704's archived change folder, and only that archive writes the
    living specs and the archive. Each blocker names the folder readiness expects, with the
    PR's own change when it has one, or each file only the archive may write."""
    assert _blockers(_ready_pr(), gh=_grounding_gh(files)) == blockers


@pytest.mark.parametrize(
    ("closing", "files", "cause"),
    [
        (_closing(), [_ARCHIVE_704], "it closes no issue. Put Closes #<issue> in its body"),
        (
            _closing(_closing_issue(1), _closing_issue(2)),
            [_ARCHIVE_704],
            "it closes 2 issues (#1, #2), and a PR delivers exactly one.",
        ),
        (
            _closing(_closing_issue(1), _closing_issue(2), total=12),
            [_ARCHIVE_704],
            "it closes 12 issues (#1, #2)",
        ),
        (
            _closing(_closing_issue(repo="other/project")),
            [_ARCHIVE_704],
            "it closes other/project#704, which is not an issue of dan-petty/devops-cli.",
        ),
        (
            _closing(_closing_issue(state="CLOSED")),
            [_ARCHIVE_704],
            "it closes #704, which is not open.",
        ),
        (
            _closing(_closing_issue(boards=(("dan-petty", 9),))),
            [_ARCHIVE_704],
            "#704 is not on the roadmap board, project 2.",
        ),
        (
            _closing(_closing_issue(boards=(("someone-else", _BOARD),))),
            [_ARCHIVE_704],
            "#704 is not on the roadmap board, project 2.",
        ),
        (
            _closing(_closing_issue()),
            _SERVER_ERROR,
            "could not be read (gh: Server Error (HTTP 500))",
        ),
        (_SERVER_ERROR, [_ARCHIVE_704], "the issues it closes could not be read (gh: Server Error"),
        (
            _gh_reply({"errors": [{"message": "Something went wrong"}]}),
            [_ARCHIVE_704],
            "the issues it closes could not be read (Something went wrong).",
        ),
        (
            _gh_reply({"data": {"repository": None}}),
            [_ARCHIVE_704],
            "the issues it closes could not be read (malformed reply:",
        ),
        (
            _gh_reply("not json"),
            [_ARCHIVE_704],
            "the issues it closes could not be read (malformed",
        ),
    ],
    ids=[
        "no-closing-reference",
        "two-issues",
        "more-issues-than-one-page",
        "issue-of-another-repository",
        "closed-issue",
        "issue-on-another-board",
        "issue-on-another-owners-board",
        "files-unreadable",
        "closing-issues-unreadable",
        "closing-issues-graphql-error",
        "closing-issues-malformed",
        "closing-issues-not-json",
    ],
)
def test_grounding_blocks_once_and_names_the_cause(
    closing: MagicMock, files: object, cause: str
) -> None:
    """Each way a PR can be ungrounded is exactly one blocker that says what is missing."""
    blockers = _blockers(_ready_pr(), gh=_grounding_gh(files, closing=closing))
    assert [cause in blocker for blocker in blockers] == [True], blockers


def test_an_invalid_roadmap_config_is_one_blocker(roadmap_board: InMemoryRoadmapStore) -> None:
    roadmap_board.seed_file(CONST_ROADMAP_CONFIG_PATH, "board = 0\n")
    blockers = _blockers(_ready_pr(), gh=_grounding_gh([_ARCHIVE_704]))
    assert blockers == [
        "PR #335 is not grounded: the roadmap board in .github/roadmap.toml could not be read "
        "(.github/roadmap.toml: board: Input should be greater than or equal to 1)."
    ]


@pytest.mark.usefixtures("unreadable_github_roadmap")
def test_a_roadmap_config_github_cannot_read_is_one_blocker() -> None:
    blockers = _blockers(_ready_pr(), gh=_grounding_gh([_ARCHIVE_704]))
    assert [
        "the roadmap board in .github/roadmap.toml could not be read (" in blocker
        for blocker in blockers
    ] == [True], blockers


def test_a_pr_into_another_branch_is_one_blocker_naming_the_default_branch() -> None:
    """GitHub closes an issue only when its PR merges into the default branch, so a PR into any
    other branch is held there, and its issues are not read."""
    gh = _grounding_gh([_ARCHIVE_704])
    base = {"ref": "feat/stacked", "sha": "b" * 40, "repo": _REPO}
    blockers = _blockers(_ready_pr(base=base), gh=gh)
    sent = [" ".join(call.args[0]) for call in gh.call_args_list]
    assert (blockers, any(_CLOSING_ROUTE in call for call in sent)) == (
        [
            "PR #335 is not grounded: it targets feat/stacked, not the default branch main. "
            "Change its base with devops pr edit 335 --base main."
        ],
        False,
    )


def test_a_pr_whose_repository_names_no_default_branch_is_one_blocker() -> None:
    base = {"ref": "main", "sha": "b" * 40, "repo": {"full_name": _OWN_REPO}}
    blockers = _blockers(_ready_pr(base=base), gh=_grounding_gh([_ARCHIVE_704]))
    assert blockers == [
        "PR #335 is not grounded: GitHub names no default branch for dan-petty/devops-cli."
    ]


def test_grounding_skips_a_base_without_change_folders() -> None:
    """A 404 for `openspec/changes` means the repository keeps none, so nothing is required.

    None of the other repositories devops-cli manages has the directory, and a file list that
    can't be read there is a warning, not a blocker.
    """
    gh = _grounding_gh(_SERVER_ERROR, changes_dir=_NOT_FOUND)
    with patch("devops_cli.commands.pr.print_warning") as warn:
        blockers = _blockers(_ready_pr(body="", base={"ref": "feat/x", "repo": _REPO}), gh=gh)
    assert (blockers, warn.call_count, "Could not read the files" in str(warn.call_args)) == (
        [],
        1,
        True,
    )


def test_grounding_blocks_when_the_change_directory_lookup_fails() -> None:
    """Only a 404 rules grounding out; any other failure is a blocker that names it."""
    blockers = _blockers(_ready_pr(), gh=_grounding_gh([_ARCHIVE_704], changes_dir=_SERVER_ERROR))
    assert blockers == [
        "PR #335 is not grounded: openspec/changes/ could not be read at its base "
        "(gh: Server Error (HTTP 500))."
    ]


def test_grounding_reads_the_files_the_base_the_closing_issues_and_the_board_once_each(
    routed_session: _RoutedSession, roadmap_store_repos: list[str]
) -> None:
    """The files are one session listing at `per_page=100` (GitHub's default page is 30), then
    gh reads the base's change directory and the issues the PR closes in one GraphQL request, and
    the roadmap store reads the board. A files read sent through `gh api` instead shows here as
    a gh call."""
    from devops_cli.commands.pr import closing_issues_args

    gh = _grounding_gh([_ARCHIVE_704])
    _blockers(_ready_pr(), gh=gh)
    assert (
        routed_session.reads,
        [call.args[0] for call in gh.call_args_list],
        roadmap_store_repos,
    ) == (
        ["/repos/dan-petty/devops-cli/pulls/335/files?per_page=100"],
        [
            [_SESSION_READ, "GET", "repos/dan-petty/devops-cli/pulls/335/files?per_page=100"],
            [
                "gh",
                "api",
                "--silent",
                f"repos/dan-petty/devops-cli/contents/openspec/changes?ref={'b' * 40}",
            ],
            closing_issues_args("dan-petty", "devops-cli", 335),
        ],
        ["dan-petty/devops-cli"],
    )


def test_the_closing_issues_read_asks_for_the_pr_and_both_page_sizes() -> None:
    from devops_cli.commands.pr import closing_issues_args

    argv = closing_issues_args("dan-petty", "devops-cli", 335)
    assert (argv[:3], argv[-10:]) == (
        ["gh", "api", "graphql"],
        [
            "-f",
            "owner=dan-petty",
            "-f",
            "name=devops-cli",
            "-F",
            "number=335",
            "-F",
            "issues=10",
            "-F",
            "cards=100",
        ],
    )


@pytest.mark.parametrize(
    "closing",
    [_closing(), _closing(_closing_issue(1), _closing_issue(2)), _SERVER_ERROR],
    ids=["none", "several", "unread"],
)
def test_the_board_is_read_only_for_a_pr_that_closes_one_issue(
    closing: MagicMock, roadmap_store_repos: list[str]
) -> None:
    _blockers(_ready_pr(), gh=_grounding_gh([_ARCHIVE_704], closing=closing))
    assert roadmap_store_repos == []


_FILES_READ = "repos/dan-petty/devops-cli/pulls/335/files?per_page=100"
_FILES_PAGE_2 = "/repositories/1/pulls/335/files?per_page=100&page=2"


def test_the_changed_files_are_read_from_every_linked_page(github_api: GitHubApiFake) -> None:
    """The 101st file, on the second page, is read through the session.

    PR #738 changed 51 files; a read stopping at GitHub's default page of 30 missed the rest.
    """
    from devops_cli.commands import pr as pr_module

    first = [_file(f"src/m{n}.py") for n in range(100)]
    github_api.route("GET", f"/{_FILES_READ}", github_json(first, headers=next_page(_FILES_PAGE_2)))
    github_api.route("GET", _FILES_PAGE_2, github_json([_ARCHIVE_704]))
    files = pr_module._fetch_pr_files(335, "dan-petty", "devops-cli")
    assert (len(files), files[-1], len(github_api.sent)) == (
        101,
        ChangedFile("openspec/changes/archive/2026-10-23-704-x/proposal.md", "added"),
        2,
    )


def test_a_changed_files_page_that_is_no_list_is_a_read_failure(github_api: GitHubApiFake) -> None:
    """Readiness keeps a malformed second page as the read's failure, not a shorter file list."""
    from devops_cli.commands import pr as pr_module

    github_api.route(
        "GET", f"/{_FILES_READ}", github_json([_ARCHIVE_704], headers=next_page(_FILES_PAGE_2))
    )
    github_api.route(
        "GET",
        _FILES_PAGE_2,
        httpx2.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>"),
    )
    read = pr_module._read_pr_files(335, "dan-petty", "devops-cli")
    assert (read.files, "page 2" in read.error) == ([], True)


@pytest.mark.parametrize(
    ("entry", "error"),
    [
        ("not an object", "returned a non-object entry"),
        ({"filename": "a.py"}, "returned an entry without a filename or status"),
    ],
    ids=["non-object", "no-status"],
)
def test_a_malformed_files_entry_is_a_read_failure(entry: object, error: str) -> None:
    gh = _grounding_gh([entry])
    blockers = _blockers(_ready_pr(), gh=gh)
    assert [error in blocker for blocker in blockers] == [True], blockers


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
