"""A poll that reads no check is a poll with no data and reports pending, not ready (#4927)."""

from __future__ import annotations

import json
from typing import Any

import pytest

import devops_cli.github.pr_monitor as pr_monitor
from devops_cli.github.merge_readiness import Blocker, BlockerKind, MergeReadiness
from devops_cli.github.pr_monitor import (
    CopilotReviewStatus,
    PRMonitorStatus,
    RawReviewsList,
    get_pr_monitoring_status,
)
from tests.support.fakes.process import ProcessAnswer


def test_settled_result_with_empty_checks_reports_not_ready() -> None:
    """A settled result with no check runs reported must fail closed and not report ready (#4927)."""
    status = PRMonitorStatus(number=4916, head_sha="7316135", checks=[], blockers=[])
    settle_fn = getattr(pr_monitor, "settled_result", getattr(pr_monitor, "_settled_result", None))
    assert settle_fn is not None
    result = settle_fn(status, 4916)
    assert result.success is False
    assert result.exit_code != 0
    assert "ready" not in result.message.lower()


def test_get_pr_monitoring_status_with_empty_checks(
    github_api_and_gh: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a PR has no check runs reported, it is marked with pending checks and a blocker."""
    _api, gh = github_api_and_gh
    pr_payload = {"number": 168, "state": "open", "draft": False, "head": {"sha": "7316135"}}
    gh.answer(
        lambda call: " ".join(call.argv).endswith("api repos/octo/repo/pulls/168"),
        ProcessAnswer(stdout=json.dumps(pr_payload)),
    )
    monkeypatch.setattr(pr_monitor, "assess_merge_readiness", lambda *a, **k: MergeReadiness())
    monkeypatch.setattr(
        pr_monitor, "fetch_raw_reviews", lambda *a, **k: RawReviewsList([], error="")
    )
    monkeypatch.setattr(
        pr_monitor, "detect_copilot_status", lambda *a, **k: CopilotReviewStatus(state="none")
    )
    monkeypatch.setattr(pr_monitor, "resolve_review_decision", lambda *a, **k: "NONE")

    status = get_pr_monitoring_status("octo", "repo", 168)
    assert "checks" in status.pending_checks
    assert any("has no check runs reported yet" in b for b in status.blockers)


def test_get_pr_monitoring_status_with_no_head_commit_fails_closed(
    github_api_and_gh: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A poll whose payload names no head commit is not ready: checks_failed, a blocker, exit 1
    (#4927)."""
    _api, gh = github_api_and_gh
    pr_payload = {"number": 168, "state": "open", "draft": False}
    gh.answer(
        lambda call: " ".join(call.argv).endswith("api repos/octo/repo/pulls/168"),
        ProcessAnswer(stdout=json.dumps(pr_payload)),
    )
    verdict = MergeReadiness(
        blocking=(
            Blocker(
                BlockerKind.CHECKS_UNREAD,
                "PR #168 check verification failed closed: the pull request read gave no head "
                "commit.",
            ),
        )
    )
    monkeypatch.setattr(pr_monitor, "assess_merge_readiness", lambda *a, **k: verdict)
    monkeypatch.setattr(
        pr_monitor, "fetch_raw_reviews", lambda *a, **k: RawReviewsList([], error="")
    )
    monkeypatch.setattr(
        pr_monitor, "detect_copilot_status", lambda *a, **k: CopilotReviewStatus(state="none")
    )
    monkeypatch.setattr(pr_monitor, "resolve_review_decision", lambda *a, **k: "NONE")

    status = get_pr_monitoring_status("octo", "repo", 168)
    result = pr_monitor.settled_result(status, 168)

    assert (
        status.checks_failed,
        bool(status.blockers),
        result.success,
        result.exit_code,
    ) == (True, True, False, 1)
