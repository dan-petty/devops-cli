"""Test suite for GitHub Issues and Milestones editing, syncing, and roadmap reconciliation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.mcp.server import (
    gh_issue_edit,
    gh_issue_reconcile_roadmap,
    gh_milestone_edit,
    gh_milestone_sync,
)
from devops_cli.commands.gh import app
from devops_cli.github.issues import (
    GitHubIssue,
    _resolve_milestone_number,
    _resolve_updated_labels,
    edit_repository_issue,
)
from devops_cli.github.milestones import (
    MilestoneSpec,
    MilestoneSyncResult,
    calculate_milestone_progress,
    edit_repository_milestone,
    find_milestones_to_update,
)
from devops_cli.github.projects import (
    _reconcile_single_item,
)
from devops_cli.github.roadmap_sync import (
    IssueMilestoneReconcileResult,
    reconcile_issue_milestones_from_roadmap,
)

runner = CliRunner()


def test_edit_repository_milestone_by_number() -> None:
    """edit_repository_milestone modifies existing milestone attributes."""
    mock_client = MagicMock()
    success = edit_repository_milestone(
        mock_client,
        repo="example/repo",
        version_or_title_or_number=42,
        title="v0.2.22",
        description="New Desc",
        state="closed",
        due_on="2026-10-01",
    )
    assert (success, mock_client.edit_milestone.called) == (True, True)
    kwargs = mock_client.edit_milestone.call_args[1]
    assert (
        kwargs.get("title"),
        kwargs.get("description"),
        kwargs.get("state"),
        kwargs.get("due_on"),
    ) == ("v0.2.22", "New Desc", "closed", "2026-10-01")


def test_edit_repository_milestone_resolve_by_title() -> None:
    """edit_repository_milestone resolves version title to milestone number."""
    mock_client = MagicMock()
    mock_client.get_milestones.return_value = [
        {"number": 7, "title": "v0.2.21", "description": "Old Desc"}
    ]
    success = edit_repository_milestone(
        mock_client,
        repo="example/repo",
        version_or_title_or_number="v0.2.21",
        description="Updated Desc",
    )
    assert (success, mock_client.edit_milestone.called) == (True, True)
    args = mock_client.edit_milestone.call_args[0]
    assert (args[1], mock_client.edit_milestone.call_args[1].get("description")) == (
        7,
        "Updated Desc",
    )


def test_find_milestones_to_update() -> None:
    """find_milestones_to_update flags milestones when description changed."""
    desired = [
        MilestoneSpec(title="v0.2.21", description="New Title Description"),
        MilestoneSpec(title="v0.2.22", description="Unchanged Description"),
        MilestoneSpec(title="v0.2.23", description="New Milestone"),
    ]
    existing = [
        {"number": 1, "title": "v0.2.21", "description": "Old Title Description"},
        {"number": 2, "title": "v0.2.22", "description": "Unchanged Description"},
    ]
    updates = find_milestones_to_update(desired, existing)
    assert (len(updates), updates[0][0], updates[0][1].title) == (
        1,
        1,
        "v0.2.21",
    )


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes accurate metrics and completion states."""
    active_m = {
        "title": "v0.2.21",
        "open_issues": 2,
        "closed_issues": 6,
        "state": "open",
    }
    prog_active = calculate_milestone_progress(active_m)
    assert (
        prog_active.total_issues,
        prog_active.percent_complete,
        prog_active.is_complete,
    ) == (8, 75.0, False)

    closed_m = {
        "title": "v0.2.20",
        "open_issues": 0,
        "closed_issues": 0,
        "state": "closed",
    }
    prog_closed = calculate_milestone_progress(closed_m)
    assert (
        prog_closed.total_issues,
        prog_closed.percent_complete,
        prog_closed.is_complete,
    ) == (0, 100.0, True)


