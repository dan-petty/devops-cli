"""Unit tests for GitHub check-runs classification and retrieval."""

from __future__ import annotations

from unittest.mock import patch

import httpx2
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
from tests.github_session_fakes import GitHubApiFake, github_json, next_page


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


_CHECK_RUNS = "/repos/octo/repo/commits/sha123/check-runs?per_page=100"
_CHECK_RUNS_PAGE_2 = "/repositories/1/commits/sha123/check-runs?per_page=100&page=2"


def _check_runs_page(*names: str, next_url: str | None = None) -> httpx2.Response:
    """One page of the check-runs listing, its runs passed."""
    runs = [{"name": name, "status": "completed", "conclusion": "success"} for name in names]
    return github_json(
        {"total_count": 2, "check_runs": runs}, headers=next_page(next_url) if next_url else None
    )


def test_check_runs_are_read_from_every_page(github_api: GitHubApiFake) -> None:
    """The check-runs listing is read through the session, page after linked page."""
    github_api.route("GET", _CHECK_RUNS, _check_runs_page("ci-lint", next_url=_CHECK_RUNS_PAGE_2))
    github_api.route("GET", _CHECK_RUNS_PAGE_2, _check_runs_page("ci-test"))
    items, err = _fetch_check_runs_from_rest("octo", "repo", "sha123")
    assert (err, [item.name for item in items]) == ("", ["ci-lint", "ci-test"])


@pytest.mark.parametrize(
    "second_page",
    [
        pytest.param(
            httpx2.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=b"<html>upstream 502 Bad Gateway</html>",
            ),
            id="html",
        ),
        pytest.param(github_json({"check_runs": "bad"}), id="runs-not-a-list"),
        pytest.param(github_json({"message": "Server Error"}), id="error-object"),
        pytest.param(github_json({"message": "Bad Gateway"}, status=502), id="5xx"),
    ],
)
def test_a_malformed_second_check_runs_page_is_a_read_failure_in_readiness(
    github_api: GitHubApiFake, second_page: httpx2.Response
) -> None:
    """Readiness reports a check-runs page it can't read as a read failure, never as a shorter
    list of passing checks."""
    github_api.route("GET", _CHECK_RUNS, _check_runs_page("ci-lint", next_url=_CHECK_RUNS_PAGE_2))
    github_api.route("GET", _CHECK_RUNS_PAGE_2, second_page)
    blockers = _check_run_blockers(
        {"head": {"sha": "sha123"}},
        pr_num=42,
        owner="octo",
        repo_name="repo",
        allow_pending_checks=False,
    )
    assert (
        len(blockers),
        "check verification failed closed" in blockers[0],
        any(cause in blockers[0] for cause in ("page 2", "HTTP 502")),
    ) == (1, True, True)


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
