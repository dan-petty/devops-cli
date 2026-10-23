"""Test suite for GitHub Issues and Milestones editing and progress."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import gh_issues_edit, gh_milestones_edit
from devops_cli.commands.gh import app, milestones_app
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnreadError
from devops_cli.github.issues import (
    _resolve_milestone_number,
    _resolve_updated_labels,
)
from devops_cli.github.milestones import calculate_milestone_progress
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, Milestone
from tests.support.fakes.github import GitHubApiFake, github_json, next_page

runner = CliRunner()


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes accurate metrics and completion states."""
    active_m = Milestone(number=21, title="2026-11-05", open_issues=2, closed_issues=6)
    prog_active = calculate_milestone_progress(active_m)
    assert (
        prog_active.total_issues,
        prog_active.percent_complete,
        prog_active.is_complete,
    ) == (8, 75.0, False)

    closed_m = Milestone(number=20, title="Q4 hardening", state=GitHubState.CLOSED)
    prog_closed = calculate_milestone_progress(closed_m)
    assert (
        prog_closed.total_issues,
        prog_closed.percent_complete,
        prog_closed.is_complete,
    ) == (0, 100.0, True)


_MILESTONES = "/repos/example/repo/milestones?state=all&per_page=100"
_MILESTONES_PAGE_2 = "/repositories/1/milestones?state=all&per_page=100&page=2"


def test_resolve_milestone_number_needs_no_request_for_a_number_or_none(
    github_api: GitHubApiFake,
) -> None:
    """A number, or a value that clears the milestone, is resolved without asking GitHub."""
    assert (
        _resolve_milestone_number("example/repo", None),
        _resolve_milestone_number("example/repo", "none"),
        _resolve_milestone_number("example/repo", 12),
        _resolve_milestone_number("example/repo", "15"),
        github_api.sent,
    ) == (None, None, 12, 15, [])


@pytest.mark.parametrize(
    ("title", "number", "requests"),
    [
        pytest.param("Q4 hardening", 98, 1, id="on-the-first-page"),
        pytest.param("2026-11-05", 99, 2, id="on-the-second-page"),
    ],
)
def test_resolve_milestone_number_reads_pages_until_the_title_matches(
    github_api: GitHubApiFake, title: str, number: int, requests: int
) -> None:
    """The milestones are read page by page, and reading stops at the matching title."""
    github_api.route(
        "GET",
        _MILESTONES,
        github_json(
            [{"number": 98, "title": "Q4 hardening"}], headers=next_page(_MILESTONES_PAGE_2)
        ),
    )
    github_api.route(
        "GET", _MILESTONES_PAGE_2, github_json([{"number": 99, "title": "2026-11-05"}])
    )
    found = _resolve_milestone_number("example/repo", title)
    assert (found, len(github_api.sent)) == (number, requests)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Q5", id="no-milestone-has-it"),
        pytest.param("q4 hardening", id="another-case"),
        pytest.param("v2026-11-05", id="a-v-prefix-added"),
    ],
)
def test_a_name_that_is_no_exact_title_is_an_error(github_api: GitHubApiFake, name: str) -> None:
    """Only the exact title matches: no case fold and no version prefix. A name no milestone
    has as its title raises, after every page is read."""
    github_api.route(
        "GET",
        _MILESTONES,
        github_json(
            [{"number": 98, "title": "Q4 hardening"}, {"number": 99, "title": "2026-11-05"}]
        ),
    )
    with pytest.raises(GitHubOperationError, match="was not found"):
        _resolve_milestone_number("example/repo", name)


def test_a_milestone_read_that_fails_is_not_a_missing_milestone(github_api: GitHubApiFake) -> None:
    """A page that is no list of milestones raises the unread error, not "not found"."""
    github_api.route("GET", _MILESTONES, github_json({"message": "Server Error"}))
    with pytest.raises(GitHubUnreadError):
        _resolve_milestone_number("example/repo", "Q4 hardening")


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


def test_cli_gh_milestones_edit_leaves_the_milestone_open(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones edit Q4 --description x changes the description, not the state."""
    roadmap_store.seed_milestone("Q4", description="Multi-IDE MCP Scaffolding")

    result = runner.invoke(
        milestones_app, ["edit", "Q4", "--description", "x", "-R", "example/repo"]
    )
    edited = roadmap_store.milestone("Q4")
    assert (
        result.exit_code,
        "Milestone 'Q4' updated successfully" in result.output,
        (edited.description, edited.state) if edited else None,
        roadmap_store_repos,
    ) == (0, True, ("x", GitHubState.OPEN), ["example/repo"])


def test_cli_gh_milestones_edit_changes_only_the_fields_given(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """edit renames, closes and dates the milestone its number names; bad or no input changes
    nothing, and a title another milestone has is refused."""
    first = roadmap_store.seed_milestone("2026-10-01", description="Old Desc")
    roadmap_store.seed_milestone("Docs pass")

    edit = ["edit", "-R", "example/repo"]
    renamed = runner.invoke(
        milestones_app,
        [
            *edit,
            str(first.number),
            "--title",
            "Q4",
            "--state",
            "closed",
            "--due-date",
            "2026-10-01",
        ],
    )
    bad_date = runner.invoke(milestones_app, [*edit, "Q4", "--due-date", "soon"])
    unchanged = runner.invoke(milestones_app, [*edit, "Q4"])
    taken = runner.invoke(milestones_app, [*edit, "Q4", "--title", "Docs pass"])
    assert (
        (renamed.exit_code, bad_date.exit_code, "No changes specified" in unchanged.output),
        (taken.exit_code, "already has the title 'Docs pass'" in " ".join(taken.output.split())),
        [(m.title, m.description, m.state, m.due_on) for m in roadmap_store.milestones()],
        roadmap_store_repos,
    ) == (
        (0, 1, True),
        (1, True),
        [
            ("Q4", "Old Desc", GitHubState.CLOSED, date(2026, 10, 1)),
            ("Docs pass", "", GitHubState.OPEN, None),
        ],
        ["example/repo", "example/repo"],
    )


def test_cli_gh_issues_edit() -> None:
    """CLI devops gh issues edit sends the PATCH for the fields given."""
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
            ["issues", "edit", "42", "--title", "Updated Issue Title", "--milestone", "Q4"],
        )
        assert (result.exit_code, mock_gh.called) == (0, True)
        assert "Issue #42 updated successfully" in result.output


def test_fastmcp_gh_tools() -> None:
    """FastMCP tools execute CLI commands."""
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Success") as mock_cmd:
        r1 = gh_milestones_edit("Q4", description="New description")
        r2 = gh_issues_edit(number=10, milestone="Q4")

        assert (r1, r2, mock_cmd.call_count) == ("Success", "Success", 2)
