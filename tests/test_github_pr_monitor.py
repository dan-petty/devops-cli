"""Unit tests for GitHub PR monitoring engine."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.pr_monitor import (
    CopilotReviewStatus,
    PRCheckRun,
    PRMonitorStatus,
    _CopilotTimeline,
    _fetch_raw_reviews,
    _query_timeline_copilot_state,
    get_pr_monitoring_status,
    monitor_pr,
    resolve_branch_pr_number,
)
from devops_cli.github.pr_threads import ReviewComment, ReviewThread
from tests.copilot_review_payloads import (
    CHANGES_RECOMMENDED,
    FIRST_REVIEW_ID,
    MAINTAINER,
    NO_CHANGES,
    SECOND_REVIEW_ID,
    TIMELINE_COPILOT,
    copilot_pass,
    copilot_review,
    review_request_removed,
    review_requested,
    reviewed,
    work_started,
)
from tests.github_session_fakes import GitHubApiFake, github_json, next_page

# The timeline and the reviews of PR #168, as the GitHub session reads them (#983).
_TIMELINE_168 = "/repos/dan-petty/devops-cli/issues/168/timeline?per_page=100"
_REVIEWS_168 = "/repos/dan-petty/devops-cli/pulls/168/reviews?per_page=100"
_CHECK_RUNS_7316135 = "/repos/dan-petty/devops-cli/commits/7316135/check-runs?per_page=100"


class TestPRMonitorModels:
    """Test data models and properties."""

    def test_pr_check_run_states(self) -> None:
        passing = PRCheckRun(name="Test", status="COMPLETED", conclusion="SUCCESS")
        assert passing.is_completed is True
        assert passing.is_success is True
        assert passing.is_failure is False
        assert passing.is_pending is False

        failing = PRCheckRun(name="Lint", status="COMPLETED", conclusion="FAILURE")
        assert failing.is_completed is True
        assert failing.is_success is False
        assert failing.is_failure is True
        assert failing.is_pending is False

        pending = PRCheckRun(name="Build", status="IN_PROGRESS", conclusion="")
        assert pending.is_completed is False
        assert pending.is_success is False
        assert pending.is_failure is False
        assert pending.is_pending is True

    def test_pr_monitor_status_properties(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        c2 = PRCheckRun(name="Test", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            title="Feature PR",
            head_sha="abcdef1",
            checks=[c1, c2],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=True,
            mergeable_state="clean",
            review_decision="APPROVED",
        )
        assert status.total_checks == 2
        assert status.completed_checks == 2
        assert status.successful_checks == 2
        assert status.failing_checks == []
        assert status.pending_checks == []
        assert status.all_checks_completed is True
        assert status.all_checks_passed is True
        assert status.is_ready_for_merge is True

    def test_pr_monitor_status_not_ready_unresolved_threads(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        thread = ReviewThread(
            id="PRRT_1",
            is_resolved=False,
            path="main.py",
            comments=[ReviewComment(id="PRRC_1", body="Fix this")],
        )
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[thread],
        )
        assert status.is_ready_for_merge is False

    def test_pr_monitor_status_not_ready_copilot_working(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=True, state="working"),
            unresolved_threads=[],
        )
        assert status.is_ready_for_merge is False

    def test_pr_monitor_status_not_ready_blocked_mergeable_state(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable_state="blocked",
        )
        assert status.is_ready_for_merge is False

    def test_pr_monitor_status_not_ready_dirty_conflicts(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=False,
            mergeable_state="dirty",
        )
        assert status.is_ready_for_merge is False

    def test_pr_monitor_status_not_ready_changes_requested(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            has_changes_requested=True,
        )
        assert status.is_ready_for_merge is False

    def test_pr_monitor_status_review_approval_gate(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            title="Feature PR",
            head_sha="abcdef1",
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=True,
            mergeable_state="clean",
            review_decision="REVIEW_REQUIRED",
            require_reviews=True,
        )
        assert status.is_ready_for_merge is False

        # When require_reviews is False, approval is not mandatory
        status.require_reviews = False
        assert status.is_ready_for_merge is True

        # When review is approved, ready for merge even when require_reviews is True
        status.require_reviews = True
        status.review_decision = "APPROVED"
        assert status.is_ready_for_merge is True

    def test_pr_monitor_status_not_ready_unstable_state(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=True,
            mergeable_state="unstable",
            review_decision="APPROVED",
        )
        assert status.is_ready_for_merge is False

    def test_pr_monitor_status_not_ready_unresolved_mergeable(self) -> None:
        c1 = PRCheckRun(name="Lint", status="COMPLETED", conclusion="SUCCESS")
        status = PRMonitorStatus(
            number=100,
            checks=[c1],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=None,
            mergeable_state="clean",
            review_decision="APPROVED",
        )
        assert status.is_ready_for_merge is False


class TestResolveBranchPrNumber:
    """Test resolving PR number from branch."""

    def test_resolve_success(self) -> None:
        mock_proc = MagicMock(returncode=0, stdout="168\n", stderr="")
        with patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc):
            num = resolve_branch_pr_number("feat/test")
            assert num == 168

    def test_resolve_failure_no_branch(self) -> None:
        mock_proc = MagicMock(returncode=1, stdout="", stderr="git error")
        with patch("devops_cli.github.pr_monitor.run_subprocess", return_value=mock_proc):
            with pytest.raises(
                GitHubOperationError, match="Unable to determine current git branch"
            ):
                resolve_branch_pr_number()

    def test_resolve_failure_no_pr(self) -> None:
        mock_proc = MagicMock(returncode=1, stdout="", stderr="no pull requests found")
        with patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc):
            with pytest.raises(GitHubOperationError, match="No open pull request found"):
                resolve_branch_pr_number("feat/untracked")


class TestGetPRMonitoringStatus:
    """Test querying and compiling PR monitoring status."""

    def test_get_pr_monitoring_status_success(self, github_api: GitHubApiFake) -> None:
        pr_rest_data = {
            "number": 168,
            "title": "fix: metrics delta",
            "draft": False,
            "head": {"sha": "7316135"},
            "mergeable": True,
            "mergeable_state": "clean",
        }
        check_runs_data = {
            "check_runs": [
                {
                    "name": "Validation",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/runs/1",
                    "app": {"name": "CI Quality Gate"},
                },
                {
                    "name": "CodeQL",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/runs/2",
                    "app": {"name": "CodeQL"},
                },
            ]
        }
        reviews_data = [
            copilot_review(FIRST_REVIEW_ID, body=NO_CHANGES),
            {
                "user": {"login": "tech-lead"},
                "state": "APPROVED",
                "commit_id": "7316135",
                "submitted_at": "2026-09-12T14:05:00Z",
            },
        ]

        timeline_output = json.dumps(copilot_pass(FIRST_REVIEW_ID))

        github_api.route("GET", _REVIEWS_168, github_json(reviews_data))
        github_api.route("GET", _TIMELINE_168, github_json(json.loads(timeline_output)))
        github_api.route("GET", _CHECK_RUNS_7316135, github_json(check_runs_data))

        def mock_subprocess(cmd: list[str], **kwargs: object) -> MagicMock:
            cmd_str = " ".join(cmd)
            if "pulls/168" in cmd_str:
                return MagicMock(returncode=0, stdout=json.dumps(pr_rest_data), stderr="")
            if "status" in cmd_str:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({"state": "success", "statuses": [], "total_count": 0}),
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("devops_cli.github.pr_monitor.run_gh", side_effect=mock_subprocess),
            patch("devops_cli.github.pr_monitor.list_pr_review_threads", return_value=[]),
        ):
            status = get_pr_monitoring_status("dan-petty", "devops-cli", 168)
            assert status.number == 168
            assert status.title == "fix: metrics delta"
            assert status.total_checks == 2
            assert status.all_checks_passed is True
            assert status.copilot_status.state == "completed"
            assert status.copilot_status.is_active is False
            assert status.unresolved_threads == []
            assert status.is_ready_for_merge is True

    def test_get_pr_monitoring_status_unread_when_reviews_read_fails(
        self, github_api: GitHubApiFake
    ) -> None:
        pr_rest_data = {
            "number": 168,
            "title": "fix: metrics delta",
            "draft": False,
            "head": {"sha": "7316135"},
            "mergeable": True,
            "mergeable_state": "clean",
        }
        check_runs_data = {
            "check_runs": [
                {
                    "name": "Validation",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/runs/1",
                    "app": {"name": "CI Quality Gate"},
                },
            ]
        }
        timeline_output = json.dumps(copilot_pass(FIRST_REVIEW_ID))

        github_api.route("GET", _REVIEWS_168, github_json({"message": "Bad Gateway"}, status=502))
        github_api.route("GET", _TIMELINE_168, github_json(json.loads(timeline_output)))
        github_api.route("GET", _CHECK_RUNS_7316135, github_json(check_runs_data))

        def mock_subprocess(cmd: list[str], **kwargs: object) -> MagicMock:
            cmd_str = " ".join(cmd)
            if "pulls/168" in cmd_str:
                return MagicMock(returncode=0, stdout=json.dumps(pr_rest_data), stderr="")
            if "status" in cmd_str:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({"state": "success", "statuses": [], "total_count": 0}),
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("devops_cli.github.pr_monitor.run_gh", side_effect=mock_subprocess),
            patch("devops_cli.github.pr_monitor.list_pr_review_threads", return_value=[]),
        ):
            status = get_pr_monitoring_status("dan-petty", "devops-cli", 168)
            assert (
                status.copilot_status.state,
                "HTTP 502" in status.copilot_status.unread_reason,
                status.is_review_ready,
            ) == ("unread", True, False)


class TestMonitorPR:
    """Test monitor_pr loop and exit code outcomes."""

    def test_monitor_pr_ready(self) -> None:
        mock_status = PRMonitorStatus(
            number=168,
            title="fix: all green",
            checks=[PRCheckRun(name="CI", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=True,
            mergeable_state="clean",
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=mock_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=False,
            )
            assert result.success is True
            assert result.exit_code == 0
            assert "100% READY FOR MERGING" in result.message

    def test_monitor_pr_failing_checks(self) -> None:
        mock_status = PRMonitorStatus(
            number=168,
            title="fix: broken",
            checks=[
                PRCheckRun(
                    name="Validation",
                    status="COMPLETED",
                    conclusion="FAILURE",
                    url="https://github.com/run/failed",
                )
            ],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=mock_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
            )
            assert result.success is False
            assert result.exit_code == 1
            assert "CI checks failed" in result.message

    def test_monitor_pr_unresolved_threads(self) -> None:
        thread = ReviewThread(
            id="PRRT_kw1",
            is_resolved=False,
            path="src/file.py",
            comments=[ReviewComment(id="C1", body="Please fix memory leak")],
        )
        mock_status = PRMonitorStatus(
            number=168,
            title="fix: comments exist",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[thread],
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=mock_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=False,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "1 unresolved review discussion thread(s)" in result.message

    def test_monitor_pr_timeout(self) -> None:
        pending_status = PRMonitorStatus(
            number=168,
            title="fix: slow",
            checks=[PRCheckRun(name="Validation", status="IN_PROGRESS", conclusion="")],
            copilot_status=CopilotReviewStatus(is_active=True, state="working"),
            unresolved_threads=[],
        )
        with (
            patch(
                "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=pending_status
            ),
            patch("time.sleep", return_value=None),
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=1,
                interval=1,
                settle_timeout=0,
            )
            assert result.success is False
            assert result.exit_code == 3
            assert "timed out" in result.message

    def test_monitor_pr_does_not_certify_ready_while_copilot_unread(self) -> None:
        unread_status = PRMonitorStatus(
            number=168,
            title="fix: ready checks but copilot unread",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(
                is_active=False,
                state="unread",
                unread_reason="HTTP 403: rate limit",
                message="Copilot review state could not be read: HTTP 403: rate limit",
            ),
            unresolved_threads=[],
            review_decision="APPROVED",
            mergeable=True,
            mergeable_state="clean",
        )
        with (
            patch(
                "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=unread_status
            ),
            patch("time.sleep", return_value=None),
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=1,
                interval=1,
                settle_timeout=0,
            )
            assert (result.success, result.exit_code) == (False, 3)
            assert "HTTP 403: rate limit" in result.message

    def test_monitor_pr_changes_requested_returns_exit_code_2(self) -> None:
        cr_status = PRMonitorStatus(
            number=168,
            title="fix: changes requested",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="changes_requested"),
            unresolved_threads=[],
        )
        with patch("devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=cr_status):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=True,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "Copilot review requested changes" in result.message

    def test_monitor_pr_draft_returns_exit_code_2(self) -> None:
        draft_status = PRMonitorStatus(
            number=168,
            title="feat: in-progress work",
            is_draft=True,
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=draft_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=True,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "is still a draft" in result.message

    def test_monitor_pr_blocked_by_protection_returns_exit_code_2(self) -> None:
        blocked_status = PRMonitorStatus(
            number=168,
            title="fix: blocked",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable_state="blocked",
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=blocked_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=True,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "blocked from merging by GitHub" in result.message

    def test_monitor_pr_conflicts_returns_exit_code_2(self) -> None:
        conflict_status = PRMonitorStatus(
            number=168,
            title="fix: conflicts",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=False,
            mergeable_state="dirty",
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=conflict_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=True,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "merge conflicts" in result.message

    def test_detect_copilot_status_detects_changes_recommended_in_body(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert status.state == "changes_requested"
        assert status.is_active is False
        assert "recommended changes" in status.message

    def test_detect_copilot_status_completed_when_zero_unresolved_threads(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status(
            "dan-petty", "devops-cli", 168, reviews_data, unresolved_threads=[]
        )
        assert status.state == "completed"
        assert status.is_active is False
        assert "resolved" in status.message

    def test_detect_copilot_status_retains_changes_requested_when_unresolved_threads_exist(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        unresolved = [
            ReviewThread(
                id="PRRT_123",
                is_resolved=False,
                path="src/main.py",
                line=10,
                comments=[ReviewComment(id="PRRC_1", body="Fix this", author="copilot")],
            )
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status(
            "dan-petty", "devops-cli", 168, reviews_data, unresolved_threads=unresolved
        )
        assert status.state == "changes_requested"
        assert status.is_active is False
        assert "recommended changes" in status.message

    def test_detect_copilot_status_unread_when_timeline_read_fails(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟢 No changes recommended\n\nLooks good!",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route(
            "GET", _TIMELINE_168, github_json({"message": "Resource not accessible"}, status=403)
        )
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        pr_status = PRMonitorStatus(
            number=168,
            title="test",
            copilot_status=status,
            unresolved_threads=[],
            review_decision="APPROVED",
        )
        assert (
            status.state,
            "HTTP 403" in status.unread_reason,
            status.is_active,
            pr_status.is_review_ready,
            f"could not be read: {status.unread_reason}" in status.message,
        ) == ("unread", True, False, False, True)

    def test_detect_copilot_status_unread_wins_over_changes_requested(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nFix this.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json({"message": "Server Error"}, status=500))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert (status.state, "HTTP 500" in status.unread_reason, status.is_active) == (
            "unread",
            True,
            False,
        )

    def test_monitor_pr_succeeds_when_copilot_changes_resolved(self) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        pr_details = {
            "title": "fix: resolved copilot changes",
            "head": {"sha": "headsha123456"},
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
        }
        checks = [PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")]

        with (
            patch("devops_cli.github.pr_monitor._fetch_pr_details", return_value=pr_details),
            patch("devops_cli.github.pr_monitor._fetch_rest_check_runs", return_value=checks),
            patch("devops_cli.github.pr_monitor._fetch_raw_reviews", return_value=reviews_data),
            patch("devops_cli.github.pr_monitor._fetch_unresolved_threads", return_value=[]),
            patch(
                "devops_cli.github.pr_monitor._query_timeline_copilot_state",
                return_value=_CopilotTimeline(event="reviewed"),
            ),
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=False,
            )
            assert result.success is True
            assert result.exit_code == 0
            assert "READY FOR MERGING" in result.message
            assert result.status is not None
            assert result.status.copilot_status.state == "completed"

    def test_monitor_pr_fails_when_copilot_changes_unresolved(self) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        pr_details = {
            "title": "fix: unresolved copilot changes",
            "head": {"sha": "headsha123456"},
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
        }
        checks = [PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")]
        unresolved = [
            ReviewThread(
                id="PRRT_123",
                is_resolved=False,
                path="src/main.py",
                line=10,
                comments=[ReviewComment(id="PRRC_1", body="Fix this", author="copilot")],
            )
        ]

        with (
            patch("devops_cli.github.pr_monitor._fetch_pr_details", return_value=pr_details),
            patch("devops_cli.github.pr_monitor._fetch_rest_check_runs", return_value=checks),
            patch("devops_cli.github.pr_monitor._fetch_raw_reviews", return_value=reviews_data),
            patch(
                "devops_cli.github.pr_monitor._fetch_unresolved_threads", return_value=unresolved
            ),
            patch(
                "devops_cli.github.pr_monitor._query_timeline_copilot_state",
                return_value=_CopilotTimeline(event="reviewed"),
            ),
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=False,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "Copilot review requested changes" in result.message
            assert result.status is not None
            assert result.status.copilot_status.state == "changes_requested"

    def test_detect_copilot_status_excludes_no_changes_recommended(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟢 No changes recommended\n\nAll automated checks look clean.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert status.state == "completed"
        assert status.is_active is False

    def test_detect_copilot_status_uses_latest_review_state(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-09-12T13:00:00Z",
            },
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "APPROVED",
                "submitted_at": "2026-09-12T14:00:00Z",
            },
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json([]))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert status.state == "completed"
        assert status.is_active is False

    def test_detect_copilot_status_human_review_does_not_clear_copilot(
        self, github_api: GitHubApiFake
    ) -> None:
        reviews_data = [copilot_review(FIRST_REVIEW_ID)]
        timeline = json.dumps(
            [*copilot_pass(FIRST_REVIEW_ID), work_started(), reviewed(5444000001, MAINTAINER)]
        )
        from devops_cli.github.pr_monitor import _detect_copilot_status

        github_api.route("GET", _TIMELINE_168, github_json(json.loads(timeline)))
        status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
        assert (status.is_active, status.state) == (True, "working")

    def test_get_pr_monitoring_status_bounds_oversized_errors(self) -> None:
        huge_err = "x" * 500
        mock_proc = MagicMock(returncode=1, stdout="", stderr=huge_err)
        with patch("devops_cli.github.pr_monitor.run_gh", return_value=mock_proc):
            with pytest.raises(GitHubOperationError) as exc_info:
                get_pr_monitoring_status("dan-petty", "devops-cli", 168)
            assert len(str(exc_info.value)) < 350
            assert "x" * 256 in str(exc_info.value)
            assert "x" * 257 not in str(exc_info.value)

    def test_pr_monitor_status_unknown_mergeable_state_not_ready(self) -> None:
        status = PRMonitorStatus(
            number=123,
            title="Test",
            head_sha="abcdef123456",
            is_draft=False,
            mergeable=True,
            mergeable_state="unknown",
            has_changes_requested=False,
            checks=[
                PRCheckRun(name="ci", status="completed", conclusion="success"),
            ],
            copilot_status=CopilotReviewStatus(is_active=False, state="idle", message="idle"),
            unresolved_threads=[],
            failure_reasons=[],
        )
        assert status.is_ready_for_merge is False

    def test_has_active_changes_requested_evaluates_latest_per_user(self) -> None:
        from devops_cli.github.pr_monitor import _has_active_changes_requested

        reviews_resolved = [
            {"user": {"login": "reviewer1"}, "state": "CHANGES_REQUESTED"},
            {"user": {"login": "reviewer1"}, "state": "APPROVED"},
        ]
        assert _has_active_changes_requested(reviews_resolved) is False

        reviews_active = [
            {"user": {"login": "reviewer1"}, "state": "APPROVED"},
            {"user": {"login": "reviewer2"}, "state": "CHANGES_REQUESTED"},
        ]
        assert _has_active_changes_requested(reviews_active) is True

    def test_monitor_pr_blocked_unconditional_with_no_require_reviews(self) -> None:
        blocked_status = PRMonitorStatus(
            number=168,
            title="fix: blocked",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable_state="blocked",
            mergeable=True,
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=blocked_status
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=False,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "blocked from merging by GitHub" in result.message

    def test_monitor_pr_requires_approved_review_decision(self) -> None:
        clean_no_approval = PRMonitorStatus(
            number=168,
            title="fix: waiting on review",
            checks=[PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            unresolved_threads=[],
            mergeable=True,
            mergeable_state="clean",
            review_decision="REVIEW_REQUIRED",
        )
        with patch(
            "devops_cli.github.pr_monitor.get_pr_monitoring_status", return_value=clean_no_approval
        ):
            result = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=10,
                interval=1,
                settle_timeout=0,
                require_reviews=True,
            )
            assert result.success is False
            assert result.exit_code == 2
            assert "requires review approval before merging" in result.message

    def test_resolve_review_decision_latest_per_reviewer(self) -> None:
        from devops_cli.github.pr_monitor import _resolve_review_decision

        raw_reviews = [
            {"user": {"login": "alice"}, "state": "CHANGES_REQUESTED"},
            {"user": {"login": "bob"}, "state": "COMMENTED"},
            {"user": {"login": "alice"}, "state": "APPROVED"},
        ]
        assert _resolve_review_decision(raw_reviews) == "APPROVED"

    def test_resolve_review_decision_ignores_copilot_bot_reviews(self) -> None:
        from devops_cli.github.pr_monitor import _resolve_review_decision

        raw_reviews = [
            {"user": {"login": "copilot-pull-request-reviewer[bot]"}, "state": "CHANGES_REQUESTED"},
            {"user": {"login": "alice"}, "state": "APPROVED"},
        ]
        assert _resolve_review_decision(raw_reviews) == "APPROVED"

    def test_is_copilot_changes_recommended_heading_only(self) -> None:
        """Verify heading extraction correctly flags changes recommended even if body mentions no changes."""
        from devops_cli.github.pr_monitor import _is_copilot_changes_recommended

        body = (
            "### 🟡 Changes recommended\n\n"
            "Summary of changes:\n"
            "- File A: Needs fix\n"
            "- File B: No changes requested\n"
        )
        assert _is_copilot_changes_recommended(body) is True

        no_changes_body = "### 🟢 No changes recommended\n\nLooks great to me!\n"
        assert _is_copilot_changes_recommended(no_changes_body) is False

    def test_resolve_review_decision_stale_commit_id(self) -> None:
        """Verify _resolve_review_decision rejects approvals targeting stale commit_id."""
        from devops_cli.github.pr_monitor import _resolve_review_decision

        raw_reviews = [
            {"user": {"login": "alice"}, "state": "APPROVED", "commit_id": "commit_sha_1"},
        ]
        # When current revision is commit_sha_2, approval on commit_sha_1 is stale
        decision = _resolve_review_decision(raw_reviews, head_sha="commit_sha_2")
        assert decision == "REVIEW_REQUIRED"

        # When current revision matches, approval is valid
        decision_valid = _resolve_review_decision(raw_reviews, head_sha="commit_sha_1")
        assert decision_valid == "APPROVED"

    def test_build_failure_reasons_includes_review_approval(self) -> None:
        """Verify _build_failure_reasons records missing review approval when required."""
        from devops_cli.github.pr_monitor import _build_failure_reasons

        reasons = _build_failure_reasons(
            checks=[],
            unresolved_threads=[],
            copilot_status=CopilotReviewStatus(is_active=False, state="completed"),
            has_changes_requested=False,
            mergeable=True,
            mergeable_state="clean",
            is_draft=False,
            require_reviews=True,
            review_decision="REVIEW_REQUIRED",
        )
        assert any("requires approved review" in r for r in reasons)

    def test_build_failure_reasons_includes_copilot_unread(self) -> None:
        """Verify _build_failure_reasons records unread reason when Copilot review cannot be read."""
        from devops_cli.github.pr_monitor import _build_failure_reasons

        reasons = _build_failure_reasons(
            checks=[],
            unresolved_threads=[],
            copilot_status=CopilotReviewStatus(
                is_active=False,
                state="unread",
                unread_reason="HTTP 403: rate limit",
                message="Copilot review state could not be read: HTTP 403: rate limit",
            ),
            has_changes_requested=False,
            mergeable=True,
            mergeable_state="clean",
            is_draft=False,
            require_reviews=True,
            review_decision="APPROVED",
        )
        assert any(
            "Copilot review state could not be read: HTTP 403: rate limit" in r for r in reasons
        )

    def test_monitor_pr_pending_when_zero_checks_reported(self) -> None:
        """Verify monitor_pr treats 0 runs and 0 statuses as pending 'no checks reported'."""
        pr_details = {
            "title": "feat: zero checks",
            "head": {"sha": "headsha_zero"},
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
        }
        reviews_data = [
            {
                "user": {"login": "lead"},
                "state": "APPROVED",
                "commit_id": "headsha_zero",
            }
        ]
        with (
            patch("devops_cli.github.pr_monitor._fetch_pr_details", return_value=pr_details),
            patch("devops_cli.github.pr_monitor._fetch_raw_reviews", return_value=reviews_data),
            patch("devops_cli.github.pr_monitor._fetch_unresolved_threads", return_value=[]),
            patch(
                "devops_cli.github.pr_monitor._query_timeline_copilot_state",
                return_value=_CopilotTimeline(event="reviewed"),
            ),
            patch(
                "devops_cli.github.check_verdict._fetch_checks_from_rest",
                return_value=CheckVerdictSummary(
                    items=[
                        PRCheckItem(
                            name="no checks reported",
                            bucket=CheckBucket.PENDING,
                            state="pending",
                        )
                    ]
                ),
            ),
        ):
            status = get_pr_monitoring_status("dan-petty", "devops-cli", 168)
            assert (
                status.total_checks,
                status.pending_checks[0].name,
                status.is_ready_for_merge,
            ) == (1, "no checks reported", False)

            res = monitor_pr(
                "dan-petty",
                "devops-cli",
                168,
                timeout=1,
                interval=1,
                settle_timeout=0,
                require_reviews=True,
            )
            assert (res.success, res.exit_code, "timed out" in res.message) == (False, 3, True)

    def test_monitor_pr_blocks_on_combined_commit_status_failure(self) -> None:
        """Verify monitor_pr immediately fails when combined status indicates failure."""
        pr_details = {
            "title": "fix: failing combined status",
            "head": {"sha": "headsha_combined"},
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
        }
        with (
            patch("devops_cli.github.pr_monitor._fetch_pr_details", return_value=pr_details),
            patch("devops_cli.github.pr_monitor._fetch_raw_reviews", return_value=[]),
            patch("devops_cli.github.pr_monitor._fetch_unresolved_threads", return_value=[]),
            patch(
                "devops_cli.github.pr_monitor._query_timeline_copilot_state",
                return_value=_CopilotTimeline(event="reviewed"),
            ),
            patch(
                "devops_cli.github.check_verdict._fetch_checks_from_rest",
                return_value=CheckVerdictSummary(
                    items=[
                        PRCheckItem(
                            name="commit status (combined)",
                            bucket=CheckBucket.FAIL,
                            state="failure",
                        )
                    ]
                ),
            ),
        ):
            res = monitor_pr(
                "dan-petty", "devops-cli", 168, timeout=5, interval=1, settle_timeout=0
            )
            assert (res.success, res.exit_code, "CI checks failed" in res.message) == (
                False,
                1,
                True,
            )

    def test_monitor_pr_fails_closed_when_checks_unread(self) -> None:
        """Verify monitor_pr fails closed with exit code 1 when checks API cannot be read."""
        pr_details = {
            "title": "fix: unread checks",
            "head": {"sha": "headsha_unread"},
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
        }
        with (
            patch("devops_cli.github.pr_monitor._fetch_pr_details", return_value=pr_details),
            patch("devops_cli.github.pr_monitor._fetch_raw_reviews", return_value=[]),
            patch("devops_cli.github.pr_monitor._fetch_unresolved_threads", return_value=[]),
            patch(
                "devops_cli.github.pr_monitor._query_timeline_copilot_state",
                return_value=_CopilotTimeline(event="reviewed"),
            ),
            patch(
                "devops_cli.github.check_verdict._fetch_checks_from_rest",
                return_value=CheckVerdictSummary(
                    unread_reason="GitHub commit status API error: HTTP 500"
                ),
            ),
        ):
            status = get_pr_monitoring_status("dan-petty", "devops-cli", 168)
            assert (
                any("check verification failed closed" in r for r in status.failure_reasons),
                status.is_ready_for_merge,
            ) == (True, False)

            res = monitor_pr(
                "dan-petty", "devops-cli", 168, timeout=5, interval=1, settle_timeout=0
            )
            assert (
                res.success,
                res.exit_code,
                "check verification failed closed: GitHub commit status API error: HTTP 500"
                in res.message,
            ) == (False, 1, True)


# ── Timeline and reviews through the GitHub session (#983) ───────────────────────────────────────

_TIMELINE = "/repos/octo/repo/issues/168/timeline?per_page=100"
_TIMELINE_PAGE_2 = "/repositories/1/issues/168/timeline?per_page=100&page=2"
_REVIEWS = "/repos/octo/repo/pulls/168/reviews?per_page=100"
_REVIEWS_PAGE_2 = "/repositories/1/pulls/168/reviews?per_page=100&page=2"


def test_a_two_page_timeline_gives_both_copilot_events(github_api: GitHubApiFake) -> None:
    """Copilot starting on page 1 and finishing on page 2 reads as finished: every page is read."""
    github_api.route(
        "GET",
        _TIMELINE,
        github_json([work_started(), {"event": "commented"}], headers=next_page(_TIMELINE_PAGE_2)),
    )
    github_api.route("GET", _TIMELINE_PAGE_2, github_json([reviewed(FIRST_REVIEW_ID)]))
    state = _query_timeline_copilot_state("octo", "repo", 168, frozenset({FIRST_REVIEW_ID}))
    assert (state, len(github_api.sent)) == (_CopilotTimeline(event="reviewed"), 2)


def test_a_timeline_page_that_is_no_list_leaves_the_copilot_state_unread(
    github_api: GitHubApiFake,
) -> None:
    """A malformed second page is a read failure, never a timeline that ends early."""
    github_api.route(
        "GET", _TIMELINE, github_json([work_started()], headers=next_page(_TIMELINE_PAGE_2))
    )
    github_api.route("GET", _TIMELINE_PAGE_2, github_json({"message": "Server Error"}))
    state = _query_timeline_copilot_state("octo", "repo", 168, frozenset())
    assert (state.working, state.event, "page 2" in state.error) == (False, "", True)


# A person's review and one by the coding agent, which the timeline also names `Copilot`.
_PERSON_REVIEW_ID = 5444000001
_CODING_AGENT_EVENT_ID = 5444000002
_BOT_REVIEWER = {"login": "github-actions[bot]", "type": "Bot", "id": 41898282}


@pytest.mark.parametrize(
    ("events", "state"),
    [
        pytest.param([], _CopilotTimeline(), id="no-events"),
        pytest.param(
            [work_started(), reviewed(_PERSON_REVIEW_ID, _BOT_REVIEWER)],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="another-reviewer-leaves-copilot-working",
        ),
        pytest.param(
            copilot_pass(FIRST_REVIEW_ID),
            _CopilotTimeline(event="reviewed"),
            id="copilot-review-ends-the-work",
        ),
        pytest.param(
            [work_started(), reviewed(_PERSON_REVIEW_ID, MAINTAINER)],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="a-persons-review-leaves-copilot-working",
        ),
        pytest.param(
            [work_started(), reviewed(_CODING_AGENT_EVENT_ID, TIMELINE_COPILOT)],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="a-copilot-event-that-is-no-copilot-review-leaves-copilot-working",
        ),
        pytest.param(
            ["not an event", work_started()],
            _CopilotTimeline(working=True, event="copilot_work_started"),
            id="non-object-entries-skipped",
        ),
        pytest.param(
            [review_requested()],
            _CopilotTimeline(requested=True),
            id="a-request-copilot-has-not-started-is-pending",
        ),
        pytest.param(
            [*copilot_pass(FIRST_REVIEW_ID), review_requested()],
            _CopilotTimeline(event="reviewed", requested=True),
            id="a-request-after-a-finished-pass-is-pending",
        ),
        pytest.param(
            [review_requested(), review_request_removed()],
            _CopilotTimeline(),
            id="a-withdrawn-request-is-not-pending",
        ),
        pytest.param(
            [review_requested(MAINTAINER)],
            _CopilotTimeline(),
            id="a-request-to-a-person-is-not-copilots",
        ),
    ],
)
def test_the_timeline_events_give_the_copilot_state(
    events: list[object], state: _CopilotTimeline
) -> None:
    """Copilot works from its start event until the `reviewed` event of one of its own reviews,
    named by the review's id, since the timeline names the account `Copilot` (#1345). A request
    to it is pending until it starts, is withdrawn, or a review of its ends the pass."""
    from devops_cli.github.pr_monitor import _timeline_copilot_state

    assert _timeline_copilot_state(events, frozenset({FIRST_REVIEW_ID})) == state


def test_the_reviews_are_read_from_every_page(github_api: GitHubApiFake) -> None:
    """Both pages of a pull request's reviews are read, in order."""
    github_api.route(
        "GET",
        _REVIEWS,
        github_json(
            [{"user": {"login": "user1"}, "state": "APPROVED"}],
            headers=next_page(_REVIEWS_PAGE_2),
        ),
    )
    github_api.route(
        "GET", _REVIEWS_PAGE_2, github_json([{"user": {"login": "user2"}, "state": "COMMENTED"}])
    )
    reviews = _fetch_raw_reviews("octo", "repo", 168)
    assert ([review["user"]["login"] for review in reviews], reviews.error) == (
        ["user1", "user2"],
        "",
    )


