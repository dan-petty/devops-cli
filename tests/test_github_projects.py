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


def test_verify_project_auth_scopes_unrelated_error_ignored() -> None:
    """verify_project_auth_scopes does not misclassify unrelated errors containing 'project'."""
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import verify_project_auth_scopes

    # Subprocess returns non-zero with "project not found", should not raise "lacks 'project' scope"
    mock_proc = MagicMock(
        return_value=MagicMock(
            returncode=1,
            stderr="error: project not found",
            stdout="",
        )
    )
    with patch("devops_cli.github.projects.run_subprocess", mock_proc):
        # Should complete without raising GitHubOperationError about scopes
        verify_project_auth_scopes()


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


def test_map_view_layout() -> None:
    """_map_view_layout maps layout names to GraphQL enum strings."""
    from devops_cli.github.projects import _map_view_layout

    assert _map_view_layout("board") == "BOARD_LAYOUT"
    assert _map_view_layout("roadmap") == "ROADMAP_LAYOUT"
    assert _map_view_layout("table") == "TABLE_LAYOUT"
    assert _map_view_layout("unknown") == "TABLE_LAYOUT"


def test_sync_remote_project_views() -> None:
    """sync_remote_project_views identifies existing views and provisions missing ones."""
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        ProjectView,
        sync_remote_project_views,
    )

    fake_template = MagicMock()
    fake_template.views = [
        ProjectView(name="Existing View", layout="table"),
        ProjectView(name="New Board View", layout="board"),
    ]

    with (
        patch("devops_cli.github.projects.verify_project_auth_scopes"),
        patch(
            "devops_cli.github.projects.get_remote_project_views",
            return_value=(
                "PVT_123",
                2,
                [{"id": "v1", "name": "Existing View", "layout": "TABLE_LAYOUT"}],
            ),
        ),
        patch("devops_cli.github.projects._create_project_view", return_value=True) as mock_create,
    ):
        res = sync_remote_project_views("dan-petty", "devops-cli", fake_template)
        assert res["project_number"] == 2
        assert "Existing View" in res["existing"]
        assert "New Board View" in res["created"]
        mock_create.assert_called_once_with("PVT_123", "New Board View", "board")


