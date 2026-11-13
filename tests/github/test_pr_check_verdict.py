"""Unit tests for fail-closed PR check verdict classifier and aggregator."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    classify_check_item,
    fetch_pr_check_verdicts,
    read_check_runs,
)
from tests.support.fakes.github import JSON_TYPE, GitHubApiFake, github_json, next_page
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.recorded_check_runs import PR_5357_HEAD, REPLACED_CHECK, pr_5357_head_runs

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


def test_fetch_pr_check_verdicts_from_gh_json() -> None:
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


def test_fetch_pr_check_verdicts_falls_back_to_rest_on_cli_error(github_api: GitHubApiFake) -> None:
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
    mock_rest_statuses = json.dumps(
        {
            "state": "success",
            "total_count": 1,
            "statuses": [
                {
                    "context": "ci/status",
                    "state": "success",
                    "target_url": "https://example.com/s",
                }
            ],
        }
    )
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="GraphQL error: rate limit"),
            MagicMock(returncode=0, stdout=mock_pr_view, stderr=""),
            MagicMock(returncode=0, stdout=mock_rest_statuses, stderr=""),
        ]
    )
    github_api.route("GET", _check_runs("c0ffee123456"), _json(mock_rest_check_runs))
    verdict = fetch_pr_check_verdicts(184, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.pass_count,
        verdict.pending_count,
        [i.name for i in verdict.items],
    ) == (8, 2, 1, ["Tests", "Coverage", "ci/status"])


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
    mock_rest_statuses = json.dumps(
        {
            "state": "success",
            "total_count": 1,
            "statuses": [
                {
                    "context": "ci/status",
                    "state": "success",
                    "target_url": "https://example.com/s",
                }
            ],
        }
    )
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI json not available"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "headsha999"}}), stderr=""),
            MagicMock(returncode=0, stdout=mock_rest_statuses, stderr=""),
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
        verdict.items[-1].name,
    ) == (6, 1, False, 2, 1, 1, 1, 1, "ci/status")


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


_ACTIONS, _OTHER_APP = 15368, 57789


def _run(
    conclusion: str | None,
    started_at: str | None,
    *,
    status: str = "completed",
    completed_at: str | None = None,
    app: int = _ACTIONS,
) -> dict[str, Any]:
    return {
        "name": "Fail-to-Pass Check",
        "status": status,
        "conclusion": conclusion,
        "started_at": started_at,
        "completed_at": completed_at,
        "app": {"id": app},
    }


_EARLY, _LATE = "2026-11-13T04:32:51Z", "2026-11-13T06:41:35Z"


@pytest.mark.parametrize(
    ("runs", "buckets"),
    [
        ([_run("cancelled", _EARLY), _run("success", _LATE)], [CheckBucket.PASS]),
        ([_run("cancelled", _EARLY)], [CheckBucket.CANCEL]),
        ([_run("success", _EARLY), _run("cancelled", _LATE)], [CheckBucket.CANCEL]),
        ([_run("failure", _EARLY), _run("success", _LATE)], [CheckBucket.PASS]),
        ([_run("success", _EARLY), _run("failure", _LATE)], [CheckBucket.FAIL]),
        ([_run("success", _LATE), _run("failure", _EARLY)], [CheckBucket.PASS]),
        (
            [_run("success", _EARLY), _run(None, _LATE, status="in_progress")],
            [CheckBucket.PENDING],
        ),
        (
            [_run("failure", None, completed_at=_EARLY), _run("success", None, completed_at=_LATE)],
            [CheckBucket.PASS],
        ),
        ([_run("success", _LATE), _run("failure", None)], [CheckBucket.PASS, CheckBucket.FAIL]),
        ([_run("failure", _EARLY), _run("success", _EARLY)], [CheckBucket.FAIL, CheckBucket.PASS]),
        (
            [_run("failure", _EARLY), _run("success", _LATE, app=_OTHER_APP)],
            [CheckBucket.FAIL, CheckBucket.PASS],
        ),
    ],
    ids=[
        "replaced-cancel",
        "cancel-only",
        "cancel-after-pass",
        "failure-then-pass",
        "pass-then-failure",
        "newest-listed-first",
        "pass-then-running",
        "completed-at-when-no-start",
        "no-time-stays",
        "same-start-both-stay",
        "other-app-both-stay",
    ],
)
def test_only_the_latest_run_of_each_check_counts(
    github_api: GitHubApiFake,
    pin_github_session: str,
    runs: list[dict[str, Any]],
    buckets: list[CheckBucket],
) -> None:
    """A new event on a pull request starts a new workflow run in a new check suite, and the
    REST API lists the latest run of a check in each suite. Only the run of a check that started
    last counts, whatever its conclusion: a newer pass replaces an older failure, and a newer
    failure or cancel stays a failure (#5383). A run that has no time, and runs that start at the
    same time or come from two apps, all stay."""
    github_api.route(
        "GET", _check_runs("sha5383"), github_json({"total_count": len(runs), "check_runs": runs})
    )

    verdict = read_check_runs("owner", "repo", "sha5383")

    assert [item.bucket for item in verdict.items] == buckets


@pytest.mark.parametrize(
    ("newer_fails", "passing", "failing"),
    [(False, True, []), (True, False, [REPLACED_CHECK])],
    ids=["newer-run-passed", "newer-run-failed"],
)
def test_the_recorded_head_of_pr_5357_counts_the_latest_run_of_each_check(
    github_api: GitHubApiFake,
    pin_github_session: str,
    newer_fails: bool,
    passing: bool,
    failing: list[str],
) -> None:
    """The head of pull request 5357 had two runs of 20 of its 25 checks in two check suites, and
    its older Fail-to-Pass Check run failed. The latest run of each check passed (20) or was
    skipped (5), so the head passes (#5383)."""
    runs = pr_5357_head_runs(newer_fails=newer_fails)
    github_api.route(
        "GET",
        f"/repos/owner/repo/commits/{PR_5357_HEAD}/check-runs?per_page=100",
        github_json({"total_count": len(runs), "check_runs": runs}),
    )

    verdict = read_check_runs("owner", "repo", PR_5357_HEAD)

    assert (
        verdict.is_passing,
        len(verdict.items),
        verdict.skipping_count,
        [item.name for item in verdict.items if item.bucket is CheckBucket.FAIL],
    ) == (passing, 25, 5, failing)


@pytest.mark.parametrize(
    "error",
    [StopIteration("status mock exhausted"), IndexError("status index out of range")],
    ids=["stop-iteration", "index-error"],
)
def test_commit_status_read_raising_propagates_and_never_passes(
    github_api: GitHubApiFake, error: BaseException
) -> None:
    """When check runs pass and the commit status runner raises StopIteration or IndexError,
    fetch_pr_check_verdicts propagates the exception rather than returning a passing verdict (#1350)."""
    github_api.route("GET", _check_runs("sha_raise"), github_json(_ONE_PASSING_BUILD))
    responses = iter(
        [
            subprocess.CompletedProcess(["gh"], 1, "", "CLI error"),
            subprocess.CompletedProcess(["gh"], 0, json.dumps({"head": {"sha": "sha_raise"}}), ""),
        ]
    )

    def runner(_cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        try:
            return next(responses)
        except StopIteration:
            raise error from None

    with pytest.raises(type(error)) as raised:
        fetch_pr_check_verdicts(1350, repo="owner/repo", runner=runner)
    assert str(raised.value) != "" or getattr(raised.value, "error_code", None) is not None


def test_with_no_repo_the_fallback_reads_the_origin_of_the_checkout_it_gets(
    github_api: GitHubApiFake, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """With no `repo`, the REST fallback reads the checks in the repository of the origin of the
    checkout that the caller gives, not of the directory that the process runs in (#2127)."""
    (tmp_path / ".git").mkdir()
    process_fake.answer(
        "git remote get-url origin", ProcessAnswer(stdout="https://github.com/owner/repo.git\n")
    )
    github_api.route("GET", _check_runs("sha2127"), github_json(_ONE_PASSING_BUILD))
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(
                returncode=0,
                stdout=json.dumps({"state": "success", "total_count": 0, "statuses": []}),
                stderr="",
            ),
        ]
    )
    verdict = fetch_pr_check_verdicts(
        2127, head_sha="sha2127", runner=mock_runner, checkout=tmp_path
    )
    assert (verdict.is_passing, [call.cwd for call in process_fake.calls]) == (
        True,
        [tmp_path.resolve()],
    )


def _check_run(name: str, status: str, conclusion: str | None) -> dict[str, Any]:
    return {"name": name, "status": status, "conclusion": conclusion}


@pytest.mark.parametrize(
    ("runs", "passing", "buckets"),
    [
        ([_check_run("build", "completed", "success")], True, [CheckBucket.PASS]),
        (
            [
                _check_run("build", "completed", "success"),
                _check_run("lint", "completed", "skipped"),
            ],
            True,
            [CheckBucket.PASS, CheckBucket.SKIPPING],
        ),
        (
            [
                _check_run("build", "completed", "success"),
                _check_run("test", "completed", "failure"),
            ],
            False,
            [CheckBucket.PASS, CheckBucket.FAIL],
        ),
        ([_check_run("test", "completed", "cancelled")], False, [CheckBucket.CANCEL]),
        (
            [_check_run("build", "completed", "success"), _check_run("test", "in_progress", None)],
            False,
            [CheckBucket.PASS, CheckBucket.PENDING],
        ),
        ([], False, [CheckBucket.PENDING]),
    ],
    ids=["passed", "passed-and-skipped", "failed", "cancelled", "running", "no-check-yet"],
)
def test_the_check_runs_of_a_commit_pass_only_when_every_run_ended_and_passed(
    github_api: GitHubApiFake,
    pin_github_session: str,
    runs: list[dict[str, Any]],
    passing: bool,
    buckets: list[CheckBucket],
) -> None:
    github_api.route(
        "GET",
        _check_runs("headsha"),
        github_json({"total_count": len(runs), "check_runs": runs}),
    )

    verdict = read_check_runs("owner", "repo", "headsha")

    assert (verdict.is_passing, [item.bucket for item in verdict.items]) == (passing, buckets)


def test_the_check_runs_of_a_commit_are_read_with_one_request_and_no_commit_status(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The App token holds no `statuses` permission, so the read must not call that endpoint."""
    github_api.route("GET", _check_runs("headsha"), github_json(_ONE_PASSING_BUILD))

    read_check_runs("owner", "repo", "headsha")

    assert github_api.requested == [
        "GET https://api.github.com/repos/owner/repo/commits/headsha/check-runs?per_page=100"
    ]


def test_check_runs_that_cannot_be_read_do_not_pass(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    verdict = read_check_runs("owner", "repo", "headsha")

    assert (verdict.is_passing, verdict.items, "check-runs" in verdict.unread_reason) == (
        False,
        [],
        True,
    )


def test_check_runs_of_a_missing_head_do_not_pass() -> None:
    verdict = read_check_runs("owner", "repo", "")

    assert (verdict.is_passing, bool(verdict.unread_reason)) == (False, True)
