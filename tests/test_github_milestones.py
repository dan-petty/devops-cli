"""Test suite for GitHub Milestones extraction, synchronization, and progress tracking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.github.milestones import (
    MilestoneProgress,
    MilestoneSpec,
    MilestoneSyncResult,
    calculate_milestone_progress,
    diff_milestones,
    extract_roadmap_milestones,
    sync_repository_milestones,
)


def test_extract_roadmap_milestones(tmp_path: Path) -> None:
    """extract_roadmap_milestones parses markdown milestone headings into MilestoneSpec objects."""
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        "# Roadmap\n\n"
        "### Core Foundation (v0.0.1 - Completed)\n"
        "- [x] Feature A\n\n"
        "### Valkey Management (v0.2.12 - Scheduled)\n"
        "- [ ] Task 1\n\n"
        "### Library Ingestion (v0.2.13 - Scheduled)\n"
        "- [ ] Task 2\n",
        encoding="utf-8",
    )

    specs = extract_roadmap_milestones(roadmap)
    assert len(specs) >= 2
    titles = [s.title for s in specs]
    assert "v0.2.12" in titles
    assert "v0.2.13" in titles
    valkey_spec = next(s for s in specs if s.title == "v0.2.12")
    assert "Valkey Management" in valkey_spec.description


def test_diff_milestones() -> None:
    """diff_milestones correctly detects new, existing, and closed milestones."""
    desired = [
        MilestoneSpec(title="v0.2.12", description="Valkey"),
        MilestoneSpec(title="v0.2.13", description="Library"),
    ]
    existing = [
        {"title": "v0.2.12", "number": 1, "state": "open", "description": "Valkey"},
    ]

    to_create, existing_matches = diff_milestones(desired, existing)
    assert len(to_create) == 1
    assert to_create[0].title == "v0.2.13"
    assert len(existing_matches) == 1
    assert existing_matches[0]["title"] == "v0.2.12"


def test_sync_repository_milestones_dry_run() -> None:
    """Dry-run milestone synchronization simulates creates without sending mutating requests."""
    desired = [
        MilestoneSpec(title="v0.2.15", description="Scanner Framework"),
    ]
    mock_client = MagicMock()
    mock_client.get_milestones.return_value = []

    res = sync_repository_milestones(mock_client, "dan-petty/devops-cli", desired, dry_run=True)
    assert isinstance(res, MilestoneSyncResult)
    assert res.created_count == 1
    assert res.dry_run is True
    mock_client.create_milestone.assert_not_called()


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes closed ratio and health metrics."""
    data = {
        "title": "v0.2.11",
        "open_issues": 2,
        "closed_issues": 8,
        "state": "open",
    }
    progress = calculate_milestone_progress(data)
    assert isinstance(progress, MilestoneProgress)
    assert progress.total_issues == 10
    assert progress.percent_complete == 80.0
    assert progress.is_complete is False
