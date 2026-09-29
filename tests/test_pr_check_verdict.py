"""Unit tests for fail-closed PR check verdict classifier and aggregator."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    classify_check_item,
    fetch_pr_check_verdicts,
)


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


def test_fetch_pr_check_verdicts_rest_fallback_on_cli_failure() -> None:
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
            MagicMock(returncode=0, stdout=mock_rest_check_runs, stderr=""),
        ]
    )
    verdict = fetch_pr_check_verdicts(184, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.pass_count,
        verdict.pending_count,
        verdict.items[0].name,
        verdict.items[1].name,
    ) == (8, 1, 1, "Tests", "Coverage")


def test_fetch_pr_check_verdicts_fails_closed_when_rest_fails() -> None:
    """Verify fetch_pr_check_verdicts returns unread verdict when both CLI and REST fail."""
    mock_runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="CLI error"),
            MagicMock(returncode=0, stdout=json.dumps({"head": {"sha": "sha123"}}), stderr=""),
            MagicMock(returncode=1, stdout="", stderr="REST HTTP 500 error"),
        ]
    )
    verdict = fetch_pr_check_verdicts(184, repo="owner/repo", runner=mock_runner)
    assert (
        verdict.exit_code,
        verdict.is_passing,
        "REST HTTP 500 error" in verdict.unread_reason,
    ) == (1, False, True)
