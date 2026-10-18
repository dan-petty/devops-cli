"""Unit tests for fail-closed PR check verdict classifier and aggregator."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    classify_check_item,
    fetch_pr_check_verdicts,
)
from tests.github_session_fakes import JSON_TYPE, GitHubApiFake, github_json, next_page

# The REST fallback reads check runs through the GitHub session (#983).
_NO_RUNS = {"total_count": 0, "check_runs": []}
_ONE_PASSING_BUILD = {
    "total_count": 1,
    "check_runs": [{"name": "build", "status": "completed", "conclusion": "success"}],
}


def _check_runs(sha: str) -> str:
    """The check-runs listing of `sha` in owner/repo, as the session reads it."""
    return f"/repos/owner/repo/commits/{sha}/check-runs?per_page=100"


def _json(text: str) -> httpx2.Response:
    """A JSON answer whose body is `text` as written."""
    return httpx2.Response(200, headers={"content-type": JSON_TYPE}, content=text.encode())


def test_check_bucket_values() -> None:
    """Verify CheckBucket enum values match GitHub CLI and fail-closed constants."""
    assert (
        CheckBucket.PASS.value,
        CheckBucket.FAIL.value,
        CheckBucket.PENDING.value,
        CheckBucket.SKIPPING.value,
        CheckBucket.CANCEL.value,
        CheckBucket.UNREAD.value,
    ) == (
        "pass",
        "fail",
        "pending",
        "skipping",
        "cancel",
        "unread",
    )


def test_classify_check_item_from_bucket_field() -> None:
    """Verify classify_check_item correctly uses the bucket attribute when provided."""
    item_pass = classify_check_item("unit-tests", bucket="pass")
    item_fail = classify_check_item("lint", bucket="fail")
    item_pend = classify_check_item("build", bucket="pending")
    item_skip = classify_check_item("deploy", bucket="skipping")
    item_canc = classify_check_item("security", bucket="cancel")
    assert (
        item_pass.bucket,
        item_fail.bucket,
        item_pend.bucket,
        item_skip.bucket,
        item_canc.bucket,
    ) == (
        CheckBucket.PASS,
        CheckBucket.FAIL,
        CheckBucket.PENDING,
        CheckBucket.SKIPPING,
        CheckBucket.CANCEL,
    )


def test_classify_check_item_from_conclusion_and_status() -> None:
    """Verify classify_check_item falls back to conclusion and status fields."""
    c_success = classify_check_item("ci", conclusion="success")
    c_failure = classify_check_item("ci", conclusion="failure")
    c_timeout = classify_check_item("ci", conclusion="timed_out")
    c_cancelled = classify_check_item("ci", conclusion="cancelled")
    c_neutral = classify_check_item("ci", conclusion="neutral")
    s_in_progress = classify_check_item("ci", status="in_progress")
    s_unknown = classify_check_item("ci", status="weird_state")
    assert (
        c_success.bucket,
        c_failure.bucket,
        c_timeout.bucket,
        c_cancelled.bucket,
        c_neutral.bucket,
        s_in_progress.bucket,
        s_unknown.bucket,
    ) == (
        CheckBucket.PASS,
        CheckBucket.FAIL,
        CheckBucket.FAIL,
        CheckBucket.CANCEL,
        CheckBucket.SKIPPING,
        CheckBucket.PENDING,
        CheckBucket.UNREAD,
    )


def test_verdict_summary_exit_codes() -> None:
    """Verify CheckVerdictSummary computes fail-closed exit codes."""
    all_pass = CheckVerdictSummary(
        items=[
            PRCheckItem(name="t1", bucket=CheckBucket.PASS),
            PRCheckItem(name="t2", bucket=CheckBucket.SKIPPING),
        ]
    )
    with_pending = CheckVerdictSummary(
        items=[
            PRCheckItem(name="t1", bucket=CheckBucket.PASS),
            PRCheckItem(name="t2", bucket=CheckBucket.PENDING),
        ]
    )
    with_fail = CheckVerdictSummary(
        items=[
            PRCheckItem(name="t1", bucket=CheckBucket.PASS),
            PRCheckItem(name="t2", bucket=CheckBucket.FAIL),
        ]
    )
    with_cancel = CheckVerdictSummary(
        items=[
            PRCheckItem(name="t1", bucket=CheckBucket.PASS),
            PRCheckItem(name="t2", bucket=CheckBucket.CANCEL),
        ]
    )
    with_unread = CheckVerdictSummary(
        items=[
            PRCheckItem(name="t1", bucket=CheckBucket.PASS),
            PRCheckItem(name="t2", bucket=CheckBucket.UNREAD),
        ]
    )
    with_reason = CheckVerdictSummary(unread_reason="API failure")

    assert (
        all_pass.exit_code,
        all_pass.is_passing,
        with_pending.exit_code,
        with_pending.is_passing,
        with_fail.exit_code,
        with_cancel.exit_code,
        with_unread.exit_code,
        with_reason.exit_code,
    ) == (
        0,
        True,
        8,
        False,
        1,
        1,
        1,
        1,
    )


def test_fetch_pr_check_verdicts_gh_json_success() -> None:
    """Verify fetch_pr_check_verdicts successfully parses gh pr checks JSON output."""
    mock_payload = json.dumps(
        [
            {
                "name": "Analyze",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "CI",
                "link": "https://example.com/1",
            },
            {
                "name": "Format",
                "state": "SKIPPED",
                "bucket": "skipping",
                "workflow": "CI",
                "link": "https://example.com/2",
            },
        ]
    )
    mock_runner = MagicMock(return_value=MagicMock(returncode=0, stdout=mock_payload, stderr=""))
    verdict = fetch_pr_check_verdicts(101, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        verdict.pass_count,
        verdict.skipping_count,
        len(verdict.items),
    ) == (0, True, 1, 1, 2)


def test_fetch_pr_check_verdicts_gh_json_fails_closed_on_failing_bucket() -> None:
    """Verify verdict is fail-closed (exit 1) even when gh pr checks --json exits 0 with a fail bucket."""
    mock_payload = json.dumps(
        [
            {
                "name": "Build",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "CI",
                "link": "https://example.com/1",
            },
            {
                "name": "Analyze",
                "state": "FAILURE",
                "bucket": "fail",
                "workflow": "CI",
                "link": "https://example.com/2",
            },
        ]
    )
    mock_runner = MagicMock(return_value=MagicMock(returncode=0, stdout=mock_payload, stderr=""))
    verdict = fetch_pr_check_verdicts(401, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        verdict.fail_count,
        verdict.pass_count,
    ) == (1, False, 1, 1)


def test_fetch_pr_check_verdicts_rest_fallback_on_cli_failure(github_api: GitHubApiFake) -> None:
    """Verify fetch_pr_check_verdicts falls back to REST check-runs API when CLI checks fail."""
    mock_pr_view = json.dumps({"head": {"sha": "c0ffee123456"}})
    mock_rest_check_runs = json.dumps(
        {
            "check_runs": [
                {
                    "name": "Tests",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://example.com/t",
                },
                {
                    "name": "Coverage",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://example.com/c",
                },
            ]
        }
    )
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="GraphQL error: rate limit"),
            MagicMock(returncode=0, stdout=mock_pr_view, stderr=""),
        ]
    )
    github_api.route("GET", _check_runs("c0ffee123456"), _json(mock_rest_check_runs))
    verdict = fetch_pr_check_verdicts(184, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.pass_count,
        verdict.pending_count,
        verdict.items[0].name,
        verdict.items[1].name,
    ) == (8, 1, 1, "Tests", "Coverage")


def test_fetch_pr_check_verdicts_fails_closed_when_rest_fails(github_api: GitHubApiFake) -> None:
    """Verify fetch_pr_check_verdicts returns unread verdict when both CLI and REST fail."""
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha123"}}), stderr=""),
        ]
    )
    github_api.route(
        "GET", _check_runs("sha123"), github_json({"message": "Server Error"}, status=500)
    )
    verdict = fetch_pr_check_verdicts(184, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        "HTTP 500" in verdict.unread_reason,
    ) == (1, False, True)


def test_bucket_parity_against_gh_pr_checks_json_bucket() -> None:
    """Verify exact parity between GitHub CLI json buckets and REST conclusions/statuses."""
    gh_buckets = ["pass", "fail", "pending", "skipping", "cancel"]
    classified_from_gh = [classify_check_item("t", bucket=b).bucket for b in gh_buckets]
    expected_gh = [
        CheckBucket.PASS,
        CheckBucket.FAIL,
        CheckBucket.PENDING,
        CheckBucket.SKIPPING,
        CheckBucket.CANCEL,
    ]

    rest_conclusions = [
        ("success", CheckBucket.PASS),
        ("failure", CheckBucket.FAIL),
        ("timed_out", CheckBucket.FAIL),
        ("action_required", CheckBucket.FAIL),
        ("startup_failure", CheckBucket.FAIL),
        ("stale", CheckBucket.FAIL),
        ("cancelled", CheckBucket.CANCEL),
        ("skipped", CheckBucket.SKIPPING),
        ("neutral", CheckBucket.SKIPPING),
    ]
    concl_actual = [
        classify_check_item("t", conclusion=c, status="completed").bucket
        for c, _ in rest_conclusions
    ]
    concl_expected = [exp for _, exp in rest_conclusions]

    rest_statuses = [
        ("queued", CheckBucket.PENDING),
        ("in_progress", CheckBucket.PENDING),
        ("waiting", CheckBucket.PENDING),
        ("requested", CheckBucket.PENDING),
        ("pending", CheckBucket.PENDING),
    ]
    status_actual = [classify_check_item("t", status=s).bucket for s, _ in rest_statuses]
    status_expected = [exp for _, exp in rest_statuses]

    commit_states = [
        ("success", CheckBucket.PASS),
        ("failure", CheckBucket.FAIL),
        ("error", CheckBucket.FAIL),
        ("pending", CheckBucket.PENDING),
    ]
    states_actual = [classify_check_item("t", state=st).bucket for st, _ in commit_states]
    states_expected = [exp for _, exp in commit_states]

    assert (
        classified_from_gh,
        concl_actual,
        status_actual,
        states_actual,
    ) == (
        expected_gh,
        concl_expected,
        status_expected,
        states_expected,
    )


def test_rest_pagination_bucket_count_matches_total_count(github_api: GitHubApiFake) -> None:
    """Verify multi-page slurped REST check-runs parse correctly and bucket count matches total_count."""
    page_1 = {
        "total_count": 5,
        "check_runs": [
            {
                "name": "check-1",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://example.com/1",
            },
            {
                "name": "check-2",
                "status": "completed",
                "conclusion": "skipped",
                "html_url": "https://example.com/2",
            },
            {
                "name": "check-3",
                "status": "completed",
                "conclusion": "failure",
                "html_url": "https://example.com/3",
            },
        ],
    }
    page_2 = {
        "total_count": 5,
        "check_runs": [
            {
                "name": "check-4",
                "status": "completed",
                "conclusion": "cancelled",
                "html_url": "https://example.com/4",
            },
            {
                "name": "check-5",
                "status": "in_progress",
                "conclusion": None,
                "html_url": "https://example.com/5",
            },
        ],
    }
    second = "/repositories/1/commits/headsha999/check-runs?per_page=100&page=2"
    github_api.route(
        "GET", _check_runs("headsha999"), github_json(page_1, headers=next_page(second))
    )
    github_api.route("GET", second, github_json(page_2))
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI json not available"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "headsha999"}}), stderr=""),
        ]
    )
    verdict = fetch_pr_check_verdicts(401, repo="owner/repo", runner=mock_runner)
    assert (
        len(verdict.items),
        verdict.exit_code,
        verdict.is_passing,
        verdict.pass_count,
        verdict.skipping_count,
        verdict.fail_count,
        verdict.cancel_count,
        verdict.pending_count,
    ) == (5, 1, False, 1, 1, 1, 1, 1)


def test_fetch_pr_check_verdicts_zero_runs_and_zero_statuses_reports_pending(
    github_api: GitHubApiFake,
) -> None:
    """Verify head commit with 0 runs and 0 statuses reports pending 'no checks reported'."""
    github_api.route("GET", _check_runs("sha_zero"), github_json(_NO_RUNS))
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha_zero"}}), stderr=""),
            MagicMock(
                returncode=0,
                stdout=json.dumps({"state": "pending", "statuses": [], "total_count": 0}),
                stderr="",
            ),
        ]
    )
    verdict = fetch_pr_check_verdicts(100, repo="owner/repo", runner=mock_runner)
    assert (
        len(verdict.items),
        verdict.exit_code,
        verdict.is_passing,
        verdict.pending_count,
        verdict.items[0].name,
        verdict.items[0].bucket,
    ) == (1, 8, False, 1, "no checks reported", CheckBucket.PENDING)


def test_fetch_pr_check_verdicts_gh_json_empty_reports_pending() -> None:
    """Verify gh pr checks returning empty JSON list reports pending 'no checks reported'."""
    mock_runner = MagicMock(return_value=MagicMock(returncode=0, stdout="[]", stderr=""))
    verdict = fetch_pr_check_verdicts(101, repo="owner/repo", runner=mock_runner)
    assert (
        len(verdict.items),
        verdict.exit_code,
        verdict.is_passing,
        verdict.pending_count,
        verdict.items[0].name,
        verdict.items[0].bucket,
    ) == (1, 8, False, 1, "no checks reported", CheckBucket.PENDING)


def test_fetch_pr_check_verdicts_combined_status_failure_past_page_one(
    github_api: GitHubApiFake,
) -> None:
    """Verify >30 status contexts with combined state failure past page 1 blocks fail-closed."""
    github_api.route("GET", _check_runs("sha_combined"), github_json(_ONE_PASSING_BUILD))
    page_1_statuses = [
        {"context": f"ci/status-{i}", "state": "success", "target_url": f"https://example.com/{i}"}
        for i in range(30)
    ]
    status_payload = {
        "state": "failure",
        "total_count": 35,
        "statuses": page_1_statuses,
    }
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(
                returncode=0, stdout=json.dumps({"head": {"sha": "sha_combined"}}), stderr=""
            ),
            MagicMock(returncode=0, stdout=json.dumps(status_payload), stderr=""),
        ]
    )
    verdict = fetch_pr_check_verdicts(200, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        verdict.fail_count,
        any(
            i.name == "commit status (combined)" and i.bucket == CheckBucket.FAIL
            for i in verdict.items
        ),
    ) == (1, False, 1, True)


def test_fetch_pr_check_verdicts_combined_status_pending_past_page_one(
    github_api: GitHubApiFake,
) -> None:
    """Verify >30 status contexts with combined state pending past page 1 yields pending verdict."""
    github_api.route("GET", _check_runs("sha_pending"), github_json(_ONE_PASSING_BUILD))
    page_1_statuses = [
        {"context": f"ci/status-{i}", "state": "success", "target_url": f"https://example.com/{i}"}
        for i in range(30)
    ]
    status_payload = {
        "state": "pending",
        "total_count": 35,
        "statuses": page_1_statuses,
    }
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha_pending"}}), stderr=""),
            MagicMock(returncode=0, stdout=json.dumps(status_payload), stderr=""),
        ]
    )
    verdict = fetch_pr_check_verdicts(201, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        verdict.pending_count,
        any(
            i.name == "commit status (combined)" and i.bucket == CheckBucket.PENDING
            for i in verdict.items
        ),
    ) == (8, False, 1, True)


def test_fetch_pr_check_verdicts_fails_closed_when_commit_statuses_fail(
    github_api: GitHubApiFake,
) -> None:
    """Verify fetch_pr_check_verdicts returns unread verdict when commit status API fails."""
    github_api.route("GET", _check_runs("sha_err"), github_json(_NO_RUNS))
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha_err"}}), stderr=""),
            MagicMock(returncode=1, stdout="", stderr="HTTP 500 status failure"),
        ]
    )
    verdict = fetch_pr_check_verdicts(202, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        "HTTP 500 status failure" in verdict.unread_reason,
    ) == (1, False, True)


def test_fetch_pr_check_verdicts_fails_closed_when_commit_statuses_empty(
    github_api: GitHubApiFake,
) -> None:
    """Verify fetch_pr_check_verdicts returns unread verdict when commit status API returns empty body."""
    github_api.route("GET", _check_runs("sha_empty"), github_json(_NO_RUNS))
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha_empty"}}), stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
    )
    verdict = fetch_pr_check_verdicts(203, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        "empty response" in verdict.unread_reason,
    ) == (1, False, True)


def _run(conclusion: str, started_at: str) -> dict[str, str]:
    return {
        "name": "Fail-to-Pass Check",
        "status": "completed",
        "conclusion": conclusion,
        "started_at": started_at,
    }


@pytest.mark.parametrize(
    ("runs", "passing"),
    [
        (
            [_run("cancelled", "2026-10-16T23:01:07Z"), _run("success", "2026-10-16T23:01:38Z")],
            True,
        ),
        ([_run("cancelled", "2026-10-16T23:01:07Z")], False),
        (
            [_run("success", "2026-10-16T23:01:07Z"), _run("cancelled", "2026-10-16T23:01:38Z")],
            False,
        ),
        ([_run("failure", "2026-10-16T23:01:07Z"), _run("success", "2026-10-16T23:01:38Z")], False),
    ],
    ids=["replaced-cancel", "cancel-only", "cancel-after-pass", "failure-then-pass"],
)
def test_a_cancelled_run_a_newer_run_of_its_check_replaced_does_not_fail_the_pr(
    github_api: GitHubApiFake, runs: list[dict[str, str]], passing: bool
) -> None:
    """A workflow that cancels its in-progress run when a newer event starts it leaves the old
    run, cancelled, beside the new one in the commit's check runs, which the REST API lists
    across check suites. Only that run is dropped: a failure is never hidden."""
    github_api.route(
        "GET", _check_runs("sha1599"), github_json({"total_count": len(runs), "check_runs": runs})
    )
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha1599"}}), stderr=""),
            MagicMock(
                returncode=0,
                stdout=json.dumps({"state": "success", "total_count": 0, "statuses": []}),
                stderr="",
            ),
        ]
    )
    verdict = fetch_pr_check_verdicts(1599, repo="owner/repo", runner=mock_runner)
    assert verdict.is_passing is passing