def test_a_failed_reviews_read_is_reported_with_no_reviews(github_api: GitHubApiFake) -> None:
    """A reviews read that fails gives no reviews and the reason, not a shorter list."""
    github_api.route("GET", _REVIEWS, github_json({"message": "Bad Gateway"}, status=502))
    reviews = _fetch_raw_reviews("octo", "repo", 168)
    assert (list(reviews), "HTTP 502" in reviews.error) == ([], True)


def test_a_review_by_a_user_whose_login_contains_copilot_is_not_copilots(
    github_api: GitHubApiFake,
) -> None:
    """Only Copilot's own logins make a review Copilot's (#1345): a person named copilot-fan who
    recommends changes and approves is a person reviewing, so Copilot is idle and the approval
    counts."""
    from devops_cli.github.pr_monitor import _detect_copilot_status, _resolve_review_decision

    reviews = [
        {
            "user": {"login": "copilot-fan", "type": "User"},
            "state": "APPROVED",
            "commit_id": "7316135",
            "body": "### Changes recommended\n\nRename this.",
            "submitted_at": "2026-10-18T10:00:00Z",
        }
    ]
    github_api.route("GET", _TIMELINE_168, github_json([]))
    status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews)
    assert (status.state, _resolve_review_decision(reviews, head_sha="7316135")) == (
        "idle",
        "APPROVED",
    )


