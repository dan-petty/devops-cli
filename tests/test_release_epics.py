"""Tests for release epics tracking issue generation, synchronization, and CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.ai.mcp.server import release_epic_sync
from devops_cli.commands.release import app
from devops_cli.github.issues import GitHubIssue
from devops_cli.github.release_epics import (
    ReleaseEpicDeliverable,
    ReleaseEpicSpec,
    ReleaseEpicSyncResult,
    _format_deliverable_line,
    _resolve_item_issue_number,
    build_release_epic_specs,
    find_existing_release_epic,
    render_release_epic_body,
    sync_all_release_epics,
    sync_single_release_epic,
)
from devops_cli.github.roadmap_sync import RoadmapItem

runner = CliRunner()


def test_release_epic_spec_properties() -> None:
    """Validate ReleaseEpicSpec progress calculations."""
    empty_spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Test Milestone",
        deliverables=[],
    )
    assert (
        empty_spec.total_count,
        empty_spec.completed_count,
        empty_spec.percent_complete,
        empty_spec.is_all_completed,
    ) == (0, 0, 100.0, False)

    spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Test Milestone",
        deliverables=[
            ReleaseEpicDeliverable(title="Task 1", is_completed=True),
            ReleaseEpicDeliverable(title="Task 2", is_completed=False),
        ],
    )
    assert (
        spec.total_count,
        spec.completed_count,
        spec.percent_complete,
        spec.is_all_completed,
    ) == (2, 1, 50.0, False)

    all_done_spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Test Milestone",
        deliverables=[
            ReleaseEpicDeliverable(title="Task 1", is_completed=True),
            ReleaseEpicDeliverable(title="Task 2", is_completed=True),
        ],
    )
    assert (
        all_done_spec.total_count,
        all_done_spec.completed_count,
        all_done_spec.percent_complete,
        all_done_spec.is_all_completed,
    ) == (2, 2, 100.0, True)


def test_format_deliverable_line() -> None:
    """Format single deliverable line with and without issue number."""
    item_with_issue = ReleaseEpicDeliverable(
        title="Epic Support",
        issue_number=42,
        priority="priority/p1-high",
        scope="scope/release",
        is_completed=True,
    )
    item_without_issue = ReleaseEpicDeliverable(
        title="Draft Tasks",
        issue_number=None,
        priority="priority/p2-medium",
        scope="scope/cli",
        is_completed=False,
    )
    assert (
        _format_deliverable_line(item_with_issue),
        _format_deliverable_line(item_without_issue),
    ) == (
        "- [x] #42: Epic Support (`priority/p1-high`, `scope/release`)",
        "- [ ] Draft Tasks (`priority/p2-medium`, `scope/cli`)",
    )


def test_render_release_epic_body() -> None:
    """Validate full markdown body generation for release epics."""
    spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Syntopical AI",
        milestone_status="Active",
        deliverables=[
            ReleaseEpicDeliverable(
                title="Deliverable One",
                issue_number=101,
                priority="priority/p1-high",
                scope="scope/ai",
                is_completed=True,
            )
        ],
    )
    body = render_release_epic_body(spec)
    assert (
        "# Release Epic: v0.2.21 — Syntopical AI" in body,
        "**Milestone**: `v0.2.21`" in body,
        "**Deliverable Progress**: 1/1 completed (100.0%)" in body,
        "## Phase 6: SDLC Release Choreography" in body,
        "- [x] #101: Deliverable One" in body,
    ) == (True, True, True, True, True)


def test_resolve_item_issue_number() -> None:
    """Verify issue matching by number and matching by title."""
    issues = [
        GitHubIssue(number=10, title="Syntopical Research", state="closed", labels=[]),
        GitHubIssue(number=20, title="Argo Rollout Hook", state="open", labels=[]),
    ]

    item_with_existing = RoadmapItem(
        raw_title="Syntopical Research",
        title="Syntopical Research",
        milestone="v0.2.21",
        milestone_title="AI",
        milestone_status="Active",
        existing_issue_number=10,
        is_completed=False,
    )
    num1, done1 = _resolve_item_issue_number(item_with_existing, issues)

    item_matching_title = RoadmapItem(
        raw_title="Argo Rollout Hook",
        title="Argo Rollout Hook",
        milestone="v0.2.21",
        milestone_title="AI",
        milestone_status="Active",
        is_completed=False,
    )
    num2, done2 = _resolve_item_issue_number(item_matching_title, issues)

    item_unmatched = RoadmapItem(
        raw_title="Unmatched Work",
        title="Unmatched Work",
        milestone="v0.2.21",
        milestone_title="AI",
        milestone_status="Active",
        is_completed=True,
    )
    num3, done3 = _resolve_item_issue_number(item_unmatched, issues)

    assert ((num1, done1), (num2, done2), (num3, done3)) == (
        (10, True),
        (20, False),
        (None, True),
    )


def test_build_release_epic_specs(tmp_path: Path) -> None:
    """Parse temporary roadmap file and construct ReleaseEpicSpecs."""
    roadmap_content = """# Roadmap

