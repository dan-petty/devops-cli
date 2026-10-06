"""Unit tests for GitHub check-runs classification and retrieval."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.commands.pr import (
    _check_run_blockers,
    _classify_check_run,
    _failing_check_runs,
)
from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    _fetch_check_runs_from_rest,
)


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        (None, (None, None)),
        ("invalid", (None, None)),
        (123, (None, None)),
        ({}, (None, "check")),
        ({"name": "lint", "status": "in_progress"}, (None, "lint")),
        ({"name": "build", "status": "queued"}, (None, "build")),
        ({"name": "test", "status": "completed", "conclusion": "success"}, (None, None)),
        ({"name": "audit", "status": "completed", "conclusion": "failure"}, ("audit", None)),
        ({"name": "sec", "status": "completed", "conclusion": "timed_out"}, ("sec", None)),
        ({"name": "gate", "status": "completed", "conclusion": "cancelled"}, ("gate", None)),
        (
            {"name": "req", "status": "completed", "conclusion": "action_required"},
            ("req", None),
        ),
    ],
)
def test_classify_check_run(run: object, expected: tuple[str | None, str | None]) -> None:
    assert _classify_check_run(run) == expected


def test_fetch_check_runs_payload_error_cases_raise_runtime_error() -> None:
    cases = [
        MagicMock(returncode=1, stdout="", stderr="error"),
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=0, stdout="invalid json", stderr=""),
        MagicMock(returncode=0, stdout="[1, 2, 3]", stderr=""),
        MagicMock(returncode=0, stdout=json.dumps({"check_runs": "bad"}), stderr=""),
    ]
    for mock_res in cases:
        mock_runner = MagicMock(return_value=mock_res)
        _, err = _fetch_check_runs_from_rest("owner", "repo", "sha123", runner=mock_runner)
        assert bool(err) is True


def test_fetch_check_runs_payload_success_paginated() -> None:
    page1 = {"check_runs": [{"name": "ci-lint", "status": "completed", "conclusion": "success"}]}
    page2 = {"check_runs": [{"name": "ci-test", "status": "completed", "conclusion": "success"}]}
    mock_ok = MagicMock(
        returncode=0,
        stdout=json.dumps([page1, page2]),
        stderr="",
    )
    mock_runner = MagicMock(return_value=mock_ok)
    items, err = _fetch_check_runs_from_rest("owner", "repo", "sha123", runner=mock_runner)
    assert (err, len(items), items[0].name, items[1].name) == ("", 2, "ci-lint", "ci-test")


def test_failing_check_runs_and_commit_statuses_integration() -> None:
    mock_summary = CheckVerdictSummary(
        items=[
            PRCheckItem(name="unit-tests", bucket=CheckBucket.FAIL, state="failure"),
            PRCheckItem(name="build", bucket=CheckBucket.PENDING, state="in_progress"),
            PRCheckItem(name="lint", bucket=CheckBucket.PASS, state="success"),
            PRCheckItem(name="security/sonar", bucket=CheckBucket.FAIL, state="failure"),
            PRCheckItem(name="deploy/preview", bucket=CheckBucket.PENDING, state="pending"),
            PRCheckItem(name="code-review/approved", bucket=CheckBucket.PASS, state="success"),
        ]
    )
    with patch(
        "devops_cli.github.check_verdict._fetch_checks_from_rest", return_value=mock_summary
    ):
        failing, pending = _failing_check_runs("owner", "repo", "sha123")
        assert (failing, pending) == (
            ["unit-tests", "security/sonar"],
            ["build", "deploy/preview"],
        )


def test_failing_check_runs_raises_on_unread() -> None:
    mock_summary = CheckVerdictSummary(unread_reason="GitHub commit status API error: HTTP 500")
    with patch(
        "devops_cli.github.check_verdict._fetch_checks_from_rest", return_value=mock_summary
    ):
        with pytest.raises(RuntimeError, match="GitHub commit status API error: HTTP 500"):
            _failing_check_runs("owner", "repo", "sha123")


def test_check_run_blockers_blocks_on_no_checks_reported() -> None:
    pr_data = {"head": {"sha": "abcdef123456"}}
    mock_summary = CheckVerdictSummary(
        items=[PRCheckItem(name="no checks reported", bucket=CheckBucket.PENDING, state="pending")]
    )
    with patch(
        "devops_cli.github.check_verdict._fetch_checks_from_rest", return_value=mock_summary
    ):
        blockers = _check_run_blockers(
            pr_data, pr_num=42, owner="owner", repo_name="repo", allow_pending_checks=False
        )
        assert blockers == ["PR #42 has 1 check(s) still running: no checks reported."]


def test_check_run_blockers_blocks_on_combined_commit_status_failure() -> None:
    pr_data = {"head": {"sha": "abcdef123456"}}
    mock_summary = CheckVerdictSummary(
        items=[
            PRCheckItem(name="commit status (combined)", bucket=CheckBucket.FAIL, state="failure")
        ]
    )
    with patch(
        "devops_cli.github.check_verdict._fetch_checks_from_rest", return_value=mock_summary
    ):
        blockers = _check_run_blockers(
            pr_data, pr_num=42, owner="owner", repo_name="repo", allow_pending_checks=False
        )
        assert blockers == ["PR #42 has 1 failing check(s): commit status (combined)."]


def test_check_run_blockers_fails_closed_on_api_error() -> None:
    pr_data = {"head": {"sha": "abcdef123456"}}
    with patch(
        "devops_cli.commands.pr._failing_check_runs",
        side_effect=RuntimeError("GitHub API 500 Internal Server Error"),
    ):
        blockers = _check_run_blockers(
            pr_data, pr_num=42, owner="owner", repo_name="repo", allow_pending_checks=False
        )
        assert (len(blockers), "check verification failed closed" in blockers[0]) == (1, True)


def test_run_gh_paginated_handles_check_runs_dict() -> None:
    from subprocess import CompletedProcess

    from devops_cli.github.rate_limiter import GitHubRateLimiter, _run_gh_paginated

    limiter = GitHubRateLimiter()
    page1 = {"total_count": 2, "check_runs": [{"name": "test-1"}]}
    page2 = {"total_count": 2, "check_runs": [{"name": "test-2"}]}

    calls = [
        CompletedProcess(["gh"], 0, json.dumps(page1), ""),
        CompletedProcess(["gh"], 0, json.dumps(page2), ""),
    ]

    with patch("devops_cli.github.rate_limiter._execute_single_page", side_effect=calls):
        res = _run_gh_paginated(
            ["api", "--paginate", "--slurp", "repos/owner/repo/commits/sha/check-runs?per_page=1"],
            limiter=limiter,
            target_resource="checks",
        )
        assert (res.returncode, json.loads(res.stdout)) == (0, [page1, page2])
