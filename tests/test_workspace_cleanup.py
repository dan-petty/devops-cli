"""Unit tests for workspace and data tier cleanup engine."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_REVIEW_STAGING_DIRNAME
from devops_cli.core.cleanup import cleanup_data_tier


@pytest.fixture(autouse=True)
def default_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean the default `.data` under each test's `repo_root`: the suite-wide absolute
    `DEVOPS_CLI_DATA_DIR` would otherwise decide the directory whatever `repo_root` is."""
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)


def test_cleanup_data_tier_pruning(tmp_path: Path) -> None:
    data_dir = tmp_path / ".data"
    reviews_dir = data_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    old_file = reviews_dir / "old_review.json"
    old_file.write_text('{"status": "ok"}', encoding="utf-8")

    # Set old timestamp (10 days ago)
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    new_file = reviews_dir / "recent_review.json"
    new_file.write_text('{"status": "recent"}', encoding="utf-8")

    summary = cleanup_data_tier(repo_root=tmp_path, older_than_seconds=7 * 86400, dry_run=False)

    assert len(summary.pruned_files) == 1
    assert "old_review.json" in summary.pruned_files[0]
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_data_tier_dry_run(tmp_path: Path) -> None:
    data_dir = tmp_path / ".data" / "analysis"
    data_dir.mkdir(parents=True, exist_ok=True)

    old_file = data_dir / "old_analysis.json"
    old_file.write_text("{}", encoding="utf-8")
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    summary = cleanup_data_tier(repo_root=tmp_path, older_than_seconds=7 * 86400, dry_run=True)

    assert len(summary.pruned_files) == 1
    assert old_file.exists()  # Kept in dry-run mode


def test_cleanup_data_tier_directory_pruning_and_missing_dir(tmp_path: Path) -> None:
    """Verify cleanup_data_tier prunes a stale session directory under `repo_root`'s data
    directory, and prunes nothing for a `repo_root` whose data directory does not exist."""
    data_dir = tmp_path / ".data" / "reviews"
    data_dir.mkdir(parents=True, exist_ok=True)
    old_dir = data_dir / "20260101-session"
    old_dir.mkdir(exist_ok=True)
    sub_file = old_dir / "findings.json"
    sub_file.write_text('{"findings": []}', encoding="utf-8")

    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_dir, (ten_days_ago, ten_days_ago))

    # 1. A missing data directory: the stale session elsewhere is not its to prune.
    missing_root = tmp_path / "nonexistent"
    empty_summary = cleanup_data_tier(repo_root=missing_root)
    assert (
        (missing_root / ".data").exists(),
        empty_summary.pruned_files,
        empty_summary.pruned_dirs,
        old_dir.exists(),
    ) == (False, [], [], True)

    # 2. Directory pruning
    summary = cleanup_data_tier(repo_root=tmp_path, older_than_seconds=7 * 86400, dry_run=False)
    assert len(summary.pruned_dirs) == 1
    assert "20260101-session" in summary.pruned_dirs[0]
    assert not old_dir.exists()
    assert summary.freed_bytes > 0


def test_cleanup_judges_each_staged_review_by_its_own_age(tmp_path: Path) -> None:
    """A staged review is pruned when it is old, though other reviews keep `.staging` itself fresh:
    it is the sessions inside `.staging` that cleanup judges, not the directory they share."""
    staging = tmp_path / ".data" / "reviews" / CONST_REVIEW_STAGING_DIRNAME
    abandoned = staging / "20260101-000000"
    running = staging / "20261022-000000"
    for session in (abandoned, running):
        (session / "files").mkdir(parents=True)
        (session / "profile.json").write_text("{}", encoding="utf-8")
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(abandoned, (ten_days_ago, ten_days_ago))

    summary = cleanup_data_tier(repo_root=tmp_path, older_than_seconds=7 * 86400, dry_run=False)

    assert (summary.pruned_dirs, abandoned.exists(), running.exists(), staging.is_dir()) == (
        [f"reviews/{CONST_REVIEW_STAGING_DIRNAME}/20260101-000000"],
        False,
        True,
        True,
    )