## Release Milestones (Chronological Order)

### Syntopical Research (v0.2.21 - Active)
- [x] #10 Implement AST analysis (`priority/p1-high`, `scope/ai`)
- [ ] Implement query engine (`priority/p2-medium`, `scope/ai`)

### Next Release (v0.2.22 - Scheduled)
- [ ] Setup cluster deploy (`priority/p2-medium`, `scope/k8s`)

## Value vs. Effort Prioritization Matrix
"""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(roadmap_content, encoding="utf-8")

    issues = [
        GitHubIssue(number=10, title="Implement AST analysis", state="closed", labels=[]),
    ]
    specs = build_release_epic_specs(roadmap_file, issues)
    assert len(specs) == 2
    spec1, spec2 = specs[0], specs[1]
    assert (
        spec1.milestone_version,
        spec1.milestone_title,
        spec1.completed_count,
        spec1.total_count,
    ) == ("v0.2.21", "Syntopical Research", 1, 2)
    assert (
        spec2.milestone_version,
        spec2.milestone_title,
        spec2.completed_count,
        spec2.total_count,
    ) == ("v0.2.22", "Next Release", 0, 1)


def test_find_existing_release_epic() -> None:
    """Locate release epic issue by prefix matching."""
    issues = [
        GitHubIssue(number=5, title="Release Epic: v0.2.21 — Syntopical", state="open", labels=[]),
        GitHubIssue(number=6, title="Release Epic: 0.2.22 — Next", state="open", labels=[]),
        GitHubIssue(number=7, title="Regular bug fix", state="open", labels=[]),
    ]
    epic1 = find_existing_release_epic(issues, "v0.2.21")
    epic2 = find_existing_release_epic(issues, "0.2.22")
    epic_none = find_existing_release_epic(issues, "v0.2.23")

    assert (
        epic1.number if epic1 else None,
        epic2.number if epic2 else None,
        epic_none,
    ) == (5, 6, None)


def test_sync_single_release_epic_unchanged() -> None:
    """Sync single release epic when body is identical returns unchanged."""
    spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Title",
        deliverables=[],
    )
    identical_body = render_release_epic_body(spec)
    existing = GitHubIssue(
        number=55,
        title="Release Epic: v0.2.21 — Title",
        body=identical_body,
        state="open",
        labels=[],
    )
    action, num = sync_single_release_epic("example/repo", spec, existing, dry_run=False)
    assert (action, num) == ("unchanged", 55)


def test_sync_single_release_epic_update() -> None:
    """Sync single release epic when body changed executes edit_repository_issue."""
    spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Title",
        deliverables=[ReleaseEpicDeliverable(title="New Work", is_completed=True)],
    )
    existing = GitHubIssue(
        number=55,
        title="Release Epic: v0.2.21 — Title",
        body="Old body text",
        state="open",
        labels=[],
    )
    with patch("devops_cli.github.release_epics.edit_repository_issue") as mock_edit:
        action_dry, num_dry = sync_single_release_epic("example/repo", spec, existing, dry_run=True)
        assert (action_dry, num_dry, mock_edit.called) == ("updated", 55, False)

        action_live, num_live = sync_single_release_epic(
            "example/repo", spec, existing, dry_run=False
        )
        assert (action_live, num_live, mock_edit.called) == ("updated", 55, True)


def test_sync_single_release_epic_create() -> None:
    """Sync single release epic when missing creates new issue."""
    spec = ReleaseEpicSpec(
        milestone_version="v0.2.21",
        milestone_title="Title",
        deliverables=[],
    )
    with patch("devops_cli.github.release_epics.create_repository_issue") as mock_create:
        mock_create.return_value = GitHubIssue(
            number=99,
            title="Release Epic: v0.2.21 — Title",
            body="Body",
            state="open",
            labels=[],
        )
        action_dry, num_dry = sync_single_release_epic("example/repo", spec, None, dry_run=True)
        assert (action_dry, num_dry, mock_create.called) == ("created", None, False)

        action_live, num_live = sync_single_release_epic("example/repo", spec, None, dry_run=False)
        assert (action_live, num_live, mock_create.called) == ("created", 99, True)


def test_sync_all_release_epics(tmp_path: Path) -> None:
    """Verify sync_all_release_epics aggregates counts and respects version filter."""
    roadmap_content = """# Roadmap

