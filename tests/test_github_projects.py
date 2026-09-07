"""Test suite for GitHub Projects v2 schema, views, and task synchronization."""

from __future__ import annotations

from pathlib import Path

from devops_cli.github.projects import (
    ProjectTemplate,
    load_project_template,
    parse_tasks_to_project_items,
)


def test_load_project_template() -> None:
    """ProjectTemplate properly parses the declarative template schema."""
    template_path = Path(".github/project-template.json")
    assert template_path.exists()

    template = load_project_template(template_path)
    assert isinstance(template, ProjectTemplate)
    assert "DevOps CLI" in template.name
    assert len(template.fields) >= 4
    assert len(template.views) == 4

    view_names = [v.name for v in template.views]
    assert "Sprint Kanban" in view_names
    assert "Roadmap Timeline" in view_names
    assert "Triage & Quality Table" in view_names
    assert "Value vs Effort Priority Matrix" in view_names


def test_parse_tasks_to_project_items(tmp_path: Path) -> None:
    """parse_tasks_to_project_items converts task.md lines into ProjectItem models."""
    sample_task_md = tmp_path / "task.md"
    sample_task_md.write_text(
        "# Task Tracking\n\n"
        "### Completed Tasks\n"
        "- [x] Phase 1: Baseline CI run\n\n"
        "### In-Progress Tasks (WIP)\n"
        "- [ ] Phase 2: Active feature work\n\n"
        "### Pending Tasks\n"
        "- [ ] Phase 3: Future item\n",
        encoding="utf-8",
    )

    items = parse_tasks_to_project_items(sample_task_md)
    assert len(items) == 3
    assert items[0].title == "Phase 1: Baseline CI run"
    assert items[0].status == "Done"

    assert items[1].title == "Phase 2: Active feature work"
    assert items[1].status == "In Progress"

    assert items[2].title == "Phase 3: Future item"
    assert items[2].status == "Backlog"


def test_verify_project_auth_scopes_insufficient_scope() -> None:
    """verify_project_auth_scopes raises GitHubOperationError when token lacks project scope."""
    from unittest.mock import MagicMock, patch

    import pytest

    from devops_cli.exceptions.git import GitHubOperationError
    from devops_cli.github.projects import verify_project_auth_scopes

    mock_proc = MagicMock(
        return_value=MagicMock(
            returncode=1,
            stderr="error: your authentication token is missing required scopes [read:project]",
            stdout="",
        )
    )
    with patch("devops_cli.github.projects.run_subprocess", mock_proc):
        with pytest.raises(GitHubOperationError) as exc_info:
            verify_project_auth_scopes()
        assert "lacks 'project' scope" in str(exc_info.value)


def test_sync_remote_project_dry_run() -> None:
    """sync_remote_project in dry_run mode returns preview without mutations."""
    from unittest.mock import patch

    from devops_cli.github.projects import (
        ProjectItem,
        load_project_template,
        sync_remote_project,
    )

    template = load_project_template(Path(".github/project-template.json"))
    items = [ProjectItem(title="Task A", status="Done")]

    with patch("devops_cli.github.projects.verify_project_auth_scopes"):
        res = sync_remote_project(
            owner="dan-petty",
            repo="dan-petty/devops-cli",
            template=template,
            items=items,
            dry_run=True,
        )
        assert res.dry_run is True
        assert res.items_synced == 1
        assert res.project_title == template.name


def test_cli_project_link_command() -> None:
    """CLI devops gh project link invokes link_project_to_repository."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch("devops_cli.commands.gh.link_project_to_repository", return_value=True):
        res = runner.invoke(app, ["project", "link", "1", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "Linked project #1 to dan-petty/devops-cli" in res.output