def test_resolve_milestone_number() -> None:
    """_resolve_milestone_number looks up milestone number by name."""
    assert _resolve_milestone_number("example/repo", None) is None
    assert _resolve_milestone_number("example/repo", "none") is None
    assert _resolve_milestone_number("example/repo", 12) == 12
    assert _resolve_milestone_number("example/repo", "15") == 15

    mock_gh_res = MagicMock(
        returncode=0,
        stdout=json.dumps([{"number": 99, "title": "v0.2.21"}]),
    )
    with patch("devops_cli.github.issues.run_gh", return_value=mock_gh_res):
        num = _resolve_milestone_number("example/repo", "v0.2.21")
        assert num == 99


def test_resolve_updated_labels() -> None:
    """_resolve_updated_labels computes addition and removal of labels."""
    existing_issue_json = json.dumps({"labels": [{"name": "type/feature"}, {"name": "scope/cli"}]})
    mock_res = MagicMock(returncode=0, stdout=existing_issue_json)
    with patch("devops_cli.github.issues.run_gh", return_value=mock_res):
        new_labels = _resolve_updated_labels(
            repo="example/repo",
            number=1,
            labels=None,
            add_labels=["priority/p0-critical"],
            remove_labels=["type/feature"],
        )
        assert new_labels == ["priority/p0-critical", "scope/cli"]


def test_edit_repository_issue_mutation() -> None:
    """edit_repository_issue sends PATCH mutation with resolved milestone and labels."""
    mock_res_patch = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "number": 123,
                "title": "New Issue Title",
                "body": "New Body",
                "state": "open",
                "milestone": {"title": "v0.2.21"},
                "labels": [{"name": "type/feature"}],
            }
        ),
    )

    with (
        patch("devops_cli.github.issues._resolve_milestone_number", return_value=10),
        patch("devops_cli.github.issues.run_gh", return_value=mock_res_patch) as mock_gh,
    ):
        issue = edit_repository_issue(
            repo="example/repo",
            number=123,
            title="New Issue Title",
            body="New Body",
            milestone="v0.2.21",
        )
        assert (issue.number, issue.title, issue.milestone) == (
            123,
            "New Issue Title",
            "v0.2.21",
        )
        args = mock_gh.call_args[0][0]
        assert ("api", "--method", "PATCH", "repos/example/repo/issues/123") == (
            args[1],
            args[2],
            args[3],
            args[4],
        )


def test_reconcile_issue_milestones_from_roadmap(tmp_path: Path) -> None:
    """reconcile_issue_milestones_from_roadmap updates misaligned issue milestones."""
    roadmap_content = """# Roadmap

## Release Milestones (Chronological Order)

### Syntopical Research (v0.2.21 - Active)
- [x] #10 Implement AST analysis (`priority/p1-high`, `scope/ai`)

## Value vs. Effort Prioritization Matrix
"""
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(roadmap_content, encoding="utf-8")

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_file = tasks_dir / "task-10-implement-ast-analysis.md"
    task_file.write_text(
        "---\nissue: 10\nmilestone: v0.2.20\ntitle: Implement AST analysis\n---\nBody",
        encoding="utf-8",
    )

    issues = [
        GitHubIssue(
            number=10,
            title="Implement AST analysis",
            milestone="v0.2.20",
            state="open",
            labels=[],
        )
    ]

    with (
        patch("devops_cli.github.roadmap_sync.get_repository_issues", return_value=issues),
        patch("devops_cli.github.issues.edit_repository_issue") as mock_edit,
    ):
        res_dry = reconcile_issue_milestones_from_roadmap(
            repo="example/repo",
            roadmap_path=roadmap_file,
            tasks_dir=tasks_dir,
            dry_run=True,
        )
        assert (res_dry.reconciled_count, mock_edit.called) == (1, False)

        res_live = reconcile_issue_milestones_from_roadmap(
            repo="example/repo",
            roadmap_path=roadmap_file,
            tasks_dir=tasks_dir,
            dry_run=False,
        )
        assert (res_live.reconciled_count, mock_edit.called) == (1, True)
        assert "milestone: v0.2.21" in task_file.read_text(encoding="utf-8")


def test_cli_gh_milestones_edit() -> None:
    """CLI devops gh milestones edit command modifies milestone."""
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value="example/repo"),
        patch(
            "devops_cli.github.milestones.edit_repository_milestone", return_value=True
        ) as mock_edit,
    ):
        result = runner.invoke(
            app,
            [
                "milestones",
                "edit",
                "v0.2.21",
                "--title",
                "v0.2.21-revised",
                "--description",
                "Updated Milestone Description",
            ],
        )
        assert (result.exit_code, mock_edit.called) == (0, True)
        assert "Milestone 'v0.2.21' updated successfully" in result.output


