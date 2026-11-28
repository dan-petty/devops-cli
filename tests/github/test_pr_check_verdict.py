"""Unit tests for fail-closed PR check verdict classifier and aggregator."""

from __future__ import annotations

import json
from typing import Any

import pytest

from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    classify_check_item,
    no_checks_reported,
    read_check_runs,
    read_pr_checks,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.recorded_check_runs import PR_5357_HEAD, REPLACED_CHECK, pr_5357_head_runs

# `read_check_runs` reads the check runs through the GitHub session (#983).
_ONE_PASSING_BUILD = {
    "total_count": 1,
    "check_runs": [{"name": "build", "status": "completed", "conclusion": "success"}],
}


def _check_runs(sha: str) -> str:
    """The check-runs listing of `sha` in owner/repo, as the session reads it."""
    return f"/repos/owner/repo/commits/{sha}/check-runs?per_page=100"


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


_PR_CHECKS = (
    "gh",
    "pr",
    "checks",
    "335",
    "--json",
    "name,state,bucket,workflow,link",
    "--repo",
    "dan-petty/devops-cli",
)


def _listed(name: str, state: str, bucket: str) -> dict[str, str]:
    """One entry of the list that `gh pr checks --json name,state,bucket,workflow,link` prints."""
    return {
        "name": name,
        "state": state,
        "bucket": bucket,
        "workflow": "CI",
        "link": f"https://example.com/{name}",
    }


def test_the_checks_of_a_pull_request_are_the_list_that_gh_pr_checks_prints(
    gh_edge: ProcessFake,
) -> None:
    """gh keeps the newest run of each check and each commit status, and gives its bucket, so
    the reader takes each entry as gh lists it (#7508)."""
    listed = [
        _listed("Analyze", "SUCCESS", "pass"),
        _listed("Format", "SKIPPED", "skipping"),
        _listed("CodeQL", "FAILURE", "fail"),
        _listed("Trivy", "IN_PROGRESS", "pending"),
        _listed("zizmor", "CANCELLED", "cancel"),
    ]
    gh_edge.answer(list(_PR_CHECKS), ProcessAnswer(stdout=json.dumps(listed)))

    verdict = read_pr_checks(335, "dan-petty/devops-cli")

    expected = CheckVerdictSummary(
        items=[
            PRCheckItem(
                name=entry["name"],
                state=entry["state"],
                bucket=CheckBucket(entry["bucket"]),
                workflow="CI",
                link=entry["link"],
            )
            for entry in listed
        ]
    )
    assert (verdict, [call.argv for call in gh_edge.calls]) == (expected, [_PR_CHECKS])


@pytest.mark.parametrize(
    "answer",
    [
        ProcessAnswer(returncode=1, stderr="no checks reported on the 'feat/x' branch\n"),
        ProcessAnswer(stdout="[]"),
    ],
    ids=["no-checks-reported", "empty-list"],
)
def test_a_head_with_no_check_reads_as_the_pending_stand_in(
    gh_edge: ProcessFake, answer: ProcessAnswer
) -> None:
    """gh answers a head with no check with exit 1 and `no checks reported`, the exit code of a
    failed check, so the reader tells them apart by the text. A check can still start, so the
    head is pending (#3767, #7508)."""
    gh_edge.answer(list(_PR_CHECKS), answer)

    verdict = read_pr_checks(335, "dan-petty/devops-cli")

    assert (verdict, verdict.reports_nothing, verdict.exit_code) == (
        CheckVerdictSummary(items=[no_checks_reported()]),
        True,
        8,
    )


@pytest.mark.parametrize(
    ("answer", "cause"),
    [
        (
            ProcessAnswer(
                returncode=1, stderr="HTTP 502: Bad Gateway (https://api.github.com/graphql)"
            ),
            "HTTP 502",
        ),
        (ProcessAnswer(returncode=4), "exit code 4"),
        (ProcessAnswer(stdout='{"check_runs": []}'), "no list of checks"),
        (ProcessAnswer(stdout="<html>"), "no list of checks"),
    ],
    ids=["gh-error", "no-stderr", "object", "not-json"],
)
def test_a_failed_read_of_the_checks_fails_closed_with_its_cause(
    gh_edge: ProcessFake, answer: ProcessAnswer, cause: str
) -> None:
    """A read that fails, or output that is no list of checks, is no read of the checks: no item
    passes, and the reason names the cause (#7508)."""
    gh_edge.answer(list(_PR_CHECKS), answer)

    verdict = read_pr_checks(335, "dan-petty/devops-cli")

    assert (verdict.items, verdict.exit_code, cause in verdict.unread_reason) == ([], 1, True), (
        verdict.unread_reason
    )


def test_with_no_repository_gh_reads_the_pull_request_of_the_working_directory(
    gh_edge: ProcessFake,
) -> None:
    """With no `repo`, gh finds the repository itself, so the command sends no `--repo`."""
    gh_edge.answer(
        list(_PR_CHECKS[:6]), ProcessAnswer(stdout=json.dumps([_listed("CI", "SUCCESS", "pass")]))
    )

    verdict = read_pr_checks(335)

    assert (verdict.is_passing, [call.argv for call in gh_edge.calls]) == (True, [_PR_CHECKS[:6]])


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
