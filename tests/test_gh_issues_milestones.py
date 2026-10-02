"""Test suite for GitHub Issues and Milestones editing and progress."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.mcp.server import gh_issue_edit, gh_milestone_edit
from devops_cli.commands.gh import app, milestones_app
from devops_cli.github.issues import (
    _resolve_milestone_number,
    _resolve_updated_labels,
    edit_repository_issue,
)
from devops_cli.github.milestones import calculate_milestone_progress
from devops_cli.github.projects import (
    _reconcile_single_item,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, Release

runner = CliRunner()


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes accurate metrics and completion states."""
    active_m = Release(number=21, title="v0.2.21", open_issues=2, closed_issues=6)
    prog_active = calculate_milestone_progress(active_m)
    assert (
        prog_active.total_issues,
        prog_active.percent_complete,
        prog_active.is_complete,
    ) == (8, 75.0, False)

    closed_m = Release(number=20, title="v0.2.20", state=GitHubState.CLOSED)
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


def test_cli_gh_milestones_edit_leaves_the_release_open(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones edit v0.2.25 --description x changes the description, not the state."""
    roadmap_store.create_release("v0.2.25", description="Multi-IDE MCP Scaffolding")

    result = runner.invoke(
        milestones_app, ["edit", "v0.2.25", "--description", "x", "-R", "example/repo"]
    )
    edited = roadmap_store.release("v0.2.25")
    assert (
        result.exit_code,
        "Milestone 'v0.2.25' updated successfully" in result.output,
        (edited.description, edited.state) if edited else None,
        roadmap_store_repos,
    ) == (0, True, ("x", GitHubState.OPEN), ["example/repo"])


def test_cli_gh_milestones_edit_changes_only_the_fields_given(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """edit renames, closes and dates a Release found without its v; bad or no input changes nothing."""
    roadmap_store.create_release("v0.2.21", description="Old Desc")

    edit = ["edit", "-R", "example/repo"]
    renamed = runner.invoke(
        milestones_app,
        [*edit, "0.2.21", "--title", "v0.2.22", "--state", "closed", "--due-date", "2026-10-01"],
    )
    bad_date = runner.invoke(milestones_app, [*edit, "v0.2.22", "--due-date", "soon"])
    unchanged = runner.invoke(milestones_app, [*edit, "v0.2.22"])
    assert (
        (renamed.exit_code, bad_date.exit_code, "No changes specified" in unchanged.output),
        [(r.title, r.description, r.state, r.due_on) for r in roadmap_store.releases()],
        roadmap_store_repos,
    ) == (
        (0, 1, True),
        [("v0.2.22", "Old Desc", GitHubState.CLOSED, date(2026, 10, 1))],
        ["example/repo"],
    )


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


def test_reconcile_never_writes_the_milestone_the_board_mirrors() -> None:
    """_reconcile_single_item plans no Milestone change though the board's copy differs."""
    item = {
        "url": "https://github.com/example/repo/issues/1",
        "title": "Test Issue",
        "state": "OPEN",
        "labels": [{"name": "priority/p1-high"}],
        "milestone": {"title": "v0.2.21"},
    }
    current_fields: dict[str, str | None] = {
        "status": "New",
        "priority": "P1-High",
        "value": "High",
        "effort": "Medium",
        "milestone": "v0.2.20",
    }
    changes = _reconcile_single_item(
        owner="example",
        project_number=2,
        item=item,
        dry_run=True,
        current_fields=current_fields,
    )
    assert [(c.field, c.old, c.new) for c in changes] == []


def test_fastmcp_gh_tools() -> None:
    """FastMCP tools execute CLI commands."""
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Success") as mock_cmd:
        r1 = gh_milestone_edit("v0.2.21", description="New description")
        r2 = gh_issue_edit(issue_number=10, milestone="v0.2.21")

        assert (r1, r2, mock_cmd.call_count) == ("Success", "Success", 2)
