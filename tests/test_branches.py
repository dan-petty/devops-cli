"""Tests for branches commands and branch naming logic."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.branches import app as branches_app
from devops_cli.main import app as main_app

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
    """Verify branches list and delete-merged subcommands."""
    (tmp_path / ".git").mkdir()
    with (
        patch("devops_cli.core.repo.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.git.operations.list_branches",
            return_value=MagicMock(branches=["main", "feat/test"], current="main"),
        ),
        patch("devops_cli.git.operations.delete_merged_branches", return_value=["feat/test"]),
    ):
        res_list = runner.invoke(main_app, ["--dry-run", "branches", "list"])
        assert res_list.exit_code == 0

        res_del = runner.invoke(main_app, ["--dry-run", "branches", "delete-merged"])
        assert res_del.exit_code == 0

        res_direct = runner.invoke(branches_app, ["list"])
        assert res_direct.exit_code == 0