def test_cli_views_sync_command() -> None:
    """CLI devops gh views sync invokes sync_remote_project_views."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import views_app

    runner = CliRunner()
    with patch(
        "devops_cli.commands.gh.sync_remote_project_views",
        return_value={
            "project_number": 2,
            "existing": ["Sprint Kanban"],
            "created": ["Roadmap Timeline"],
            "views": ["Sprint Kanban", "Roadmap Timeline"],
        },
    ):
        res = runner.invoke(views_app, ["sync", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "Project #2 views synchronized" in res.output
        assert "Repository Issues Views" in res.output


def test_cli_project_status_and_template_commands() -> None:
    """CLI devops gh project status and template display declarative configuration."""
    from typer.testing import CliRunner

    from devops_cli.commands.gh import project_app

    runner = CliRunner()
    res_status = runner.invoke(project_app, ["status"])
    assert res_status.exit_code == 0
    assert "GitHub Projects v2 Configuration" in res_status.output
    assert "Custom Fields" in res_status.output

    res_tpl = runner.invoke(project_app, ["template"])
    assert res_tpl.exit_code == 0
    assert "DevOps CLI" in res_tpl.output


def test_cli_project_sync_command() -> None:
    """CLI devops gh project sync parses local tasks and outputs sync summary."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import project_app
    from devops_cli.github.projects import ProjectSyncResult

    runner = CliRunner()
    mock_res = ProjectSyncResult(
        project_number=2,
        project_title="DevOps CLI Roadmap",
        owner="dan-petty",
        repo="dan-petty/devops-cli",
        fields_provisioned=["Status"],
        items_synced=5,
        dry_run=True,
        linked=True,
    )
    with patch("devops_cli.commands.gh.sync_remote_project", return_value=mock_res):
        res = runner.invoke(project_app, ["sync", "--dry-run", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "DRY RUN" in res.output
        assert "synchronized 5 items" in res.output

    # Error handling branch
    with patch("devops_cli.commands.gh.sync_remote_project", side_effect=RuntimeError("API error")):
        res_err = runner.invoke(project_app, ["sync", "--repo", "dan-petty/devops-cli"])
        assert res_err.exit_code == 0
        assert "Remote project sync skipped or failed" in res_err.output


def test_cli_project_link_failure() -> None:
    """CLI devops gh project link exits with code 1 when linkage fails."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import project_app

    runner = CliRunner()
    with patch("devops_cli.commands.gh.link_project_to_repository", return_value=False):
        res = runner.invoke(project_app, ["link", "99", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 1
        assert "Failed to link project #99" in res.output


def test_cli_views_list_and_spec_commands() -> None:
    """CLI devops gh views list and spec output formatted views and JSON schemas."""
    from typer.testing import CliRunner

    from devops_cli.commands.gh import views_app

    runner = CliRunner()
    res_list = runner.invoke(views_app, ["list"])
    assert res_list.exit_code == 0
    assert "Sprint Kanban" in res_list.output
    assert "Roadmap Timeline" in res_list.output

    res_spec = runner.invoke(views_app, ["spec"])
    assert res_spec.exit_code == 0
    assert "Sprint Kanban" in res_spec.output
    assert '"layout":' in res_spec.output


def test_cli_views_sync_no_project_found() -> None:
    """CLI devops gh views sync handles unlinked projects gracefully."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import views_app

    runner = CliRunner()
    with patch(
        "devops_cli.commands.gh.sync_remote_project_views",
        return_value={"project_number": None, "status": "No linked project found"},
    ):
        res = runner.invoke(views_app, ["sync", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "No linked project found" in res.output
        assert "milestone%3Acurrent" in res.output
        assert "sort%3Apriority-desc" in res.output


def test_find_and_create_remote_project() -> None:
    """find_remote_project and create_remote_project interact correctly with gh CLI."""
    import json
    from unittest.mock import MagicMock, patch

    import pytest

    from devops_cli.exceptions.git import GitHubOperationError
    from devops_cli.github.projects import create_remote_project, find_remote_project

    # Subprocess error
    mock_fail = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="error"))
    with patch("devops_cli.github.projects.run_subprocess", mock_fail):
        assert find_remote_project("dan-petty", "My Project") is None
        with pytest.raises(GitHubOperationError):
            create_remote_project("dan-petty", "My Project")

    # Match found
    mock_success = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout=json.dumps({"projects": [{"title": "My Project", "number": 3}]}),
            stderr="",
        )
    )
    with patch("devops_cli.github.projects.run_subprocess", mock_success):
        matched = find_remote_project("dan-petty", "my project")
        assert matched is not None
        assert matched["number"] == 3

        # Create remote project success
        mock_create = MagicMock(
            return_value=MagicMock(
                returncode=0,
                stdout=json.dumps({"title": "New Board", "number": 4}),
                stderr="",
            )
        )
        with patch("devops_cli.github.projects.run_subprocess", mock_create):
            created = create_remote_project("dan-petty", "New Board")
            assert created["number"] == 4


def test_provision_remote_project_fields() -> None:
    """provision_remote_project_fields provisions missing text and single-select fields."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        ProjectField,
        ProjectFieldOption,
        provision_remote_project_fields,
    )

    existing = {"fields": [{"name": "Status"}, {"name": "Assignees"}]}
    mock_proc = MagicMock(
        side_effect=[
            MagicMock(returncode=0, stdout=json.dumps(existing), stderr=""),  # list
            MagicMock(returncode=0, stdout="{}", stderr=""),  # create Priority
            MagicMock(returncode=0, stdout="{}", stderr=""),  # create Category
        ]
    )
    fields = [
        ProjectField(name="Status", type="single_select"),
        ProjectField(
            name="Priority",
            type="single_select",
            options=[ProjectFieldOption(name="P0"), ProjectFieldOption(name="P1")],
        ),
        ProjectField(name="Category", type="text"),
    ]
    with patch("devops_cli.github.projects.run_subprocess", mock_proc):
        provisioned = provision_remote_project_fields(2, "dan-petty", fields)
        assert "Priority" in provisioned
        assert "Category" in provisioned
        assert "Status" not in provisioned


def test_get_remote_project_views() -> None:
    """get_remote_project_views parses GraphQL repository response."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import get_remote_project_views

    # Failure path
    mock_fail = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="graphql err"))
    with patch("devops_cli.github.projects.run_subprocess", mock_fail):
        pid, pnum, views = get_remote_project_views("dan-petty", "devops-cli")
        assert pid is None
        assert pnum is None
        assert views == []

    # Success path
    payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "id": "PVT_99",
                            "number": 5,
                            "views": {
                                "nodes": [{"id": "v_1", "name": "View 1", "layout": "TABLE_LAYOUT"}]
                            },
                        }
                    ]
                }
            }
        }
    }
    mock_ok = MagicMock(return_value=MagicMock(returncode=0, stdout=json.dumps(payload), stderr=""))
    with patch("devops_cli.github.projects.run_subprocess", mock_ok):
        pid, pnum, views = get_remote_project_views("dan-petty", "devops-cli")
        assert pid == "PVT_99"
        assert pnum == 5
        assert len(views) == 1
        assert views[0]["name"] == "View 1"


