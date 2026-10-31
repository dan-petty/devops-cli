"""Test suite for GitHub Projects v2 workflows inspection, linking, and bot guards."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from devops_cli.config.constants import CONST_PROJECT_WORKFLOW_EXPECTATIONS
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.projects import (
    create_remote_project,
    fetch_project_workflow_nodes,
    find_project_via_repo,
    find_remote_project,
    get_project_workflows,
    link_project_to_repository,
    reset_project_caches,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def _rate_limit_payload() -> str:
    """A /rate_limit answer with a live quota so `run_gh` refreshes without a real gh."""
    return json.dumps(
        {
            "resources": {
                name: {"limit": 5000, "used": 0, "remaining": 4990, "reset": int(time.time()) + 600}
                for name in ("core", "graphql", "search")
            }
        }
    )


def _setup_board_and_workflows(
    process_fake: ProcessFake,
    workflows: list[dict[str, Any]],
    *,
    project_number: int = 2,
    project_id: str = "PVT_123",
) -> None:
    """Answer GraphQL queries for repository board lookup and workflow listing."""
    repo_boards = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "number": project_number,
                            "id": project_id,
                            "title": str(project_number),
                            "url": f"https://github.com/users/dan-petty/projects/{project_number}",
                        }
                    ]
                }
            }
        }
    }
    workflow_nodes = {
        "data": {
            "node": {
                "workflows": {
                    "nodes": workflows,
                }
            }
        }
    }
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: (
            call.argv[:3] == ("gh", "api", "graphql")
            and any("projectsV2" in arg for arg in call.argv)
        ),
        ProcessAnswer(returncode=0, stdout=json.dumps(repo_boards)),
    )
    process_fake.answer(
        lambda call: (
            call.argv[:3] == ("gh", "api", "graphql")
            and any("workflows" in arg for arg in call.argv)
        ),
        ProcessAnswer(returncode=0, stdout=json.dumps(workflow_nodes)),
    )


def test_find_project_via_repo_finds_linked_project(process_fake: ProcessFake) -> None:
    """find_project_via_repo locates a project linked directly to a repository."""
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
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("projectsV2" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(mock_payload)),
    )
    project = find_project_via_repo(
        "dan-petty", "devops-cli", "DevOps CLI — Enterprise Development & Release Roadmap"
    )
    assert project is not None
    assert (project["number"], project["id"]) == (2, "PVT_kwHOAHXnKc4Biwcg")


def test_find_project_via_repo_returns_none_when_empty_and_raises_on_error(
    process_fake: ProcessFake,
) -> None:
    """find_project_via_repo returns None when no matching project exists and raises on error."""
    mock_empty = {"data": {"repository": {"projectsV2": {"nodes": []}}}}
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("projectsV2" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(mock_empty)),
    )
    res1 = find_project_via_repo("dan-petty", "devops-cli", "Nonexistent")
    assert res1 is None

    process_fake.answer(
        lambda call: any("projectsV2" in arg for arg in call.argv),
        ProcessAnswer(returncode=1, stderr="Not found"),
    )
    with pytest.raises(GitHubOperationError) as raised:
        find_project_via_repo(
            "dan-petty", "devops-cli", "DevOps CLI — Enterprise Development & Release Roadmap"
        )
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_find_remote_project_prefers_repo_link(process_fake: ProcessFake) -> None:
    """find_remote_project queries repository links first before user/org enumeration."""
    mock_payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "number": 2,
                            "title": "Target Project",
                            "id": "PVT_123",
                            "url": "https://github.com/users/dan-petty/projects/2",
                        }
                    ]
                }
            }
        }
    }
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("projectsV2" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(mock_payload)),
    )
    found = find_remote_project("dan-petty", "Target Project", repo="dan-petty/devops-cli")
    assert found is not None
    assert (found["number"], found["id"]) == (2, "PVT_123")
    assert not any(call.argv[:3] == ("gh", "project", "list") for call in process_fake.calls)


def test_find_remote_project_falls_back_when_not_in_repo(process_fake: ProcessFake) -> None:
    """find_remote_project falls back to REST/CLI when repo search returns None."""
    mock_empty = {"data": {"repository": {"projectsV2": {"nodes": []}}}}
    fallback_project = [
        {
            "number": 5,
            "title": "Fallback Project",
            "id": "PVT_456",
            "url": "https://github.com/users/dan-petty/projects/5",
        }
    ]
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: call.argv[:3] == ("gh", "api", "graphql"),
        ProcessAnswer(returncode=0, stdout=json.dumps(mock_empty)),
    )
    process_fake.answer(
        lambda call: any("projectsV2" in arg for arg in call.argv) and "graphql" not in call.argv,
        ProcessAnswer(returncode=0, stdout=json.dumps(fallback_project)),
    )
    found = find_remote_project("dan-petty", "Fallback Project", repo="dan-petty/devops-cli")
    assert found is not None
    assert (found["number"], found["id"]) == (5, "PVT_456")


def test_link_project_to_repository_formatting(process_fake: ProcessFake) -> None:
    """link_project_to_repository formats owner and repo properly and invokes gh project link."""
    reset_project_caches()
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(["gh", "api", "user"], ProcessAnswer(returncode=0, stdout="dan-petty\n"))
    process_fake.answer(["gh", "project", "link"], ProcessAnswer(returncode=0, stdout=""))

    success = link_project_to_repository(2, "@me", "dan-petty/devops-cli")
    assert success is True
    link_calls = [call for call in process_fake.calls if call.argv[:3] == ("gh", "project", "link")]
    assert len(link_calls) == 1
    call_args = link_calls[0].argv
    assert call_args[3] == "2"
    assert ("--owner", "dan-petty") == (call_args[4], call_args[5])
    assert ("--repo", "dan-petty/devops-cli") == (call_args[6], call_args[7])


def test_fetch_project_workflow_nodes(process_fake: ProcessFake) -> None:
    """fetch_project_workflow_nodes parses GraphQL ProjectV2 node workflows."""
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
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("workflows" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(graphql_response)),
    )
    nodes = fetch_project_workflow_nodes("PVT_123")
    assert len(nodes) == 2
    assert (nodes[0]["name"], nodes[0]["enabled"]) == ("Item closed", True)
    assert (nodes[1]["name"], nodes[1]["enabled"]) == ("Item added", False)


def test_get_project_workflows(process_fake: ProcessFake) -> None:
    """get_project_workflows discovers project and enriches workflow nodes with URLs."""
    _setup_board_and_workflows(
        process_fake,
        [{"id": "PW_1", "name": "Pull request merged", "number": 2, "enabled": True}],
    )
    workflows = get_project_workflows(2, owner="dan-petty", repo="dan-petty/devops-cli")
    assert len(workflows) == 1
    assert (workflows[0]["id"], workflows[0]["name"], workflows[0]["enabled"]) == (
        "PW_1",
        "Pull request merged",
        True,
    )
    assert "users/dan-petty/projects/2/workflows/2" in workflows[0]["url"]


def test_get_project_workflows_not_found(process_fake: ProcessFake) -> None:
    """get_project_workflows returns empty list when project cannot be located."""
    mock_empty = {"data": {"repository": {"projectsV2": {"nodes": []}}}}
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: call.argv[:3] == ("gh", "api", "graphql"),
        ProcessAnswer(returncode=0, stdout=json.dumps(mock_empty)),
    )
    process_fake.answer(
        lambda call: any("projects" in arg for arg in call.argv) and "graphql" not in call.argv,
        ProcessAnswer(returncode=0, stdout=json.dumps([])),
    )
    process_fake.answer(
        ["gh", "project", "list"],
        ProcessAnswer(returncode=0, stdout=json.dumps([])),
    )
    workflows = get_project_workflows(999, owner="dan-petty")
    assert workflows == []


def test_create_remote_project_bot_guard(process_fake: ProcessFake) -> None:
    """create_remote_project aborts with an actionable error when executed under github-actions bot."""
    reset_project_caches()
    process_fake.answer(["gh", "auth", "token"], ProcessAnswer(returncode=0, stdout="fake-token\n"))
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        ["gh", "api", "user"], ProcessAnswer(returncode=0, stdout="github-actions[bot]\n")
    )

    with pytest.raises(GitHubOperationError) as exc_info:
        create_remote_project("dan-petty", "Test Board")

    assert "does not have permission to create user-owned Projects v2" in str(exc_info.value)


def test_cli_project_workflows_list_table(process_fake: ProcessFake, cli: Any) -> None:
    """devops gh project workflows list renders formatted table of automations."""
    mock_workflows = [
        {
            "id": "PW_1",
            "name": "Auto-add sub-issues to project",
            "number": 4,
            "enabled": True,
        },
        {
            "id": "PW_2",
            "name": "Auto-close issue",
            "number": 3,
            "enabled": False,
        },
    ]
    _setup_board_and_workflows(process_fake, mock_workflows)
    result = cli(
        "gh",
        "project",
        "workflows",
        "list",
        "--project-number",
        "2",
        "--repo",
        "dan-petty/devops-cli",
    )
    assert result.exit_code == 0
    assert "Auto-add sub-issues to project" in result.output
    assert "Auto-close issue" in result.output
    assert "Enabled" in result.output
    assert "Disabled" in result.output


def test_cli_project_workflows_list_json(process_fake: ProcessFake, cli: Any) -> None:
    """devops gh project workflows list --json outputs raw workflow definitions."""
    mock_workflows = [
        {
            "id": "PW_1",
            "name": "Pull request merged",
            "number": 2,
            "enabled": True,
        }
    ]
    _setup_board_and_workflows(process_fake, mock_workflows)
    result = cli(
        "gh",
        "project",
        "workflows",
        "list",
        "--project-number",
        "2",
        "--repo",
        "dan-petty/devops-cli",
        "--json",
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert (payload[0]["id"], payload[0]["enabled"]) == ("PW_1", True)


def test_cli_project_workflows_list_empty(process_fake: ProcessFake, cli: Any) -> None:
    """devops gh project workflows list prints informational message when empty."""
    _setup_board_and_workflows(process_fake, [])
    result = cli(
        "gh",
        "project",
        "workflows",
        "list",
        "--project-number",
        "2",
        "--repo",
        "dan-petty/devops-cli",
    )
    assert (result.exit_code, "No built-in workflows found" in result.output) == (0, True)


# =============================================================================
# Expected configuration
# =============================================================================


def _workflow(name: str, number: int, enabled: bool) -> dict[str, object]:
    """Shape one built-in workflow as the API returns it."""
    return {
        "id": f"PW_{number}",
        "name": name,
        "number": number,
        "enabled": enabled,
    }


def _run_list(cli: Any) -> Any:
    """Invoke the listing against a fixed board."""
    return cli(
        "gh",
        "project",
        "workflows",
        "list",
        "--project-number",
        "2",
        "--repo",
        "dan-petty/devops-cli",
    )


def test_a_disabled_automation_is_named_with_what_it_should_do(
    process_fake: ProcessFake, cli: Any
) -> None:
    """A board whose automations are off stops tracking silently.

    The listing showed only enabled/disabled, so a board that had never been configured
    looked the same as one deliberately left manual. GitHub's GraphQL API offers no
    mutation that enables a workflow, so naming the gap precisely is the whole remedy.
    """
    workflows = [
        _workflow("Item closed", 1, False),
        _workflow("Auto-add sub-issues to project", 4, True),
    ]
    _setup_board_and_workflows(process_fake, workflows)
    result = _run_list(cli)
    assert (result.exit_code, "Set Status to Done" in result.output) == (0, True)


def test_the_gap_is_counted_against_the_automations_the_board_has(
    process_fake: ProcessFake, cli: Any
) -> None:
    """Counting against every known expectation would report a gap for absent workflows."""
    workflows = [_workflow("Item closed", 1, False), _workflow("Item added to project", 6, False)]
    _setup_board_and_workflows(process_fake, workflows)
    result = _run_list(cli)
    assert "2 of 2 expected automations are disabled" in result.output


def test_a_fully_configured_board_reports_no_gap(process_fake: ProcessFake, cli: Any) -> None:
    """The report must be quiet when there is nothing to act on."""
    workflows = [_workflow("Item closed", 1, True), _workflow("Pull request merged", 2, True)]
    _setup_board_and_workflows(process_fake, workflows)
    result = _run_list(cli)
    assert "Every expected automation is enabled" in result.output


def test_the_expectations_match_the_board_as_its_owner_configured_it() -> None:
    """Pins board 2's built-in workflows as set on 2026-10-01 (#739).

    Added and reopened items are New. A linked pull request puts its issue In Review, which
    reconcile would otherwise restore. Auto-close, auto-archive and auto-add are off, so they
    have no entry: closure writes the summary, and no roadmap job reads or adds a card
    (ADR 0016).
    """
    assert CONST_PROJECT_WORKFLOW_EXPECTATIONS == {
        "Item added to project": "Set Status to New",
        "Item closed": "Set Status to Done",
        "Item reopened": "Set Status to New",
        "Pull request linked to issue": "Set Status to In Review",
        "Pull request merged": "Set Status to Done",
    }


def test_an_auto_add_workflow_left_off_is_not_reported_as_a_gap(
    process_fake: ProcessFake, cli: Any
) -> None:
    """The audit does not ask for auto-add: a person decides which issues go onto the board."""
    workflows = [
        _workflow("Item closed", 1, True),
        _workflow("Auto-add sub-issues to project", 4, False),
    ]
    _setup_board_and_workflows(process_fake, workflows)
    result = _run_list(cli)
    assert (result.exit_code, "Every expected automation is enabled" in result.output) == (0, True)
