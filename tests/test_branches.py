"""Tests for branches commands."""

from __future__ import annotations

import re

import pytest


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


def test_branches_create_command(tmp_path) -> None:
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from devops_cli.commands.branches import app

    runner = CliRunner()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    with (
        patch("devops_cli.commands.branches.fetch_all"),
        patch("devops_cli.commands.branches.gitlib.Repo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.branches = []
        mock_repo.remotes = []
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["create", "test-feature", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "Created and checked out" in result.output
        mock_repo.git.checkout.assert_called_once()
        args = mock_repo.git.checkout.call_args[0]
        assert "-b" in args
        assert "feat/test-feature" in args


def test_branches_status_command(tmp_path) -> None:
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from devops_cli.commands.branches import app

    runner = CliRunner()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    with patch("devops_cli.commands.branches.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "feat/test"
        mock_repo.active_branch.tracking_branch.return_value = None
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["status", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "Git Branch Status" in result.output
        assert "feat/test" in result.output
        assert "clean" in result.output
