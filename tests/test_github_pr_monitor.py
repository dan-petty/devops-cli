"""Unit tests for GitHub PR monitoring engine."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_monitor import (
    CopilotReviewStatus,
    PRCheckRun,
    PRMonitorStatus,
    get_pr_monitoring_status,
    monitor_pr,
    resolve_branch_pr_number,
)
from devops_cli.github.pr_threads import ReviewComment, ReviewThread


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


class TestResolveBranchPrNumber:
    """Test resolving PR number from branch."""

    def test_resolve_success(self) -> None:
        mock_proc = MagicMock(returncode=0, stdout="168\n", stderr="")
        with patch("devops_cli.github.pr_monitor.run_subprocess", return_value=mock_proc):
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
        with patch("devops_cli.github.pr_monitor.run_subprocess", return_value=mock_proc):
            with pytest.raises(GitHubOperationError, match="No open pull request found"):
                resolve_branch_pr_number("feat/untracked")


class TestGetPRMonitoringStatus:
    """Test querying and compiling PR monitoring status."""

    def test_get_pr_monitoring_status_success(self) -> None:
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
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "submitted_at": "2026-09-12T13:59:17Z",
            },
            {
                "user": {"login": "tech-lead"},
                "state": "APPROVED",
                "commit_id": "7316135",
                "submitted_at": "2026-09-12T14:05:00Z",
            },
        ]

        timeline_output = (
            '{"event": "copilot_work_started", "created_at": "2026-09-12T13:52:12Z"}\n'
            '{"event": "reviewed", "submitted_at": "2026-09-12T13:59:17Z"}\n'
        )

        def mock_subprocess(cmd: list[str], **kwargs: object) -> MagicMock:
            cmd_str = " ".join(cmd)
            if "pulls/168/reviews" in cmd_str:
                return MagicMock(returncode=0, stdout=json.dumps(reviews_data), stderr="")
            if "pulls/168" in cmd_str:
                return MagicMock(returncode=0, stdout=json.dumps(pr_rest_data), stderr="")
            if "check-runs" in cmd_str:
                return MagicMock(returncode=0, stdout=json.dumps(check_runs_data), stderr="")
            if "timeline" in cmd_str:
                return MagicMock(returncode=0, stdout=timeline_output, stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("devops_cli.github.pr_monitor.run_subprocess", side_effect=mock_subprocess),
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

    def test_detect_copilot_status_detects_changes_recommended_in_body(self) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟡 Changes recommended\n\nUnresolved concerns remain.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        with patch("devops_cli.github.pr_monitor.run_subprocess") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")
            status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
            assert status.state == "changes_requested"
            assert status.is_active is False
            assert "recommended changes" in status.message

    def test_detect_copilot_status_excludes_no_changes_recommended(self) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "body": "### 🟢 No changes recommended\n\nAll automated checks look clean.",
                "submitted_at": "2026-09-12T14:00:00Z",
            }
        ]
        from devops_cli.github.pr_monitor import _detect_copilot_status

        with patch("devops_cli.github.pr_monitor.run_subprocess") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")
            status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
            assert status.state == "completed"
            assert status.is_active is False

    def test_detect_copilot_status_uses_latest_review_state(self) -> None:
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

        with patch("devops_cli.github.pr_monitor.run_subprocess") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")
            status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
            assert status.state == "completed"
            assert status.is_active is False

    def test_detect_copilot_status_human_review_does_not_clear_copilot(self) -> None:
        reviews_data = [
            {
                "user": {"login": "copilot-pull-request-reviewer[bot]"},
                "state": "COMMENTED",
                "submitted_at": "2026-09-12T13:00:00Z",
            }
        ]
        timeline = (
            '{"event": "copilot_work_started", "created_at": "2026-09-12T13:00:00Z"}\n'
            '{"event": "reviewed", "author": "human-developer", "submitted_at": "2026-09-12T13:05:00Z"}\n'
        )
        from devops_cli.github.pr_monitor import _detect_copilot_status

        with patch("devops_cli.github.pr_monitor.run_subprocess") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout=timeline, stderr="")
            status = _detect_copilot_status("dan-petty", "devops-cli", 168, reviews_data)
            assert status.is_active is True
            assert status.state == "working"

    def test_get_pr_monitoring_status_bounds_oversized_errors(self) -> None:
        huge_err = "x" * 500
        mock_proc = MagicMock(returncode=1, stdout="", stderr=huge_err)
        with patch("devops_cli.github.pr_monitor.run_subprocess", return_value=mock_proc):
            with pytest.raises(GitHubOperationError) as exc_info:
                get_pr_monitoring_status("dan-petty", "devops-cli", 168)
            assert len(str(exc_info.value)) < 350
            assert "x" * 256 in str(exc_info.value)
            assert "x" * 257 not in str(exc_info.value)

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

    def test_fetch_raw_reviews_paginated(self) -> None:
        from devops_cli.github.pr_monitor import _fetch_raw_reviews

        page1 = json.dumps([{"user": {"login": "user1"}, "state": "APPROVED"}])
        page2 = json.dumps([{"user": {"login": "user2"}, "state": "COMMENTED"}])
        paginated_stdout = f"{page1}\n{page2}\n"

        with patch("devops_cli.github.pr_monitor.run_subprocess") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout=paginated_stdout, stderr="")
            reviews = _fetch_raw_reviews("dan-petty", "devops-cli", 168)
            assert len(reviews) == 2
            assert reviews[0]["user"]["login"] == "user1"
            assert reviews[1]["user"]["login"] == "user2"

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