# ── #1283's first two Copilot passes, as GitHub recorded them (#1345) ─────────────────────────────

_REVIEWS_1283 = "/repos/dan-petty/devops-cli/pulls/1283/reviews?per_page=100"
_TIMELINE_1283 = "/repos/dan-petty/devops-cli/issues/1283/timeline?per_page=100"
_HEAD_1283 = "1d2c3b4a5f6e"


class _Clock:
    """`time` as `monitor_pr` reads it, where a sleep moves the clock on and takes no time."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _route_1283(github_api: GitHubApiFake, *, second_body: str, then: list[object]) -> list[object]:
    """Route #1283's reviews and timeline: two finished Copilot passes, the second with
    `second_body`, a person's approval of the head, and the events in `then` after them."""
    reviews = [
        copilot_review(FIRST_REVIEW_ID),
        copilot_review(SECOND_REVIEW_ID, body=second_body, submitted_at="2026-10-07T15:35:57Z"),
        {"id": 5444999999, "user": MAINTAINER, "state": "APPROVED", "commit_id": _HEAD_1283},
    ]
    timeline = [*copilot_pass(FIRST_REVIEW_ID), *copilot_pass(SECOND_REVIEW_ID), *then]
    github_api.route("GET", _REVIEWS_1283, github_json(reviews))
    github_api.route("GET", _TIMELINE_1283, github_json(timeline))
    return reviews