## Release Milestones (Chronological Order)

### Syntopical Research (v0.2.21 - Active)
- [x] AST analysis (`priority/p1-high`, `scope/ai`)

### Next Release (v0.2.22 - Scheduled)
- [ ] Cluster deploy (`priority/p2-medium`, `scope/k8s`)

## Value vs. Effort Prioritization Matrix
"""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(roadmap_content, encoding="utf-8")

    with (
        patch("devops_cli.github.release_epics.get_repository_issues", return_value=[]),
        patch("devops_cli.github.release_epics.create_repository_issue") as mock_create,
    ):
        mock_create.return_value = GitHubIssue(
            number=1, title="Test", body="Test", state="open", labels=[]
        )

        res_filter = sync_all_release_epics(
            repo="example/repo",
            roadmap_path=roadmap_file,
            dry_run=True,
            version_filter="v0.2.21",
        )
        assert (res_filter.total_milestones, res_filter.created_count, res_filter.dry_run) == (
            1,
            1,
            True,
        )

        res_all = sync_all_release_epics(
            repo="example/repo",
            roadmap_path=roadmap_file,
            dry_run=False,
        )
        assert (res_all.total_milestones, res_all.created_count, res_all.dry_run) == (
            2,
            2,
            False,
        )


def test_release_epic_cmd_validation() -> None:
    """CLI devops release epic validates arguments."""
    with patch("devops_cli.commands.gh._resolve_repo", return_value=None):
        res_no_repo = runner.invoke(app, ["epic", "v0.2.21"])
        assert res_no_repo.exit_code == 1

    with patch("devops_cli.commands.gh._resolve_repo", return_value="example/repo"):
        res_no_ver = runner.invoke(app, ["epic"])
        assert res_no_ver.exit_code == 1


def test_release_epic_cmd_success(tmp_path: Path) -> None:
    """CLI devops release epic invokes sync and displays output."""
    mock_res = ReleaseEpicSyncResult(
        total_milestones=1,
        created_count=1,
        updated_count=0,
        unchanged_count=0,
        dry_run=True,
        epics=[
            {
                "version": "v0.2.21",
                "action": "created",
                "issue_number": None,
                "deliverables": 4,
                "completed": 2,
                "percent": 50.0,
            }
        ],
    )
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value="example/repo"),
        patch("devops_cli.github.release_epics.sync_all_release_epics", return_value=mock_res),
    ):
        result = runner.invoke(app, ["epic", "v0.2.21", "--dry-run"])
        assert (result.exit_code, "v0.2.21" in result.output, "DRY RUN" in result.output) == (
            0,
            True,
            True,
        )


def test_fastmcp_release_epic_sync() -> None:
    """FastMCP release_epic_sync tool runs CLI command."""
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Synced") as mock_cmd:
        res = release_epic_sync(
            version="v0.2.21", all_milestones=False, dry_run=True, repo="example/repo"
        )
        assert (res, mock_cmd.called) == ("Synced", True)
        args = mock_cmd.call_args[0][0]
        assert (
            "release" in args,
            "epic" in args,
            "v0.2.21" in args,
            "--dry-run" in args,
            "--repo" in args,
        ) == (True, True, True, True, True)
