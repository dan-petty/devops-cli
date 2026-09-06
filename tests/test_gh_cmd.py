"""Test suite for devops gh CLI command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.gh import app

runner = CliRunner()


def test_gh_labels_list() -> None:
    """devops gh labels list outputs label records."""
    mock_labels = [
        {"name": "type/feature", "color": "0E8A16", "description": "Feature addition"},
        {"name": "type/bug", "color": "D73A4A", "description": "Bug fix"},
    ]
    with patch("devops_cli.commands.gh._get_repo_labels", return_value=mock_labels):
        result = runner.invoke(app, ["labels", "list"])
        assert result.exit_code == 0
        assert "type/feature" in result.output
        assert "type/bug" in result.output


def test_gh_labels_sync_dry_run() -> None:
    """devops gh labels sync --dry-run previews label reconciliations without mutations."""
    with (
        patch("devops_cli.commands.gh._get_repo_labels", return_value=[]),
        patch("devops_cli.commands.gh.sync_repository_labels") as mock_sync,
    ):
        mock_sync.return_value = MagicMock(created_count=5, updated_count=0, dry_run=True)
        result = runner.invoke(app, ["labels", "sync", "--dry-run"])
        assert result.exit_code == 0
        assert (
            "DRY RUN" in result.output or "dry-run" in result.output.lower() or "5" in result.output
        )


def test_gh_milestones_list() -> None:
    """devops gh milestones list prints milestones and progress rates."""
    mock_milestones = [
        {
            "title": "v0.2.11",
            "state": "open",
            "open_issues": 1,
            "closed_issues": 9,
            "due_on": "2026-09-10",
        },
    ]
    with patch("devops_cli.commands.gh._get_repo_milestones", return_value=mock_milestones):
        result = runner.invoke(app, ["milestones", "list"])
        assert result.exit_code == 0
        assert "v0.2.11" in result.output


def test_gh_milestones_sync_dry_run() -> None:
    """devops gh milestones sync --dry-run extracts roadmap milestones and simulates create."""
    with (
        patch("devops_cli.commands.gh._get_repo_milestones", return_value=[]),
        patch("devops_cli.commands.gh.sync_repository_milestones") as mock_sync,
    ):
        mock_sync.return_value = MagicMock(created_count=4, dry_run=True)
        result = runner.invoke(app, ["milestones", "sync", "--dry-run"])
        assert result.exit_code == 0


def test_gh_views_list() -> None:
    """devops gh views list displays all 4 standardized project views."""
    result = runner.invoke(app, ["views", "list"])
    assert result.exit_code == 0
    assert "Sprint Kanban" in result.output
    assert "Roadmap Timeline" in result.output
    assert "Triage & Quality Table" in result.output
    assert "Value vs Effort Priority Matrix" in result.output


def test_gh_views_spec() -> None:
    """devops gh views spec outputs JSON schema for GitHub Projects v2 views."""
    result = runner.invoke(app, ["views", "spec"])
    assert result.exit_code == 0
    assert "Sprint Kanban" in result.output
    assert "layout" in result.output
