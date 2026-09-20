"""Test suite for GitHub Projects v2 workflows inspection, linking, and bot guards."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.projects import (
    _fetch_project_workflow_nodes,
    _find_project_via_repo,
    create_remote_project,
    find_remote_project,
    get_project_workflows,
    link_project_to_repository,
)

runner = CliRunner()


def _mock_proc(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """Helper to construct CompletedProcess instances for run_gh / _run_project_cli."""
    return subprocess.CompletedProcess(args=["gh"], returncode=returncode, stdout=stdout, stderr="")


def test_find_project_via_repo_found() -> None:
    """_find_project_via_repo locates a project linked directly to a repository."""
    mock_payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "number": 2,
                            "title": "DevOps CLI — Enterprise Development & Release Roadmap",
                            "id": "PVT_kwHOAHXnKc4Biwcg",
                            "url": "https://github.com/users/dan-petty/projects/2",
                        }
                    ]
                }
            }
        }
    }
    with patch(
        "devops_cli.github.projects.run_gh", return_value=_mock_proc(json.dumps(mock_payload))
    ):
        project = _find_project_via_repo(
            "dan-petty", "devops-cli", "DevOps CLI — Enterprise Development & Release Roadmap"
        )
        assert project is not None
        assert (project["number"], project["id"]) == (2, "PVT_kwHOAHXnKc4Biwcg")


def test_find_project_via_repo_not_found_or_error() -> None:
    """_find_project_via_repo returns None when no matching project exists or query errors."""
    mock_empty = {"data": {"repository": {"projectsV2": {"nodes": []}}}}
    with patch(
        "devops_cli.github.projects.run_gh", return_value=_mock_proc(json.dumps(mock_empty))
    ):
        res1 = _find_project_via_repo("dan-petty", "devops-cli", "Nonexistent")

    with patch("devops_cli.github.projects.run_gh", return_value=_mock_proc("", returncode=1)):
        res2 = _find_project_via_repo(
            "dan-petty", "devops-cli", "DevOps CLI — Enterprise Development & Release Roadmap"
        )

    assert (res1, res2) == (None, None)


def test_find_remote_project_prefers_repo_link() -> None:
    """find_remote_project queries repository links first before user/org enumeration."""
    linked_project = {
        "number": 2,
        "title": "Target Project",
        "id": "PVT_123",
        "url": "https://github.com/users/dan-petty/projects/2",
    }
    with (
        patch(
            "devops_cli.github.projects._find_project_via_repo", return_value=linked_project
        ) as mock_repo_find,
        patch("devops_cli.github.projects._find_project_via_rest") as mock_rest,
        patch("devops_cli.github.projects._find_project_via_cli") as mock_cli,
    ):
        found = find_remote_project("dan-petty", "Target Project", repo="dan-petty/devops-cli")
        assert (found, mock_repo_find.called, mock_rest.called, mock_cli.called) == (
            linked_project,
            True,
            False,
            False,
        )


def test_find_remote_project_falls_back_when_not_in_repo() -> None:
    """find_remote_project falls back to REST/CLI when repo search returns None."""
    fallback_project = {
        "number": 5,
        "title": "Fallback Project",
        "id": "PVT_456",
        "url": "https://github.com/users/dan-petty/projects/5",
    }
    with (
        patch("devops_cli.github.projects._find_project_via_repo", return_value=None),
        patch("devops_cli.github.projects._find_project_via_rest", return_value=fallback_project),
    ):
        found = find_remote_project("dan-petty", "Fallback Project", repo="dan-petty/devops-cli")
        assert found == fallback_project


def test_link_project_to_repository_formatting() -> None:
    """link_project_to_repository formats owner and repo properly and invokes gh project link."""
    with (
        patch("devops_cli.github.projects.run_gh", return_value=_mock_proc()) as mock_run_gh,
        patch("devops_cli.github.projects._get_authenticated_user", return_value="dan-petty"),
    ):
        success = link_project_to_repository(2, "@me", "dan-petty/devops-cli")
        assert success is True
        call_args = mock_run_gh.call_args[0][0]
        assert (call_args[0], call_args[1], call_args[2]) == ("gh", "project", "link")
        assert call_args[3] == "2"
        assert ("--owner", "dan-petty") == (call_args[4], call_args[5])
        assert ("--repo", "dan-petty/devops-cli") == (call_args[6], call_args[7])


def test_fetch_project_workflow_nodes() -> None:
    """_fetch_project_workflow_nodes parses GraphQL ProjectV2 node workflows."""
    graphql_response = {
        "data": {
            "node": {
                "workflows": {
                    "nodes": [
                        {"id": "PW_1", "name": "Item closed", "number": 1, "enabled": True},
                        {"id": "PW_2", "name": "Item added", "number": 2, "enabled": False},
                    ]
                }
            }
        }
    }
    with patch(
        "devops_cli.github.projects.run_gh", return_value=_mock_proc(json.dumps(graphql_response))
    ):
        nodes = _fetch_project_workflow_nodes("PVT_123")
        assert len(nodes) == 2
        assert (nodes[0]["name"], nodes[0]["enabled"]) == ("Item closed", True)
        assert (nodes[1]["name"], nodes[1]["enabled"]) == ("Item added", False)


def test_get_project_workflows() -> None:
    """get_project_workflows discovers project and enriches workflow nodes with URLs."""
    mock_project = {
        "number": 2,
        "title": "Roadmap",
        "id": "PVT_123",
        "url": "https://github.com/users/dan-petty/projects/2",
    }
    mock_nodes = [{"id": "PW_1", "name": "Pull request merged", "number": 2, "enabled": True}]
    with (
        patch("devops_cli.github.projects.find_remote_project", return_value=mock_project),
        patch("devops_cli.github.projects._fetch_project_workflow_nodes", return_value=mock_nodes),
    ):
        workflows = get_project_workflows(2, owner="dan-petty", repo="dan-petty/devops-cli")
        assert len(workflows) == 1
        assert (workflows[0]["id"], workflows[0]["name"], workflows[0]["enabled"]) == (
            "PW_1",
            "Pull request merged",
            True,
        )
        assert "users/dan-petty/projects/2/workflows/2" in workflows[0]["url"]


def test_get_project_workflows_not_found() -> None:
    """get_project_workflows returns empty list when project cannot be located."""
    with (
        patch("devops_cli.github.projects.find_remote_project", return_value=None),
        patch("devops_cli.github.projects.list_remote_projects", return_value=[]),
    ):
        workflows = get_project_workflows(999, owner="dan-petty")
        assert workflows == []


def test_create_remote_project_bot_guard() -> None:
    """create_remote_project aborts with an actionable error when executed under github-actions bot."""
    with patch(
        "devops_cli.github.projects._get_authenticated_user", return_value="github-actions[bot]"
    ):
        with pytest.raises(GitHubOperationError) as exc_info:
            create_remote_project("dan-petty", "Test Board")

        assert "does not have permission to create user-owned Projects v2" in str(exc_info.value)


def test_cli_project_workflows_list_table() -> None:
    """devops gh project workflows list renders formatted table of automations."""
    mock_workflows = [
        {
            "id": "PW_1",
            "name": "Auto-add sub-issues to project",
            "number": 4,
            "enabled": True,
            "url": "https://github.com/users/dan-petty/projects/2/workflows/4",
        },
        {
            "id": "PW_2",
            "name": "Auto-close issue",
            "number": 3,
            "enabled": False,
            "url": "https://github.com/users/dan-petty/projects/2/workflows/3",
        },
    ]
    with patch("devops_cli.commands.gh.get_project_workflows", return_value=mock_workflows):
        result = runner.invoke(
            app,
            [
                "project",
                "workflows",
                "list",
                "--project-number",
                "2",
                "--repo",
                "dan-petty/devops-cli",
            ],
        )
        assert result.exit_code == 0
        assert "Auto-add sub-issues to project" in result.output
        assert "Auto-close issue" in result.output
        assert "Enabled" in result.output
        assert "Disabled" in result.output


def test_cli_project_workflows_list_json() -> None:
    """devops gh project workflows list --json outputs raw workflow definitions."""
    mock_workflows = [
        {
            "id": "PW_1",
            "name": "Pull request merged",
            "number": 2,
            "enabled": True,
            "url": "https://github.com/users/dan-petty/projects/2/workflows/2",
        }
    ]
    with patch("devops_cli.commands.gh.get_project_workflows", return_value=mock_workflows):
        result = runner.invoke(
            app,
            [
                "project",
                "workflows",
                "list",
                "--project-number",
                "2",
                "--repo",
                "dan-petty/devops-cli",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert (payload[0]["id"], payload[0]["enabled"]) == ("PW_1", True)


def test_cli_project_workflows_list_empty() -> None:
    """devops gh project workflows list prints informational message when empty."""
    with patch("devops_cli.commands.gh.get_project_workflows", return_value=[]):
        result = runner.invoke(
            app,
            [
                "project",
                "workflows",
                "list",
                "--project-number",
                "2",
                "--repo",
                "dan-petty/devops-cli",
            ],
        )
        assert (result.exit_code, "No built-in workflows found" in result.output) == (0, True)
