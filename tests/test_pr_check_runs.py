"""Unit tests for GitHub check-runs classification and retrieval."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.commands.pr import (
    _check_run_blockers,
    _classify_check_run,
    _failing_check_runs,
    _fetch_check_runs_payload,
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
        with patch("devops_cli.commands.pr.run_gh", return_value=mock_res):
            with pytest.raises(RuntimeError):
                _fetch_check_runs_payload("owner", "repo", "sha123")


def test_fetch_check_runs_payload_success_paginated() -> None:
    page1 = {"check_runs": [{"name": "ci-lint", "status": "completed"}]}
    page2 = {"check_runs": [{"name": "ci-test", "status": "completed"}]}
    mock_ok = MagicMock(
        returncode=0,
        stdout=json.dumps([page1, page2]),
        stderr="",
    )
    with patch("devops_cli.commands.pr.run_gh", return_value=mock_ok):
        res = _fetch_check_runs_payload("owner", "repo", "sha123")
        assert (len(res), res[0]["name"], res[1]["name"]) == (2, "ci-lint", "ci-test")


def test_failing_check_runs_and_commit_statuses_integration() -> None:
    runs_payload = [
        {"name": "unit-tests", "status": "completed", "conclusion": "failure"},
        {"name": "build", "status": "in_progress"},
        {"name": "lint", "status": "completed", "conclusion": "success"},
    ]
    statuses_payload = [
        {"context": "security/sonar", "state": "failure"},
        {"context": "deploy/preview", "state": "pending"},
        {"context": "code-review/approved", "state": "success"},
    ]
    with patch("devops_cli.commands.pr._fetch_check_runs_payload", return_value=runs_payload):
        with patch(
            "devops_cli.commands.pr._fetch_commit_statuses_payload", return_value=statuses_payload
        ):
            failing, pending = _failing_check_runs("owner", "repo", "sha123")
            assert (failing, pending) == (
                ["unit-tests", "security/sonar"],
                ["build", "deploy/preview"],
            )


def test_check_run_blockers_fails_closed_on_api_error() -> None:
    pr_data = {"head": {"sha": "abcdef123456"}}
    with patch(
        "devops_cli.commands.pr._failing_check_runs",
        side_effect=RuntimeError("GitHub API 500 Internal Server Error"),
    ):
        blockers = _check_run_blockers(
            pr_data, pr_num=42, owner="owner", repo_name="repo", allow_pending_checks=False
        )
        assert len(blockers) == 1
        assert "check verification failed closed" in blockers[0]
