"""Tests for the dashboard Review data provider."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ui.data_providers import ReviewSummary, fetch_review_status


def test_fetch_review_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_review_status parses latest session findings and severity counts."""
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260908-120000-sample-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-09-08T12:00:00",
        "personas": ["devsecops"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "status": "UNVERIFIED",
                "verified": False,
            },
            {
                "persona": "qa",
                "severity": "LOW",
                "location": "test.py:10",
                "title": "Missing docstring",
                "status": "VERIFIED",
                "verified": True,
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    summary = fetch_review_status()
    assert isinstance(summary, ReviewSummary)
    assert summary.has_session is True
    assert summary.total_findings == 2
    assert summary.verified_count == 1
    assert summary.unverified_count == 1
    assert summary.severity_distribution["HIGH"] == 1
    assert summary.severity_distribution["LOW"] == 1


def test_fetch_review_status_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_review_status handles missing review directories without error."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    summary = fetch_review_status()
    assert isinstance(summary, ReviewSummary)
    assert summary.has_session is False
    assert summary.total_findings == 0


def test_the_review_summary_reads_sessions_written_where_the_reviews_directory_setting_points(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Verify the summary looks where a review writes, not under `data.dir` beside it."""
    elsewhere = tmp_path / "elsewhere"
    session_dir = elsewhere / "20261001-120000"
    session_dir.mkdir(parents=True)
    (session_dir / "findings.json").write_text('{"findings": [{}, {}]}', encoding="utf-8")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR")
    monkeypatch.setenv("DEVOPS_CLI_DATA_REVIEWS_DIR", str(elsewhere))
    config(data={"dir": str(tmp_path / "data")})

    summary = fetch_review_status()

    assert (summary.has_session, summary.session_name, summary.total_findings) == (
        True,
        "20261001-120000",
        2,
    )


def test_the_review_summary_has_no_session_for_a_reviews_directory_setting_that_is_not_a_path(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """Verify a settings file the schema refuses leaves the review summary empty, not raising."""
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR")
    config(data={"reviews_dir": [1, 2]})

    assert fetch_review_status() == ReviewSummary(has_session=False)


def test_review_status_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify fetch_review_status rejects directory traversal sequences."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "../../../outside")
    assert fetch_review_status() == ReviewSummary(has_session=False)


def test_review_status_rejects_forbidden_system_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify fetch_review_status rejects forbidden system directories."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "/etc")
    assert fetch_review_status() == ReviewSummary(has_session=False)
