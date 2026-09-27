"""Unit tests for GitHub check-runs classification and retrieval."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.commands.pr import (
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


def test_fetch_check_runs_payload_error_cases() -> None:
    mock_nonzero = MagicMock(returncode=1, stdout="", stderr="error")
    mock_empty = MagicMock(returncode=0, stdout="", stderr="")
    mock_bad_json = MagicMock(returncode=0, stdout="invalid json", stderr="")
    mock_non_dict = MagicMock(returncode=0, stdout="[1, 2, 3]", stderr="")
    mock_non_list_field = MagicMock(
        returncode=0, stdout=json.dumps({"check_runs": "bad"}), stderr=""
    )

    with patch("devops_cli.commands.pr.run_gh", return_value=mock_nonzero):
        assert _fetch_check_runs_payload("owner", "repo", "sha123") == []

    with patch("devops_cli.commands.pr.run_gh", return_value=mock_empty):
        assert _fetch_check_runs_payload("owner", "repo", "sha123") == []

    with patch("devops_cli.commands.pr.run_gh", return_value=mock_bad_json):
        assert _fetch_check_runs_payload("owner", "repo", "sha123") == []

    with patch("devops_cli.commands.pr.run_gh", return_value=mock_non_dict):
        assert _fetch_check_runs_payload("owner", "repo", "sha123") == []

    with patch("devops_cli.commands.pr.run_gh", return_value=mock_non_list_field):
        assert _fetch_check_runs_payload("owner", "repo", "sha123") == []


def test_fetch_check_runs_payload_success() -> None:
    expected_runs = [{"name": "ci", "status": "completed"}]
    mock_ok = MagicMock(
        returncode=0,
        stdout=json.dumps({"check_runs": expected_runs}),
        stderr="",
    )
    with patch("devops_cli.commands.pr.run_gh", return_value=mock_ok):
        assert _fetch_check_runs_payload("owner", "repo", "sha123") == expected_runs


def test_failing_check_runs_integration() -> None:
    payload = [
        {"name": "unit-tests", "status": "completed", "conclusion": "failure"},
        {"name": "build", "status": "in_progress"},
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "sec-scan", "status": "completed", "conclusion": "timed_out"},
    ]
    with patch("devops_cli.commands.pr._fetch_check_runs_payload", return_value=payload):
        failing, pending = _failing_check_runs("owner", "repo", "sha123")
        assert (failing, pending) == (["unit-tests", "sec-scan"], ["build"])
