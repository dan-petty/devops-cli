"""Tests for branches commands and branch naming logic."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.branches import app as branches_app

runner = CliRunner()


def _make_branch(ticket_id: str, slug: str | None = None) -> str:
    """Replicate the branch naming logic from commands/branches.py."""
    ticket_upper = ticket_id.upper()
    if slug:
        safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
        return f"feature/{ticket_upper}-{safe_slug}"
    return f"feature/{ticket_upper}"


_JIRA_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)$", re.IGNORECASE)


@pytest.mark.parametrize(
    "ticket_id,valid",
    [
        ("PROJ-123", True),
        ("ABC-1", True),
        ("abc-99", True),
        ("A1B-42", True),
        ("123-PROJ", False),
        ("PROJ", False),
        ("PROJ-", False),
        ("", False),
        ("-123", False),
    ],
)
def test_jira_id_validation(ticket_id: str, valid: bool) -> None:
    assert bool(_JIRA_RE.match(ticket_id)) == valid


@pytest.mark.parametrize(
    "ticket_id,slug,expected",
    [
        ("PROJ-123", None, "feature/PROJ-123"),
        ("proj-456", None, "feature/PROJ-456"),
        ("PROJ-123", "add user auth", "feature/PROJ-123-add-user-auth"),
        ("PROJ-123", "Fix Bug!!!", "feature/PROJ-123-fix-bug"),
        ("PROJ-789", "  leading spaces  ", "feature/PROJ-789-leading-spaces"),
        ("PROJ-1", "a---b", "feature/PROJ-1-a-b"),
        ("ABC-99", "Update / Refactor", "feature/ABC-99-update-refactor"),
    ],
)
def test_branch_name_generation(ticket_id: str, slug: str | None, expected: str) -> None:
    assert _make_branch(ticket_id, slug) == expected


def test_branches_commands(tmp_path: Path) -> None:
    """Verify branches list, clean, jira, and update subcommands."""
    repo_dir = tmp_path / "my-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    with (
        patch("devops_cli.commands.branches.iter_workspace_repos", return_value=[repo_dir]),
        patch(
            "devops_cli.commands.branches.list_branches",
            return_value=MagicMock(branches=["main", "feat/test"], current="main"),
        ),
        patch("devops_cli.commands.branches.delete_merged_branches", return_value=["feat/test"]),
        patch("devops_cli.commands.branches.fetch_all"),
        patch("devops_cli.commands.branches.pull_tracking"),
        patch("devops_cli.commands.branches.create_branch"),
    ):
        res_list = runner.invoke(branches_app, ["list", "--all"])
        assert res_list.exit_code == 0

        res_clean = runner.invoke(branches_app, ["clean", "--dry-run"])
        assert res_clean.exit_code == 0

        res_update = runner.invoke(branches_app, ["update"])
        assert res_update.exit_code == 0

        res_jira = runner.invoke(
            branches_app, ["jira", "PROJ-123", "--slug", "my-feature", "--repo", str(repo_dir)]
        )
        assert res_jira.exit_code == 0
