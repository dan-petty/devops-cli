"""Unit tests for workspace and data tier cleanup engine."""

from __future__ import annotations

import os
import time
from pathlib import Path

from devops_cli.core.cleanup import cleanup_data_tier


def test_cleanup_data_tier_pruning(tmp_path: Path) -> None:
    data_dir = tmp_path / ".data"
    reviews_dir = data_dir / "reviews"
    reviews_dir.mkdir(parents=True)

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
    data_dir.mkdir(parents=True)

    old_file = data_dir / "old_analysis.json"
    old_file.write_text("{}", encoding="utf-8")
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    summary = cleanup_data_tier(repo_root=tmp_path, older_than_seconds=7 * 86400, dry_run=True)

    assert len(summary.pruned_files) == 1
    assert old_file.exists()  # Kept in dry-run mode
