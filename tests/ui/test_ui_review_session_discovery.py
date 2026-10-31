"""Tests for Review Session Discovery behaviour in reactive dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.review.session import ReviewSession
from devops_cli.ui.data_providers import (
    fetch_review_status,
)
from tests.support.builders import make_finding


def _make_sessions(tmp_path: Path, spec: dict[str, int | None]) -> Path:
    """Create review sessions; a None count leaves the session in staging, still being written."""
    reviews = tmp_path / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    for name, count in spec.items():
        directory = reviews / name
        if count is None:
            ReviewSession(directory).create()
        else:
            directory.mkdir()
            findings = [make_finding(severity="LOW", title=f"f{i}") for i in range(count)]
            payload = {"findings": [f.model_dump() for f in findings]}
            (directory / "findings.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_an_in_progress_review_does_not_displace_the_last_completed_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A running review writes into staging before it publishes anything.

    Taking the newest session therefore presented an empty one as the latest result and hid
    the last real review behind it.
    """
    root = _make_sessions(
        tmp_path, {"20260921-212653": None, "20260920-124350": 55, "20260919-145233": 286}
    )
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status()
    assert (summary.session_name, summary.total_findings) == ("20260920-124350", 55)


def test_a_review_with_nothing_completed_still_shows_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Showing the in-flight session beats showing nothing at all."""
    root = _make_sessions(tmp_path, {"20260921-212653": None})
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status()
    assert (summary.has_session, summary.session_name, summary.total_findings) == (
        True,
        "20260921-212653",
        0,
    )


def test_a_workspace_that_was_never_reviewed_has_no_review_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workspace that has never been reviewed is not an error."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    assert fetch_review_status().has_session is False


def test_every_finding_of_a_session_is_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The provider keeps every finding of a session, so a session of 60 findings gives 60."""
    root = _make_sessions(tmp_path, {"20260930-000000": 60})
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status()
    assert (len(summary.findings), summary.total_findings) == (60, 60)