def test_graphql_query_and_mutation_escaping() -> None:
    """Verify get_remote_project_views, _create_project_view, and _rename_default_view safely escape quotes."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        _create_project_view,
        _rename_default_view,
        get_remote_project_views,
    )

    mock_proc = MagicMock(
        return_value=MagicMock(
            returncode=0, stdout=json.dumps({"data": {"repository": {"projectsV2": {"nodes": []}}}})
        )
    )
    with patch("devops_cli.github.projects.run_subprocess", mock_proc):
        # Query with quotes in owner/repo
        get_remote_project_views('owner"with"quotes', 'repo"with"quotes')
        called_cmd = mock_proc.call_args[0][0]
        query_arg = next(arg for arg in called_cmd if arg.startswith("query="))
        assert r"\"owner\"with\"quotes\"" in query_arg or r"owner\"with\"quotes" in query_arg

        # Mutation with quotes in view name
        ok_create = _create_project_view("PVT_1", 'Sprint "Special" Kanban', "BOARD")
        assert ok_create is True
        called_cmd = mock_proc.call_args[0][0]
        mutation_arg = next(arg for arg in called_cmd if arg.startswith("query="))
        assert r"Sprint \"Special\" Kanban" in mutation_arg

        ok_rename = _rename_default_view("V_1", 'Default "Renamed" View', "TABLE")
        assert ok_rename is True
        called_cmd = mock_proc.call_args[0][0]
        mutation_arg = next(arg for arg in called_cmd if arg.startswith("query="))
        assert r"Default \"Renamed\" View" in mutation_arg


def test_list_remote_projects() -> None:
    """list_remote_projects parses gh project list json."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import list_remote_projects

    payload = {
        "projects": [
            {
                "number": 2,
                "title": "Roadmap Board",
                "closed": False,
                "id": "PVT_123",
                "url": "https://github.com/users/test/projects/2",
            }
        ]
    }
    with patch("devops_cli.github.projects.run_subprocess") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        projects = list_remote_projects("test")
        assert len(projects) == 1
        assert projects[0]["number"] == 2
        assert projects[0]["state"] == "open"


def test_audit_remote_project_views() -> None:
    """audit_remote_project_views matches template views against remote views."""
    from unittest.mock import patch

    from devops_cli.github.projects import ProjectTemplate, ProjectView, audit_remote_project_views

    template = ProjectTemplate(
        name="Test",
        views=[
            ProjectView(name="Sprint Kanban", layout="BOARD"),
            ProjectView(name="Roadmap Timeline", layout="ROADMAP"),
        ],
    )
    remote_views = [{"name": "Sprint Kanban", "layout": "BOARD_LAYOUT"}]
    with patch(
        "devops_cli.github.projects.get_remote_project_views",
        return_value=("PVT_1", 2, remote_views),
    ):
        res = audit_remote_project_views("owner", "repo", template)
        assert res["project_number"] == 2
        assert res["compliant"] is False
        assert "Roadmap Timeline" in res["missing_views"]
        assert "Sprint Kanban" in res["matching_views"]


def test_audit_project_drift() -> None:
    """audit_project_drift produces comprehensive status check."""
    from unittest.mock import patch

    from devops_cli.github.projects import ProjectTemplate, audit_project_drift

    template = ProjectTemplate(name="Test Board", short_name="test-board", views=[])
    views_audit = {
        "project_number": 2,
        "compliant": True,
        "missing_views": [],
        "matching_views": [],
    }
    with (
        patch("devops_cli.github.projects.audit_remote_project_views", return_value=views_audit),
        patch("devops_cli.github.projects.find_remote_project", return_value={"number": 2}),
    ):
        res = audit_project_drift("owner", "repo", template)
        assert res["project_found"] is True
        assert res["project_number"] == 2
        assert res["views_compliant"] is True