def test_two_finished_copilot_passes_read_as_completed(github_api: GitHubApiFake) -> None:
    """Each `reviewed` event names one of Copilot's reviews, so both passes have ended."""
    from devops_cli.github.pr_monitor import _detect_copilot_status

    reviews = _route_1283(github_api, second_body=NO_CHANGES, then=[])
    status = _detect_copilot_status("dan-petty", "devops-cli", 1283, reviews, unresolved_threads=[])
    assert (status.is_active, status.state) == (False, "completed")


_UNRESOLVED = ReviewThread(
    id="PRRT_1283",
    is_resolved=False,
    path="src/devops_cli/github/pr_monitor.py",
    line=1,
    comments=[ReviewComment(id="PRRC_1283", body="Rename this.", author="Copilot")],
)


@pytest.mark.parametrize(
    ("second_body", "then", "threads", "exit_code", "says"),
    [
        pytest.param(NO_CHANGES, [], [], 0, "READY FOR MERGING", id="ready"),
        pytest.param(
            NO_CHANGES, [work_started()], [], 3, "Copilot review still active", id="third-pass"
        ),
        pytest.param(
            CHANGES_RECOMMENDED,
            [],
            [_UNRESOLVED],
            2,
            "Copilot review requested changes",
            id="unresolved-thread",
        ),
    ],
)
def test_the_monitor_reads_1283s_recorded_copilot_passes(
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
    second_body: str,
    then: list[object],
    threads: list[ReviewThread],
    exit_code: int,
    says: str,
) -> None:
    """With checks green, an approval of the head and a clean merge, the monitor passes once
    Copilot's two passes have ended, waits while a third runs, and stops on an unresolved
    thread of Copilot's."""
    from devops_cli.github import pr_monitor

    _route_1283(github_api, second_body=second_body, then=then)
    pr_details = {
        "title": "feat: thirteen copilot passes",
        "head": {"sha": _HEAD_1283},
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
    }
    checks = [PRCheckRun(name="Validation", status="COMPLETED", conclusion="SUCCESS")]
    monkeypatch.setattr(pr_monitor, "time", _Clock())
    with (
        patch("devops_cli.github.pr_monitor._fetch_pr_details", return_value=pr_details),
        patch("devops_cli.github.pr_monitor._fetch_rest_check_runs", return_value=checks),
        patch("devops_cli.github.pr_monitor._fetch_unresolved_threads", return_value=threads),
    ):
        result = pr_monitor.monitor_pr(
            "dan-petty", "devops-cli", 1283, timeout=120, interval=60, settle_timeout=0
        )
    assert (result.exit_code, says in result.message) == (exit_code, True)


def test_a_pending_copilot_request_leaves_the_monitor_waiting_on_nothing(
    github_api: GitHubApiFake,
) -> None:
    """A request Copilot has not started is no running pass: the monitor never waits on a
    request Copilot may never take up (#1566, #1581 and #1615 got no Copilot review)."""
    from devops_cli.github.pr_monitor import _detect_copilot_status

    github_api.route("GET", _TIMELINE_168, github_json([review_requested()]))
    status = _detect_copilot_status("dan-petty", "devops-cli", 168, [])
    assert (status.is_active, status.state, status.pass_requested) == (False, "idle", True)