def test_cli_gh_milestones_sync_with_epics() -> None:
    """CLI devops gh milestones sync with --create-release-epics invokes release epic sync."""
    mock_sync_res = MilestoneSyncResult(
        created_count=1,
        updated_count=1,
        existing_count=2,
        created=["v0.2.23"],
        updated=["v0.2.21"],
        dry_run=True,
    )
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value="example/repo"),
        patch("devops_cli.commands.gh.sync_repository_milestones", return_value=mock_sync_res),
        patch("devops_cli.github.release_epics.sync_all_release_epics") as mock_epic_sync,
    ):
        mock_epic_sync.return_value = MagicMock(
            created_count=1, updated_count=0, unchanged_count=0, total_milestones=1
        )
        result = runner.invoke(app, ["milestones", "sync", "--dry-run", "--create-release-epics"])
        assert (result.exit_code, mock_epic_sync.called) == (0, True)


def test_cli_gh_issues_edit() -> None:
    """CLI devops gh issues edit invokes edit_repository_issue."""
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value="example/repo"),
        patch("devops_cli.github.issues._resolve_milestone_number", return_value=12),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(
                returncode=0, stdout='{"title": "Updated Issue Title"}', stderr=""
            ),
        ) as mock_gh,
    ):
        result = runner.invoke(
            app,
            ["issues", "edit", "42", "--title", "Updated Issue Title", "--milestone", "v0.2.21"],
        )
        assert (result.exit_code, mock_gh.called) == (0, True)
        assert "Issue #42 updated successfully" in result.output


def test_cli_gh_issues_reconcile_roadmap() -> None:
    """CLI devops gh issues reconcile-roadmap calls reconciliation and displays output."""
    mock_res = IssueMilestoneReconcileResult(
        total_roadmap_items=10,
        total_issues_checked=10,
        reconciled_count=1,
        dry_run=True,
        reconciled_issues=[
            {
                "number": 10,
                "title": "Implement AST analysis",
                "old_milestone": "v0.2.20",
                "new_milestone": "v0.2.21",
            }
        ],
    )
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value="example/repo"),
        patch(
            "devops_cli.github.roadmap_sync.reconcile_issue_milestones_from_roadmap",
            return_value=mock_res,
        ),
    ):
        result = runner.invoke(app, ["issues", "reconcile-roadmap", "--dry-run"])
        assert (result.exit_code, "DRY RUN" in result.output, "#10" in result.output) == (
            0,
            True,
            True,
        )


def test_project_custom_field_milestone_reconciliation() -> None:
    """_reconcile_single_item detects when Project item Milestone field differs from target."""
    item = {
        "url": "https://github.com/example/repo/issues/1",
        "title": "Test Issue",
        "state": "OPEN",
        "labels": [{"name": "priority/p1-high"}],
        "milestone": {"title": "v0.2.21"},
    }
    current_fields: dict[str, str | None] = {
        "Status": "Backlog",
        "Priority": "P1 - High",
        "Category": "CLI",
        "Value": "High",
        "Effort": "Medium",
        "Milestone": "v0.2.20",
    }
    should_update = _reconcile_single_item(
        owner="example",
        project_number=2,
        item=item,
        dry_run=True,
        current_fields=current_fields,
    )
    assert should_update is True


def test_fastmcp_gh_tools() -> None:
    """FastMCP tools execute CLI commands."""
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Success") as mock_cmd:
        r1 = gh_milestone_edit("v0.2.21", description="New description")
        r2 = gh_milestone_sync(dry_run=True, create_release_epics=True)
        r3 = gh_issue_edit(issue_number=10, milestone="v0.2.21")
        r4 = gh_issue_reconcile_roadmap(dry_run=True)

        assert (r1, r2, r3, r4) == ("Success", "Success", "Success", "Success")
        assert mock_cmd.call_count == 4
